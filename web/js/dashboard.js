/* ═══════════════════════════════════════════════════════════════════════════
   dashboard.js — the 4 bento tiles (top players / demo leaders / top clans /
   recent matches). See .rebuild/CONTRACT.md §2.2 and FEATURE_API.md (dashboard).
   ═══════════════════════════════════════════════════════════════════════════ */

import { state, loadLeaderboard, loadRecentMatches } from './data.js';
import {
    escapeHtml, prettifyToken, formatNumber, rankMedal, tierBadge, clanLogoHTML, matchDateLabel,
} from './utils.js';

function emptyState(host, msg) {
    host.innerHTML = `<div class="empty-state">${escapeHtml(msg)}</div>`;
}

function errorState(host, msg) {
    host.innerHTML = `<div class="error-state">${escapeHtml(msg)}</div>`;
}

/** Tile 1: top 5 players by Performance Score. */
function renderTopPlayers() {
    const host = document.getElementById('tile-top-body');
    if (!host) return;
    const players = (state.playersData || []).slice(0, 5);
    if (!players.length) { emptyState(host, 'Sin datos de jugadores.'); return; }

    host.innerHTML = players.map((p, i) => {
        const tier = tierBadge(p['Performance Score'] || 0);
        const clan = p.Clan ? clanLogoHTML(p.Clan, 18) : '';
        return `<div class="rank-row">
            <span class="rank-pos">${rankMedal(i + 1)}</span>
            <span class="rank-name">${clan} ${escapeHtml(p.Player)}</span>
            <span class="rank-value ${tier.cssClass}">${formatNumber(p['Performance Score'] || 0)}</span>
        </div>`;
    }).join('');
}

/** Tile 2: top 5 by kills from the weekly leaderboard. */
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

        host.innerHTML = rows.map((p, i) => `<div class="rank-row">
            <span class="rank-pos">${rankMedal(i + 1)}</span>
            <span class="rank-name">${escapeHtml(p.ign)}</span>
            <span class="rank-value">${formatNumber(p.kills || 0)} kills</span>
        </div>`).join('');
    } catch (_) {
        errorState(host, 'No se pudo cargar el leaderboard.');
    }
}

/** Tile 3: top 5 clans by Performance Score. */
function renderTopClans() {
    const host = document.getElementById('tile-clans-body');
    if (!host) return;
    const clans = (state.clanAveragesData || [])
        .slice()
        .sort((a, b) => (b['Performance Score'] || 0) - (a['Performance Score'] || 0))
        .slice(0, 5);
    if (!clans.length) { emptyState(host, 'Sin datos de clanes.'); return; }

    host.innerHTML = clans.map((c, i) => `<div class="rank-row">
        <span class="rank-pos">${rankMedal(i + 1)}</span>
        <span class="rank-name">${clanLogoHTML(c.Clan, 18)} ${escapeHtml(c.Clan)}</span>
        <span class="rank-value">${formatNumber(c['Performance Score'] || 0)}</span>
    </div>`).join('');
}

/** Tile 4: 5 most recent matches. */
async function renderRecentMatches() {
    const host = document.getElementById('tile-matches-body');
    if (!host) return;
    try {
        const matches = await loadRecentMatches(5);
        if (!matches.length) { emptyState(host, 'Sin partidas recientes.'); return; }

        host.innerHTML = matches.map((m) => {
            const date = matchDateLabel(m.filename) || '—';
            const map = prettifyToken(m.map_name);
            let winner;
            if (m.winner === 1) winner = escapeHtml(m.blufor_team || 'BLUFOR');
            else if (m.winner === 2) winner = escapeHtml(m.opfor_team || 'OPFOR');
            else winner = 'Sin definir';
            return `<div class="rank-row">
                <span class="rank-pos">${escapeHtml(date)}</span>
                <span class="rank-name">${map}</span>
                <span class="rank-value">🏆 ${winner}</span>
            </div>`;
        }).join('');
    } catch (_) {
        errorState(host, 'No se pudieron cargar las partidas.');
    }
}

/** Dashboard init: fill all 4 bento tiles, replacing their skeletons. */
export function initDashboard() {
    renderTopPlayers();
    renderTopClans();
    // async tiles (independent fetches)
    renderLeaders();
    renderRecentMatches();
}
