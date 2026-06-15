/* ═══════════════════════════════════════════════════════════════════════════
   clans.js — clan-averages horizontal bar chart + per-clan stat cards.
   See .rebuild/CONTRACT.md §2.9 / §1.2 and FEATURE_API.md (clans notes).
   ═══════════════════════════════════════════════════════════════════════════ */

import { state } from './data.js';
import { renderClanAveragesChart } from './charts.js';
import { escapeHtml, clanLogoHTML, tierBadge, formatNumber } from './utils.js';

/** One per-clan stat card. */
function clanCard(c) {
    const tier = tierBadge(c['Performance Score'] || 0);
    return `
        <div class="card clan-card">
            <div class="clan-card-header">${clanLogoHTML(c.Clan, 28)} <span class="clan-card-name">${escapeHtml(c.Clan)}</span></div>
            <div class="badge tier-badge ${tier.cssClass}">${tier.emoji} ${escapeHtml(tier.name)}</div>
            <div class="stat-row"><span class="stat-label">Performance Score</span><span class="stat-value">${formatNumber(c['Performance Score'] || 0)}</span></div>
            <div class="stat-row"><span class="stat-label">K/D Ratio</span><span class="stat-value">${formatNumber(c['K/D Ratio'] || 0)}</span></div>
            <div class="stat-row"><span class="stat-label">Kills por Ronda</span><span class="stat-value">${formatNumber(c['Kills per Round'] || 0)}</span></div>
            <div class="stat-row"><span class="stat-label">Score por Ronda</span><span class="stat-value">${formatNumber(c['Score per Round'] || 0)}</span></div>
            <div class="stat-row"><span class="stat-label">Rondas</span><span class="stat-value">${formatNumber(c['Rounds'] || 0)}</span></div>
        </div>`;
}

/** Clan averages init: chart + sorted stat cards. */
export function initClanAverages() {
    const clans = state.clanAveragesData || [];

    const canvas = document.getElementById('clanAveragesChart');
    if (canvas) renderClanAveragesChart(clans, canvas);

    const results = document.getElementById('clan-averages-results');
    if (!results) return;

    if (!clans.length) {
        results.innerHTML = '<div class="empty-state">No hay datos de clanes disponibles.</div>';
        return;
    }

    const sorted = [...clans].sort((a, b) => (b['Performance Score'] || 0) - (a['Performance Score'] || 0));
    results.innerHTML = sorted.map(clanCard).join('');
}
