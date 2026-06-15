/* ═══════════════════════════════════════════════════════════════════════════
   charts.js — Chart.js builders (player radar, history, team radar, clan bars).
   `Chart` is the global from the CDN script in index.html.
   See .rebuild/CONTRACT.md §3.
   ═══════════════════════════════════════════════════════════════════════════ */

import { state } from './data.js';
import { p95 } from './utils.js';
import { COLORS } from './config.js';

const RADAR_LABELS = ['Letalidad', 'Supervivencia', 'Teamwork', 'Impacto', 'Consistencia', 'Versatilidad'];
const RADAR_KEYS = ['letalidad', 'supervivencia', 'teamwork', 'impacto', 'consistencia', 'versatilidad'];

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
    const scores = historyData.map(d => d['Performance Score']);
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
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                y: { beginAtZero: false, grid: { color: COLORS.grid }, ticks: { color: '#ffffff' } },
                x: { grid: { color: COLORS.gridDim }, ticks: { color: '#ffffff', maxRotation: 45, maxTicksLimit: 10 } },
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
        const up = slope > 0.0005, down = slope < -0.0005;
        const emoji = up ? '📈' : down ? '📉' : '➡️';
        const text = up ? 'Tendencia en alza' : down ? 'Tendencia a la baja' : 'Rendimiento estable';
        info.innerHTML = `<span class="trend-emoji">${emoji}</span> ${text}`;
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
    let labels, values, max;

    if (withRadar.length) {
        labels = RADAR_LABELS;
        values = RADAR_KEYS.map(k => withRadar.reduce((s, p) => s + (p.radar[k] ?? 0), 0) / withRadar.length);
        max = 1.0;
    } else {
        labels = ['Combate (K/D)', 'Eficiencia (KPR)', 'Puntuación (SPR)', 'Experiencia', 'Performance'];
        const avg = key => team.reduce((s, p) => s + (p[key] || 0), 0) / team.length;
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
            }],
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
export function renderClanAveragesChart(clanAveragesData, canvas) {
    if (!canvas || typeof Chart === 'undefined' || !Array.isArray(clanAveragesData)) return;
    if (clanAveragesChartInstance) clanAveragesChartInstance.destroy();

    const sorted = [...clanAveragesData].sort((a, b) => (b['Performance Score'] || 0) - (a['Performance Score'] || 0));
    const n = sorted.length;
    const labels = sorted.map(c => c.Clan);
    const data = sorted.map(c => c['Performance Score'] || 0);

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
            datasets: [{ label: 'Performance Score', data, backgroundColor: bg, borderColor: border, borderWidth: 1, borderRadius: 5, barThickness: 30 }],
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
