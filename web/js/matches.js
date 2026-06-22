/* ═══════════════════════════════════════════════════════════════════════════
   matches.js — recent rounds feed table (lazy-loaded, retry on error).
   See .rebuild/CONTRACT.md §2.11 / §1.11 and FEATURE_API.md (matches notes).
   ═══════════════════════════════════════════════════════════════════════════ */

import { loadRecentMatches } from './data.js';
import { escapeHtml, formatNumber, matchDateLabel, mapLabel, gamemodeLabel } from './utils.js';
import { REPLAY_VIEWER_URL } from './config.js';

/** "Ver replay" link to the official viewer (only if we have the demo URL). */
function replayCell(round) {
    if (!round.demo_url) return '<span class="muted">—</span>';
    const href = REPLAY_VIEWER_URL + '?demo=' + encodeURIComponent(round.demo_url);
    return `<a class="replay-link" href="${href}" target="_blank" rel="noopener" title="Abrir replay 3D">▶ Replay</a>`;
}

/** Winner cell from numeric winner code (1=blufor, 2=opfor, -1=none). */
function winnerLabel(round) {
    const blufor = round.blufor_team ? escapeHtml(round.blufor_team) : 'BLUFOR';
    const opfor = round.opfor_team ? escapeHtml(round.opfor_team) : 'OPFOR';
    if (round.winner === 1) return `<span class="round-win">${blufor}</span>`;
    if (round.winner === 2) return `<span class="round-win">${opfor}</span>`;
    return '<span class="round-draw">Empate</span>';
}

async function renderRecentMatches() {
    const results = document.getElementById('recent-matches-results');
    if (!results) return false;

    results.innerHTML = '<div class="empty-state">Cargando partidas recientes…</div>';

    let matches;
    try {
        matches = await loadRecentMatches(25);
    } catch (_) {
        results.innerHTML = '<div class="error-state">No se pudieron cargar las partidas. Reintentando al volver a la sección…</div>';
        return false;
    }

    if (!Array.isArray(matches) || !matches.length) {
        results.innerHTML = '<div class="empty-state">No hay partidas recientes disponibles.</div>';
        return false;
    }

    const rows = matches.map((r) => `
        <tr>
            <td>${matchDateLabel(r.filename) || 'N/A'}</td>
            <td>${escapeHtml(mapLabel(r.map_name))}</td>
            <td>${escapeHtml(gamemodeLabel(r.gamemode))}</td>
            <td>${winnerLabel(r)}</td>
            <td>${formatNumber(r.total_kills || 0)}</td>
            <td>${replayCell(r)}</td>
        </tr>`).join('');

    results.innerHTML = `
        <table class="data-table recent-matches-table">
            <thead><tr><th>Fecha</th><th>Mapa</th><th>Modo</th><th>Ganador</th><th>Kills</th><th>Replay</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
    return true;
}

/** Recent matches init: lazy-load on scroll; one-shot flag reset on error for retry. */
export function initRecentMatches() {
    const section = document.getElementById('recent-matches');
    let loaded = false;

    const tryRender = async () => {
        if (loaded) return;
        const ok = await renderRecentMatches();
        loaded = !!ok; // reset to false on error so a future intersection retries
    };

    if (section && typeof IntersectionObserver !== 'undefined') {
        const obs = new IntersectionObserver((entries) => {
            entries.forEach((e) => {
                if (e.isIntersecting) {
                    tryRender().then(() => {
                        if (loaded) obs.unobserve(e.target);
                    });
                }
            });
        }, { threshold: 0.1 });
        obs.observe(section);
    } else {
        tryRender();
    }
}
