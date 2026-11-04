/* ═══════════════════════════════════════════════════════════════════════════
   charts.js — Chart.js builders (player radar, history, team radar, clan bars).
   `Chart` is the global from the CDN script in index.html.
   See .rebuild/CONTRACT.md §3.
   ═══════════════════════════════════════════════════════════════════════════ */

import { state } from './data.js';
import { p95, teamAverage, escapeHtml as escapeLabel } from './utils.js';
import { COLORS } from './config.js';

const RADAR_LABELS = ['Letalidad', 'Supervivencia', 'Teamwork', 'Impacto', 'Consistencia', 'Versatilidad'];
const RADAR_KEYS = ['letalidad', 'supervivencia', 'teamwork', 'impacto', 'consistencia', 'versatilidad'];

/** Qué mide cada eje del radar (scraper/scoring.py _compute_radar), de 0 a 1. */
export const RADAR_HELP = 'Cada eje va de 0 a 1. Letalidad: kills por ronda frente al resto. '
    + 'Supervivencia: K/D frente al resto y pocas muertes por ronda. Teamwork: parte del score que es '
    + 'trabajo en equipo, revives y banderas. Impacto: cuánto gana por encima del 50 % y cuánto más mata '
    + 'cuando gana. Consistencia: qué tan parejo juega entre rondas. Versatilidad: variedad de roles que juega.';

let radarChartInstance = null;
let historyChartInstance = null;
let teamRadarInstance = null;
let clanAveragesChartInstance = null;

// Shared dark-theme styling for the polar (radar) scale.
function radarScale(max) {
    return {
        r: {
            beginAtZero: true,
            max,
            ticks: { stepSize: max / 5, color: 'rgba(255,255,255,0.5)', backdropColor: 'transparent', font: { size: 10 } },
            grid: { color: COLORS.grid },
            angleLines: { color: 'rgba(255,255,255,0.15)' },
            pointLabels: { color: '#ffffff', font: { size: 11, family: 'Roboto' } },
        },
    };
}

const whiteLegend = { labels: { color: '#ffffff', font: { family: 'Roboto' } } };

/** Tear down only the history chart + its trend note. Used when a profile has no
 *  history, so the previous player's chart/"Tendencia…" note doesn't linger while
 *  keeping the freshly-rendered radar intact. */
export function clearHistoryChart() {
    if (historyChartInstance) { historyChartInstance.destroy(); historyChartInstance = null; }
    const hc = document.getElementById('historyChart');
    if (hc) hc.style.display = 'none';
    document.querySelectorAll('.trend-info').forEach(el => el.remove());
}

/** Tear down the player-profile charts (radar + history) and their trend note.
 *  Used when a search returns no player, so stale charts don't linger. */
export function clearPlayerCharts() {
    if (radarChartInstance) { radarChartInstance.destroy(); radarChartInstance = null; }
    clearHistoryChart();
}

// ── Player radar ─────────────────────────────────────────────────────────────

/** Radar of one player vs. their clan average. */
export function renderRadarChart(player, clan) {
    const canvas = document.getElementById('radarChart');
    if (!canvas || typeof Chart === 'undefined') return;
    if (radarChartInstance) radarChartInstance.destroy();

    let playerValues;
    if (player.radar) {
        playerValues = RADAR_KEYS.map(k => player.radar[k] ?? 0);
    } else {
        const allKpr = state.playersData.map(p => p['Kills per Round']).filter(v => v != null);
        const kpr = player['Kills per Round'] || 0;
        const rounds = player['Rounds'] || 0;
        const dpr = rounds > 0 ? (player['Total Deaths'] || 0) / rounds : 0;
        playerValues = [
            Math.min(kpr / p95(allKpr), 1),
            Math.max(0, 1 - dpr / 6),
            0.3, 0.3, 0.3, 0.3,
        ];
    }

    const datasets = [{
        label: player.Player,
        data: playerValues,
        fill: true,
        backgroundColor: 'rgba(0,255,255,0.2)',
        borderColor: COLORS.accent,
        pointBackgroundColor: COLORS.accent,
        pointRadius: 4,
    }];

    // Clan average over members that have a radar.
    const mates = state.playersData.filter(p => p.Clan === clan && p.radar);
    if (mates.length) {
        const avg = RADAR_KEYS.map(k => mates.reduce((s, p) => s + (p.radar[k] ?? 0), 0) / mates.length);
        datasets.push({
            label: `Promedio ${clan}`,
            data: avg,
            fill: false,
            borderColor: COLORS.orange,
            borderDash: [5, 5],
            pointBackgroundColor: COLORS.orange,
            pointRadius: 3,
        });
    }

    radarChartInstance = new Chart(canvas, {
        type: 'radar',
        data: { labels: RADAR_LABELS, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: radarScale(1.0),
            plugins: { legend: whiteLegend },
        },
    });
}

// ── Player history (line + linear trend) ─────────────────────────────────────

/** Line chart of Performance Score over time, with a least-squares trend line. */
export function renderHistoryChart(historyData, canvas) {
    if (!canvas || typeof Chart === 'undefined' || !Array.isArray(historyData) || !historyData.length) return;
    if (historyChartInstance) historyChartInstance.destroy();

    const labels = historyData.map(d => d.Date);
    // Guard against a missing/null 'Performance Score' on any row: an undefined
    // value would turn sumY/sumXY → NaN and blank the whole trend line.
    const scores = historyData.map(d => Number(d['Performance Score']) || 0);
    const n = scores.length;

    // Least-squares trend.
    const xs = scores.map((_, i) => i);
    const sumX = xs.reduce((a, b) => a + b, 0);
    const sumY = scores.reduce((a, b) => a + b, 0);
    const sumXY = xs.reduce((s, x, i) => s + x * scores[i], 0);
    const sumXX = xs.reduce((s, x) => s + x * x, 0);
    const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX || 1);
    const intercept = (sumY - slope * sumX) / n;
    const trend = xs.map(x => intercept + slope * x);

    const pointRadius = n > 60 ? 0 : (n > 30 ? 2 : 3);

    // Cortes de tier como líneas de referencia (solo los que caen cerca de la curva).
    const t = state.tierConfigData?.thresholds || {};
    const lo = Math.min(...scores) - 0.05, hi = Math.max(...scores) + 0.05;
    const TIER_LINES = [['elite', 'Corte Elite', '255,215,0'], ['veterano', 'Corte Veterano', '0,255,136'], ['experimentado', 'Corte Experimentado', '0,170,255'], ['soldado', 'Corte Soldado', '255,170,0']];
    const tierSets = TIER_LINES.filter(([k]) => t[k] != null && t[k] >= lo && t[k] <= hi).map(([k, label, rgb]) => ({
        label, data: scores.map(() => t[k]), borderColor: `rgba(${rgb},0.55)`, borderDash: [2, 4],
        borderWidth: 1, pointRadius: 0, fill: false,
    }));

    canvas.style.display = 'block';
    historyChartInstance = new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Performance Score',
                    data: scores,
                    borderColor: COLORS.accent,
                    backgroundColor: 'rgba(0,255,255,0.15)',
                    fill: true,
                    tension: 0.3,
                    pointRadius,
                    borderWidth: 2,
                },
                {
                    label: 'Tendencia',
                    data: trend,
                    borderColor: COLORS.orange,
                    borderDash: [8, 4],
                    pointRadius: 0,
                    fill: false,
                    borderWidth: 1.5,
                },
                ...tierSets,
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                y: { beginAtZero: false, grid: { color: COLORS.grid }, ticks: { color: '#ffffff' },
                    title: { display: true, text: 'Performance (de 0 a 1)', color: '#a0a0b0' } },
                x: { grid: { color: COLORS.gridDim }, ticks: { color: '#ffffff', maxRotation: 45, maxTicksLimit: 10 },
                    title: { display: true, text: 'Fecha (los tramos planos son días sin partidas nuevas)', color: '#a0a0b0' } },
            },
            plugins: {
                legend: whiteLegend,
                tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${Number(ctx.parsed.y).toFixed(4)}` } },
            },
        },
    });

    // Streak note next to the chart.
    const parent = canvas.parentElement;
    if (parent) {
        let info = parent.querySelector('.trend-info');
        if (!info) {
            info = document.createElement('div');
            info.className = 'trend-info';
            parent.appendChild(info);
        }
        // La misma recta del gráfico, dicha en números: cuánto cambió de punta a punta.
        const delta = trend[n - 1] - trend[0];
        const up = delta >= 0.02, down = delta <= -0.02;
        const emoji = up ? '📈' : down ? '📉' : '➡️';
        const word = up ? 'en alza' : down ? 'a la baja' : 'estable';
        const num = `${delta >= 0 ? '+' : '−'}${Math.abs(delta).toFixed(2).replace('.', ',')}`;
        info.innerHTML = `<span class="trend-emoji">${emoji}</span> Tendencia de largo plazo: ${word} (${num} desde ${escapeLabel(labels[0])})`;
    }
}

// ── Team radar ───────────────────────────────────────────────────────────────

/** Average radar of a team; falls back to a 5-axis stat radar if no member has `radar`. */
export function renderTeamRadar(team, container) {
    if (!container || typeof Chart === 'undefined') return;
    if (teamRadarInstance) teamRadarInstance.destroy();

    let canvas = container.querySelector('#teamRadarChart');
    if (!canvas) {
        canvas = document.createElement('canvas');
        canvas.id = 'teamRadarChart';
        canvas.setAttribute('aria-label', 'Radar promedio del equipo');
        container.appendChild(canvas);
    }

    const withRadar = team.filter(p => p.radar);
    let labels, values, max, refValues = null;

    if (withRadar.length) {
        labels = RADAR_LABELS;
        values = RADAR_KEYS.map(k => withRadar.reduce((s, p) => s + (p.radar[k] ?? 0), 0) / withRadar.length);
        max = 1.0;
        // Referencia: el promedio de los jugadores con 50+ rondas.
        const pop = (state.playersData || []).filter(p => p.radar && (p.Rounds || 0) >= 50);
        if (pop.length) refValues = RADAR_KEYS.map(k => pop.reduce((s, p) => s + (p.radar[k] ?? 0), 0) / pop.length);
    } else {
        labels = ['Combate (K/D)', 'Eficiencia (KPR)', 'Puntuación (SPR)', 'Experiencia', 'Performance'];
        const avg = key => teamAverage(team, key);
        const all = key => state.playersData.map(p => p[key]);
        values = [
            Math.min(avg('K/D Ratio') / p95(all('K/D Ratio')), 1.5),
            Math.min(avg('Kills per Round') / p95(all('Kills per Round')), 1.5),
            Math.min(avg('Score per Round') / p95(all('Score per Round')), 1.5),
            Math.min(avg('Rounds') / p95(all('Rounds')), 1.5),
            Math.min(avg('Performance Score') / p95(all('Performance Score')), 1.5),
        ];
        max = 1.5;
    }

    teamRadarInstance = new Chart(canvas, {
        type: 'radar',
        data: {
            labels,
            datasets: [{
                label: 'Promedio del equipo',
                data: values,
                fill: true,
                backgroundColor: 'rgba(0,255,255,0.2)',
                borderColor: COLORS.accent,
                pointBackgroundColor: COLORS.accent,
                pointRadius: 4,
            }, ...(refValues ? [{
                label: 'Promedio de la comunidad (50+ rondas)',
                data: refValues,
                fill: false,
                borderColor: 'rgba(255,170,0,0.9)',
                borderDash: [6, 4],
                pointRadius: 3,
                pointBackgroundColor: 'rgba(255,170,0,0.9)',
            }] : [])],
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: radarScale(max),
            plugins: { legend: whiteLegend },
        },
    });
}

// ── Clan averages (horizontal bars) ──────────────────────────────────────────

/** Horizontal bar chart of clan Performance Score (cyan → orange gradient). */
/** Barras horizontales de clanes por `metricKey` (por defecto Performance Score). */
export function renderClanAveragesChart(clanAveragesData, canvas, metricKey = 'Performance Score', metricLabel = 'Performance Score') {
    if (!canvas || typeof Chart === 'undefined' || !Array.isArray(clanAveragesData)) return;
    if (clanAveragesChartInstance) clanAveragesChartInstance.destroy();

    const sorted = [...clanAveragesData].sort((a, b) => (b[metricKey] || 0) - (a[metricKey] || 0));
    const n = sorted.length;
    const labels = sorted.map(c => c.Clan);
    const data = sorted.map(c => c[metricKey] || 0);

    const bg = [], border = [];
    sorted.forEach((_, i) => {
        const t = n > 1 ? i / (n - 1) : 0;
        const r = Math.round(0 + t * 255);
        const g = Math.round(255 - t * 90);
        const b = Math.round(255 - t * 255);
        bg.push(`rgba(${r},${g},${b},0.6)`);
        border.push(`rgba(${r},${g},${b},1)`);
    });

    // Parent height scales with clan count.
    if (canvas.parentElement) canvas.parentElement.style.height = `${Math.max(n * 35, 300)}px`;

    clanAveragesChartInstance = new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [{ label: metricLabel, data, backgroundColor: bg, borderColor: border, borderWidth: 1, borderRadius: 5, barThickness: 30 }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { beginAtZero: true, grid: { color: COLORS.grid }, ticks: { color: '#ffffff' } },
                y: { grid: { color: COLORS.gridDim }, ticks: { color: '#ffffff', font: { size: 13, weight: 'bold' } } },
            },
            plugins: { legend: { display: false } },
        },
    });
}
