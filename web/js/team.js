/* ═══════════════════════════════════════════════════════════════════════════
   team.js — aggregate team stats + per-player cards + team radar (2..8 players).
   See .rebuild/CONTRACT.md §2.8 and FEATURE_API.md (team notes).
   ═══════════════════════════════════════════════════════════════════════════ */

import { state } from './data.js';
import { setupAutocomplete, playerSource } from './autocomplete.js';
import { renderTeamRadar } from './charts.js';
import {
    escapeHtml, findPlayer, clanLogoHTML, tierBadge, getPlayerArchetype, formatNumber,
} from './utils.js';

/** Collect resolved, deduped players from the 8 inputs. */
function collectTeam() {
    const players = state.playersData || [];
    const team = [];
    const seen = new Set();
    for (let i = 1; i <= 8; i++) {
        const name = document.getElementById(`player${i}`)?.value.trim();
        if (!name) continue;
        const p = findPlayer(players, name);
        if (p && !seen.has(p.Player)) {
            seen.add(p.Player);
            team.push(p);
        }
    }
    return team;
}

/** One per-player card. */
function playerCard(p) {
    const tier = tierBadge(p['Performance Score'] || 0);
    const arch = getPlayerArchetype(p);
    const clan = p.Clan ? `${clanLogoHTML(p.Clan, 18)} <span class="card-clan">${escapeHtml(p.Clan)}</span>` : '';
    return `
        <div class="card team-player-card">
            <div class="team-player-name">${escapeHtml(p.Player)} ${clan}</div>
            <div class="badge tier-badge ${tier.cssClass}">${tier.emoji} ${escapeHtml(tier.name)}</div>
            <div class="badge team-player-archetype">${arch.emoji} ${escapeHtml(arch.name)}</div>
            <div class="stat-row"><span class="stat-label">PS</span><span class="stat-value">${formatNumber(p['Performance Score'] || 0)}</span></div>
            <div class="stat-row"><span class="stat-label">K/D</span><span class="stat-value">${formatNumber(p['K/D Ratio'] || 0)}</span></div>
            <div class="stat-row"><span class="stat-label">KPR</span><span class="stat-value">${formatNumber(p['Kills per Round'] || 0)}</span></div>
            <div class="stat-row"><span class="stat-label">Rondas</span><span class="stat-value">${formatNumber(p['Rounds'] || 0)}</span></div>
        </div>`;
}

function performTeamAnalysis() {
    const results = document.getElementById('team-results');
    if (!results) return;

    const team = collectTeam();
    if (team.length < 2) {
        results.innerHTML = '<div class="empty-state">Ingresá al menos 2 jugadores para analizar el equipo.</div>';
        return;
    }

    const totalKills = team.reduce((s, p) => s + (p['Total Kills'] || 0), 0);
    const totalDeaths = team.reduce((s, p) => s + (p['Total Deaths'] || 0), 0);
    const teamKD = totalDeaths === 0 ? totalKills : totalKills / totalDeaths;
    const avg = key => team.reduce((s, p) => s + (p[key] || 0), 0) / team.length;
    const avgPS = avg('Performance Score');
    const avgKPR = avg('Kills per Round');
    const avgDPR = avg('Deaths per Round');

    const cards = team.map(playerCard).join('');

    results.innerHTML = `
        <div class="card team-aggregates">
            <h3>Resumen del equipo (${team.length} jugadores)</h3>
            <div class="stat-row"><span class="stat-label">K/D del equipo</span><span class="stat-value">${formatNumber(Number(teamKD.toFixed(2)))}</span></div>
            <div class="stat-row"><span class="stat-label">PS promedio</span><span class="stat-value">${formatNumber(avgPS)}</span></div>
            <div class="stat-row"><span class="stat-label">KPR promedio</span><span class="stat-value">${formatNumber(avgKPR)}</span></div>
            <div class="stat-row"><span class="stat-label">DPR promedio</span><span class="stat-value">${formatNumber(avgDPR)}</span></div>
            <div class="stat-row"><span class="stat-label">Kills totales</span><span class="stat-value">${formatNumber(totalKills)}</span></div>
            <div class="stat-row"><span class="stat-label">Muertes totales</span><span class="stat-value">${formatNumber(totalDeaths)}</span></div>
        </div>
        <div class="team-player-cards">${cards}</div>
        <div class="team-radar-wrapper"></div>`;

    // Radar appended into results (renderTeamRadar creates/owns #teamRadarChart).
    const radarHost = results.querySelector('.team-radar-wrapper') || results;
    renderTeamRadar(team, radarHost);
}

/** Team analysis init: wire 8 autocompletes + submit handler. */
export function initTeamAnalysis() {
    const source = playerSource(() => state.playersData || []);
    for (let i = 1; i <= 8; i++) {
        const input = document.getElementById(`player${i}`);
        const sug = document.getElementById(`suggestions${i}`);
        if (input && sug) setupAutocomplete(input, sug, source);
    }

    const form = document.getElementById('team-analysis-form');
    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            performTeamAnalysis();
        });
    }
}
