/* ═══════════════════════════════════════════════════════════════════════════
   leaderboards.js — demo-derived leaderboard by period + metric (lazy-loaded).
   See .rebuild/CONTRACT.md §2.6 / §1.9 and FEATURE_API.md (leaderboards notes).
   ═══════════════════════════════════════════════════════════════════════════ */

import { loadLeaderboard } from './data.js';
import { escapeHtml, rankMedal, formatNumber } from './utils.js';

const LB_METRIC_LABELS = {
    kills: 'Kills',
    kd: 'K/D',
    score: 'Score',
    revives: 'Revives',
    teamwork_score: 'Teamwork',
};

/** Metric value for a leaderboard row (kd computed = kills/deaths). */
function metricValue(player, metric) {
    if (metric === 'kd') {
        const deaths = player.deaths || 0;
        return deaths === 0 ? (player.kills || 0) : (player.kills || 0) / deaths;
    }
    return player[metric] || 0;
}

async function renderLeaderboard() {
    const results = document.getElementById('leaderboard-results');
    if (!results) return false;

    const period = document.getElementById('lb-period')?.value || 'semana';
    const metric = document.getElementById('lb-metric')?.value || 'kills';
    const count = Math.max(1, Math.min(50, parseInt(document.getElementById('lb-count')?.value, 10) || 15));

    results.innerHTML = '<div class="empty-state">Cargando leaderboard…</div>';

    let data;
    try {
        data = await loadLeaderboard(period);
    } catch (_) {
        results.innerHTML = '<div class="error-state">No se pudo cargar el leaderboard. Reintentando al volver a la sección…</div>';
        return false;
    }

    const players = Array.isArray(data?.players) ? data.players : [];
    if (!players.length) {
        results.innerHTML = '<div class="empty-state">No hay datos para este período.</div>';
        return false;
    }

    const label = LB_METRIC_LABELS[metric] || metric;
    const sorted = [...players].sort((a, b) => metricValue(b, metric) - metricValue(a, metric));
    const shown = sorted.slice(0, count);

    const rows = shown.map((p, i) => {
        const pos = i + 1;
        const value = metricValue(p, metric);
        const kd = (p.deaths || 0) === 0 ? (p.kills || 0) : (p.kills || 0) / (p.deaths || 1);
        const name = escapeHtml(p.ign);
        return `
            <div class="rank-row">
                <span class="rank-pos">${rankMedal(pos)}</span>
                <span class="rank-name">${name}</span>
                <span class="rank-detail">
                    <span class="stat-value">${formatNumber(metric === 'kd' ? Number(value.toFixed(2)) : value)}</span>
                    <span class="rank-subdetail">${formatNumber(p.rounds || 0)} rondas · ${formatNumber(p.kills || 0)} K · ${formatNumber(p.deaths || 0)} D · ${kd.toFixed(2)} K/D</span>
                </span>
            </div>`;
    }).join('');

    results.innerHTML = `
        <div class="rankings-header">Top ${shown.length} por ${escapeHtml(label)} · ${data.total_rounds || 0} rondas en total</div>
        <div class="rank-list">${rows}</div>`;
    return true;
}

/** Leaderboards init: lazy-load on scroll, re-render on control change. */
export function initLeaderboards() {
    const section = document.getElementById('leaderboards');
    let rendered = false;

    const ensureRendered = async () => {
        if (rendered) return;
        // Only latch on success, so a transient fetch error retries on re-entry.
        rendered = !!(await renderLeaderboard());
    };

    // Re-render on control changes (only after first load).
    const period = document.getElementById('lb-period');
    const metric = document.getElementById('lb-metric');
    const countEl = document.getElementById('lb-count');
    if (period) period.addEventListener('change', () => { if (rendered) renderLeaderboard(); });
    if (metric) metric.addEventListener('change', () => { if (rendered) renderLeaderboard(); });
    if (countEl) countEl.addEventListener('input', () => { if (rendered) renderLeaderboard(); });

    // Lazy-load the first render when the section scrolls into view.
    if (section && typeof IntersectionObserver !== 'undefined') {
        const obs = new IntersectionObserver((entries) => {
            entries.forEach((e) => {
                if (e.isIntersecting) {
                    ensureRendered().then(() => {
                        if (rendered) obs.unobserve(e.target);
                    });
                }
            });
        }, { threshold: 0.1 });
        obs.observe(section);
    } else {
        ensureRendered();
    }
}
