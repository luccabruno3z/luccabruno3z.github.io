/* ═══════════════════════════════════════════════════════════════════════════
   heatmaps.js — per-map death-density heatmaps from graphs/demos/heatmaps/.

   Dependency-free canvas renderer (heatmap.js technique): accumulate radial
   blobs into an offscreen alpha buffer, then colorize via a 256-entry LUT.
   Coordinates are already normalized map-center in the data → cell (gx,gy) maps
   directly to canvas UV, so an optional minimap image overlays without recalibration.
   ═══════════════════════════════════════════════════════════════════════════ */

import { loadHeatmapIndex, loadHeatmap, loadMapImgManifest, state } from './data.js';
import { mapLabel, formatNumber, escapeHtml } from './utils.js';
import { MAP_IMG_URL } from './config.js';

let _lut = null;
function gradientLUT() {
    if (_lut) return _lut;
    const c = document.createElement('canvas'); c.width = 256; c.height = 1;
    const g = c.getContext('2d');
    const grad = g.createLinearGradient(0, 0, 256, 0);
    grad.addColorStop(0.00, '#0b2230');
    grad.addColorStop(0.30, '#00b3ff');
    grad.addColorStop(0.55, '#00ff88');
    grad.addColorStop(0.78, '#ffd700');
    grad.addColorStop(1.00, '#ff3b3b');
    g.fillStyle = grad; g.fillRect(0, 0, 256, 1);
    _lut = g.getImageData(0, 0, 256, 1).data;
    return _lut;
}

/** Draw the neutral backdrop (dark + subtle grid) into ctx. */
function drawBackdrop(ctx, W, H) {
    ctx.fillStyle = '#0a0e14';
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    const step = W / 8;
    for (let i = 1; i < 8; i++) {
        ctx.beginPath(); ctx.moveTo(i * step, 0); ctx.lineTo(i * step, H); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(0, i * step); ctx.lineTo(W, i * step); ctx.stroke();
    }
}

/** Paint the density layer for the selected team onto ctx (over whatever backdrop). */
function drawDensity(ctx, hm, team, W, H) {
    const cells = hm.cells || [];
    const grid = hm.grid_size || 128;
    const valOf = team === '1' ? (c) => c[2] : team === '2' ? (c) => c[3] : (c) => c[2] + c[3];
    let maxV = 0;
    for (const c of cells) maxV = Math.max(maxV, valOf(c));
    if (!maxV) return false;

    const off = document.createElement('canvas'); off.width = W; off.height = H;
    const octx = off.getContext('2d');
    const radius = Math.max(8, (W / grid) * 2.6);  // smoothing radius
    octx.globalCompositeOperation = 'lighter';
    for (const c of cells) {
        const v = valOf(c); if (!v) continue;
        const cx = ((c[0] + 0.5) / grid) * W;
        const cy = ((c[1] + 0.5) / grid) * H;
        const a = Math.min(1, Math.pow(v / maxV, 0.55));  // gamma → contrast
        const g = octx.createRadialGradient(cx, cy, 0, cx, cy, radius);
        g.addColorStop(0, `rgba(0,0,0,${a})`);
        g.addColorStop(1, 'rgba(0,0,0,0)');
        octx.fillStyle = g;
        octx.fillRect(cx - radius, cy - radius, radius * 2, radius * 2);
    }
    // Colorize by the accumulated alpha.
    const img = octx.getImageData(0, 0, W, H);
    const d = img.data; const lut = gradientLUT();
    for (let i = 0; i < d.length; i += 4) {
        const alpha = d[i + 3];
        if (!alpha) continue;
        const idx = alpha << 2;
        d[i] = lut[idx]; d[i + 1] = lut[idx + 1]; d[i + 2] = lut[idx + 2];
        d[i + 3] = Math.min(255, Math.round(alpha * 0.82) + 30);
    }
    octx.putImageData(img, 0, 0);
    ctx.drawImage(off, 0, 0);
    return true;
}

/** Load an optional minimap image for a map (or null). */
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

async function renderSelected(mapName, team) {
    const canvas = document.getElementById('heatmap-canvas');
    const meta = document.getElementById('heatmap-meta');
    if (!canvas) return;
    const W = canvas.width, H = canvas.height;
    const ctx = canvas.getContext('2d');

    const entry = (state.heatmapIndex || []).find(e => e.map === mapName);
    if (!entry) { drawBackdrop(ctx, W, H); if (meta) meta.textContent = ''; return; }

    const [hm, img] = await Promise.all([loadHeatmap(entry.file), mapImage(mapName)]);
    drawBackdrop(ctx, W, H);
    if (img) { ctx.globalAlpha = 0.85; ctx.drawImage(img, 0, 0, W, H); ctx.globalAlpha = 1; }

    let painted = false;
    if (hm) painted = drawDensity(ctx, hm, team, W, H);

    if (meta) {
        meta.innerHTML = painted
            ? `${escapeHtml(mapLabel(mapName))} — <b>${formatNumber(hm.kills)}</b> muertes en <b>${formatNumber(hm.rounds)}</b> rondas${img ? '' : ' · <span class="muted">sin minimapa (fondo neutro)</span>'}`
            : `<span class="empty-state">⏳ Sin datos de posiciones para este mapa todavía (se acumulan desde las partidas nuevas).</span>`;
    }
}

export async function initHeatmaps() {
    const select = document.getElementById('heatmap-map');
    const meta = document.getElementById('heatmap-meta');
    if (!select) return;

    await Promise.all([loadHeatmapIndex(), loadMapImgManifest()]);
    const index = state.heatmapIndex || [];
    if (!index.length) {
        if (meta) meta.innerHTML = '<span class="empty-state">⏳ Los heatmaps se generan a partir de las partidas nuevas. Volvé en unos días.</span>';
        const c = document.getElementById('heatmap-canvas');
        if (c) drawBackdrop(c.getContext('2d'), c.width, c.height);
        return;
    }

    // Most-active maps first.
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
