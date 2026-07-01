/* ═══════════════════════════════════════════════════════════════════════════
   rankings.js — Top-N players by metric, optional clan filter.
   See .rebuild/CONTRACT.md §2.5 and FEATURE_API.md (rankings notes).
   ═══════════════════════════════════════════════════════════════════════════ */

import { state } from './data.js';
import { MIN_ROUNDS_FOR_RANKING } from './config.js';
import { escapeHtml, clanLogoHTML, tierBadge, rankMedal, formatNumber } from './utils.js';

// Metric value → the raw player field it reads, plus whether higher is better.
const METRICS = {
    performance: { key: 'Performance Score', label: 'Performance Score' },
    kd:          { key: 'K/D Ratio',         label: 'K/D Ratio' },
    kills:       { key: 'Total Kills',       label: 'Total Kills' },
    deaths:      { key: 'Total Deaths',      label: 'Total Deaths' },
    rounds:      { key: 'Rounds',            label: 'Rounds' },
};

// Lowercased dropdown values that don't simply uppercase to the Clan field.
const CLAN_VALUE_MAP = { 'rim-la': 'RIM:LA' };

/** Resolve a lowercased dropdown value to the canonical clan token to match. */
function clanTokenFor(value) {
    if (CLAN_VALUE_MAP[value]) return CLAN_VALUE_MAP[value];
    return value.toUpperCase();
}

function renderRankings() {
    const results = document.getElementById('top-results');
    if (!results) return;

    const category = (document.getElementById('category')?.value || 'general').toLowerCase();
    const metricKey = document.getElementById('metric')?.value || 'performance';
    const topN = Math.max(1, parseInt(document.getElementById('top-number')?.value, 10) || 10);
    const metric = METRICS[metricKey] || METRICS.performance;

    const players = state.playersData || [];
    if (!players.length) {
        results.innerHTML = '<div class="empty-state">No hay datos de jugadores disponibles.</div>';
        return;
    }

    // Filter by clan (case-insensitive against canonical token).
    let pool = players;
    let clanLabel = '';
    if (category !== 'general') {
        const token = clanTokenFor(category).toLowerCase();
        pool = players.filter(p => p.Clan && p.Clan.toLowerCase() === token);
        clanLabel = clanTokenFor(category);
    }

    // Exclude players below the rounds threshold; report how many were excluded.
    // Fuente única: el umbral sale de tier_config.json (min_rounds) con fallback a config.js.
    const minRounds = state.tierConfigData?.min_rounds ?? MIN_ROUNDS_FOR_RANKING;
    const qualified = pool.filter(p => (p.Rounds || 0) >= minRounds);
    const excluded = pool.length - qualified.length;

    if (!qualified.length) {
        const where = clanLabel ? ` para el clan ${escapeHtml(clanLabel)}` : '';
        results.innerHTML = `<div class="empty-state">No hay jugadores con al menos ${minRounds} rondas${where}.</div>`;
        return;
    }

    const sorted = [...qualified].sort((a, b) => (b[metric.key] || 0) - (a[metric.key] || 0));
    const shown = sorted.slice(0, topN);
    const maxValue = shown.reduce((m, p) => Math.max(m, p[metric.key] || 0), 0) || 1;

    const headerBits = [`Top ${shown.length} por ${escapeHtml(metric.label)}`];
    if (clanLabel) headerBits.push(`Clan ${escapeHtml(clanLabel)}`);

    const rows = shown.map((p, i) => {
        const pos = i + 1;
        const value = p[metric.key] || 0;
        const pct = Math.max(0, Math.min(100, (value / maxValue) * 100));
        const tier = tierBadge(p['Performance Score'] || 0);
        const name = escapeHtml(p.Player);
        const clan = p.Clan ? `${clanLogoHTML(p.Clan, 18)} <span class="rank-clan">${escapeHtml(p.Clan)}</span>` : '';
        return `
            <div class="rank-row">
                <span class="rank-pos">${rankMedal(pos)}</span>
                <span class="rank-name">${name} ${clan}
                    <span class="badge tier-badge ${tier.cssClass}">${tier.emoji} ${escapeHtml(tier.name)}</span>
                </span>
                <div class="progress-row">
                    <div class="progress-track">
                        <div class="progress-fill" style="width:${pct}%;"></div>
                    </div>
                </div>
                <span class="rank-value">${formatNumber(value)}</span>
            </div>`;
    }).join('');

    const excludedNote = excluded > 0
        ? `<p class="rankings-excluded">${excluded} jugador${excluded === 1 ? '' : 'es'} excluido${excluded === 1 ? '' : 's'} por tener menos de ${minRounds} rondas.</p>`
        : '';

    results.innerHTML = `
        <div class="rankings-header">${headerBits.join(' · ')}</div>
        <div class="rank-list">${rows}</div>
        ${excludedNote}`;
}

/** Rankings init: render on submit + initial render. */
export function initRankings() {
    const form = document.getElementById('top-players-form');
    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            renderRankings();
        });
    }
    // Re-render live when controls change.
    ['category', 'metric', 'top-number'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', renderRankings);
    });

    renderRankings();
}
