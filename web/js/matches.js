/* ═══════════════════════════════════════════════════════════════════════════
   matches.js — recent rounds feed table (lazy-loaded, retry on error).
   See .rebuild/CONTRACT.md §2.11 / §1.11 and FEATURE_API.md (matches notes).
   ═══════════════════════════════════════════════════════════════════════════ */

import { loadRecentMatches } from './data.js';
import { escapeHtml, formatNumber, matchDateLabel, mapLabel, gamemodeLabel } from './utils.js';
import { tableHTML } from './ui.js';

/** Ganador como chip (1=blufor, 2=opfor, otro=empate), igual que en el Inicio. */
function winnerLabel(round) {
    const blufor = round.blufor_team ? escapeHtml(round.blufor_team) : 'BLUFOR';
    const opfor = round.opfor_team ? escapeHtml(round.opfor_team) : 'OPFOR';
    if (round.winner === 1) return `<span class="dtable-chip is-win">${blufor}</span>`;
    if (round.winner === 2) return `<span class="dtable-chip is-win">${opfor}</span>`;
    return '<span class="dtable-chip">Empate</span>';
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

    // Tabla compartida (ui.js): columnas alineadas y scroll horizontal propio en celular.
    results.innerHTML = tableHTML(
        [
            { label: 'Fecha', width: '120px' },
            { label: 'Mapa', width: 'minmax(0,2fr)' },
            { label: 'Modo', width: 'minmax(0,1fr)' },
            { label: 'Ganador', width: 'minmax(0,1fr)' },
            { label: 'Kills', width: '80px', align: 'end' },
        ],
        matches.map((r) => [
            `<span class="dtable-muted">${escapeHtml(matchDateLabel(r.filename) || '—')}</span>`,
            `<span class="dtable-name">${escapeHtml(mapLabel(r.map_name))}</span>`,
            `<span class="dtable-chip">${escapeHtml(gamemodeLabel(r.gamemode) || '—')}</span>`,
            winnerLabel(r),
            formatNumber(r.total_kills || 0),
        ]),
        { minWidth: 600, caption: 'Partidas recientes' },
    );
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
