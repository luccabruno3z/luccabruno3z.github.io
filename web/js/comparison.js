/* ═══════════════════════════════════════════════════════════════════════════
   comparison.js — player-vs-player OR clan-vs-clan head-to-head.
   See .rebuild/CONTRACT.md §2.4 and FEATURE_API.md (comparison notes).
   ═══════════════════════════════════════════════════════════════════════════ */

import { state } from './data.js';
import {
    escapeHtml, formatNumber, findPlayer, highlightWinner, advantagePct, clanLogoHTML,
} from './utils.js';
import { setupAutocomplete } from './autocomplete.js';

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

/** Player vs player: 7 metrics + win count + verdict. */
function renderPlayerComparison(p1, p2) {
    const num = formatNumber;
    const metrics = [
        ['Performance Score', p1['Performance Score'] || 0, p2['Performance Score'] || 0, true],
        ['K/D Ratio', p1['K/D Ratio'] || 0, p2['K/D Ratio'] || 0, true],
        ['Kills por Ronda', p1['Kills per Round'] || 0, p2['Kills per Round'] || 0, true],
        ['Deaths por Ronda', p1['Deaths per Round'] || 0, p2['Deaths per Round'] || 0, false],
        ['Score por Ronda', p1['Score per Round'] || 0, p2['Score per Round'] || 0, true],
        ['Total Kills', p1['Total Kills'] || 0, p2['Total Kills'] || 0, true],
        ['Rondas', p1['Rounds'] || 0, p2['Rounds'] || 0, true],
    ];

    let wins1 = 0, wins2 = 0;
    metrics.forEach(([, v1, v2, hb]) => {
        if (v1 === v2) return;
        const oneWins = hb ? v1 > v2 : v1 < v2;
        if (oneWins) wins1++; else wins2++;
    });

    const rows = metrics.map(([label, v1, v2, hb]) => {
        const { class1, class2 } = highlightWinner(v1, v2, hb);
        return `<div class="compare-row">
            <span class="compare-cell ${class1}">${num(v1)}</span>
            <span class="compare-metric">${escapeHtml(label)} <small class="compare-adv">${escapeHtml(advantagePct(v1, v2))}</small></span>
            <span class="compare-cell ${class2}">${num(v2)}</span>
        </div>`;
    }).join('');

    let verdict;
    if (wins1 > wins2) verdict = `Gana <strong>${escapeHtml(p1.Player)}</strong> (${wins1}–${wins2})`;
    else if (wins2 > wins1) verdict = `Gana <strong>${escapeHtml(p2.Player)}</strong> (${wins2}–${wins1})`;
    else verdict = `Empate (${wins1}–${wins2})`;

    return `<div class="card compare-card">
        <div class="compare-header">
            <span class="compare-entity">${p1.Clan ? clanLogoHTML(p1.Clan, 20) : ''} ${escapeHtml(p1.Player)}</span>
            <span class="compare-vs">VS</span>
            <span class="compare-entity">${p2.Clan ? clanLogoHTML(p2.Clan, 20) : ''} ${escapeHtml(p2.Player)}</span>
        </div>
        <div class="compare-table">${rows}</div>
        <div class="compare-verdict">${verdict}</div>
    </div>`;
}

/** Aggregate a clan's members into the comparison stats. */
function clanAggregate(members) {
    const n = members.length;
    const sum = key => members.reduce((s, p) => s + (p[key] || 0), 0);
    const avg = key => (n ? sum(key) / n : 0);
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

    let wins1 = 0, wins2 = 0;
    metrics.forEach(([, v1, v2, hb]) => {
        if (v1 === v2) return;
        const oneWins = hb ? v1 > v2 : v1 < v2;
        if (oneWins) wins1++; else wins2++;
    });

    const rows = metrics.map(([label, v1, v2, hb]) => metricRow(label, v1, v2, num, hb)).join('');

    let verdict;
    if (wins1 > wins2) verdict = `Gana <strong>${escapeHtml(name1)}</strong> (${wins1}–${wins2})`;
    else if (wins2 > wins1) verdict = `Gana <strong>${escapeHtml(name2)}</strong> (${wins2}–${wins1})`;
    else verdict = `Empate (${wins1}–${wins2})`;

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
    const p1 = findPlayer(players, input1);
    const p2 = findPlayer(players, input2);

    if (p1 && p2) {
        host.innerHTML = renderPlayerComparison(p1, p2);
        return;
    }

    // Try clan-vs-clan.
    const [name1, members1] = clanMembers(input1);
    const [name2, members2] = clanMembers(input2);
    if (members1.length && members2.length) {
        host.innerHTML = renderClanComparison(name1, members1, name2, members2);
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

    if (form && input1 && input2) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const v1 = input1.value.trim();
            const v2 = input2.value.trim();
            if (!v1 || !v2) return;
            performComparison(v1, v2);
        });
    }
}
