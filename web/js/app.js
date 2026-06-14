/* ═══════════════════════════════════════════════════════════════════════════
   Legion de Hierro — Stats Tracker
   Premium Esports Analytics Dashboard
   ═══════════════════════════════════════════════════════════════════════════ */

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 1: CONFIG & CONSTANTS
// ─────────────────────────────────────────────────────────────────────────────

const BASE_URL = 'https://luccabruno3z.github.io';
const GRAPHS_URL = `${BASE_URL}/graphs`;
const ALL_PLAYERS_URL = `${GRAPHS_URL}/all_players_clusters.json`;
const CLAN_AVERAGES_URL = `${GRAPHS_URL}/clan_averages.json`;
const DEMOS_URL = `${GRAPHS_URL}/demos`;
const HISTORY_URL = `${GRAPHS_URL}/history`;
const LEADERBOARDS_URL = `${DEMOS_URL}/leaderboards`;
const ROUNDS_URL = `${DEMOS_URL}/rounds`;
const PLAYER_ROUNDS_URL = `${DEMOS_URL}/player_rounds`;
const MIN_ROUNDS_FOR_RANKING = 50;
const NORM_CAPS = { kd: 5.0, spr: 500.0, kpr: 10.0, rounds: 1000.0 };
const CACHE_TTL = 300000; // 5 min
const AUTOCOMPLETE_DEBOUNCE_MS = 150;
const TIER_CONFIG_URL = `${GRAPHS_URL}/tier_config.json`;
let tierConfigData = null;

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 2: IN-MEMORY CACHE
// ─────────────────────────────────────────────────────────────────────────────

const memoryCache = new Map();

/**
 * Fetch JSON with in-memory + localStorage caching.
 * Falls back gracefully on network errors.
 */
async function cachedFetch(url, options = {}) {
    const { ttl = CACHE_TTL, silent = false } = options;

    // Check in-memory cache first
    const cached = memoryCache.get(url);
    if (cached && Date.now() - cached.time < ttl) {
        return cached.data;
    }

    try {
        const resp = await fetch(url);
        if (!resp.ok) {
            if (silent) return null;
            throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
        }
        const data = await resp.json();
        memoryCache.set(url, { data, time: Date.now() });
        return data;
    } catch (err) {
        // Return stale cache if available
        if (cached) return cached.data;
        if (silent) return null;
        throw err;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 3: UTILITY FUNCTIONS (ported from bot/utils.py)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Format a number with thousands separators. Floats get 2 decimals.
 * Large round floats are shown as integers.
 */
function formatNumber(n) {
    if (n == null) return 'N/A';
    if (typeof n === 'number' && !Number.isInteger(n)) {
        if (n === Math.floor(n) && Math.abs(n) > 100) {
            return Math.floor(n).toLocaleString('es-AR');
        }
        return n.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return n.toLocaleString('es-AR');
}

/**
 * Load tier configuration from server for dynamic thresholds.
 */
async function loadTierConfig() {
    try {
        tierConfigData = await cachedFetch(TIER_CONFIG_URL);
    } catch (e) {
        console.warn('Could not load tier_config.json, using defaults');
    }
}

/**
 * Performance tier badge. Returns {emoji, name, cssClass}.
 * Uses dynamic thresholds from tier_config.json if available.
 */
function tierBadge(score) {
    const t = tierConfigData?.thresholds || {elite: 0.70, veterano: 0.55, experimentado: 0.40, soldado: 0.25};
    if (score >= t.elite) return { emoji: '\u{1F947}', name: 'Elite', cssClass: 'tier-elite' };
    if (score >= t.veterano) return { emoji: '\u{1F948}', name: 'Veterano', cssClass: 'tier-veterano' };
    if (score >= t.experimentado) return { emoji: '\u{1F949}', name: 'Experimentado', cssClass: 'tier-experimentado' };
    if (score >= t.soldado) return { emoji: '\u2694\uFE0F', name: 'Soldado', cssClass: 'tier-soldado' };
    return { emoji: '\u{1F530}', name: 'Recluta', cssClass: 'tier-recluta' };
}

/**
 * Just the tier emoji.
 */
function tierEmoji(score) {
    return tierBadge(score).emoji;
}

/**
 * Medal emoji for top 3 positions.
 */
function rankMedal(position) {
    if (position === 1) return '\u{1F947}';
    if (position === 2) return '\u{1F948}';
    if (position === 3) return '\u{1F949}';
    return `#${position}`;
}

/**
 * Classify player's playstyle based on stats. Returns {emoji, name}.
 */
function classifyPlaystyle(kd, kpr, dpr, rounds) {
    if (kd >= 2.0 && kpr < 3.0) return { emoji: '\u{1F3AF}', name: 'Francotirador' };
    if (kpr >= 5.0 && dpr >= 4.0) return { emoji: '\u{1F5E1}\uFE0F', name: 'Asesino' };
    if (dpr < 2.5 && kd >= 1.2) return { emoji: '\u{1F6E1}\uFE0F', name: 'Superviviente' };
    if (rounds >= 500 && kd >= 0.8 && kd <= 1.8) return { emoji: '\u2B50', name: 'Veterano' };
    if (kpr >= 4.0 && rounds >= 200) return { emoji: '\u{1F3CB}\uFE0F', name: 'Tanque' };
    if (rounds < 50) return { emoji: '\u{1F331}', name: 'Novato' };
    return { emoji: '\u2694\uFE0F', name: 'Soldado' };
}

/**
 * Get player archetype from pre-computed data, falling back to classifyPlaystyle.
 */
function getPlayerArchetype(player) {
    const arch = player.archetype;
    if (arch && typeof arch === 'object') {
        return { emoji: arch.emoji || '\u2694\uFE0F', name: arch.name || 'Soldado', desc: arch.desc || '' };
    }
    const kd = player['K/D Ratio'] || 0;
    const kpr = player['Kills per Round'] || 0;
    const rounds = player['Rounds'] || 0;
    const dpr = rounds > 0 ? (player['Total Deaths'] || 0) / rounds : 0;
    return classifyPlaystyle(kd, kpr, dpr, rounds);
}

/**
 * Experience badge based on rounds played. Returns {emoji, name}.
 */
function experienceBadge(rounds) {
    if (rounds >= 1000) return { emoji: '\u{1F396}\uFE0F', name: 'Leyenda' };
    if (rounds >= 500) return { emoji: '\u2B50', name: 'Veterano' };
    if (rounds >= 200) return { emoji: '\u2694\uFE0F', name: 'Experimentado' };
    if (rounds >= 50) return { emoji: '\u{1F6E1}\uFE0F', name: 'Regular' };
    if (rounds >= 10) return { emoji: '\u{1F331}', name: 'Novato' };
    return { emoji: '\u2753', name: 'Sin datos suficientes' };
}

/**
 * How reliable are stats based on sample size. Returns {emoji, text, cssClass}.
 */
function sampleReliability(rounds) {
    if (rounds >= 200) return { emoji: '\u{1F7E2}', text: 'Alta confiabilidad', cssClass: 'reliability-high' };
    if (rounds >= 50) return { emoji: '\u{1F7E1}', text: 'Confiabilidad media', cssClass: 'reliability-medium' };
    if (rounds >= 10) return { emoji: '\u{1F7E0}', text: 'Baja confiabilidad', cssClass: 'reliability-low' };
    return { emoji: '\u{1F534}', text: 'Datos insuficientes', cssClass: 'reliability-none' };
}

/**
 * Activity index (0-100). 40% volume log + 30% engagement + 30% impact.
 */
function activityIndex(rounds, spr, kpr) {
    const volumeLog = Math.min(Math.log10(Math.max(rounds, 1)) / Math.log10(NORM_CAPS.rounds), 1.0);
    const engagement = Math.min(spr / NORM_CAPS.spr, 1.0);
    const impact = Math.min(kpr / NORM_CAPS.kpr, 1.0);
    return Math.round((0.4 * volumeLog + 0.3 * engagement + 0.3 * impact) * 100);
}

/**
 * Calculate percentile among all values. Returns "top X%" string.
 */
function percentile(playerValue, allValues) {
    if (!allValues || allValues.length === 0) return 'N/A';
    const countBelow = allValues.filter(v => v < playerValue).length;
    const pct = (countBelow / allValues.length) * 100;
    const topPct = 100 - pct;
    if (topPct < 1) return 'top 1%';
    return `top ${Math.round(topPct)}%`;
}

/**
 * Score breakdown — returns HTML string with 4 progress bars.
 */
function scoreBreakdown(player) {
    const normKd = player['Normalized_KD'] || 0;
    const normScore = player['Normalized_Score'] || 0;
    const normKpr = player['Normalized_Kills_Per_Round'] || 0;
    const normRounds = player['Normalized_Rounds'] || 0;

    const components = [
        { name: 'Combate', val: normKd, desc: 'Kills vs muertes', color: '#00FFFF' },
        { name: 'Puntuacion', val: normScore, desc: 'Score por ronda', color: '#FFA500' },
        { name: 'Agresividad', val: normKpr, desc: 'Kills por ronda', color: '#FF4444' },
        { name: 'Experiencia', val: normRounds, desc: 'Rondas jugadas', color: '#44FF44' },
    ];

    const values = {};
    components.forEach(c => { values[c.name] = c.val; });
    const bottleneck = Object.keys(values).reduce((a, b) => values[a] < values[b] ? a : b);
    const best = Object.keys(values).reduce((a, b) => values[a] > values[b] ? a : b);

    let html = '<div class="score-breakdown">';
    components.forEach(c => {
        let tag = '';
        if (c.name === bottleneck && c.val < 0.7) tag = '<span class="tag-warning" title="Area de mejora">\u26A0\uFE0F</span>';
        else if (c.name === best) tag = '<span class="tag-best" title="Tu mejor stat">\u2B50</span>';

        html += `
            <div class="breakdown-row">
                <div class="breakdown-header">
                    <span class="breakdown-label">${c.name} ${tag}</span>
                    <span class="breakdown-value">${c.val.toFixed(2)}</span>
                </div>
                ${progressBarHTML(c.val, 1.0, c.name, c.color)}
                <span class="breakdown-desc">${c.desc}</span>
            </div>`;
    });
    html += '<p class="breakdown-legend">\u2B50 = tu mejor stat &middot; \u26A0\uFE0F = area de mejora</p>';
    html += '</div>';
    return html;
}

/**
 * Highlight winner/loser in comparison. Returns {class1, class2}.
 */
function highlightWinner(v1, v2, higherBetter = true) {
    if (v1 === v2) return { class1: 'compare-tie', class2: 'compare-tie' };
    if (higherBetter) {
        return v1 > v2
            ? { class1: 'compare-winner', class2: 'compare-loser' }
            : { class1: 'compare-loser', class2: 'compare-winner' };
    }
    return v1 < v2
        ? { class1: 'compare-winner', class2: 'compare-loser' }
        : { class1: 'compare-loser', class2: 'compare-winner' };
}

/**
 * Calculate advantage percentage. Returns "+25.3%" string.
 */
function advantagePct(v1, v2) {
    if (v2 === 0) return v1 > 0 ? '+\u221E%' : '0%';
    const pct = ((v1 - v2) / Math.abs(v2)) * 100;
    return `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`;
}

/**
 * Find a player by name with 3-priority cascade:
 * 1. Exact case-sensitive
 * 2. Exact case-insensitive
 * 3. Partial contains (case-insensitive)
 */
function findPlayer(data, name) {
    if (!name || !data) return null;
    // 1. Exact case-sensitive
    for (const p of data) {
        if (p.Player === name) return p;
    }
    // 2. Exact case-insensitive
    const lower = name.toLowerCase();
    for (const p of data) {
        if (p.Player.toLowerCase() === lower) return p;
    }
    // 3. Partial contains
    for (const p of data) {
        if (p.Player.toLowerCase().includes(lower)) return p;
    }
    return null;
}

/**
 * Sigmoid penalty for low round counts. 1/(1+exp(-(rounds-25)/10))
 */
function sigmoidPenalty(rounds) {
    return 1.0 / (1.0 + Math.exp(-((rounds - 25) / 10)));
}

/**
 * Returns HTML for a styled progress bar.
 */
function progressBarHTML(value, maxValue, label, color = '#00FFFF') {
    const pct = maxValue > 0 ? Math.min(Math.max((value / maxValue) * 100, 0), 100) : 0;
    return `
        <div class="progress-bar-container" title="${label}: ${value.toFixed(2)} / ${maxValue.toFixed(2)}">
            <div class="progress-bar-fill" style="width:${pct.toFixed(1)}%;background:${color}"></div>
        </div>`;
}

/**
 * P95 normalization value from an array.
 */
function p95(values) {
    if (!values || values.length === 0) return 1;
    const sorted = [...values].filter(v => v != null).sort((a, b) => a - b);
    return sorted[Math.floor(sorted.length * 0.95)] || 1;
}

/**
 * Normalize a player name for file URL usage.
 */
function normalizeName(name) {
    return name.replace(/[^a-zA-Z0-9_-]/g, '_');
}

// Escape user/data-derived text before injecting into innerHTML, so names like
// "<img>" or "a & b" can't break the layout or inject markup.
function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, (c) => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
}

// Pretty-print map / gamemode identifiers ("kafar_halab" -> "kafar halab").
function prettifyToken(token) {
    return escapeHtml(String(token || '').replace(/_/g, ' '));
}

/**
 * Build clan logo img tag with fallback to gif.
 */
function clanLogoHTML(clan, size = 48) {
    if (!clan) return '';
    return `<img src="logos/Logo_${clan}.png" alt="Logo ${clan}" class="clan-logo" width="${size}" height="${size}" loading="lazy" onerror="this.onerror=null;this.src='logos/Logo_${clan}.gif';">`;
}

/**
 * Show an error message in a container.
 */
function showError(message, container) {
    if (!container) return;
    container.innerHTML = `<div class="error-message"><span>\u26A0\uFE0F</span> ${message}</div>`;
}

/**
 * Show loading spinner in a container.
 */
function showLoading(container) {
    if (!container) return;
    container.classList.add('loading');
    container.innerHTML = '<div class="loading-indicator"><div class="loading"></div><span>Cargando datos...</span></div>';
}

/**
 * Remove loading state from a container.
 */
function hideLoading(container) {
    if (!container) return;
    container.classList.remove('loading');
}

/**
 * Simple debounce helper.
 */
function debounce(fn, delay) {
    let timer = null;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 4: DATA LOADING & CACHING
// ─────────────────────────────────────────────────────────────────────────────

let playersData = [];
let clanAveragesData = [];
let demoPlayerDetails = null;
let demoMapStats = null;
let dataLoaded = false;
let dataLoading = false;

async function loadData() {
    if (dataLoaded) return;
    if (dataLoading) {
        // Wait for in-progress load
        return new Promise(resolve => {
            const check = setInterval(() => {
                if (dataLoaded) { clearInterval(check); resolve(); }
            }, 50);
        });
    }
    dataLoading = true;

    try {
        // Check localStorage cache (TTL 5 min)
        const cached = localStorage.getItem('playersData');
        const cachedTime = localStorage.getItem('playersDataTime');
        const cachedClans = localStorage.getItem('clanAveragesData');

        if (cached && cachedClans && cachedTime && Date.now() - parseInt(cachedTime) < CACHE_TTL) {
            playersData = JSON.parse(cached);
            clanAveragesData = JSON.parse(cachedClans);
            dataLoaded = true;
            dataLoading = false;
            return;
        }

        const [playersResp, clansResp] = await Promise.all([
            fetch(ALL_PLAYERS_URL),
            fetch(CLAN_AVERAGES_URL)
        ]);

        if (!playersResp.ok) throw new Error('Error al cargar datos de jugadores');
        if (!clansResp.ok) throw new Error('Error al cargar promedios de clanes');

        playersData = await playersResp.json();
        clanAveragesData = await clansResp.json();

        playersData.sort((a, b) => (b['Performance Score'] || 0) - (a['Performance Score'] || 0));

        // Cache to localStorage
        try {
            localStorage.setItem('playersData', JSON.stringify(playersData));
            localStorage.setItem('clanAveragesData', JSON.stringify(clanAveragesData));
            localStorage.setItem('playersDataTime', Date.now().toString());
        } catch (e) {
            // localStorage full — silently ignore
        }

        // Also cache in memory
        memoryCache.set(ALL_PLAYERS_URL, { data: playersData, time: Date.now() });
        memoryCache.set(CLAN_AVERAGES_URL, { data: clanAveragesData, time: Date.now() });

        dataLoaded = true;
    } catch (err) {
        console.error('Error cargando datos:', err);
        showError('No se pudieron cargar los datos. Intenta recargar la pagina.', document.getElementById('player-profile-card'));
    } finally {
        dataLoading = false;
    }
}

/**
 * Load demo data (player details, map stats) for enriched profiles.
 * Fetched on demand, cached in memory.
 */
async function loadDemoData() {
    if (demoPlayerDetails !== null) return; // already loaded (or attempted)

    try {
        const [details, maps] = await Promise.all([
            cachedFetch(`${DEMOS_URL}/player_details.json`, { silent: true }),
            cachedFetch(`${DEMOS_URL}/map_stats.json`, { silent: true })
        ]);
        demoPlayerDetails = details || {};
        demoMapStats = maps || {};
    } catch (err) {
        console.warn('Demo data unavailable:', err);
        demoPlayerDetails = {};
        demoMapStats = {};
    }
}

/**
 * Look up a player in demo data. Returns enrichment object or null.
 */
function getDemoInfo(playerName) {
    if (!demoPlayerDetails || !playerName) return null;

    // Try exact match first, then case-insensitive
    const lower = playerName.toLowerCase();

    // demoPlayerDetails may be an object keyed by name, or an array
    if (Array.isArray(demoPlayerDetails)) {
        return demoPlayerDetails.find(p =>
            p.player === playerName || (p.player && p.player.toLowerCase() === lower) ||
            p.Player === playerName || (p.Player && p.Player.toLowerCase() === lower) ||
            p.name === playerName || (p.name && p.name.toLowerCase() === lower)
        ) || null;
    }

    // Object keyed by player name
    if (demoPlayerDetails[playerName]) return demoPlayerDetails[playerName];
    for (const key of Object.keys(demoPlayerDetails)) {
        if (key.toLowerCase() === lower) return demoPlayerDetails[key];
    }
    return null;
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 5: AUTOCOMPLETE SYSTEM (with debounce)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Create autocomplete for any input + suggestions container pair.
 * Debounces input to avoid excessive computation.
 */
function createAutocomplete(input, suggestionsContainer, onSelect) {
    if (!input || !suggestionsContainer) return;
    let activeIndex = -1;

    function updateSuggestions() {
        const query = input.value.trim().toLowerCase();
        suggestionsContainer.innerHTML = '';
        activeIndex = -1;
        if (query.length === 0 || !dataLoaded) return;

        // Collect matches: exact first, then partial
        const exactMatches = [];
        const partialMatches = [];
        for (const p of playersData) {
            const pLower = p.Player.toLowerCase();
            if (pLower === query) {
                exactMatches.unshift(p);
            } else if (pLower.startsWith(query)) {
                exactMatches.push(p);
            } else if (pLower.includes(query)) {
                partialMatches.push(p);
            }
        }
        const matches = [...exactMatches, ...partialMatches].slice(0, 15);

        matches.forEach((player, index) => {
            const item = document.createElement('div');
            item.classList.add('suggestion-item');
            item.setAttribute('role', 'option');
            item.setAttribute('aria-selected', 'false');
            item.setAttribute('id', `${suggestionsContainer.id}-opt-${index}`);

            const tier = tierBadge(player['Performance Score'] || 0);
            item.innerHTML = `
                <span class="suggestion-name">${player.Player}</span>
                <span class="suggestion-meta">
                    <span class="suggestion-clan">${player.Clan || ''}</span>
                    <span class="suggestion-tier ${tier.cssClass}">${tier.emoji}</span>
                </span>`;

            item.addEventListener('click', () => {
                input.value = player.Player;
                suggestionsContainer.innerHTML = '';
                activeIndex = -1;
                if (onSelect) onSelect(player);
            });
            suggestionsContainer.appendChild(item);
        });
    }

    // Debounced version for input events
    const debouncedUpdate = debounce(() => {
        if (!dataLoaded) {
            loadData().then(updateSuggestions);
        } else {
            updateSuggestions();
        }
    }, AUTOCOMPLETE_DEBOUNCE_MS);

    function handleKeydown(e) {
        const items = suggestionsContainer.querySelectorAll('.suggestion-item');
        if (items.length === 0) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            activeIndex = Math.min(activeIndex + 1, items.length - 1);
            updateActiveItem(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            activeIndex = Math.max(activeIndex - 1, 0);
            updateActiveItem(items);
        } else if (e.key === 'Enter' && activeIndex >= 0) {
            e.preventDefault();
            items[activeIndex].click();
        } else if (e.key === 'Escape') {
            suggestionsContainer.innerHTML = '';
            activeIndex = -1;
        }
    }

    function updateActiveItem(items) {
        items.forEach((item, i) => {
            item.classList.toggle('active', i === activeIndex);
            item.setAttribute('aria-selected', i === activeIndex ? 'true' : 'false');
        });
        if (activeIndex >= 0 && items[activeIndex]) {
            items[activeIndex].scrollIntoView({ block: 'nearest' });
            input.setAttribute('aria-activedescendant', items[activeIndex].id);
        }
    }

    input.addEventListener('input', debouncedUpdate);
    input.addEventListener('keydown', handleKeydown);

    input.addEventListener('focus', () => {
        if (!dataLoaded && !dataLoading) loadData();
    }, { once: true });
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 6: PLAYER PROFILE (search + radar + breakdown + demo data)
// ─────────────────────────────────────────────────────────────────────────────

let radarChartInstance = null;
let historyChartInstance = null;

async function renderPlayerProfile(player) {
    const container = document.getElementById('player-profile-card');
    if (!container || !player) return;

    const ranking = playersData.indexOf(player) + 1;
    const ps = player['Performance Score'] || 0;
    const tier = tierBadge(ps);
    const kd = player['K/D Ratio'] || 0;
    const kpr = player['Kills per Round'] || 0;
    const spr = player['Score per Round'] || 0;
    const rounds = player['Rounds'] || 0;
    const totalKills = player['Total Kills'] || 0;
    const totalDeaths = player['Total Deaths'] || 0;
    const totalScore = player['Total Score'] || 0;
    const dpr = rounds > 0 ? totalDeaths / rounds : 0;
    const clan = player['Clan'] || '';

    const playstyle = getPlayerArchetype(player);
    const expBadge = experienceBadge(rounds);
    const reliability = sampleReliability(rounds);
    const activity = activityIndex(rounds, spr, kpr);

    // Percentiles
    const allPS = playersData.map(p => p['Performance Score'] || 0);
    const allKD = playersData.map(p => p['K/D Ratio'] || 0);
    const allKPR = playersData.map(p => p['Kills per Round'] || 0);
    const allSPR = playersData.map(p => p['Score per Round'] || 0);
    const allRounds = playersData.map(p => p['Rounds'] || 0);

    // Sigmoid penalty display
    const penalty = sigmoidPenalty(rounds);
    let penaltyHTML = '';
    if (penalty * 100 < 95) {
        const roundsFor95 = 25 + 10 * Math.log(19);
        const remaining = Math.max(0, Math.ceil(roundsFor95) - rounds);
        penaltyHTML = `
            <div class="penalty-warning">
                \u26A0\uFE0F Penalizacion: ${(penalty * 100).toFixed(0)}% (necesitas ~${remaining} rondas mas)
            </div>`;
    }

    // Low rounds warning
    let lowRoundsWarning = '';
    if (rounds < 50) {
        lowRoundsWarning = `
            <div class="low-rounds-warning">
                <span class="warning-icon">\u26A0\uFE0F</span>
                <span>Muestra limitada (${rounds} rondas) — los stats se estabilizan con mas partidas</span>
            </div>`;
    }

    // Demo data enrichment
    await loadDemoData();
    const demoInfo = getDemoInfo(player.Player);
    let demoHTML = '';
    if (demoInfo) {
        const winrate = demoInfo.winrate != null ? demoInfo.winrate : (demoInfo.wins != null && demoInfo.total_rounds != null && demoInfo.total_rounds > 0 ? ((demoInfo.wins / demoInfo.total_rounds) * 100) : null);
        const topKits = demoInfo.top_kits || demoInfo.kits || null;
        const teamworkRaw = demoInfo.teamwork_ratio != null ? demoInfo.teamwork_ratio : (demoInfo.teamwork != null ? demoInfo.teamwork : null);

        demoHTML = '<div class="demo-data-section"><h3 class="subsection-title">Datos de Demos</h3>';

        if (winrate != null) {
            const wr = typeof winrate === 'number' && winrate <= 1 ? (winrate * 100) : winrate;
            demoHTML += `
                <div class="stat-row">
                    <span class="stat-label">Winrate</span>
                    <span class="stat-value">${typeof wr === 'number' ? wr.toFixed(1) : wr}%</span>
                    <div class="progress-bar-container" title="Winrate">
                        <div class="progress-bar-fill" style="width:${Math.min(typeof wr === 'number' ? wr : 50, 100)}%;background:${typeof wr === 'number' && wr >= 50 ? '#00FF88' : '#FF4466'}"></div>
                    </div>
                </div>`;
        }

        if (topKits) {
            let kitsDisplay = '';
            if (Array.isArray(topKits)) {
                kitsDisplay = topKits.slice(0, 5).map(k => {
                    if (typeof k === 'string') return k;
                    return k.name || k.kit || String(k);
                }).join(', ');
            } else if (typeof topKits === 'object') {
                const sorted = Object.entries(topKits).sort((a, b) => b[1] - a[1]).slice(0, 5);
                kitsDisplay = sorted.map(([name, count]) => `${name} (${count})`).join(', ');
            } else {
                kitsDisplay = String(topKits);
            }
            if (kitsDisplay) {
                demoHTML += `
                    <div class="stat-row">
                        <span class="stat-label">Top Kits</span>
                        <span class="stat-value" style="font-size:0.9rem">${kitsDisplay}</span>
                    </div>`;
            }
        }

        if (teamworkRaw != null) {
            const tw = typeof teamworkRaw === 'number' && teamworkRaw <= 1 ? (teamworkRaw * 100) : teamworkRaw;
            demoHTML += `
                <div class="stat-row">
                    <span class="stat-label">Teamwork Ratio</span>
                    <span class="stat-value">${typeof tw === 'number' ? tw.toFixed(1) : tw}%</span>
                    <div class="progress-bar-container" title="Teamwork">
                        <div class="progress-bar-fill" style="width:${Math.min(typeof tw === 'number' ? tw : 50, 100)}%;background:#00BBFF"></div>
                    </div>
                </div>`;
        }

        demoHTML += '</div>';
    }

    const ratings = player.ratings;
    let ratingsHTML = '';
    if (ratings) {
        const ratingsItems = [
            { key: 'combat', emoji: '\u2694\uFE0F', name: 'Combate' },
            { key: 'tactical', emoji: '\u{1F3AF}', name: 'Tactico' },
            { key: 'reliability', emoji: '\u{1F6E1}\uFE0F', name: 'Fiabilidad' },
            { key: 'impact', emoji: '\u{1F4A5}', name: 'Impacto' },
        ];
        ratingsHTML = '<div class="demo-data-section"><h3 class="subsection-title">Indices Compuestos</h3>';
        for (const r of ratingsItems) {
            const val = ratings[r.key] || 0;
            ratingsHTML += `
                <div class="stat-row">
                    <span class="stat-label">${r.emoji} ${r.name}</span>
                    <span class="stat-value">${val.toFixed(0)}/100</span>
                    <div class="progress-bar-container">
                        <div class="progress-bar-fill" style="width:${Math.min(val, 100)}%;background:${val >= 70 ? '#00FF88' : val >= 40 ? '#00BBFF' : '#FFA500'}"></div>
                    </div>
                </div>`;
        }
        ratingsHTML += '</div>';
    }

    container.innerHTML = `
        <div class="player-profile card animate-in">
            <div class="profile-header">
                ${clanLogoHTML(clan, 64)}
                <div class="profile-header-info">
                    <h2 class="profile-name">${player.Player}</h2>
                    <div class="profile-badges">
                        <span class="tier-badge ${tier.cssClass}">${tier.emoji} ${tier.name}</span>
                        <span class="playstyle-badge">${playstyle.emoji} ${playstyle.name}</span>
                        <span class="exp-badge">${expBadge.emoji} ${expBadge.name}</span>
                    </div>
                    ${playstyle.desc ? `<div class="archetype-desc">${playstyle.desc}</div>` : ''}
                    <div class="profile-meta">
                        <span class="rank-display">#${ranking} Global</span>
                        <span class="clan-name">${clan}</span>
                        <span class="${reliability.cssClass}">${reliability.emoji} ${reliability.text}</span>
                    </div>
                </div>
            </div>

            <div class="profile-body">
                <div class="stats-column">
                    <div class="stat-row">
                        <span class="stat-label">K/D Ratio</span>
                        <span class="stat-value">${kd.toFixed(2)}</span>
                        <span class="stat-percentile">${percentile(kd, allKD)}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Kills por Ronda</span>
                        <span class="stat-value">${kpr.toFixed(2)}</span>
                        <span class="stat-percentile">${percentile(kpr, allKPR)}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Score por Ronda</span>
                        <span class="stat-value">${spr.toFixed(2)}</span>
                        <span class="stat-percentile">${percentile(spr, allSPR)}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Performance Score</span>
                        <span class="stat-value highlight">${ps.toFixed(2)}</span>
                        <span class="stat-percentile">${percentile(ps, allPS)}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Rondas Jugadas</span>
                        <span class="stat-value">${formatNumber(rounds)}</span>
                        <span class="stat-percentile">${percentile(rounds, allRounds)}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Total Kills</span>
                        <span class="stat-value">${formatNumber(totalKills)}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Total Muertes</span>
                        <span class="stat-value">${formatNumber(totalDeaths)}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Total Score</span>
                        <span class="stat-value">${formatNumber(totalScore)}</span>
                    </div>

                    <h3 class="subsection-title">Desglose Performance</h3>
                    ${scoreBreakdown(player)}

                    <h3 class="subsection-title">Actividad</h3>
                    <div class="activity-display">
                        <div class="activity-bar-container">
                            <div class="activity-bar-fill" style="width:${activity}%"></div>
                        </div>
                        <span class="activity-value">${activity}/100</span>
                        <span class="activity-tier">${activity >= 80 ? '\u{1F525} Muy Activo' : activity >= 60 ? '\u2705 Activo' : activity >= 40 ? '\u{1F7E1} Moderado' : activity >= 20 ? '\u{1F7E0} Bajo' : '\u2744\uFE0F Inactivo'}</span>
                    </div>

                    ${penaltyHTML}
                    ${demoHTML}
                    ${ratingsHTML}
                </div>
            </div>

            ${lowRoundsWarning}
        </div>`;

    // Build radar chart using existing canvas in charts-row
    renderRadarChart(player, clan);

    // Reset and load history chart
    const historyCanvas = document.getElementById('historyChart');
    if (historyCanvas) {
        historyCanvas.style.display = 'none';
    }
    loadPlayerHistory(player.Player);
}

function renderRadarChart(player, clan) {
    const canvas = document.getElementById('radarChart');
    if (!canvas) return;

    if (radarChartInstance) {
        radarChartInstance.destroy();
        radarChartInstance = null;
    }

    const radar = player.radar;
    const radarKeys = ['letalidad', 'supervivencia', 'teamwork', 'impacto', 'consistencia', 'versatilidad'];
    const labels = ['Letalidad', 'Supervivencia', 'Teamwork', 'Impacto', 'Consistencia', 'Versatilidad'];

    let playerValues;
    if (radar) {
        playerValues = radarKeys.map(k => radar[k] || 0);
    } else {
        // Fallback for players without pre-computed radar
        const kd = player['K/D Ratio'] || 0;
        const kpr = player['Kills per Round'] || 0;
        const rounds = player['Rounds'] || 0;
        const dpr = rounds > 0 ? (player['Total Deaths'] || 0) / rounds : 0;
        const allKPR = playersData.map(p => p['Kills per Round'] || 0);
        playerValues = [
            Math.min(kpr / p95(allKPR), 1.0),
            Math.max(0, 1 - dpr / 6),
            0.3, 0.3, 0.3, 0.3
        ];
    }

    // Clan average from pre-computed radars
    const clanPlayers = playersData.filter(p => p.Clan === clan && p.radar);
    let clanAvgValues;
    if (clanPlayers.length > 0) {
        clanAvgValues = radarKeys.map(k =>
            clanPlayers.reduce((s, p) => s + (p.radar[k] || 0), 0) / clanPlayers.length
        );
    } else {
        clanAvgValues = [0, 0, 0, 0, 0, 0];
    }

    radarChartInstance = new Chart(canvas, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: player.Player,
                    data: playerValues,
                    backgroundColor: 'rgba(0, 255, 255, 0.2)',
                    borderColor: '#00FFFF',
                    borderWidth: 2,
                    pointBackgroundColor: '#00FFFF',
                    pointBorderColor: '#00FFFF',
                    pointRadius: 4
                },
                {
                    label: `Promedio ${clan}`,
                    data: clanAvgValues,
                    backgroundColor: 'rgba(255, 165, 0, 0.1)',
                    borderColor: '#FFA500',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    pointBackgroundColor: '#FFA500',
                    pointBorderColor: '#FFA500',
                    pointRadius: 3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                r: {
                    beginAtZero: true,
                    max: 1.0,
                    ticks: {
                        stepSize: 0.2,
                        color: 'rgba(255,255,255,0.5)',
                        backdropColor: 'transparent'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    angleLines: {
                        color: 'rgba(255, 255, 255, 0.15)'
                    },
                    pointLabels: {
                        color: '#ffffff',
                        font: { size: 11, family: 'Roboto' }
                    }
                }
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#ffffff',
                        font: { family: 'Roboto' }
                    }
                }
            }
        }
    });
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 7: COMPARISON
// ─────────────────────────────────────────────────────────────────────────────

function performComparison() {
    const entity1Name = document.getElementById('entity1').value.trim();
    const entity2Name = document.getElementById('entity2').value.trim();
    const container = document.getElementById('compare-results');
    if (!container) return;

    if (!entity1Name || !entity2Name) {
        showError('Ingresa ambos nombres para comparar.', container);
        return;
    }

    const p1 = findPlayer(playersData, entity1Name);
    const p2 = findPlayer(playersData, entity2Name);

    if (p1 && p2) {
        renderPlayerComparison(p1, p2, container);
    } else {
        // Try clan comparison
        const clan1Players = playersData.filter(p => p.Clan && p.Clan.toLowerCase() === entity1Name.toLowerCase());
        const clan2Players = playersData.filter(p => p.Clan && p.Clan.toLowerCase() === entity2Name.toLowerCase());

        if (clan1Players.length > 0 && clan2Players.length > 0) {
            renderClanComparison(entity1Name, clan1Players, entity2Name, clan2Players, container);
        } else {
            showError(`No se encontraron jugadores o clanes: "${!p1 ? entity1Name : entity2Name}"`, container);
        }
    }
}

function renderPlayerComparison(p1, p2, container) {
    const metrics = [
        { label: 'K/D Ratio', key: 'K/D Ratio', higherBetter: true },
        { label: 'Kills por Ronda', key: 'Kills per Round', higherBetter: true },
        { label: 'Score por Ronda', key: 'Score per Round', higherBetter: true },
        { label: 'Performance Score', key: 'Performance Score', higherBetter: true },
        { label: 'Rondas', key: 'Rounds', higherBetter: true },
        { label: 'Total Kills', key: 'Total Kills', higherBetter: true },
        { label: 'Total Score', key: 'Total Score', higherBetter: true },
    ];

    let p1Wins = 0;
    let p2Wins = 0;

    let rowsHTML = '';
    metrics.forEach(m => {
        const v1 = p1[m.key] || 0;
        const v2 = p2[m.key] || 0;
        const result = highlightWinner(v1, v2, m.higherBetter);
        if (result.class1 === 'compare-winner') p1Wins++;
        if (result.class2 === 'compare-winner') p2Wins++;

        const isFloat = typeof v1 === 'number' && v1 % 1 !== 0;
        const fmt = isFloat ? 2 : 0;

        rowsHTML += `
            <div class="compare-row">
                <span class="compare-val ${result.class1}">${v1.toFixed(fmt)}</span>
                <span class="compare-metric">${m.label}</span>
                <span class="compare-val ${result.class2}">${v2.toFixed(fmt)}</span>
                <span class="compare-adv">${advantagePct(v1, v2)}</span>
            </div>`;
    });

    const tier1 = tierBadge(p1['Performance Score'] || 0);
    const tier2 = tierBadge(p2['Performance Score'] || 0);
    let verdictHTML;
    if (p1Wins > p2Wins) {
        verdictHTML = `<div class="compare-verdict winner">\u{1F3C6} ${p1.Player} gana ${p1Wins}/${metrics.length} categorias</div>`;
    } else if (p2Wins > p1Wins) {
        verdictHTML = `<div class="compare-verdict winner">\u{1F3C6} ${p2.Player} gana ${p2Wins}/${metrics.length} categorias</div>`;
    } else {
        verdictHTML = `<div class="compare-verdict tie">\u{1F91D} Empate ${p1Wins}-${p2Wins}</div>`;
    }

    container.innerHTML = `
        <div class="comparison-card card animate-in">
            <div class="compare-header">
                <div class="compare-entity">
                    ${clanLogoHTML(p1.Clan, 40)}
                    <span class="compare-name">${p1.Player}</span>
                    <span class="tier-badge ${tier1.cssClass}">${tier1.emoji} ${tier1.name}</span>
                </div>
                <span class="compare-vs">VS</span>
                <div class="compare-entity">
                    ${clanLogoHTML(p2.Clan, 40)}
                    <span class="compare-name">${p2.Player}</span>
                    <span class="tier-badge ${tier2.cssClass}">${tier2.emoji} ${tier2.name}</span>
                </div>
            </div>
            <div class="compare-body">
                ${rowsHTML}
            </div>
            ${verdictHTML}
        </div>`;
}

function renderClanComparison(name1, clan1, name2, clan2, container) {
    const avg = (arr, key) => arr.length > 0 ? arr.reduce((s, p) => s + (p[key] || 0), 0) / arr.length : 0;
    const sum = (arr, key) => arr.reduce((s, p) => s + (p[key] || 0), 0);

    const metrics = [
        { label: 'Jugadores', v1: clan1.length, v2: clan2.length, higherBetter: true },
        { label: 'Prom. K/D', v1: avg(clan1, 'K/D Ratio'), v2: avg(clan2, 'K/D Ratio'), higherBetter: true },
        { label: 'Prom. KPR', v1: avg(clan1, 'Kills per Round'), v2: avg(clan2, 'Kills per Round'), higherBetter: true },
        { label: 'Prom. SPR', v1: avg(clan1, 'Score per Round'), v2: avg(clan2, 'Score per Round'), higherBetter: true },
        { label: 'Prom. PS', v1: avg(clan1, 'Performance Score'), v2: avg(clan2, 'Performance Score'), higherBetter: true },
        { label: 'Total Kills', v1: sum(clan1, 'Total Kills'), v2: sum(clan2, 'Total Kills'), higherBetter: true },
        { label: 'Total Score', v1: sum(clan1, 'Total Score'), v2: sum(clan2, 'Total Score'), higherBetter: true },
        { label: 'Total Rondas', v1: sum(clan1, 'Rounds'), v2: sum(clan2, 'Rounds'), higherBetter: true },
    ];

    let c1Wins = 0;
    let c2Wins = 0;
    let rowsHTML = '';
    metrics.forEach(m => {
        const result = highlightWinner(m.v1, m.v2, m.higherBetter);
        if (result.class1 === 'compare-winner') c1Wins++;
        if (result.class2 === 'compare-winner') c2Wins++;
        const isFloat = typeof m.v1 === 'number' && m.v1 % 1 !== 0;
        const fmt = isFloat ? 2 : 0;

        rowsHTML += `
            <div class="compare-row">
                <span class="compare-val ${result.class1}">${typeof m.v1 === 'number' ? m.v1.toFixed(fmt) : m.v1}</span>
                <span class="compare-metric">${m.label}</span>
                <span class="compare-val ${result.class2}">${typeof m.v2 === 'number' ? m.v2.toFixed(fmt) : m.v2}</span>
                <span class="compare-adv">${advantagePct(m.v1, m.v2)}</span>
            </div>`;
    });

    let verdictHTML;
    if (c1Wins > c2Wins) {
        verdictHTML = `<div class="compare-verdict winner">\u{1F3C6} ${name1.toUpperCase()} gana ${c1Wins}/${metrics.length} categorias</div>`;
    } else if (c2Wins > c1Wins) {
        verdictHTML = `<div class="compare-verdict winner">\u{1F3C6} ${name2.toUpperCase()} gana ${c2Wins}/${metrics.length} categorias</div>`;
    } else {
        verdictHTML = `<div class="compare-verdict tie">\u{1F91D} Empate ${c1Wins}-${c2Wins}</div>`;
    }

    container.innerHTML = `
        <div class="comparison-card card animate-in">
            <div class="compare-header">
                <div class="compare-entity">
                    ${clanLogoHTML(name1, 40)}
                    <span class="compare-name">${name1.toUpperCase()}</span>
                    <span class="compare-count">${clan1.length} jugadores</span>
                </div>
                <span class="compare-vs">VS</span>
                <div class="compare-entity">
                    ${clanLogoHTML(name2, 40)}
                    <span class="compare-name">${name2.toUpperCase()}</span>
                    <span class="compare-count">${clan2.length} jugadores</span>
                </div>
            </div>
            <div class="compare-body">
                ${rowsHTML}
            </div>
            ${verdictHTML}
        </div>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 8: TOP RANKINGS
// ─────────────────────────────────────────────────────────────────────────────

function performTopRankings() {
    const category = document.getElementById('category').value;
    const metric = document.getElementById('metric').value;
    const topNumber = parseInt(document.getElementById('top-number').value) || 10;
    const container = document.getElementById('top-results');
    if (!container) return;

    const metricMap = {
        'performance': 'Performance Score',
        'kd': 'K/D Ratio',
        'kills': 'Total Kills',
        'deaths': 'Total Deaths',
        'rounds': 'Rounds'
    };
    const metricKey = metricMap[metric] || 'Performance Score';

    let filtered = playersData;
    if (category !== 'general') {
        filtered = playersData.filter(p => p.Clan && p.Clan.toLowerCase() === category.toLowerCase());
    }

    // Separate qualified and excluded
    const qualified = filtered.filter(p => (p['Rounds'] || 0) >= MIN_ROUNDS_FOR_RANKING);
    const excludedCount = filtered.length - qualified.length;

    const sorted = [...qualified].sort((a, b) => (b[metricKey] || 0) - (a[metricKey] || 0));
    const top = sorted.slice(0, topNumber);

    if (top.length === 0) {
        showError('No se encontraron jugadores con suficientes rondas para esta categoria.', container);
        return;
    }

    // Find max value for progress bars
    const maxVal = Math.max(...top.map(p => Math.abs(p[metricKey] || 0)), 0.01);

    let rowsHTML = '';
    top.forEach((p, i) => {
        const pos = i + 1;
        const medal = rankMedal(pos);
        const val = p[metricKey] || 0;
        const tier = tierBadge(p['Performance Score'] || 0);
        const isFloat = typeof val === 'number' && val % 1 !== 0;
        const pct = (Math.abs(val) / maxVal) * 100;

        rowsHTML += `
            <div class="ranking-row ${pos <= 3 ? 'ranking-top3' : ''} animate-in" style="animation-delay:${i * 0.05}s">
                <span class="ranking-pos">${medal}</span>
                ${clanLogoHTML(p.Clan, 28)}
                <span class="ranking-name">${p.Player}</span>
                <span class="ranking-clan">${p.Clan}</span>
                <span class="ranking-tier">${tier.emoji}</span>
                <div class="ranking-bar-container">
                    <div class="ranking-bar-fill" style="width:${pct.toFixed(1)}%"></div>
                </div>
                <span class="ranking-value">${isFloat ? val.toFixed(2) : formatNumber(val)}</span>
            </div>`;
    });

    container.innerHTML = `
        <div class="rankings-card card animate-in">
            <div class="rankings-header">
                <h3>Top ${top.length} — ${category === 'general' ? 'General' : category.toUpperCase()} (${metricKey})</h3>
                ${excludedCount > 0 ? `<span class="excluded-count">${excludedCount} jugadores excluidos (&lt;${MIN_ROUNDS_FOR_RANKING} rondas)</span>` : ''}
            </div>
            <div class="rankings-body">
                ${rowsHTML}
            </div>
        </div>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 9: MATCH PREDICTOR (with animated bar)
// ─────────────────────────────────────────────────────────────────────────────

function performPrediction() {
    const container = document.getElementById('prediction-results');
    if (!container) return;

    // Collect team players
    const teamANames = [];
    const teamBNames = [];
    for (let i = 1; i <= 8; i++) {
        const aInput = document.getElementById(`teamA-p${i}`);
        const bInput = document.getElementById(`teamB-p${i}`);
        if (aInput && aInput.value.trim()) teamANames.push(aInput.value.trim());
        if (bInput && bInput.value.trim()) teamBNames.push(bInput.value.trim());
    }

    if (teamANames.length === 0 || teamBNames.length === 0) {
        showError('Agrega al menos un jugador en cada equipo.', container);
        return;
    }

    const teamA = [];
    const teamB = [];
    const notFound = [];

    teamANames.forEach(name => {
        const p = findPlayer(playersData, name);
        if (p) teamA.push(p);
        else notFound.push(name);
    });
    teamBNames.forEach(name => {
        const p = findPlayer(playersData, name);
        if (p) teamB.push(p);
        else notFound.push(name);
    });

    if (notFound.length > 0) {
        showError(`Jugadores no encontrados: ${notFound.join(', ')}`, container);
        return;
    }

    // Weighted composite using dynamic weights from tier_config
    // Web can't use winrate (no per-player demo data), so redistribute winrate weight
    function teamComposite(team) {
        if (team.length === 0) return 0;
        const raw = tierConfigData?.predictor_weights || {ps: 0.50, kd: 0.30, kpr: 0.20};
        // Normalize to 3 usable weights (exclude winrate, redistribute proportionally)
        const usable = (raw.ps || 0) + (raw.kd || 0) + (raw.kpr || 0);
        const norm = usable > 0 ? usable : 1;
        const wPS = (raw.ps || 0.50) / norm;
        const wKD = (raw.kd || 0.30) / norm;
        const wKPR = (raw.kpr || 0.20) / norm;
        const avgPS = team.reduce((s, p) => s + (p['Performance Score'] || 0), 0) / team.length;
        const avgKD = team.reduce((s, p) => s + (p['K/D Ratio'] || 0), 0) / team.length;
        const avgKPR = team.reduce((s, p) => s + (p['Kills per Round'] || 0), 0) / team.length;
        return wPS * avgPS + wKD * (avgKD / NORM_CAPS.kd) + wKPR * (avgKPR / NORM_CAPS.kpr);
    }

    const scoreA = teamComposite(teamA);
    const scoreB = teamComposite(teamB);
    const total = scoreA + scoreB || 1;
    const probA = (scoreA / total) * 100;
    const probB = (scoreB / total) * 100;

    const avgPS_A = teamA.reduce((s, p) => s + (p['Performance Score'] || 0), 0) / teamA.length;
    const avgPS_B = teamB.reduce((s, p) => s + (p['Performance Score'] || 0), 0) / teamB.length;
    const avgKD_A = teamA.reduce((s, p) => s + (p['K/D Ratio'] || 0), 0) / teamA.length;
    const avgKD_B = teamB.reduce((s, p) => s + (p['K/D Ratio'] || 0), 0) / teamB.length;
    const avgKPR_A = teamA.reduce((s, p) => s + (p['Kills per Round'] || 0), 0) / teamA.length;
    const avgKPR_B = teamB.reduce((s, p) => s + (p['Kills per Round'] || 0), 0) / teamB.length;

    function teamPlayersHTML(team, color) {
        return team.map(p => {
            const tier = tierBadge(p['Performance Score'] || 0);
            return `<div class="predictor-player">
                ${clanLogoHTML(p.Clan, 24)}
                <span>${p.Player}</span>
                <span class="tier-badge ${tier.cssClass}" style="font-size:0.8rem">${tier.emoji} ${(p['Performance Score'] || 0).toFixed(2)}</span>
            </div>`;
        }).join('');
    }

    // Render with initial 0% widths, then animate
    container.innerHTML = `
        <div class="prediction-card card animate-in">
            <h3>Resultado de la Prediccion</h3>

            <div class="prediction-bar-wrapper">
                <div class="prediction-bar">
                    <div class="prediction-bar-a" style="width:0%;transition:width 1s cubic-bezier(0.25,0.46,0.45,0.94)">
                        <span>${probA.toFixed(1)}%</span>
                    </div>
                    <div class="prediction-bar-b" style="width:0%;transition:width 1s cubic-bezier(0.25,0.46,0.45,0.94)">
                        <span>${probB.toFixed(1)}%</span>
                    </div>
                </div>
                <div class="prediction-labels">
                    <span class="prediction-label-a">Equipo A</span>
                    <span class="prediction-label-b">Equipo B</span>
                </div>
            </div>

            <div class="prediction-teams">
                <div class="prediction-team">
                    <h4>Equipo A</h4>
                    <div class="prediction-team-stats">
                        <div class="stat-mini">Prom. PS: <strong>${avgPS_A.toFixed(2)}</strong></div>
                        <div class="stat-mini">Prom. K/D: <strong>${avgKD_A.toFixed(2)}</strong></div>
                        <div class="stat-mini">Prom. KPR: <strong>${avgKPR_A.toFixed(2)}</strong></div>
                    </div>
                    <div class="prediction-roster">${teamPlayersHTML(teamA, '#00FFFF')}</div>
                </div>
                <div class="prediction-team">
                    <h4>Equipo B</h4>
                    <div class="prediction-team-stats">
                        <div class="stat-mini">Prom. PS: <strong>${avgPS_B.toFixed(2)}</strong></div>
                        <div class="stat-mini">Prom. K/D: <strong>${avgKD_B.toFixed(2)}</strong></div>
                        <div class="stat-mini">Prom. KPR: <strong>${avgKPR_B.toFixed(2)}</strong></div>
                    </div>
                    <div class="prediction-roster">${teamPlayersHTML(teamB, '#FFA500')}</div>
                </div>
            </div>

            <p class="prediction-disclaimer">\u2139\uFE0F Prediccion basada en promedios historicos. No garantiza resultados.</p>
        </div>`;

    // Animate the prediction bars after a frame
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            const barA = container.querySelector('.prediction-bar-a');
            const barB = container.querySelector('.prediction-bar-b');
            if (barA) barA.style.width = `${probA.toFixed(1)}%`;
            if (barB) barB.style.width = `${probB.toFixed(1)}%`;
        });
    });
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 10: TEAM ANALYSIS
// ─────────────────────────────────────────────────────────────────────────────

let teamRadarInstance = null;

function performTeamAnalysis() {
    const container = document.getElementById('team-results');
    if (!container) return;

    const playerNames = [];
    for (let i = 1; i <= 8; i++) {
        const input = document.getElementById(`player${i}`);
        if (input && input.value.trim()) playerNames.push(input.value.trim());
    }

    if (playerNames.length < 2 || playerNames.length > 8) {
        showError('Selecciona entre 2 y 8 jugadores.', container);
        return;
    }

    const team = [];
    const notFound = [];
    playerNames.forEach(name => {
        const p = findPlayer(playersData, name);
        if (p) team.push(p);
        else notFound.push(name);
    });

    if (notFound.length > 0) {
        showError(`Jugadores no encontrados: ${notFound.join(', ')}`, container);
        return;
    }

    // Aggregate stats
    const totalKills = team.reduce((s, p) => s + (p['Total Kills'] || 0), 0);
    const totalDeaths = team.reduce((s, p) => s + (p['Total Deaths'] || 0), 0);
    const totalScore = team.reduce((s, p) => s + (p['Total Score'] || 0), 0);
    const totalRounds = team.reduce((s, p) => s + (p['Rounds'] || 0), 0);
    const avgPS = team.reduce((s, p) => s + (p['Performance Score'] || 0), 0) / team.length;
    const teamKD = totalDeaths > 0 ? totalKills / totalDeaths : 0;
    const avgKPR = totalRounds > 0 ? totalKills / totalRounds : 0;
    const avgDPR = totalRounds > 0 ? totalDeaths / totalRounds : 0;

    // Per-player cards
    let playersHTML = '';
    team.forEach(p => {
        const kd = p['K/D Ratio'] || 0;
        const kpr = p['Kills per Round'] || 0;
        const rounds = p['Rounds'] || 0;
        const style = getPlayerArchetype(p);
        const tier = tierBadge(p['Performance Score'] || 0);

        playersHTML += `
            <div class="team-player-card">
                ${clanLogoHTML(p.Clan, 32)}
                <div class="team-player-info">
                    <span class="team-player-name">${p.Player}</span>
                    <span class="tier-badge ${tier.cssClass}">${tier.emoji} ${tier.name}</span>
                    <span class="playstyle-badge">${style.emoji} ${style.name}</span>
                </div>
                <div class="team-player-stats">
                    <span>K/D: ${kd.toFixed(2)}</span>
                    <span>KPR: ${kpr.toFixed(2)}</span>
                    <span>PS: ${(p['Performance Score'] || 0).toFixed(2)}</span>
                </div>
            </div>`;
    });

    container.innerHTML = `
        <div class="team-analysis-card card animate-in">
            <h3>Metricas del Equipo</h3>
            <div class="team-aggregate-stats">
                <div class="stat-card">
                    <span class="stat-card-value">${teamKD.toFixed(2)}</span>
                    <span class="stat-card-label">Team K/D</span>
                </div>
                <div class="stat-card">
                    <span class="stat-card-value">${avgPS.toFixed(2)}</span>
                    <span class="stat-card-label">Prom. PS</span>
                </div>
                <div class="stat-card">
                    <span class="stat-card-value">${avgKPR.toFixed(2)}</span>
                    <span class="stat-card-label">KPR</span>
                </div>
                <div class="stat-card">
                    <span class="stat-card-value">${formatNumber(totalKills)}</span>
                    <span class="stat-card-label">Total Kills</span>
                </div>
                <div class="stat-card">
                    <span class="stat-card-value">${formatNumber(totalDeaths)}</span>
                    <span class="stat-card-label">Total Muertes</span>
                </div>
                <div class="stat-card">
                    <span class="stat-card-value">${formatNumber(totalRounds)}</span>
                    <span class="stat-card-label">Total Rondas</span>
                </div>
            </div>

            <h3>Composicion del Equipo</h3>
            <div class="team-players-grid">
                ${playersHTML}
            </div>

            <h3>Radar del Equipo</h3>
            <canvas id="teamRadarChart"></canvas>
        </div>`;

    // Team radar chart
    renderTeamRadar(team);
}

function renderTeamRadar(team) {
    const canvas = document.getElementById('teamRadarChart');
    if (!canvas) return;

    if (teamRadarInstance) {
        teamRadarInstance.destroy();
        teamRadarInstance = null;
    }

    // Check if team members have pre-computed radar data
    const teamWithRadar = team.filter(p => p.radar);

    let teamValues;
    let chartMax;
    let labels;
    if (teamWithRadar.length > 0) {
        // Use pre-computed 6-axis radar, averaging across team members with radar data
        const radarKeys = ['letalidad', 'supervivencia', 'teamwork', 'impacto', 'consistencia', 'versatilidad'];
        labels = ['Letalidad', 'Supervivencia', 'Teamwork', 'Impacto', 'Consistencia', 'Versatilidad'];
        teamValues = radarKeys.map(k =>
            teamWithRadar.reduce((s, p) => s + (p.radar[k] || 0), 0) / teamWithRadar.length
        );
        chartMax = 1.0;
    } else {
        // Fallback to 5-axis computation from raw stats
        labels = ['Combate (K/D)', 'Eficiencia (KPR)', 'Puntuacion (SPR)', 'Experiencia', 'Performance'];
        const allKD = playersData.map(p => p['K/D Ratio'] || 0);
        const allKPR = playersData.map(p => p['Kills per Round'] || 0);
        const allSPR = playersData.map(p => p['Score per Round'] || 0);
        const allRounds = playersData.map(p => p['Rounds'] || 0);
        const allPS = playersData.map(p => p['Performance Score'] || 0);

        const p95KD = p95(allKD);
        const p95KPR = p95(allKPR);
        const p95SPR = p95(allSPR);
        const p95Rounds = p95(allRounds);
        const p95PS = p95(allPS);

        const avgKD = team.reduce((s, p) => s + (p['K/D Ratio'] || 0), 0) / team.length;
        const avgKPR = team.reduce((s, p) => s + (p['Kills per Round'] || 0), 0) / team.length;
        const avgSPR = team.reduce((s, p) => s + (p['Score per Round'] || 0), 0) / team.length;
        const avgRounds = team.reduce((s, p) => s + (p['Rounds'] || 0), 0) / team.length;
        const avgPS = team.reduce((s, p) => s + (p['Performance Score'] || 0), 0) / team.length;

        teamValues = [
            Math.min(avgKD / p95KD, 1.5),
            Math.min(avgKPR / p95KPR, 1.5),
            Math.min(avgSPR / p95SPR, 1.5),
            Math.min(avgRounds / p95Rounds, 1.5),
            Math.min(avgPS / p95PS, 1.5)
        ];
        chartMax = 1.5;
    }

    teamRadarInstance = new Chart(canvas, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Equipo',
                data: teamValues,
                backgroundColor: 'rgba(0, 255, 255, 0.2)',
                borderColor: '#00FFFF',
                borderWidth: 2,
                pointBackgroundColor: '#00FFFF',
                pointRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                r: {
                    beginAtZero: true,
                    max: chartMax,
                    ticks: { color: 'rgba(255,255,255,0.5)', backdropColor: 'transparent' },
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    angleLines: { color: 'rgba(255,255,255,0.15)' },
                    pointLabels: { color: '#fff', font: { size: 11 } }
                }
            },
            plugins: {
                legend: { labels: { color: '#fff' } }
            }
        }
    });
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 11: CLAN AVERAGES
// ─────────────────────────────────────────────────────────────────────────────

let clanAveragesChartInstance = null;

function renderClanAverages() {
    if (!clanAveragesData || clanAveragesData.length === 0) return;

    const sorted = [...clanAveragesData].sort((a, b) => (b['Performance Score'] || 0) - (a['Performance Score'] || 0));
    const container = document.getElementById('clan-averages-results');
    const chartCanvas = document.getElementById('clanAveragesChart');

    // Bar chart
    if (chartCanvas) {
        if (clanAveragesChartInstance) {
            clanAveragesChartInstance.destroy();
            clanAveragesChartInstance = null;
        }

        const labels = sorted.map(c => c.Clan);
        const scores = sorted.map(c => c['Performance Score'] || 0);

        // Generate colors: gradient from cyan to orange
        const colors = scores.map((_, i) => {
            const t = i / Math.max(scores.length - 1, 1);
            const r = Math.round(0 + t * 255);
            const g = Math.round(255 - t * 90);
            const b = Math.round(255 - t * 255);
            return `rgba(${r}, ${g}, ${b}, 0.6)`;
        });
        const borderColors = colors.map(c => c.replace('0.6', '1'));

        // Set fixed height based on number of clans (Chart.js needs explicit height, not minHeight)
        chartCanvas.parentElement.style.height = `${Math.max(sorted.length * 35, 300)}px`;

        clanAveragesChartInstance = new Chart(chartCanvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Performance Score',
                    data: scores,
                    backgroundColor: colors,
                    borderColor: borderColors,
                    borderWidth: 1,
                    borderRadius: 5,
                    barThickness: 30,
                    hoverBackgroundColor: borderColors
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255,255,255,0.1)' },
                        ticks: { color: '#fff' }
                    },
                    y: {
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#fff', font: { size: 13, weight: 'bold' } }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    // Stats cards
    if (container) {
        const maxPS = sorted.length > 0 ? (sorted[0]['Performance Score'] || 1) : 1;

        let html = '';
        sorted.forEach((clan, i) => {
            const ps = clan['Performance Score'] || 0;
            const kd = clan['K/D Ratio'] || 0;
            const kpr = clan['Kills per Round'] || 0;
            const spr = clan['Score per Round'] || 0;
            const rounds = clan['Rounds'] || 0;

            html += `
                <div class="clan-avg-card card">
                    <div class="clan-avg-header">
                        ${clanLogoHTML(clan.Clan, 40)}
                        <div>
                            <h4>${clan.Clan}</h4>
                            <span class="clan-rank">#${i + 1}</span>
                        </div>
                    </div>
                    <div class="clan-avg-stats">
                        <div class="clan-stat">
                            <span class="clan-stat-label">Performance</span>
                            ${progressBarHTML(ps, maxPS, 'PS', '#00FFFF')}
                            <span class="clan-stat-value">${ps.toFixed(2)}</span>
                        </div>
                        <div class="clan-stat">
                            <span class="clan-stat-label">K/D</span>
                            <span class="clan-stat-value">${kd.toFixed(2)}</span>
                        </div>
                        <div class="clan-stat">
                            <span class="clan-stat-label">KPR</span>
                            <span class="clan-stat-value">${kpr.toFixed(2)}</span>
                        </div>
                        <div class="clan-stat">
                            <span class="clan-stat-label">SPR</span>
                            <span class="clan-stat-value">${spr.toFixed(2)}</span>
                        </div>
                    </div>
                </div>`;
        });
        container.innerHTML = html;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 11.5: DEMO STATS
// ─────────────────────────────────────────────────────────────────────────────

let demoPlayerData = null;
let demoMapData = null;
let demoDataLoaded = false;

async function loadDemoStatsData() {
    if (demoDataLoaded) return;
    try {
        const [playerResp, mapResp] = await Promise.all([
            fetch(`${DEMOS_URL}/player_details.json`),
            fetch(`${DEMOS_URL}/map_stats.json`)
        ]);
        if (playerResp.ok) demoPlayerData = await playerResp.json();
        if (mapResp.ok) demoMapData = await mapResp.json();
        demoDataLoaded = true;
    } catch (err) {
        console.error('Error cargando datos de demos:', err);
    }
}

function createDemoPlayerAutocomplete(input, suggestionsContainer) {
    if (!input || !suggestionsContainer) return;
    let activeIndex = -1;

    input.addEventListener('input', async () => {
        if (!demoDataLoaded) await loadDemoStatsData();
        const query = input.value.trim().toLowerCase();
        suggestionsContainer.innerHTML = '';
        activeIndex = -1;
        if (query.length === 0 || !demoPlayerData) return;

        const matches = demoPlayerData
            .filter(p => p.ign.toLowerCase().includes(query))
            .slice(0, 15);

        matches.forEach((player, index) => {
            const item = document.createElement('div');
            item.classList.add('suggestion-item');
            item.setAttribute('role', 'option');
            item.textContent = player.ign;
            item.addEventListener('click', () => {
                input.value = player.ign;
                suggestionsContainer.innerHTML = '';
            });
            suggestionsContainer.appendChild(item);
        });
    });
}

function createDemoMapAutocomplete(input, suggestionsContainer) {
    if (!input || !suggestionsContainer) return;

    input.addEventListener('input', async () => {
        if (!demoDataLoaded) await loadDemoStatsData();
        const query = input.value.trim().toLowerCase();
        suggestionsContainer.innerHTML = '';
        if (query.length === 0 || !demoMapData) return;

        const uniqueMaps = [...new Set(demoMapData.map(m => m.map_name))];
        const matches = uniqueMaps.filter(m => m.toLowerCase().includes(query)).slice(0, 15);

        matches.forEach(mapName => {
            const item = document.createElement('div');
            item.classList.add('suggestion-item');
            item.setAttribute('role', 'option');
            item.textContent = mapName;
            item.addEventListener('click', () => {
                input.value = mapName;
                suggestionsContainer.innerHTML = '';
            });
            suggestionsContainer.appendChild(item);
        });
    });
}

function renderDemoPlayerStats(playerName) {
    const container = document.getElementById('demo-player-results');
    if (!container || !demoPlayerData) return;

    const player = demoPlayerData.find(p => p.ign.toLowerCase() === playerName.toLowerCase());
    if (!player) {
        showError(`Jugador "${playerName}" no encontrado en datos de demos.`, container);
        return;
    }

    const kd = player.total_deaths > 0 ? (player.total_kills / player.total_deaths).toFixed(2) : 'N/A';
    const kpr = player.rounds_played > 0 ? (player.total_kills / player.rounds_played).toFixed(2) : 'N/A';

    // Top 5 kits
    const kits = Object.entries(player.kits_used || {})
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);

    let kitsHTML = kits.map(([kit, count]) =>
        `<div class="demo-kit-row"><span>${prettifyToken(kit)}</span><span>${count} usos</span></div>`
    ).join('');

    container.innerHTML = `
        <div class="stats-box animate-in">
            <h3>${escapeHtml(player.ign)}</h3>
            <p><strong>Rondas jugadas:</strong> ${player.rounds_played}</p>
            <p><strong>Kills:</strong> ${formatNumber(player.total_kills)} | <strong>Muertes:</strong> ${formatNumber(player.total_deaths)} | <strong>K/D:</strong> ${kd}</p>
            <p><strong>KPR:</strong> ${kpr} | <strong>Score:</strong> ${formatNumber(player.total_score)}</p>
            <p><strong>Revives dados:</strong> ${player.total_revives_given || 0} | <strong>Vehiculos destruidos:</strong> ${player.total_vehicles_destroyed || 0}</p>
            <h4 style="margin-top:12px;text-align:left;color:var(--accent)">Top Kits</h4>
            <div class="demo-kits-list">${kitsHTML}</div>
        </div>`;

    // Append the player's recent-round timeline (from per-player round files).
    renderPlayerRoundsTimeline(player.ign);
}

function renderDemoMapStats(mapName) {
    const container = document.getElementById('demo-map-results');
    if (!container || !demoMapData) return;

    const mapEntries = demoMapData.filter(m => m.map_name.toLowerCase() === mapName.toLowerCase());
    if (mapEntries.length === 0) {
        showError(`Mapa "${mapName}" no encontrado en datos de demos.`, container);
        return;
    }

    let html = '';
    mapEntries.forEach(entry => {
        const totalRounds = entry.rounds_played || 0;
        const avgKillsPerRound = totalRounds > 0 ? (entry.total_kills / totalRounds).toFixed(1) : 'N/A';

        html += `
            <div class="stats-box animate-in" style="margin-bottom:12px">
                <h3>${entry.map_name} (${entry.gamemode})</h3>
                <p><strong>Rondas jugadas:</strong> ${totalRounds}</p>
                <p><strong>Total Kills:</strong> ${formatNumber(entry.total_kills)} | <strong>Kills/Ronda:</strong> ${avgKillsPerRound}</p>
                <p><strong>Revives:</strong> ${formatNumber(entry.total_revives || 0)} | <strong>Vehiculos destruidos:</strong> ${formatNumber(entry.total_vehicles_destroyed || 0)}</p>
                <p><strong>Tickets prom. Equipo 1:</strong> ${(entry.avg_tickets1_final || 0).toFixed(1)} | <strong>Equipo 2:</strong> ${(entry.avg_tickets2_final || 0).toFixed(1)}</p>
            </div>`;
    });

    container.innerHTML = html;
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 11.6: ROUND-BASED STATS (leaderboards, recent matches, player rounds)
// ─────────────────────────────────────────────────────────────────────────────

const LB_METRIC_LABELS = {
    kills: 'Kills', kd: 'K/D', score: 'Score',
    revives: 'Revives', teamwork_score: 'Teamwork',
};
const leaderboardCache = {};

async function loadLeaderboardData(period) {
    if (leaderboardCache[period]) return leaderboardCache[period];
    const data = await cachedFetch(`${LEADERBOARDS_URL}/${period}.json`, { silent: true });
    leaderboardCache[period] = data || { players: [], total_rounds: 0 };
    return leaderboardCache[period];
}

async function renderLeaderboard() {
    const container = document.getElementById('leaderboard-results');
    if (!container) return;

    const periodEl = document.getElementById('lb-period');
    const metricEl = document.getElementById('lb-metric');
    const countEl = document.getElementById('lb-count');
    if (!periodEl || !metricEl || !countEl) return;

    const period = periodEl.value;
    const metric = metricEl.value;
    const count = Math.max(1, Math.min(50, parseInt(countEl.value, 10) || 15));

    container.innerHTML = '<div class="loading-indicator"><div class="loading"></div><span>Cargando...</span></div>';

    let data;
    try {
        data = await loadLeaderboardData(period);
    } catch (err) {
        console.warn('Leaderboard unavailable:', err);
        showError('No se pudieron cargar los leaderboards.', container);
        return;
    }

    const players = (data && Array.isArray(data.players)) ? data.players.slice() : [];
    if (players.length === 0) {
        container.innerHTML = '<p class="no-data-msg">No hay rondas registradas en este periodo todavia.</p>';
        return;
    }

    const sortVal = (p) => metric === 'kd'
        ? (p.deaths > 0 ? p.kills / p.deaths : p.kills)
        : (p[metric] || 0);
    const fmtVal = (p) => metric === 'kd'
        ? (p.deaths > 0 ? p.kills / p.deaths : p.kills).toFixed(2)
        : formatNumber(p[metric] || 0);

    players.sort((a, b) => sortVal(b) - sortVal(a));
    const top = players.slice(0, count);
    const medals = ['🥇', '🥈', '🥉'];

    const rows = top.map((p, i) => `
        <tr>
            <td class="lb-rank">${i < 3 ? medals[i] : (i + 1)}</td>
            <td class="lb-name">${escapeHtml(p.ign)}</td>
            <td class="lb-value">${fmtVal(p)}</td>
            <td class="lb-detail">${p.rounds}R · ${p.kills}K/${p.deaths}D</td>
        </tr>`).join('');

    container.innerHTML = `
        <p class="lb-summary"><strong>${formatNumber(data.total_rounds || 0)}</strong> rondas · <strong>${players.length}</strong> jugadores de clanes</p>
        <div class="table-scroll">
            <table class="rounds-table">
                <thead><tr><th>#</th><th>Jugador</th><th>${LB_METRIC_LABELS[metric] || 'Valor'}</th><th>Detalle</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
}

// Parse "tracker_2026_03_17_09_06_18_..." -> "2026-03-17 09:06" (or '' if N/A).
function matchDateLabel(filename) {
    const m = /tracker_(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_/.exec(filename || '');
    if (!m) return '';
    return `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}`;
}

let recentMatchesLoaded = false;
async function loadRecentMatches() {
    const container = document.getElementById('recent-matches-results');
    if (!container || recentMatchesLoaded) return;
    recentMatchesLoaded = true;

    container.innerHTML = '<div class="loading-indicator"><div class="loading"></div><span>Cargando partidas...</span></div>';

    let index;
    try {
        index = await cachedFetch(`${ROUNDS_URL}/index.json`, { silent: true });
    } catch (err) {
        console.warn('Recent matches unavailable:', err);
        recentMatchesLoaded = false; // allow retry on next view
        showError('No se pudieron cargar las partidas recientes.', container);
        return;
    }

    const dates = (index && Array.isArray(index.dates)) ? index.dates.slice().sort().reverse() : [];
    if (dates.length === 0) {
        container.innerHTML = '<p class="no-data-msg">No hay partidas registradas todavia.</p>';
        return;
    }

    const TARGET = 25;
    let rounds = [];
    for (const d of dates) {
        if (rounds.length >= TARGET) break;
        try {
            const dayRounds = await cachedFetch(`${ROUNDS_URL}/${d}.json`, { silent: true });
            if (Array.isArray(dayRounds)) rounds = rounds.concat(dayRounds);
        } catch (e) {
            console.warn(`Could not load rounds for ${d}:`, e);
        }
    }

    if (rounds.length === 0) {
        container.innerHTML = '<p class="no-data-msg">No hay partidas disponibles.</p>';
        return;
    }

    rounds.sort((a, b) => String(b.filename || '').localeCompare(String(a.filename || '')));
    const recent = rounds.slice(0, TARGET);

    const rows = recent.map((r) => {
        const winner = r.winner;
        let winLabel = '—';
        if (winner === 1) winLabel = prettifyToken(r.blufor_team || 'Equipo 1');
        else if (winner === 2) winLabel = prettifyToken(r.opfor_team || 'Equipo 2');
        return `
            <tr>
                <td>${escapeHtml(matchDateLabel(r.filename))}</td>
                <td>${prettifyToken(r.map_name)}</td>
                <td>${prettifyToken(r.gamemode)}</td>
                <td>${winLabel}</td>
                <td>${formatNumber(r.total_kills || 0)}</td>
            </tr>`;
    }).join('');

    container.innerHTML = `
        <div class="table-scroll">
            <table class="rounds-table">
                <thead><tr><th>Fecha</th><th>Mapa</th><th>Modo</th><th>Ganador</th><th>Kills</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
}

// Append a player's recent-round timeline to the demo-player results box.
async function renderPlayerRoundsTimeline(playerName) {
    const container = document.getElementById('demo-player-results');
    if (!container) return;

    let data;
    try {
        data = await cachedFetch(`${PLAYER_ROUNDS_URL}/${normalizeName(playerName)}.json`, { silent: true });
    } catch (err) {
        return; // no per-round data for this player — silently skip
    }
    if (!data || !Array.isArray(data.rounds) || data.rounds.length === 0) return;

    const recent = data.rounds.slice().reverse().slice(0, 20);
    const rows = recent.map((r) => `
        <tr>
            <td>${escapeHtml(r.date)}</td>
            <td>${prettifyToken(r.map)}</td>
            <td>${prettifyToken(r.gamemode)}</td>
            <td>${r.kills}/${r.deaths}</td>
            <td>${formatNumber(r.score)}</td>
            <td>${r.won ? '✅' : '—'}</td>
        </tr>`).join('');

    const box = document.createElement('div');
    box.className = 'stats-box animate-in';
    box.innerHTML = `
        <h4 style="margin-top:0;text-align:left;color:var(--accent)">Ultimas rondas (${recent.length} de ${data.rounds.length})</h4>
        <div class="table-scroll">
            <table class="rounds-table">
                <thead><tr><th>Fecha</th><th>Mapa</th><th>Modo</th><th>K/D</th><th>Score</th><th>Win</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    container.appendChild(box);
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 12: HISTORIAL / TRENDS
// ─────────────────────────────────────────────────────────────────────────────

async function loadPlayerHistory(playerName) {
    const normalized = normalizeName(playerName);
    const url = `${HISTORY_URL}/${normalized}_history.json`;
    const canvas = document.getElementById('historyChart');

    try {
        const historyData = await cachedFetch(url, { silent: true });
        if (!historyData || !Array.isArray(historyData) || historyData.length === 0) {
            if (canvas) canvas.style.display = 'none';
            return;
        }
        renderHistoryChart(historyData, canvas);
    } catch (err) {
        console.error('Error al cargar historial:', err);
        if (canvas) canvas.style.display = 'none';
    }
}

function renderHistoryChart(historyData, canvas) {
    if (!canvas) return;
    canvas.style.display = 'block';

    if (historyChartInstance) {
        historyChartInstance.destroy();
        historyChartInstance = null;
    }

    const dates = historyData.map(e => e.Date);
    const scores = historyData.map(e => e['Performance Score']);

    // Linear regression for trend line
    const n = scores.length;
    let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
    scores.forEach((y, x) => {
        sumX += x;
        sumY += y;
        sumXY += x * y;
        sumX2 += x * x;
    });
    const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX) || 0;
    const intercept = (sumY - slope * sumX) / n;
    const trendLine = scores.map((_, x) => slope * x + intercept);

    // Streak detection
    let currentStreak = 0;
    let streakDir = 0; // 1 = up, -1 = down
    for (let i = scores.length - 1; i > 0; i--) {
        const diff = scores[i] - scores[i - 1];
        if (i === scores.length - 1) {
            streakDir = diff >= 0 ? 1 : -1;
            currentStreak = 1;
        } else {
            if ((diff >= 0 && streakDir === 1) || (diff < 0 && streakDir === -1)) {
                currentStreak++;
            } else {
                break;
            }
        }
    }

    const trendEmoji = slope > 0.001 ? '\u{1F4C8}' : slope < -0.001 ? '\u{1F4C9}' : '\u2796';
    const trendText = slope > 0.001 ? 'Tendencia positiva' : slope < -0.001 ? 'Tendencia negativa' : 'Estable';

    // Add trend info below chart
    const parent = canvas.parentElement;
    let trendInfo = parent.querySelector('.trend-info');
    if (!trendInfo) {
        trendInfo = document.createElement('div');
        trendInfo.className = 'trend-info';
        parent.appendChild(trendInfo);
    }
    trendInfo.innerHTML = `
        <span>${trendEmoji} ${trendText}</span>
        <span>Racha: ${currentStreak} ${streakDir === 1 ? 'subiendo' : 'bajando'}</span>
    `;

    historyChartInstance = new Chart(canvas, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Performance Score',
                    data: scores,
                    borderColor: '#00FFFF',
                    backgroundColor: 'rgba(0, 255, 255, 0.15)',
                    fill: true,
                    tension: 0.3,
                    pointBackgroundColor: '#00FFFF',
                    pointRadius: scores.length > 60 ? 0 : scores.length > 30 ? 2 : 3,
                    pointHoverRadius: 5,
                    borderWidth: 2
                },
                {
                    label: 'Tendencia',
                    data: trendLine,
                    borderColor: '#FFA500',
                    borderDash: [8, 4],
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                y: {
                    beginAtZero: false,
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    ticks: { color: '#fff' }
                },
                x: {
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: {
                        color: '#fff',
                        maxRotation: 45,
                        maxTicksLimit: 10
                    }
                }
            },
            plugins: {
                legend: {
                    labels: { color: '#fff' }
                },
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(4)}`
                    }
                }
            }
        }
    });
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 13: HERO STATS COUNTER (animated count-up)
// ─────────────────────────────────────────────────────────────────────────────

let countersAnimated = false;

function animateCounters() {
    if (countersAnimated || !dataLoaded) return;
    countersAnimated = true;

    const totalPlayers = playersData.length;
    const uniqueClans = new Set(playersData.map(p => p.Clan).filter(Boolean)).size;
    const totalRounds = playersData.reduce((s, p) => s + (p['Rounds'] || 0), 0);

    animateCounter('counter-players', totalPlayers, 1500);
    animateCounter('counter-clans', uniqueClans, 1000);
    animateCounter('counter-rounds', totalRounds, 2000);
}

function animateCounter(elementId, target, duration) {
    const el = document.getElementById(elementId);
    if (!el) return;

    const startTime = performance.now();
    const startVal = 0;

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // Ease-out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(startVal + (target - startVal) * eased);
        el.textContent = current.toLocaleString('es-AR');
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    requestAnimationFrame(update);
}

// ─────────────────────────────────────────────────────────────────────────────
// SECTION 14: INITIALIZATION
// ─────────────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {

    // ── Setup autocompletes ──────────────────────────────────────────────

    // Player search
    createAutocomplete(
        document.getElementById('player-name'),
        document.getElementById('suggestions')
    );

    // Comparison inputs
    createAutocomplete(
        document.getElementById('entity1'),
        document.getElementById('suggestions-entity1')
    );
    createAutocomplete(
        document.getElementById('entity2'),
        document.getElementById('suggestions-entity2')
    );

    // Match predictor inputs
    for (let i = 1; i <= 8; i++) {
        createAutocomplete(
            document.getElementById(`teamA-p${i}`),
            document.getElementById(`suggestions-teamA-p${i}`)
        );
        createAutocomplete(
            document.getElementById(`teamB-p${i}`),
            document.getElementById(`suggestions-teamB-p${i}`)
        );
    }

    // Team analysis inputs
    for (let i = 1; i <= 8; i++) {
        createAutocomplete(
            document.getElementById(`player${i}`),
            document.getElementById(`suggestions${i}`)
        );
    }

    // ── Close suggestion dropdowns on outside click ──────────────────────

    document.addEventListener('click', (e) => {
        document.querySelectorAll('.suggestions').forEach(container => {
            const parent = container.closest('.input-group') || container.closest('.search-input-wrapper') || container.parentElement;
            if (parent && !parent.contains(e.target)) {
                container.innerHTML = '';
            }
        });
    });

    // ── Form handlers with loading states & error handling ───────────────

    // Player Search
    const searchForm = document.getElementById('search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const container = document.getElementById('player-profile-card');
            try {
                showLoading(container);
                await loadData();
                const name = document.getElementById('player-name').value.trim();
                if (!name) {
                    showError('Ingresa un nombre de jugador.', container);
                    return;
                }
                const player = findPlayer(playersData, name);
                if (player) {
                    hideLoading(container);
                    await renderPlayerProfile(player);
                } else {
                    showError(`Jugador "${name}" no encontrado en la base de datos.`, container);
                }
            } catch (err) {
                console.error('Error en busqueda:', err);
                showError('Ocurrio un error al buscar. Intenta de nuevo.', container);
            } finally {
                hideLoading(container);
            }
        });
    }

    // Comparison
    const compareForm = document.getElementById('compare-form');
    if (compareForm) {
        compareForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const container = document.getElementById('compare-results');
            try {
                showLoading(container);
                await loadData();
                hideLoading(container);
                performComparison();
            } catch (err) {
                console.error('Error en comparacion:', err);
                showError('Ocurrio un error al comparar. Intenta de nuevo.', container);
                hideLoading(container);
            }
        });
    }

    // Top Rankings
    const topForm = document.getElementById('top-players-form');
    if (topForm) {
        topForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const container = document.getElementById('top-results');
            try {
                showLoading(container);
                await loadData();
                hideLoading(container);
                performTopRankings();
            } catch (err) {
                console.error('Error en rankings:', err);
                showError('Ocurrio un error al cargar rankings. Intenta de nuevo.', container);
                hideLoading(container);
            }
        });
    }

    // Match Predictor
    const predictionForm = document.getElementById('prediction-form');
    if (predictionForm) {
        predictionForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const container = document.getElementById('prediction-results');
            try {
                showLoading(container);
                await loadData();
                hideLoading(container);
                performPrediction();
            } catch (err) {
                console.error('Error en prediccion:', err);
                showError('Ocurrio un error al predecir. Intenta de nuevo.', container);
                hideLoading(container);
            }
        });
    }

    // Team Analysis
    const teamForm = document.getElementById('team-analysis-form');
    if (teamForm) {
        teamForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const container = document.getElementById('team-results');
            try {
                showLoading(container);
                await loadData();
                hideLoading(container);
                performTeamAnalysis();
            } catch (err) {
                console.error('Error en analisis de equipo:', err);
                showError('Ocurrio un error al analizar el equipo. Intenta de nuevo.', container);
                hideLoading(container);
            }
        });
    }

    // Demo stats autocompletes
    createDemoPlayerAutocomplete(
        document.getElementById('demo-player-name'),
        document.getElementById('demo-suggestions')
    );
    createDemoMapAutocomplete(
        document.getElementById('demo-map-name'),
        document.getElementById('demo-map-suggestions')
    );

    // Demo Player Search
    const demoPlayerForm = document.getElementById('demo-player-form');
    if (demoPlayerForm) {
        demoPlayerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const container = document.getElementById('demo-player-results');
            try {
                await loadDemoStatsData();
                const name = document.getElementById('demo-player-name').value.trim();
                if (!name) {
                    showError('Ingresa un nombre de jugador.', container);
                    return;
                }
                renderDemoPlayerStats(name);
            } catch (err) {
                console.error('Error en busqueda de demos:', err);
                showError('Ocurrio un error al buscar datos de demos.', container);
            }
        });
    }

    // Demo Map Search
    const demoMapForm = document.getElementById('demo-map-form');
    if (demoMapForm) {
        demoMapForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const container = document.getElementById('demo-map-results');
            try {
                await loadDemoStatsData();
                const name = document.getElementById('demo-map-name').value.trim();
                if (!name) {
                    showError('Ingresa un nombre de mapa.', container);
                    return;
                }
                renderDemoMapStats(name);
            } catch (err) {
                console.error('Error en busqueda de mapas:', err);
                showError('Ocurrio un error al buscar datos del mapa.', container);
            }
        });
    }

    // ── Leaderboards por periodo ─────────────────────────────────────────
    ['lb-period', 'lb-metric'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', renderLeaderboard);
    });
    const lbCount = document.getElementById('lb-count');
    if (lbCount) lbCount.addEventListener('input', renderLeaderboard);

    // ── Lazy-load round-based sections when first scrolled into view ──────
    const lazyLoadOnView = (sectionId, cb) => {
        const el = document.getElementById(sectionId);
        if (!el) return;
        if (!('IntersectionObserver' in window)) { cb(); return; }
        const obs = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    obs.unobserve(entry.target);
                    cb();
                }
            });
        }, { threshold: 0.1 });
        obs.observe(el);
    };
    lazyLoadOnView('leaderboards', renderLeaderboard);
    lazyLoadOnView('recent-matches', loadRecentMatches);

    // ── Load clan averages on page load ──────────────────────────────────

    loadTierConfig(); // Load tier config for dynamic thresholds

    loadData().then(() => {
        renderClanAverages();
        // Trigger counters if hero is visible
        animateCounters();
    }).catch(err => {
        console.error('Error en carga inicial:', err);
    });

    // ── Intersection Observer for hero counters ──────────────────────────

    const heroSection = document.getElementById('hero');
    if (heroSection && 'IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    loadData().then(animateCounters);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.3 });
        observer.observe(heroSection);
    }

    // ── Intersection Observer for fade-in animations on all sections ─────

    if ('IntersectionObserver' in window) {
        const sectionObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    sectionObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });

        document.querySelectorAll('.section, .hero, section').forEach(section => {
            sectionObserver.observe(section);
        });
    }

    // ── Preload data on idle ─────────────────────────────────────────────

    if ('requestIdleCallback' in window) {
        requestIdleCallback(() => loadData());
    }
});
