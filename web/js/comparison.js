/* ═══════════════════════════════════════════════════════════════════════════
   comparison.js — player-vs-player OR clan-vs-clan head-to-head.
   See .rebuild/CONTRACT.md §2.4 and FEATURE_API.md (comparison notes).
   ═══════════════════════════════════════════════════════════════════════════ */

import { state, getDemoInfo, loadDemoData } from './data.js';
import {
    escapeHtml, formatNumber, findPlayer, highlightWinner, advantagePct, clanLogoHTML, teamAverage,
} from './utils.js';
import { setupAutocomplete } from './autocomplete.js';

/** Tally per-metric wins and build the verdict line, shared by both comparisons.
 *  `metrics` rows are [label, v1, v2, higherBetter]. */
function comparisonVerdict(metrics, name1, name2) {
    let wins1 = 0, wins2 = 0;
    metrics.forEach(([, v1, v2, hb]) => {
        if (v1 === v2) return;
        if (hb ? v1 > v2 : v1 < v2) wins1++; else wins2++;
    });
    if (wins1 > wins2) return `Gana <strong>${escapeHtml(name1)}</strong> (${wins1}–${wins2})`;
    if (wins2 > wins1) return `Gana <strong>${escapeHtml(name2)}</strong> (${wins2}–${wins1})`;
    return `Empate (${wins1}–${wins2})`;
}

/** Autocomplete source: players (with clan meta) + clan names. */
function entitySource(query) {
    const q = query.toLowerCase();
    const players = (state.playersData || [])
        .filter(p => p.Player && p.Player.toLowerCase().includes(q))
        .slice(0, 6)
        .map(p => ({ label: p.Player, value: p.Player, meta: p.Clan || '' }));
    const clans = [...new Set((state.playersData || []).map(p => p.Clan).filter(Boolean))]
        .filter(c => c.toLowerCase().includes(q))
        .slice(0, 4)
        .map(c => ({ label: c, value: c, meta: 'Clan' }));
    return [...players, ...clans].slice(0, 8);
}

/** One comparison metric row. */
function metricRow(label, v1, v2, fmt, higherBetter = true) {
    const { class1, class2 } = highlightWinner(v1, v2, higherBetter);
    return `<div class="compare-row">
        <span class="compare-cell ${class1}">${fmt(v1)}</span>
        <span class="compare-metric">${escapeHtml(label)}</span>
        <span class="compare-cell ${class2}">${fmt(v2)}</span>
    </div>`;
}

/** Player vs player: 9 metrics (mismas que el bot) + win count + verdict. */
function renderPlayerComparison(p1, p2) {
    const num = formatNumber;
    // Las mismas 9 categorías que el bot (-comparar), para que el marcador coincida.
    const metrics = [
        ['Performance Score', p1['Performance Score'] || 0, p2['Performance Score'] || 0, true],
        ['K/D Ratio', p1['K/D Ratio'] || 0, p2['K/D Ratio'] || 0, true],
        ['Kills por Ronda', p1['Kills per Round'] || 0, p2['Kills per Round'] || 0, true],
        ['Deaths por Ronda', p1['Deaths per Round'] || 0, p2['Deaths per Round'] || 0, false],
        ['Score por Ronda', p1['Score per Round'] || 0, p2['Score per Round'] || 0, true],
        ['Índice de Actividad', p1['Activity Index'] || 0, p2['Activity Index'] || 0, true],
        ['Rondas', p1['Rounds'] || 0, p2['Rounds'] || 0, true],
        ['Total Kills', p1['Total Kills'] || 0, p2['Total Kills'] || 0, true],
        ['Total Score', p1['Total Score'] || 0, p2['Total Score'] || 0, true],
    ];

    const rows = metrics.map(([label, v1, v2, hb]) => {
        const { class1, class2 } = highlightWinner(v1, v2, hb);
        return `<div class="compare-row">
            <span class="compare-cell ${class1}">${num(v1)}</span>
            <span class="compare-metric">${escapeHtml(label)} <small class="compare-adv">${escapeHtml(advantagePct(v1, v2))}</small></span>
            <span class="compare-cell ${class2}">${num(v2)}</span>
        </div>`;
    }).join('');

    const verdict = comparisonVerdict(metrics, p1.Player, p2.Player);

    return `<div class="card compare-card">
        <div class="compare-header">
            <span class="compare-entity">${p1.Clan ? clanLogoHTML(p1.Clan, 20) : ''} ${escapeHtml(p1.Player)}</span>
            <span class="compare-vs">VS</span>
            <span class="compare-entity">${p2.Clan ? clanLogoHTML(p2.Clan, 20) : ''} ${escapeHtml(p2.Player)}</span>
        </div>
        <div class="compare-table">${rows}</div>
        ${demoMetricsBlock(p1, p2)}
        <div class="compare-verdict">${verdict}</div>
    </div>`;
}

/** Bloque de componentes de demo que influyen en el Performance Score pero no se ven en
 *  las stats de prstats: winrate (con nº de partidas, para que se lea la confiabilidad),
 *  teamwork y consistencia. Informativo — no cuenta en el veredicto de arriba. */
function demoMetricsBlock(p1, p2) {
    const d1 = getDemoInfo(p1.Player), d2 = getDemoInfo(p2.Player);
    if (!d1 || !d2) return '';   // ambos necesitan datos de demo
    const wr = d => {
        const g = (d.wins || 0) + (d.losses || 0);
        return g > 0 ? (d.wins / g) * 100 : null;
    };
    const games = d => (d.wins || 0) + (d.losses || 0);
    const rowsData = [
        ['Winrate', wr(d1), wr(d2), true, v => v == null ? '—' : `${v.toFixed(1)}%`,
            `${games(d1)} part.`, `${games(d2)} part.`],
        ['Teamwork', (d1.teamwork_ratio || 0) * 100, (d2.teamwork_ratio || 0) * 100, true,
            v => `${v.toFixed(0)}%`, '', ''],
        ['Consistencia', d1.consistency_score ?? null, d2.consistency_score ?? null, true,
            v => v == null ? '—' : `${Math.round(v)}`, '', ''],
    ];
    const rows = rowsData.map(([label, v1, v2, hb, fmt, sub1, sub2]) => {
        const { class1, class2 } = (v1 == null || v2 == null) ? { class1: '', class2: '' } : highlightWinner(v1, v2, hb);
        return `<div class="compare-row">
            <span class="compare-cell ${class1}">${fmt(v1)}${sub1 ? ` <small class="compare-sub">${escapeHtml(sub1)}</small>` : ''}</span>
            <span class="compare-metric">${escapeHtml(label)}</span>
            <span class="compare-cell ${class2}">${fmt(v2)}${sub2 ? ` <small class="compare-sub">${escapeHtml(sub2)}</small>` : ''}</span>
        </div>`;
    }).join('');
    return `<div class="compare-demo-section">
        <div class="compare-demo-title">📼 Datos de partidas grabadas <small>(pesan en el Performance Score; el winrate se ajusta por nº de partidas)</small></div>
        <div class="compare-table">${rows}</div>
    </div>`;
}

/** Aggregate a clan's members into the comparison stats. */
function clanAggregate(members) {
    const n = members.length;
    const sum = key => members.reduce((s, p) => s + (p[key] || 0), 0);
    const avg = key => teamAverage(members, key);
    return {
        count: n,
        avgPS: avg('Performance Score'),
        avgKD: avg('K/D Ratio'),
        avgKPR: avg('Kills per Round'),
        avgSPR: avg('Score per Round'),
        totalKills: sum('Total Kills'),
        totalDeaths: sum('Total Deaths'),
        totalRounds: sum('Rounds'),
    };
}

/** Clan vs clan: 8 aggregate metrics + verdict. */
function renderClanComparison(name1, members1, name2, members2) {
    const a = clanAggregate(members1);
    const b = clanAggregate(members2);
    const num = formatNumber;

    const metrics = [
        ['Jugadores', a.count, b.count, true],
        ['PS promedio', a.avgPS, b.avgPS, true],
        ['K/D promedio', a.avgKD, b.avgKD, true],
        ['KPR promedio', a.avgKPR, b.avgKPR, true],
        ['SPR promedio', a.avgSPR, b.avgSPR, true],
        ['Total Kills', a.totalKills, b.totalKills, true],
        ['Total Deaths', a.totalDeaths, b.totalDeaths, false],
        ['Total Rondas', a.totalRounds, b.totalRounds, true],
    ];

    const rows = metrics.map(([label, v1, v2, hb]) => metricRow(label, v1, v2, num, hb)).join('');

    const verdict = comparisonVerdict(metrics, name1, name2);

    return `<div class="card compare-card">
        <div class="compare-header">
            <span class="compare-entity">${clanLogoHTML(name1, 24)} ${escapeHtml(name1)}</span>
            <span class="compare-vs">VS</span>
            <span class="compare-entity">${clanLogoHTML(name2, 24)} ${escapeHtml(name2)}</span>
        </div>
        <div class="compare-table">${rows}</div>
        <div class="compare-verdict">${verdict}</div>
    </div>`;
}

/** Members of a clan (case-insensitive match on Clan); returns [name, members]. */
function clanMembers(name) {
    const lower = name.toLowerCase();
    const members = (state.playersData || []).filter(p => p.Clan && p.Clan.toLowerCase() === lower);
    const canonical = members.length ? members[0].Clan : name;
    return [canonical, members];
}

/** Resolve both inputs → player-vs-player, else clan-vs-clan. */
function performComparison(input1, input2) {
    const host = document.getElementById('compare-results');
    if (!host) return;

    const players = state.playersData || [];

    // Clan-vs-clan first: a clan tag (e.g. "FI") is short and would otherwise be
    // grabbed by findPlayer's substring fallback (utils.js), silently turning a
    // clan comparison into two unrelated players.
    const [name1, members1] = clanMembers(input1);
    const [name2, members2] = clanMembers(input2);
    if (members1.length && members2.length) {
        host.innerHTML = renderClanComparison(name1, members1, name2, members2);
        return;
    }

    const p1 = findPlayer(players, input1);
    const p2 = findPlayer(players, input2);
    if (p1 && p2) {
        host.innerHTML = renderPlayerComparison(p1, p2);
        return;
    }

    const missing = [];
    if (!p1 && !members1.length) missing.push(input1);
    if (!p2 && !members2.length) missing.push(input2);
    host.innerHTML = `<div class="empty-state">No se encontró: ${escapeHtml(missing.join(', '))}.</div>`;
}

/** Comparison init: form submit + autocomplete on both inputs. */
export function initComparison() {
    const form = document.getElementById('compare-form');
    const input1 = document.getElementById('entity1');
    const input2 = document.getElementById('entity2');
    const sug1 = document.getElementById('suggestions-entity1');
    const sug2 = document.getElementById('suggestions-entity2');

    if (input1 && sug1) setupAutocomplete(input1, sug1, entitySource);
    if (input2 && sug2) setupAutocomplete(input2, sug2, entitySource);

    // Precargar los datos de demo (para los componentes que pesan en el PS).
    loadDemoData().catch(() => {});

    if (form && input1 && input2) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const v1 = input1.value.trim();
            const v2 = input2.value.trim();
            if (!v1 || !v2) return;
            await loadDemoData().catch(() => {});   // asegura demo cargado antes de comparar
            performComparison(v1, v2);
        });
    }
}
