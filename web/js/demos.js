/* ═══════════════════════════════════════════════════════════════════════════
   demos.js — demo-derived player profile (tabbed) + map tool + rounds timeline.
   Mirrors the bot's demo commands: combate, armas/vehiculos, assets, kits/modos,
   sinergia, rondas. See .rebuild/CONTRACT.md §2.10 / §1.5 / §1.6.
   ═══════════════════════════════════════════════════════════════════════════ */

import { state, loadDemoData, loadPlayerRounds, getDemoInfo, loadSynergy } from './data.js';
import { setupAutocomplete } from './autocomplete.js';
import {
    escapeHtml, formatNumber, fmtDuration, aggregateByLabel, findPlayer,
    kitLabel, weaponModel, weaponKind, vehicleLabel, mapLabel, gamemodeLabel,
    seatLabel, weaponVehicle, isVehicleKill, assetCategory, vehicleIconHTML, vehicleIconByName,
} from './utils.js';

// Weapons that aren't a personal firearm (environmental, vehicle-mounted). If
// aliases aren't loaded we can't know the kind, so only drop '?' (degrade by
// showing extra rather than emptying the list).
const _NON_INFANTRY = (code) => {
    if (code === '?') return true;
    if (!state.aliases?.weapons) return false;
    const k = weaponKind(code);
    return k === 'vehicle' || k === 'unknown';
};

const ACCUM = '⏳ Acumulándose desde las partidas nuevas.';

// ── Small HTML helpers ───────────────────────────────────────────────────────

function statRow(label, value) {
    return `<div class="stat-row"><span class="stat-label">${escapeHtml(label)}</span><span class="stat-value">${value}</span></div>`;
}

function topList(pairs, limit = 5, emptyMsg = 'Sin datos.') {
    if (!pairs.length) return `<li class="empty-state">${escapeHtml(emptyMsg)}</li>`;
    return pairs.slice(0, limit)
        .map(([label, n]) => `<li>${escapeHtml(label)} <span class="stat-value">${formatNumber(n)}</span></li>`)
        .join('');
}

/** Horizontal bars from [label, value] pairs (value can be % or count). */
function bars(items, { suffix = '', max = null, icon = null } = {}) {
    if (!items.length) return `<div class="empty-state">Sin datos.</div>`;
    const top = max ?? Math.max(...items.map(i => i[1]), 1);
    return `<div class="hbars">` + items.map(([label, val]) => {
        const pct = Math.max(2, (val / top) * 100);
        return `<div class="hbar-row">
            <span class="hbar-label">${icon ? icon(label) : ''}${escapeHtml(label)}</span>
            <span class="hbar-track"><span class="hbar-fill" style="width:${pct}%"></span></span>
            <span class="hbar-val">${formatNumber(val)}${suffix}</span>
        </div>`;
    }).join('') + `</div>`;
}

function emptyTab(msg = ACCUM) {
    return `<div class="empty-state">${escapeHtml(msg)}</div>`;
}

// ── Tab renderers (return HTML strings) ──────────────────────────────────────

function tabResumen(p) {
    const kills = p.total_kills || 0, deaths = p.total_deaths || 0;
    const kd = deaths > 0 ? kills / deaths : kills;
    const kits = aggregateByLabel(p.kits_used, kitLabel);
    const weapons = aggregateByLabel(p.kill_weapons, weaponModel, { exclude: _NON_INFANTRY });
    const favKit = kits.length ? kits[0][0] : '—';
    const favWeapon = weapons.length ? weapons[0][0] : '—';
    const lives = p.lives || 0, aliveS = p.alive_seconds || 0;
    const head = [];
    if (lives) head.push(['Vida promedio', fmtDuration(aliveS / lives)]);
    if (aliveS) head.push(['Kills/min (vida)', (kills / (aliveS / 60)).toFixed(2)]);
    if (p.best_killstreak) head.push(['Mejor racha', `${p.best_killstreak} sin morir`]);

    return `
        ${head.length ? `<div class="headline-grid">${head.map(([l, v]) =>
            `<div class="headline-stat"><span class="hs-value">${escapeHtml(String(v))}</span><span class="hs-label">${escapeHtml(l)}</span></div>`).join('')}</div>` : ''}
        <div class="stat-grid">
            ${statRow('Rondas jugadas', formatNumber(p.rounds_played || 0))}
            ${statRow('K/D', `${kd.toFixed(2)} <small>(${formatNumber(kills)}/${formatNumber(deaths)})</small>`)}
            ${statRow('Score', formatNumber(p.total_score || 0))}
            ${statRow('Revives dados', formatNumber(p.total_revives_given || 0))}
            ${statRow('Vehículos destruidos', formatNumber(p.total_vehicles_destroyed || 0))}
            ${statRow('Banderas capturadas', formatNumber(p.total_flags_captured || 0))}
            ${statRow('Kit favorito', escapeHtml(favKit))}
            ${statRow('Arma favorita', escapeHtml(favWeapon))}
        </div>`;
}

function tabCombate(p) {
    const lives = p.lives || 0, aliveS = p.alive_seconds || 0, kills = p.total_kills || 0;
    const has = lives || p.best_killstreak || p.total_clutch_kills || p.total_first_bloods
        || p.total_teamkills || p.total_suicides_demo;
    if (!has) return emptyTab();
    const rows = [];
    if (lives) {
        rows.push(statRow('Vida promedio', fmtDuration(aliveS / lives) + ` <small>(${lives} vidas)</small>`));
        rows.push(statRow('Kills/min con vida', aliveS ? (kills / (aliveS / 60)).toFixed(2) : '—'));
    }
    rows.push(statRow('🔥 Mejor racha', `${p.best_killstreak || 0} kills sin morir`));
    if (p.total_first_bloods) rows.push(statRow('🩸 First bloods', formatNumber(p.total_first_bloods)));
    if (p.total_clutch_kills) rows.push(statRow('💥 Kills clutch', `${formatNumber(p.total_clutch_kills)} <small>(equipo a ≤25 tickets)</small>`));
    let disc = '';
    if (p.total_teamkills || p.total_suicides_demo) {
        const parts = [];
        if (p.total_teamkills) parts.push(`🔫 Teamkills: <b>${formatNumber(p.total_teamkills)}</b>`);
        if (p.total_suicides_demo) parts.push(`💀 Suicidios: <b>${formatNumber(p.total_suicides_demo)}</b>`);
        disc = `<div class="disc-row">🎖️ ${parts.join(' · ')}</div>`;
    }
    return `<div class="stat-grid">${rows.join('')}</div>${disc}`;
}

function tabArmasVehiculos(p) {
    const weapons = aggregateByLabel(p.kill_weapons, weaponModel, { exclude: _NON_INFANTRY });
    const vehKills = aggregateByLabel(p.kill_weapons, weaponVehicle, { exclude: c => !isVehicleKill(c) });
    const seats = aggregateByLabel(p.seat_kills, seatLabel);
    // Destruidos por tipo: agrupar por nombre PERO conservando un code representativo
    // (el más frecuente) para mostrar el icono oficial del vehículo.
    const destAgg = new Map();
    for (const [code, n] of Object.entries(p.vehicles_destroyed_by_type || {})) {
        const label = vehicleLabel(code);
        const e = destAgg.get(label) || { n: 0, code, best: 0 };
        e.n += n;
        if (n > e.best) { e.best = n; e.code = code; }
        destAgg.set(label, e);
    }
    const destList = [...destAgg.entries()].sort((a, b) => b[1].n - a[1].n).slice(0, 8);
    const destHtml = destList.length
        ? destList.map(([label, e]) =>
            `<li>${vehicleIconHTML(e.code)}${escapeHtml(label)} <span class="stat-value">${formatNumber(e.n)}</span></li>`).join('')
        : `<li class="empty-state">${escapeHtml(ACCUM)}</li>`;
    return `
        <h4>🔫 Armas más letales</h4>
        <ul class="demo-kits-list">${topList(weapons, 8, 'Sin datos de armas.')}</ul>
        <h4>🚁 Kills con vehículos</h4>
        ${vehKills.length ? bars(vehKills.slice(0, 8), { icon: vehicleIconByName }) : emptyTab(ACCUM)}
        <h4>🔥 Vehículos destruidos (por tipo)</h4>
        <ul class="demo-kits-list">${destHtml}</ul>
        <h4>🪖 Kills por asiento</h4>
        <ul class="demo-kits-list">${topList(seats, 6, ACCUM)}</ul>`;
}

const CAT_META = [
    ['infantry', '🔫', 'A pie'], ['ground', '🚛', 'Terrestres'], ['air', '✈️', 'Aéreos'],
    ['naval', '🚤', 'Navales'], ['emplacement', '🎯', 'Emplazamientos'], ['env', '💥', 'Entorno'],
];
function tabAssets(p) {
    const cats = {};
    for (const [code, n] of Object.entries(p.kill_weapons || {})) {
        const c = assetCategory(code);
        cats[c] = (cats[c] || 0) + n;
    }
    const grand = Object.values(cats).reduce((a, b) => a + b, 0);
    if (!grand) return emptyTab('Sin datos de armas.');
    const items = CAT_META
        .filter(([k]) => cats[k])
        .map(([k, e, l]) => [`${e} ${l}`, +(cats[k] / grand * 100).toFixed(1)]);
    return `<p class="section-subtitle">Cómo consigue sus <b>${formatNumber(grand)}</b> kills, por tipo de medio.</p>
        ${bars(items, { suffix: '%', max: 100 })}`;
}

function tabKitsModos(p) {
    const kits = aggregateByLabel(p.kits_used, kitLabel);
    // K/D por kit (kit_performance), filtro ≥10 kills
    const perf = Object.entries(p.kit_performance || {})
        .filter(([, d]) => (d.kills || 0) >= 10)
        .map(([role, d]) => [role, (d.kills || 0) / Math.max(d.deaths || 0, 1), d.kills || 0, d.deaths || 0])
        .sort((a, b) => b[1] - a[1]);
    const gm = Object.entries(p.gamemode_stats || {})
        .sort((a, b) => (b[1].rounds || 0) - (a[1].rounds || 0));
    return `
        <h4>🎖️ Kits más usados</h4>
        <ul class="demo-kits-list">${topList(kits, 8, 'Sin datos de kits.')}</ul>
        <h4>⚔️ Desempeño por kit (K/D)</h4>
        ${perf.length ? `<ul class="demo-kits-list">${perf.slice(0, 8).map(([r, kd, k, d]) =>
            `<li>${escapeHtml(r)} <span class="stat-value">K/D ${kd.toFixed(2)} <small>(${k}/${d})</small></span></li>`).join('')}</ul>`
            : emptyTab(ACCUM)}
        <h4>🎮 Por gamemode</h4>
        ${gm.length ? `<table class="data-table"><thead><tr><th>Modo</th><th>WR</th><th>K/D</th><th>KPR</th><th>R</th></tr></thead>
            <tbody>${gm.map(([g, s]) => {
                const wr = s.winrate != null ? s.winrate : (s.rounds ? (s.wins || 0) / s.rounds * 100 : 0);
                return `<tr><td>${escapeHtml(gamemodeLabel(g))}</td><td>${wr.toFixed(0)}%</td>
                    <td>${(s.kd || 0).toFixed(2)}</td><td>${(s.avg_kpr || 0).toFixed(2)}</td><td>${formatNumber(s.rounds || 0)}</td></tr>`;
            }).join('')}</tbody></table>` : emptyTab(ACCUM)}`;
}

async function tabSinergia(p) {
    await loadSynergy();
    const syn = state.synergy;
    let entry = syn ? syn[p.ign] : null;
    if (!entry && syn) {
        const m = findPlayer(Object.keys(syn).map(k => ({ Player: k })), p.ign);
        if (m) entry = syn[m.Player];
    }

    // Cohesión + % escuadra (de player_details, siempre disponibles si hay data nueva)
    const extra = [];
    if (p.rounds_with_squad_data) {
        const pct = (p.rounds_in_squad || 0) / p.rounds_with_squad_data * 100;
        extra.push(statRow('👥 En escuadra', `${pct.toFixed(0)}% de las rondas <small>(${p.rounds_with_squad_data} con dato)</small>`));
    }
    if ((p.cohesion_samples || 0) >= 20) {
        const coh = p.cohesion_sum / p.cohesion_samples;
        const lbl = coh < 150 ? 'muy unida' : coh < 300 ? 'unida' : coh < 600 ? 'dispersa' : 'muy dispersa';
        extra.push(statRow('🧭 Cohesión de escuadra', `${escapeHtml(lbl)} <small>(${coh.toFixed(0)}m al centro)</small>`));
    }
    const extraHtml = extra.length ? `<div class="stat-grid">${extra.join('')}</div>` : '';

    if (!entry || !entry.mates) {
        return extraHtml + emptyTab('Aún no hay compañeros con suficientes rondas en escuadra.');
    }
    const base = entry.baseline || {}; const baseR = base.rounds || 0; const baseK = base.kills || 0;
    const baseKpr = baseR ? baseK / baseR : 0;
    const rows = [];
    for (const [q, v] of Object.entries(entry.mates)) {
        const r = v.rounds || 0;
        if (r < 3) continue;
        const kprWith = (v.kills || 0) / r;
        const woR = baseR - r;
        const kprWo = woR > 0 ? (baseK - (v.kills || 0)) / woR : baseKpr;
        rows.push({ impact: kprWith - kprWo, q, r, kprWith, kprWo, wr: (v.wins || 0) / r * 100 });
    }
    if (!rows.length) return extraHtml + emptyTab('Aún no hay compañeros con ≥3 rondas compartidas.');
    rows.sort((a, b) => b.impact - a.impact);
    const best = rows.slice(0, 5);
    const worst = rows.filter(r => r.impact < 0).slice(-3).reverse();
    const line = (r) => `<li>${r.impact >= 0 ? '📈' : '📉'} <b>${escapeHtml(r.q)}</b>
        <span class="stat-value">KPR ${r.kprWith.toFixed(2)} <small>(solo ${r.kprWo.toFixed(2)}, ${r.impact >= 0 ? '+' : ''}${r.impact.toFixed(2)})</small>
        · WR ${r.wr.toFixed(0)}% · ${r.r}R</span></li>`;
    return `${extraHtml}
        <p class="section-subtitle">KPR base en escuadra: <b>${baseKpr.toFixed(2)}</b> · ${baseR} rondas con dato.</p>
        <h4>🟢 Mejores compañeros</h4>
        <ul class="demo-kits-list">${best.map(line).join('')}</ul>
        ${worst.length ? `<h4>🔴 Rendís menos con</h4><ul class="demo-kits-list">${worst.map(line).join('')}</ul>` : ''}`;
}

async function tabRondas(p) {
    const data = await loadPlayerRounds(p.ign);
    const rounds = Array.isArray(data?.rounds) ? [...data.rounds].reverse().slice(0, 20) : [];
    if (!rounds.length) return emptyTab('Sin historial de rondas.');
    const rows = rounds.map((r) => {
        const result = r.won ? '<span class="round-win">Victoria</span>' : '<span class="round-loss">Derrota</span>';
        return `<tr><td>${escapeHtml(r.date)}</td><td>${escapeHtml(mapLabel(r.map))}</td>
            <td>${escapeHtml(gamemodeLabel(r.gamemode))}</td><td>${formatNumber(r.kills || 0)}</td>
            <td>${formatNumber(r.deaths || 0)}</td><td>${formatNumber(r.score || 0)}</td><td>${result}</td></tr>`;
    }).join('');
    return `<table class="data-table">
        <thead><tr><th>Fecha</th><th>Mapa</th><th>Modo</th><th>K</th><th>D</th><th>Score</th><th>Resultado</th></tr></thead>
        <tbody>${rows}</tbody></table>`;
}

// ── Profile shell (tabs) ─────────────────────────────────────────────────────

const TABS = [
    ['resumen', 'Resumen', tabResumen, false],
    ['combate', '⚔️ Combate', tabCombate, false],
    ['armas', '🔫 Armas & Vehículos', tabArmasVehiculos, false],
    ['assets', '🧩 Assets', tabAssets, false],
    ['kits', '🎖️ Kits & Modos', tabKitsModos, false],
    ['sinergia', '🤝 Sinergia', tabSinergia, true],   // lazy/async
    ['rondas', '🗺️ Rondas', tabRondas, true],          // lazy/async
];

async function renderDemoPlayer(name) {
    const results = document.getElementById('demo-player-results');
    if (!results) return;

    const p = getDemoInfo(name);
    if (!p) {
        results.innerHTML = `<div class="empty-state">No se encontraron datos de demos para "${escapeHtml(name)}".</div>`;
        return;
    }

    const tabBtns = TABS.map(([id, label], i) =>
        `<button class="tab${i === 0 ? ' active' : ''}" role="tab" data-tab="${id}" aria-selected="${i === 0}">${escapeHtml(label)}</button>`).join('');
    const panels = TABS.map(([id, , , lazy], i) =>
        `<div class="tab-panel${i === 0 ? ' active' : ''}" role="tabpanel" data-panel="${id}">${lazy ? '<div class="empty-state">Cargando…</div>' : ''}</div>`).join('');

    results.innerHTML = `
        <div class="card demo-player-card">
            <h3>${escapeHtml(p.ign)}</h3>
            <div class="tabs" role="tablist">${tabBtns}</div>
            <div class="tab-panels">${panels}</div>
        </div>`;

    const rendered = new Set();
    const renderInto = async (id) => {
        if (rendered.has(id)) return;
        const def = TABS.find(t => t[0] === id);
        const panel = results.querySelector(`[data-panel="${id}"]`);
        if (!def || !panel) return;
        rendered.add(id);
        try {
            panel.innerHTML = def[3] ? await def[2](p) : def[2](p);
        } catch (e) {
            console.error('[demos tab]', id, e);
            panel.innerHTML = emptyTab('No se pudo cargar esta pestaña.');
        }
    };
    // Render the synchronous tabs upfront so switching is instant.
    for (const [id, , , lazy] of TABS) if (!lazy) await renderInto(id);

    const tablist = results.querySelector('.tabs');
    tablist.addEventListener('click', (e) => {
        const btn = e.target.closest('.tab');
        if (!btn) return;
        const id = btn.dataset.tab;
        tablist.querySelectorAll('.tab').forEach(b => {
            const on = b === btn;
            b.classList.toggle('active', on);
            b.setAttribute('aria-selected', on);
        });
        results.querySelectorAll('.tab-panel').forEach(pn =>
            pn.classList.toggle('active', pn.dataset.panel === id));
        renderInto(id);  // lazy tabs render on first open
    });
}

// ── Map demo tool ────────────────────────────────────────────────────────────

function renderDemoMap(name) {
    const results = document.getElementById('demo-map-results');
    if (!results) return;

    const list = state.demoMapStats;
    if (!Array.isArray(list)) {
        results.innerHTML = '<div class="error-state">No se pudieron cargar las estadísticas de mapas.</div>';
        return;
    }
    const lower = name.toLowerCase();
    const matches = list.filter(m => m.map_name && m.map_name.toLowerCase() === lower);
    if (!matches.length) {
        results.innerHTML = `<div class="empty-state">No se encontraron datos para el mapa "${escapeHtml(name)}".</div>`;
        return;
    }

    const boxes = matches.map((m) => {
        const rounds = m.rounds_played || 0;
        const bluforWR = rounds > 0 ? (m.blufor_wins || 0) / rounds * 100 : 0;
        const opforWR = rounds > 0 ? (m.opfor_wins || 0) / rounds * 100 : 0;
        const dur = m.avg_duration_seconds || 0;
        const avgKills = rounds > 0 ? (m.total_kills || 0) / rounds : 0;
        const durRow = dur ? `
            ${statRow('Duración promedio', fmtDuration(dur))}
            ${statRow('Kills/min', (avgKills / (dur / 60)).toFixed(1))}` : '';
        return `
            <div class="card demo-map-card">
                <h4>${escapeHtml(mapLabel(m.map_name))} · ${escapeHtml(gamemodeLabel(m.gamemode))}</h4>
                ${statRow('Rondas jugadas', formatNumber(rounds))}
                ${statRow('Winrate BLUFOR', bluforWR.toFixed(1) + '%')}
                ${statRow('Winrate OPFOR', opforWR.toFixed(1) + '%')}
                ${statRow('Kills totales', formatNumber(m.total_kills || 0))}
                ${durRow}
                ${statRow('Tickets BLUFOR (prom.)', formatNumber(Number((m.avg_tickets1_final || 0).toFixed(2))))}
                ${statRow('Tickets OPFOR (prom.)', formatNumber(Number((m.avg_tickets2_final || 0).toFixed(2))))}
            </div>`;
    }).join('');

    results.innerHTML = `<div class="demo-map-cards">${boxes}</div>`;
}

// ── Init ─────────────────────────────────────────────────────────────────────

export async function initDemoStats() {
    await loadDemoData();

    const playerInput = document.getElementById('demo-player-name');
    const playerSug = document.getElementById('demo-suggestions');
    if (playerInput && playerSug) {
        const source = (query) => {
            const q = query.toLowerCase();
            return (state.demoPlayerDetails || [])
                .filter(p => p.ign && p.ign.toLowerCase().includes(q))
                .slice(0, 8)
                .map(p => ({ label: p.ign, value: p.ign }));
        };
        setupAutocomplete(playerInput, playerSug, source, (value) => {
            playerInput.value = value;
            renderDemoPlayer(value);
        });
    }
    const playerForm = document.getElementById('demo-player-form');
    if (playerForm) {
        playerForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const name = playerInput?.value.trim();
            if (name) renderDemoPlayer(name);
        });
    }

    const mapInput = document.getElementById('demo-map-name');
    const mapSug = document.getElementById('demo-map-suggestions');
    if (mapInput && mapSug) {
        const source = (query) => {
            const q = query.toLowerCase();
            const seen = new Set(); const out = [];
            for (const m of (state.demoMapStats || [])) {
                if (!m.map_name) continue;
                const key = m.map_name.toLowerCase();
                if (seen.has(key) || !key.includes(q)) continue;
                seen.add(key);
                out.push({ label: mapLabel(m.map_name), value: m.map_name });
                if (out.length >= 8) break;
            }
            return out;
        };
        setupAutocomplete(mapInput, mapSug, source, (value) => {
            mapInput.value = value;
            renderDemoMap(value);
        });
    }
    const mapForm = document.getElementById('demo-map-form');
    if (mapForm) {
        mapForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const name = mapInput?.value.trim();
            if (name) renderDemoMap(name);
        });
    }
}
