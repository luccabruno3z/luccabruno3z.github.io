/* ═══════════════════════════════════════════════════════════════════════════
   heatmaps.js — per-map death-density heatmaps with pan/zoom.

   Density (heatmap.js technique): accumulate radial blobs into an offscreen alpha
   buffer, colorize via a 256-entry LUT. Both the optional minimap image (native
   4096px from the PR map gallery) and the density layer are drawn under a single
   canvas transform, so zooming samples the minimap at full sharpness and the
   heatmap stays aligned. Coordinates are normalized map-center in the data, so
   cell UV maps directly to the minimap — no recalibration.
   ═══════════════════════════════════════════════════════════════════════════ */

import { loadHeatmapIndex, loadHeatmap, loadMapImgManifest, state } from './data.js';
import { mapLabel, formatNumber, escapeHtml } from './utils.js';
import { MAP_IMG_URL } from './config.js';

const VIEW = 1024;          // canvas backing size (logical map space at fit-scale)
const DENSITY = 2048;       // density buffer resolution
const MAX_SCALE = 4;        // 4096px minimap / VIEW → native at 4× zoom
// BF2/PR invierte el eje Z (vertical) entre el mundo y el minimapa: sin esto las
// muertes de la ciudad caían sobre el agua. Verificado contra el minimapa de Gaza.
const FLIP_X = false, FLIP_Y = true;

let _lut = null;
function gradientLUT() {
    if (_lut) return _lut;
    const c = document.createElement('canvas'); c.width = 256; c.height = 1;
    const g = c.getContext('2d');
    const grad = g.createLinearGradient(0, 0, 256, 0);
    grad.addColorStop(0.00, '#0b2230'); grad.addColorStop(0.30, '#00b3ff');
    grad.addColorStop(0.55, '#00ff88'); grad.addColorStop(0.78, '#ffd700');
    grad.addColorStop(1.00, '#ff3b3b');
    g.fillStyle = grad; g.fillRect(0, 0, 256, 1);
    _lut = g.getImageData(0, 0, 256, 1).data;
    return _lut;
}

function drawBackdrop(ctx) {
    ctx.fillStyle = '#0a0e14'; ctx.fillRect(0, 0, VIEW, VIEW);
    ctx.strokeStyle = 'rgba(255,255,255,0.05)'; ctx.lineWidth = 1;
    const step = VIEW / 8;
    for (let i = 1; i < 8; i++) {
        ctx.beginPath(); ctx.moveTo(i * step, 0); ctx.lineTo(i * step, VIEW); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(0, i * step); ctx.lineTo(VIEW, i * step); ctx.stroke();
    }
}

/** Build the colorized density layer for a team → offscreen canvas (or null). */
function buildDensity(hm, team) {
    const cells = hm.cells || [];
    const grid = hm.grid_size || 128;
    const valOf = team === '1' ? (c) => c[2] : team === '2' ? (c) => c[3] : (c) => c[2] + c[3];
    let maxV = 0;
    for (const c of cells) maxV = Math.max(maxV, valOf(c));
    if (!maxV) return null;

    const off = document.createElement('canvas'); off.width = DENSITY; off.height = DENSITY;
    const octx = off.getContext('2d');
    const radius = Math.max(10, (DENSITY / grid) * 2.6);
    octx.globalCompositeOperation = 'lighter';
    for (const c of cells) {
        const v = valOf(c); if (!v) continue;
        let gx = c[0], gy = c[1];
        if (FLIP_X) gx = grid - 1 - gx;
        if (FLIP_Y) gy = grid - 1 - gy;
        const cx = ((gx + 0.5) / grid) * DENSITY;
        const cy = ((gy + 0.5) / grid) * DENSITY;
        const a = Math.min(1, Math.pow(v / maxV, 0.55));
        const g = octx.createRadialGradient(cx, cy, 0, cx, cy, radius);
        g.addColorStop(0, `rgba(0,0,0,${a})`); g.addColorStop(1, 'rgba(0,0,0,0)');
        octx.fillStyle = g;
        octx.fillRect(cx - radius, cy - radius, radius * 2, radius * 2);
    }
    const img = octx.getImageData(0, 0, DENSITY, DENSITY);
    const d = img.data; const lut = gradientLUT();
    for (let i = 0; i < d.length; i += 4) {
        const alpha = d[i + 3]; if (!alpha) continue;
        const idx = alpha << 2;
        d[i] = lut[idx]; d[i + 1] = lut[idx + 1]; d[i + 2] = lut[idx + 2];
        d[i + 3] = Math.min(255, Math.round(alpha * 0.82) + 30);
    }
    octx.putImageData(img, 0, 0);
    return off;
}

function mapImage(mapName) {
    const ext = state.mapImgManifest?.[mapName];
    if (!ext) return Promise.resolve(null);
    return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => resolve(null);
        img.src = `${MAP_IMG_URL}/${mapName}.${ext}`;
    });
}

// ── Viewport (pan/zoom) ──────────────────────────────────────────────────────
const vp = { scale: 1, tx: 0, ty: 0, img: null, density: null, canvas: null, ctx: null };

function clampView() {
    vp.scale = Math.min(MAX_SCALE, Math.max(1, vp.scale));
    const span = VIEW * vp.scale;
    vp.tx = Math.min(0, Math.max(VIEW - span, vp.tx));
    vp.ty = Math.min(0, Math.max(VIEW - span, vp.ty));
}
function render() {
    const ctx = vp.ctx; if (!ctx) return;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    drawBackdrop(ctx);
    ctx.setTransform(vp.scale, 0, 0, vp.scale, vp.tx, vp.ty);
    ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
    if (vp.img) ctx.drawImage(vp.img, 0, 0, VIEW, VIEW);
    if (vp.density) { ctx.globalAlpha = 0.9; ctx.drawImage(vp.density, 0, 0, VIEW, VIEW); ctx.globalAlpha = 1; }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
}
function resetView() { vp.scale = 1; vp.tx = 0; vp.ty = 0; render(); }

function wireInteractions(canvas) {
    const toDev = (cx, cy) => {
        const r = canvas.getBoundingClientRect();
        return [(cx - r.left) * (VIEW / r.width), (cy - r.top) * (VIEW / r.height)];
    };
    canvas.addEventListener('wheel', (e) => {
        e.preventDefault();
        const [cx, cy] = toDev(e.clientX, e.clientY);
        const f = e.deltaY < 0 ? 1.15 : 1 / 1.15;
        const ns = Math.min(MAX_SCALE, Math.max(1, vp.scale * f));
        vp.tx = cx - (cx - vp.tx) * (ns / vp.scale);
        vp.ty = cy - (cy - vp.ty) * (ns / vp.scale);
        vp.scale = ns; clampView(); render();
    }, { passive: false });

    // Pan (and pinch-zoom) via pointer events.
    const pts = new Map(); let lastDist = 0;
    canvas.addEventListener('pointerdown', (e) => {
        pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
        canvas.setPointerCapture(e.pointerId);
        canvas.classList.add('grabbing');
    });
    canvas.addEventListener('pointermove', (e) => {
        const prev = pts.get(e.pointerId); if (!prev) return;
        const r = canvas.getBoundingClientRect(); const k = VIEW / r.width;
        if (pts.size === 1) {
            vp.tx += (e.clientX - prev.x) * k; vp.ty += (e.clientY - prev.y) * k;
        }
        pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
        if (pts.size === 2) {
            const [a, b] = [...pts.values()];
            const dist = Math.hypot(a.x - b.x, a.y - b.y);
            if (lastDist) {
                const mid = toDev((a.x + b.x) / 2, (a.y + b.y) / 2);
                const ns = Math.min(MAX_SCALE, Math.max(1, vp.scale * (dist / lastDist)));
                vp.tx = mid[0] - (mid[0] - vp.tx) * (ns / vp.scale);
                vp.ty = mid[1] - (mid[1] - vp.ty) * (ns / vp.scale);
                vp.scale = ns;
            }
            lastDist = dist;
        }
        clampView(); render();
    });
    const up = (e) => { pts.delete(e.pointerId); if (pts.size < 2) lastDist = 0; if (!pts.size) canvas.classList.remove('grabbing'); };
    canvas.addEventListener('pointerup', up);
    canvas.addEventListener('pointercancel', up);
    canvas.addEventListener('dblclick', resetView);
}

// ── Selection ────────────────────────────────────────────────────────────────
async function renderSelected(mapName, team) {
    const meta = document.getElementById('heatmap-meta');
    const entry = (state.heatmapIndex || []).find(e => e.map === mapName);
    if (!entry) { vp.img = null; vp.density = null; resetView(); if (meta) meta.textContent = ''; return; }

    const [hm, img] = await Promise.all([loadHeatmap(entry.file), mapImage(mapName)]);
    vp.img = img || null;
    vp.density = hm ? buildDensity(hm, team) : null;
    resetView();

    if (meta) {
        meta.innerHTML = vp.density
            ? `${escapeHtml(mapLabel(mapName))} — <b>${formatNumber(hm.kills)}</b> muertes en <b>${formatNumber(hm.rounds)}</b> rondas`
              + (img ? '' : ' · <span class="muted">sin minimapa (fondo neutro)</span>')
              + ' <span class="muted">· rueda/pellizco para zoom, arrastrá para mover, doble-click para reset</span>'
            : `<span class="empty-state">⏳ Sin datos de posiciones para este mapa todavía (se acumulan desde las partidas nuevas).</span>`;
    }
}

export async function initHeatmaps() {
    const select = document.getElementById('heatmap-map');
    const canvas = document.getElementById('heatmap-canvas');
    const meta = document.getElementById('heatmap-meta');
    if (!select || !canvas) return;

    canvas.width = VIEW; canvas.height = VIEW;
    vp.canvas = canvas; vp.ctx = canvas.getContext('2d');
    wireInteractions(canvas);

    await Promise.all([loadHeatmapIndex(), loadMapImgManifest()]);
    const index = state.heatmapIndex || [];
    if (!index.length) {
        if (meta) meta.innerHTML = '<span class="empty-state">⏳ Los heatmaps se generan a partir de las partidas nuevas. Volvé en unos días.</span>';
        drawBackdrop(vp.ctx);
        return;
    }

    const maps = [...index].sort((a, b) => (b.kills || 0) - (a.kills || 0));
    select.innerHTML = maps.map(e =>
        `<option value="${escapeHtml(e.map)}">${escapeHtml(mapLabel(e.map))} (${formatNumber(e.kills || 0)})</option>`).join('');

    let team = 'all';
    const draw = () => renderSelected(select.value, team);
    select.addEventListener('change', draw);
    const teamGroup = document.querySelector('.heatmap-teams');
    if (teamGroup) {
        teamGroup.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-team]');
            if (!btn) return;
            team = btn.dataset.team;
            teamGroup.querySelectorAll('button').forEach(b => b.classList.toggle('active', b === btn));
            draw();
        });
    }
    draw();
}
