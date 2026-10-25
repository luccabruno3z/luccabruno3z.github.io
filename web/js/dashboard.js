/* ═══════════════════════════════════════════════════════════════════════════
   dashboard.js — las tarjetas del Inicio: top jugadores / líderes de demos /
   top clanes (3 tarjetas del mismo alto, 5 filas con barra) y partidas
   recientes como tabla. See .rebuild/CONTRACT.md §2.2.
   ═══════════════════════════════════════════════════════════════════════════ */

import { state, loadLeaderboard, loadRecentMatches } from './data.js';
import {
    escapeHtml, formatNumber, clanLogoHTML, matchDateLabel, mapLabel, gamemodeLabel,
} from './utils.js';
import { barHTML, tierBarHTML, tableHTML, posHTML } from './ui.js';

function emptyState(host, msg) {
    host.innerHTML = `<div class="empty-state">${escapeHtml(msg)}</div>`;
}

function errorState(host, msg) {
    host.innerHTML = `<div class="error-state">${escapeHtml(msg)}</div>`;
}

/** Fila de tarjeta: posición · nombre (+ logo) con barra debajo · valor. */
function tileRow(pos, nameHTML, barMarkup, valueHTML) {
    return `<div class="tile-row">
        ${posHTML(pos)}
        <div class="tile-who"><span class="tile-name">${nameHTML}</span>${barMarkup}</div>
        ${valueHTML}
    </div>`;
}

/** Tarjeta 1: top 5 jugadores por Performance Score (barra por tier). */
function renderTopPlayers() {
    const host = document.getElementById('tile-top-body');
    if (!host) return;
    const players = (state.playersData || []).slice(0, 5);
    if (!players.length) { emptyState(host, 'Sin datos de jugadores.'); return; }

    host.innerHTML = players.map((p, i) => {
        const ps = p['Performance Score'] || 0;
        const clan = p.Clan ? clanLogoHTML(p.Clan, 20) : '';
        return tileRow(i + 1, `${clan}<span>${escapeHtml(p.Player)}</span>`, tierBarHTML(ps),
            `<span class="dtable-val">${formatNumber(ps)}</span>`);
    }).join('');
}

/** Tarjeta 2: top 5 por kills del leaderboard semanal. */
async function renderLeaders() {
    const host = document.getElementById('tile-lb-body');
    if (!host) return;
    try {
        const data = await loadLeaderboard('semana');
        const rows = (data && Array.isArray(data.players) ? data.players : [])
            .slice()
            .sort((a, b) => (b.kills || 0) - (a.kills || 0))
            .slice(0, 5);
        if (!rows.length) { emptyState(host, 'Sin datos de leaderboard.'); return; }
        const top = rows[0].kills || 1;

        host.innerHTML = rows.map((p, i) => tileRow(i + 1, `<span>${escapeHtml(p.ign)}</span>`,
            barHTML(((p.kills || 0) / top) * 100, 'orange'),
            `<span class="dtable-val-o">${formatNumber(p.kills || 0)}</span>`)).join('');
    } catch (_) {
        errorState(host, 'No se pudo cargar el leaderboard.');
    }
}

/** Tarjeta 3: top 5 clanes por Performance Score. */
function renderTopClans() {
    const host = document.getElementById('tile-clans-body');
    if (!host) return;
    const clans = (state.clanAveragesData || [])
        .slice()
        .sort((a, b) => (b['Performance Score'] || 0) - (a['Performance Score'] || 0))
        .slice(0, 5);
    if (!clans.length) { emptyState(host, 'Sin datos de clanes.'); return; }

    host.innerHTML = clans.map((c, i) => {
        const ps = c['Performance Score'] || 0;
        return tileRow(i + 1, `${clanLogoHTML(c.Clan, 20)}<span>${escapeHtml(c.Clan)}</span>`,
            tierBarHTML(ps), `<span class="dtable-val">${formatNumber(ps)}</span>`);
    }).join('');
}

/** Tarjeta 4: partidas recientes como tabla (fecha neutra, ganador resaltado). */
async function renderRecentMatches() {
    const host = document.getElementById('tile-matches-body');
    if (!host) return;
    try {
        const matches = await loadRecentMatches(6);
        if (!matches.length) { emptyState(host, 'Sin partidas recientes.'); return; }

        const rows = matches.map((m) => {
            let winner = 'Sin definir';
            if (m.winner === 1) winner = m.blufor_team || 'BLUFOR';
            else if (m.winner === 2) winner = m.opfor_team || 'OPFOR';
            const decided = m.winner === 1 || m.winner === 2;
            return [
                `<span class="dtable-muted">${escapeHtml(matchDateLabel(m.filename) || '—')}</span>`,
                `<span class="dtable-name">${escapeHtml(mapLabel(m.map_name))}</span>`,
                `<span class="dtable-chip">${escapeHtml(gamemodeLabel(m.gamemode) || '—')}</span>`,
                `<span class="dtable-chip${decided ? ' is-win' : ''}">${escapeHtml(winner)}</span>`,
                formatNumber(m.total_kills || 0),
            ];
        });
        host.innerHTML = tableHTML(
            [
                { label: 'Fecha', width: '130px' },
                { label: 'Mapa', width: 'minmax(0,2fr)' },
                { label: 'Modo', width: 'minmax(0,1fr)' },
                { label: 'Ganador', width: 'minmax(0,1fr)' },
                { label: 'Kills', width: '80px', align: 'end' },
            ],
            rows, { minWidth: 600, caption: 'Partidas recientes' },
        );
    } catch (_) {
        errorState(host, 'No se pudieron cargar las partidas.');
    }
}

/** Dashboard init: llena las 4 tarjetas reemplazando sus skeletons. */
export function initDashboard() {
    renderTopPlayers();
    renderTopClans();
    // tarjetas async (fetches independientes)
    renderLeaders();
    renderRecentMatches();
}
