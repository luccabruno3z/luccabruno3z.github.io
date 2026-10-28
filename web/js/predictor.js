/* ═══════════════════════════════════════════════════════════════════════════
   predictor.js — predictor 8v8: probabilidad de victoria + comparación completa.
   See .rebuild/CONTRACT.md §2.7 / §4 and FEATURE_API.md (predictor notes).
   ═══════════════════════════════════════════════════════════════════════════ */

import { state, loadDemoData, loadSynergy } from './data.js';
import { buildSquad, versusHTML, rosterHTML } from './squads.js';
import { setupAutocomplete, playerSource } from './autocomplete.js';
import { findPlayer } from './utils.js';

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

async function performPrediction() {
    const results = document.getElementById('prediction-results');
    if (!results) return;

    const teamA = collectTeam('A');
    const teamB = collectTeam('B');

    if (!teamA.length || !teamB.length) {
        results.innerHTML = '<div class="empty-state">Ingresá al menos un jugador en cada equipo.</div>';
        return;
    }

    // Las mismas estadísticas que las escuadras de clan: PRStats + demos (winrate,
    // revives, teamwork, juego con la escuadra, vida, fuego amigo), roles que cubre
    // cada equipo y sinergia. La probabilidad sale del mismo cálculo de siempre (squads.js composite).
    results.innerHTML = '<div class="empty-state">Calculando…</div>';
    try { await loadDemoData(); } catch (_) { /* las demos son opcionales */ }
    const synergy = await loadSynergy().catch(() => null);
    const a = buildSquad('Equipo A', teamA, synergy, false);
    const b = buildSquad('Equipo B', teamB, synergy, false);
    results.innerHTML = `${versusHTML(a, b)}
        <div class="prediction-teams-summary">${rosterHTML(a, false)}${rosterHTML(b, false)}</div>
        <p class="rankings-excluded">Probabilidad = Performance, K/D y kills por ronda promedio de cada equipo, con los pesos del modelo. Las demás filas no entran en la probabilidad: sirven para ver dónde gana cada uno.</p>`;
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
