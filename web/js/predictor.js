/* ═══════════════════════════════════════════════════════════════════════════
   predictor.js — predictor 8v8: probabilidad de victoria + comparación completa.
   See .rebuild/CONTRACT.md §2.7 / §4 and FEATURE_API.md (predictor notes).
   ═══════════════════════════════════════════════════════════════════════════ */

import { state, loadDemoData, loadSynergy } from './data.js';
import { buildSquad, versusHTML, rosterHTML, balanceTeams, winProb } from './squads.js';
import { setChipNames } from './chips.js';
import { setupAutocomplete, playerSource } from './autocomplete.js';
import { findPlayer, escapeHtml } from './utils.js';

/** Jugadores de un equipo (A|B), hasta 8; `missing` = nombres que no se encontraron. */
function collectTeam(side) {
    const players = state.playersData || [];
    const team = [], missing = [];
    for (let i = 1; i <= 8; i++) {
        const name = document.getElementById(`team${side}-p${i}`)?.value.trim();
        if (!name) continue;
        const p = findPlayer(players, name);
        if (p && !team.includes(p)) team.push(p); else if (!p) missing.push(name);
    }
    return { team, missing };
}

let last = null;   // los dos equipos de la última predicción (para balancear)

async function performPrediction() {
    const results = document.getElementById('prediction-results');
    if (!results) return;

    const A = collectTeam('A'), B = collectTeam('B');
    // El mismo jugador no puede estar en los dos equipos: queda en A.
    const dup = B.team.filter(p => A.team.includes(p));
    const teamA = A.team, teamB = B.team.filter(p => !dup.includes(p));

    if (!teamA.length || !teamB.length) {
        results.innerHTML = '<div class="empty-state">Ingresá al menos un jugador en cada equipo.</div>';
        return;
    }

    // Las mismas estadísticas que las escuadras de clan (squads.js): PRStats y demos,
    // roles que cubre cada equipo y sinergia. La probabilidad tiene en cuenta el
    // tamaño de cada equipo y las rondas de cada jugador.
    results.innerHTML = '<div class="empty-state">Calculando…</div>';
    try { await loadDemoData(); } catch (_) { /* las demos son opcionales */ }
    const synergy = await loadSynergy().catch(() => null);
    const a = buildSquad('Equipo A', teamA, synergy, false);
    const b = buildSquad('Equipo B', teamB, synergy, false);
    last = [...teamA, ...teamB];
    const warn = [];
    const lost = [...A.missing, ...B.missing];
    if (lost.length) warn.push(`No se encontraron y no cuentan: ${lost.map(escapeHtml).join(', ')}.`);
    if (dup.length) warn.push(`Estaban en los dos equipos y quedaron solo en A: ${dup.map(p => escapeHtml(p.Player)).join(', ')}.`);
    const canBalance = last.length >= 4 && last.length <= 16;
    results.innerHTML = `${warn.length ? `<ul class="sq-notes">${warn.map(w => `<li>${w}</li>`).join('')}</ul>` : ''}
        ${versusHTML(a, b, true)}
        ${canBalance ? '<div class="pred-balance"><button type="button" class="sq-open" id="pred-balance-btn">Proponer equipos parejos con estos jugadores</button><div id="pred-balance-out"></div></div>' : ''}
        <div class="prediction-teams-summary">${rosterHTML(a, false)}${rosterHTML(b, false)}</div>
        <p class="rankings-excluded">Probabilidad: Performance, K/D y kills por ronda de cada jugador con los pesos del modelo. Con menos de 50 rondas un jugador cuenta cerca del promedio de la comunidad, y un equipo con menos jugadores suma menos. Las otras filas no entran en la probabilidad: muestran dónde gana cada uno.</p>`;
}

/** Busca la división más pareja de los jugadores cargados y la ofrece. */
function showBalance() {
    const out = document.getElementById('pred-balance-out');
    if (!out || !last) return;
    const best = balanceTeams(last);
    if (!best) { out.innerHTML = '<p class="sq-sub">Hacen falta entre 4 y 16 jugadores.</p>'; return; }
    const a = buildSquad('Equipo A', best.A, null, false), b = buildSquad('Equipo B', best.B, null, false);
    const pa = winProb(a, b, true);
    const list = (t) => t.map(p => escapeHtml(p.Player)).join(', ');
    out.innerHTML = `<p>La división más pareja queda <b>${Math.round(pa * 100)}–${Math.round((1 - pa) * 100)}</b>:</p>
        <ul><li><b>Equipo A:</b> ${list(best.A)}</li><li><b>Equipo B:</b> ${list(best.B)}</li></ul>
        <button type="button" class="sq-open" id="pred-balance-use">Usar estos equipos</button>`;
    document.getElementById('pred-balance-use')?.addEventListener('click', () => {
        setChipNames('Equipo A', best.A.map(p => p.Player));
        setChipNames('Equipo B', best.B.map(p => p.Player));
        performPrediction();
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
    document.getElementById('prediction-results')?.addEventListener('click', (e) => {
        if (e.target.closest('#pred-balance-btn')) showBalance();
    });
}
