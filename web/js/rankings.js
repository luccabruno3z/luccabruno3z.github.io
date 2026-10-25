/* ═══════════════════════════════════════════════════════════════════════════
   rankings.js — Top-N players by metric, optional clan filter.
   See .rebuild/CONTRACT.md §2.5 and FEATURE_API.md (rankings notes).
   ═══════════════════════════════════════════════════════════════════════════ */

import { state } from './data.js';
import { MIN_ROUNDS_FOR_RANKING } from './config.js';
import { escapeHtml, clanLogoHTML, formatNumber } from './utils.js';
import { barHTML, tierBarHTML, tierChipHTML, podiumHTML, tableHTML, posHTML } from './ui.js';

// Metric value → the raw player field it reads, plus whether higher is better.
const METRICS = {
    performance: { key: 'Performance Score', label: 'Performance Score' },
    kd:          { key: 'K/D Ratio',         label: 'K/D Ratio' },
    kills:       { key: 'Total Kills',       label: 'Total Kills' },
    deaths:      { key: 'Total Deaths',      label: 'Total Deaths' },
    rounds:      { key: 'Rounds',            label: 'Rounds' },
};

// Lowercased dropdown values that don't simply uppercase to the Clan field.
const CLAN_VALUE_MAP = { 'rim-la': 'RIM:LA' };

/** Resolve a lowercased dropdown value to the canonical clan token to match. */
function clanTokenFor(value) {
    if (CLAN_VALUE_MAP[value]) return CLAN_VALUE_MAP[value];
    return value.toUpperCase();
}

function renderRankings() {
    const results = document.getElementById('top-results');
    if (!results) return;

    const category = (document.getElementById('category')?.value || 'general').toLowerCase();
    const metricKey = document.getElementById('metric')?.value || 'performance';
    const topN = Math.max(1, parseInt(document.getElementById('top-number')?.value, 10) || 10);
    const metric = METRICS[metricKey] || METRICS.performance;

    const players = state.playersData || [];
    if (!players.length) {
        results.innerHTML = '<div class="empty-state">No hay datos de jugadores disponibles.</div>';
        return;
    }

    // Filter by clan (case-insensitive against canonical token).
    let pool = players;
    let clanLabel = '';
    if (category !== 'general') {
        const token = clanTokenFor(category).toLowerCase();
        pool = players.filter(p => p.Clan && p.Clan.toLowerCase() === token);
        clanLabel = clanTokenFor(category);
    }

    // Exclude players below the rounds threshold; report how many were excluded.
    // Fuente única: el umbral sale de tier_config.json (min_rounds) con fallback a config.js.
    const minRounds = state.tierConfigData?.min_rounds ?? MIN_ROUNDS_FOR_RANKING;
    const qualified = pool.filter(p => (p.Rounds || 0) >= minRounds);
    const excluded = pool.length - qualified.length;

    if (!qualified.length) {
        const where = clanLabel ? ` para el clan ${escapeHtml(clanLabel)}` : '';
        results.innerHTML = `<div class="empty-state">No hay jugadores con al menos ${minRounds} rondas${where}.</div>`;
        return;
    }

    const sorted = [...qualified].sort((a, b) => (b[metric.key] || 0) - (a[metric.key] || 0));
    const shown = sorted.slice(0, topN);
    const maxValue = shown.reduce((m, p) => Math.max(m, p[metric.key] || 0), 0) || 1;

    const headerBits = [`Top ${shown.length} por ${escapeHtml(metric.label)}`];
    if (clanLabel) headerBits.push(`Clan ${escapeHtml(clanLabel)}`);

    const fmt = (v) => formatNumber(metricKey === 'kd' || metricKey === 'performance' ? Number((v || 0).toFixed(2)) : v || 0);
    const clanCell = (p) => p.Clan
        ? `${clanLogoHTML(p.Clan, 20)} <span class="dtable-muted">${escapeHtml(p.Clan)}</span>` : '';
    // Performance: barra coloreada por tier (mismos umbrales que el rango). Resto: cian,
    // relativa al primero.
    const bar = (v) => metricKey === 'performance' ? tierBarHTML(v) : barHTML((v / maxValue) * 100);

    const podium = podiumHTML(shown.slice(0, 3).map((p) => ({
        title: p.Player,
        sub: `${p.Clan ? clanLogoHTML(p.Clan, 18) + ' ' + escapeHtml(p.Clan) : ''} ${tierChipHTML(p['Performance Score'])}`,
        value: fmt(p[metric.key]),
        logo: '',
    })));

    const rest = shown.slice(3);
    const table = rest.length ? tableHTML(
        [
            { label: '#', width: '56px' },
            { label: 'Jugador', width: 'minmax(0,1.6fr)' },
            { label: 'Clan', width: 'minmax(0,1fr)' },
            { label: 'Tier', width: '130px' },
            { label: metric.label, width: 'minmax(0,1.6fr)' },
            { label: 'Valor', width: '90px', align: 'end' },
        ],
        rest.map((p, i) => [
            posHTML(i + 4),
            `<span class="dtable-name">${escapeHtml(p.Player)}</span>`,
            clanCell(p),
            tierChipHTML(p['Performance Score']),
            bar(p[metric.key] || 0),
            `<span class="dtable-val">${fmt(p[metric.key])}</span>`,
        ]),
        { minWidth: 680, caption: headerBits.join(' · ') },
    ) : '';

    const excludedNote = excluded > 0
        ? `<p class="rankings-excluded">${excluded} jugador${excluded === 1 ? '' : 'es'} excluido${excluded === 1 ? '' : 's'} por tener menos de ${minRounds} rondas.</p>`
        : '';

    results.innerHTML = `
        <div class="rankings-header">${headerBits.join(' · ')}</div>
        ${podium}${table}
        ${excludedNote}`;
}

/** Rankings init: render on submit + initial render. */
export function initRankings() {
    const form = document.getElementById('top-players-form');
    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            renderRankings();
        });
    }
    // Re-render live when controls change.
    ['category', 'metric', 'top-number'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', renderRankings);
    });

    renderRankings();
}
