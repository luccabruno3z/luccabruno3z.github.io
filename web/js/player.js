/* ═══════════════════════════════════════════════════════════════════════════
   player.js — player search: full profile card, radar, history, demo enrichment.
   See .rebuild/CONTRACT.md §2.3 / §4 and FEATURE_API.md (player notes).
   ═══════════════════════════════════════════════════════════════════════════ */

import {
    state, loadDemoData, getDemoInfo, loadPlayerHistory,
} from './data.js';
import {
    escapeHtml, formatNumber, findPlayer, tierBadge, getPlayerArchetype,
    experienceBadge, sampleReliability, percentile, scoreBreakdown,
    activityIndex, activityTier, sigmoidPenalty, clanLogoHTML,
} from './utils.js';
import { renderRadarChart, renderHistoryChart, clearPlayerCharts } from './charts.js';
import { setupAutocomplete, playerSource } from './autocomplete.js';

/** A labelled stat row, optionally with a percentile note. */
function statRow(label, value, percentileNote) {
    const note = percentileNote ? ` <span class="stat-percentile">(${escapeHtml(percentileNote)})</span>` : '';
    return `<div class="stat-row"><span class="stat-label">${escapeHtml(label)}</span>` +
        `<span class="stat-value">${value}${note}</span></div>`;
}

/** Build and render the full profile card for a player. */
async function renderPlayerProfile(player) {
    const host = document.getElementById('player-profile-card');
    if (!host) return;

    const players = state.playersData || [];
    const rank = players.indexOf(player) + 1;
    const rounds = player['Rounds'] || 0;
    const kd = player['K/D Ratio'] || 0;
    const kpr = player['Kills per Round'] || 0;
    const spr = player['Score per Round'] || 0;
    const ps = player['Performance Score'] || 0;

    const tier = tierBadge(ps);
    const arch = getPlayerArchetype(player);
    const exp = experienceBadge(rounds);
    const rel = sampleReliability(rounds);

    // Percentiles over the population.
    const pctPS = percentile(ps, players.map(p => p['Performance Score'] || 0));
    const pctKD = percentile(kd, players.map(p => p['K/D Ratio'] || 0));
    const pctKPR = percentile(kpr, players.map(p => p['Kills per Round'] || 0));
    const pctKills = percentile(player['Total Kills'] || 0, players.map(p => p['Total Kills'] || 0));

    // Activity.
    const actIdx = activityIndex(rounds, spr, kpr);
    const actTier = activityTier(actIdx);

    // Sigmoid confidence penalty.
    const penalty = sigmoidPenalty(rounds);
    let penaltyWarning = '';
    if (penalty * 100 < 95) {
        const needed = Math.ceil(25 + 10 * Math.log(19)); // ~54
        const remaining = Math.max(0, needed - rounds);
        penaltyWarning = `<div class="profile-warning">⚠️ Confianza del puntaje: ${(penalty * 100).toFixed(0)}%.` +
            ` Faltan ~${remaining} rondas para alcanzar el 95%.</div>`;
    }

    let lowRoundsWarning = '';
    if (rounds < 50) {
        lowRoundsWarning = `<div class="profile-warning">⚠️ Menos de 50 rondas: el jugador no califica para los rankings.</div>`;
    }

    const clanLine = player.Clan
        ? `<span class="profile-clan">${clanLogoHTML(player.Clan, 24)} ${escapeHtml(player.Clan)}</span>`
        : '';

    host.innerHTML = `
        <div class="card profile-card">
            <div class="profile-head">
                <div class="profile-name">${escapeHtml(player.Player)}</div>
                <div class="profile-rank">#${rank} global</div>
                <div class="profile-meta">${clanLine}</div>
                <div class="profile-badges">
                    <span class="badge tier-badge ${tier.cssClass}">${tier.emoji} ${escapeHtml(tier.name)}</span>
                    <span class="badge profile-archetype">${arch.emoji} ${escapeHtml(arch.name)}</span>
                    <span class="badge profile-experience">${exp.emoji} ${escapeHtml(exp.name)}</span>
                    <span class="badge ${rel.cssClass}">${rel.emoji} ${escapeHtml(rel.text)}</span>
                </div>
                ${arch.desc ? `<p class="profile-archetype-desc">${escapeHtml(arch.desc)}</p>` : ''}
            </div>

            ${penaltyWarning}${lowRoundsWarning}

            <div class="profile-stats">
                ${statRow('Performance Score', formatNumber(ps), pctPS)}
                ${statRow('K/D Ratio', formatNumber(kd), pctKD)}
                ${statRow('Kills por Ronda', formatNumber(kpr), pctKPR)}
                ${statRow('Score por Ronda', formatNumber(spr))}
                ${statRow('Total Kills', formatNumber(player['Total Kills'] || 0), pctKills)}
                ${statRow('Total Deaths', formatNumber(player['Total Deaths'] || 0))}
                ${statRow('Rondas', formatNumber(rounds))}
            </div>

            <div class="profile-breakdown">
                <h4 class="profile-subtitle">Desglose del puntaje</h4>
                ${scoreBreakdown(player)}
            </div>

            <div class="profile-activity">
                <h4 class="profile-subtitle">Actividad</h4>
                <div class="activity-row">
                    <span class="activity-tier">${actTier.emoji} ${escapeHtml(actTier.name)}</span>
                    <div class="progress-track">
                        <div class="progress-fill" style="width:${actIdx}%; background:#00FFFF;"></div>
                    </div>
                    <span class="activity-value">${actIdx}/100</span>
                </div>
            </div>

            <div id="profile-demo-block" class="profile-demo"></div>
        </div>`;

    // Radar vs clan average.
    renderRadarChart(player, player.Clan);

    // Demo enrichment (loose-wired in current data; keyed by ign). Best-effort.
    enrichWithDemo(player);

    // History line chart (best-effort; hidden if absent).
    const history = await loadPlayerHistory(player.Player);
    if (Array.isArray(history) && history.length) {
        renderHistoryChart(history, document.getElementById('historyChart'));
    } else {
        const hc = document.getElementById('historyChart');
        if (hc) hc.style.display = 'none';
    }
}

/** Best-effort demo-stats enrichment block (keyed by ign). */
async function enrichWithDemo(player) {
    const block = document.getElementById('profile-demo-block');
    if (!block) return;
    try {
        await loadDemoData();
    } catch (_) { /* non-fatal */ }
    const demo = getDemoInfo(player.Player);
    if (!demo) return; // silently skip when no demo record (defensive)

    const wins = demo.wins;
    const losses = demo.losses;
    let winrate = '';
    if (typeof wins === 'number' && typeof losses === 'number' && (wins + losses) > 0) {
        winrate = `${((wins / (wins + losses)) * 100).toFixed(1)}%`;
    }

    block.innerHTML = `
        <h4 class="profile-subtitle">Datos de demos</h4>
        <div class="profile-stats">
            ${typeof demo.rounds_played === 'number' ? statRow('Rondas (demos)', formatNumber(demo.rounds_played)) : ''}
            ${typeof demo.total_kills === 'number' ? statRow('Kills (demos)', formatNumber(demo.total_kills)) : ''}
            ${typeof demo.total_deaths === 'number' ? statRow('Deaths (demos)', formatNumber(demo.total_deaths)) : ''}
            ${winrate ? statRow('Winrate', winrate) : ''}
            ${typeof demo.total_revives_given === 'number' ? statRow('Revives', formatNumber(demo.total_revives_given)) : ''}
            ${typeof demo.total_vehicles_destroyed === 'number' ? statRow('Vehículos destruidos', formatNumber(demo.total_vehicles_destroyed)) : ''}
        </div>`;
}

/** Player search init: form submit + autocomplete. */
export function initPlayerSearch() {
    const form = document.getElementById('search-form');
    const input = document.getElementById('player-name');
    const suggestions = document.getElementById('suggestions');

    if (input && suggestions) {
        setupAutocomplete(input, suggestions, playerSource(() => state.playersData || []), (value) => {
            input.value = value;
            const player = findPlayer(state.playersData, value);
            if (player) renderPlayerProfile(player);
        });
    }

    if (form && input) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const name = input.value.trim();
            if (!name) return;
            const player = findPlayer(state.playersData, name);
            const host = document.getElementById('player-profile-card');
            if (!player) {
                if (host) host.innerHTML = `<div class="empty-state">No se encontró ningún jugador con "${escapeHtml(name)}".</div>`;
                clearPlayerCharts();
                return;
            }
            renderPlayerProfile(player);
        });
    }
}
