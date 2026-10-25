/* ═══════════════════════════════════════════════════════════════════════════
   leaderboards.js — demo-derived leaderboard by period + metric (lazy-loaded).
   See .rebuild/CONTRACT.md §2.6 / §1.9 and FEATURE_API.md (leaderboards notes).
   ═══════════════════════════════════════════════════════════════════════════ */

import { loadLeaderboard } from './data.js';
import { escapeHtml, formatNumber } from './utils.js';
import { barHTML, tableHTML, posHTML } from './ui.js';

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

    const top = metricValue(shown[0], metric) || 1;
    const fmtVal = (v) => formatNumber(metric === 'kd' ? Number(v.toFixed(2)) : v);
    const kdOf = (p) => ((p.deaths || 0) === 0 ? (p.kills || 0) : (p.kills || 0) / p.deaths);

    // Columnas separadas: la métrica elegida (con barra) + rondas/kills/muertes/K-D,
    // sin repetir la métrica si ya es una de esas columnas.
    const cols = [
        { label: '#', width: '56px' },
        { label: 'Jugador', width: 'minmax(0,1.6fr)' },
        { label, width: 'minmax(0,2fr)' },
        { label: 'Rondas', width: '80px', align: 'end' },
    ];
    if (metric !== 'kills') cols.push({ label: 'Kills', width: '80px', align: 'end' });
    cols.push({ label: 'Muertes', width: '90px', align: 'end' });
    if (metric !== 'kd') cols.push({ label: 'K/D', width: '80px', align: 'end' });

    const rows = shown.map((p, i) => {
        const value = metricValue(p, metric);
        const kd = kdOf(p);
        const cells = [
            posHTML(i + 1),
            `<span class="dtable-name">${escapeHtml(p.ign)}</span>`,
            `<span class="dtable-val-o">${fmtVal(value)}</span>${barHTML((value / top) * 100, 'orange')}`,
            formatNumber(p.rounds || 0),
        ];
        if (metric !== 'kills') cells.push(formatNumber(p.kills || 0));
        cells.push(`<span class="dtable-muted">${formatNumber(p.deaths || 0)}</span>`);
        if (metric !== 'kd') cells.push(`<span class="${kd < 1 ? 'dtable-bad' : ''}">${formatNumber(Number(kd.toFixed(2)))}</span>`);
        return cells;
    });

    results.innerHTML = `
        <div class="rankings-header">Top ${shown.length} por ${escapeHtml(label)} · ${formatNumber(data.total_rounds || 0)} rondas en total</div>
        ${tableHTML(cols, rows, { minWidth: 640, caption: `Leaderboard por ${label}` })}`;
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
