/* ═══════════════════════════════════════════════════════════════════════════
   predictor.js — 8v8 win-probability predictor from a composite team score.
   See .rebuild/CONTRACT.md §2.7 / §4 and FEATURE_API.md (predictor notes).
   ═══════════════════════════════════════════════════════════════════════════ */

import { state } from './data.js';
import { NORM_CAPS } from './config.js';
import { setupAutocomplete, playerSource } from './autocomplete.js';
import { escapeHtml, findPlayer, clanLogoHTML, formatNumber, teamAverage } from './utils.js';

const FALLBACK_WEIGHTS = { ps: 0.50, kd: 0.30, kpr: 0.20 };

/** Read predictor_weights, drop winrate, renormalize {ps,kd,kpr} to sum 1. */
function predictorWeights() {
    const w = state.tierConfigData?.predictor_weights;
    if (!w) return { ...FALLBACK_WEIGHTS };
    const ps = w.ps || 0;
    const kd = w.kd || 0;
    const kpr = w.kpr || 0;
    const sum = ps + kd + kpr;
    if (sum <= 0) return { ...FALLBACK_WEIGHTS };
    return { ps: ps / sum, kd: kd / sum, kpr: kpr / sum };
}

/** Collect resolved players for one team (A|B), up to 8 inputs. */
function collectTeam(side) {
    const players = state.playersData || [];
    const team = [];
    for (let i = 1; i <= 8; i++) {
        const input = document.getElementById(`team${side}-p${i}`);
        const name = input?.value.trim();
        if (!name) continue;
        const p = findPlayer(players, name);
        if (p) team.push(p);
    }
    return team;
}

/** Composite score for a team using the renormalized weights. */
function teamComposite(team, w) {
    if (!team.length) return 0;
    const avgPS = teamAverage(team, 'Performance Score');
    const avgKD = teamAverage(team, 'K/D Ratio');
    const avgKPR = teamAverage(team, 'Kills per Round');
    return w.ps * avgPS + w.kd * (avgKD / NORM_CAPS.kd) + w.kpr * (avgKPR / NORM_CAPS.kpr);
}

/** Small roster summary for one team's result column. */
function teamSummary(side, team) {
    if (!team.length) return `<div class="empty-state">Equipo ${side} vacío.</div>`;
    const members = team.map((p) => {
        const clan = p.Clan ? clanLogoHTML(p.Clan, 16) : '';
        return `<li>${clan} ${escapeHtml(p.Player)}</li>`;
    }).join('');
    return `
        <div class="predictor-team-summary">
            <h4>Equipo ${side}</h4>
            <ul class="predictor-roster">${members}</ul>
            <div class="stat-row"><span class="stat-label">PS promedio</span><span class="stat-value">${formatNumber(teamAverage(team, 'Performance Score'))}</span></div>
            <div class="stat-row"><span class="stat-label">K/D promedio</span><span class="stat-value">${formatNumber(teamAverage(team, 'K/D Ratio'))}</span></div>
            <div class="stat-row"><span class="stat-label">KPR promedio</span><span class="stat-value">${formatNumber(teamAverage(team, 'Kills per Round'))}</span></div>
        </div>`;
}

function performPrediction() {
    const results = document.getElementById('prediction-results');
    if (!results) return;

    const teamA = collectTeam('A');
    const teamB = collectTeam('B');

    if (!teamA.length || !teamB.length) {
        results.innerHTML = '<div class="empty-state">Ingresá al menos un jugador en cada equipo.</div>';
        return;
    }

    const w = predictorWeights();
    const compA = teamComposite(teamA, w);
    const compB = teamComposite(teamB, w);
    const total = compA + compB;
    const probA = total > 0 ? compA / total : 0.5;
    const probB = total > 0 ? compB / total : 0.5;
    const pctA = Math.round(probA * 100);
    const pctB = 100 - pctA;

    results.innerHTML = `
        <div class="prediction-bars">
            <div class="prediction-bar-row">
                <span class="prediction-team-label">Equipo A</span>
                <div class="progress-track">
                    <div class="progress-fill prediction-fill-a" data-target="${(probA * 100).toFixed(1)}" style="width:0%;"></div>
                </div>
                <span class="prediction-pct">${pctA}%</span>
            </div>
            <div class="prediction-bar-row">
                <span class="prediction-team-label">Equipo B</span>
                <div class="progress-track">
                    <div class="progress-fill prediction-fill-b" data-target="${(probB * 100).toFixed(1)}" style="width:0%;"></div>
                </div>
                <span class="prediction-pct">${pctB}%</span>
            </div>
        </div>
        <div class="prediction-teams-summary">
            ${teamSummary('A', teamA)}
            ${teamSummary('B', teamB)}
        </div>`;

    // Animate the bars via a double requestAnimationFrame so the transition runs.
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            results.querySelectorAll('.progress-fill[data-target]').forEach((el) => {
                el.style.width = `${el.dataset.target}%`;
            });
        });
    });
}

/** Predictor init: wire autocomplete on all 16 inputs + submit handler. */
export function initPredictor() {
    const source = playerSource(() => state.playersData || []);
    ['A', 'B'].forEach((side) => {
        for (let i = 1; i <= 8; i++) {
            const input = document.getElementById(`team${side}-p${i}`);
            const sug = document.getElementById(`suggestions-team${side}-p${i}`);
            if (input && sug) setupAutocomplete(input, sug, source);
        }
    });

    const form = document.getElementById('prediction-form');
    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            performPrediction();
        });
    }
}
