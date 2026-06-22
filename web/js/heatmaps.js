/* ═══════════════════════════════════════════════════════════════════════════
   heatmaps.js — per-map death-density heatmaps with pan/zoom.

   Density (heatmap.js technique): accumulate radial blobs into an offscreen alpha
   buffer, colorize via a 256-entry LUT. Both the optional minimap image (native
   4096px from the PR map gallery) and the density layer are drawn under a single
   canvas transform, so zooming samples the minimap at full sharpness and the
   heatmap stays aligned. Coordinates are normalized map-center in the data, so
   cell UV maps directly to the minimap — no recalibration.
   ═══════════════════════════════════════════════════════════════════════════ */

import { loadHeatmapIndex, loadHeatmap, loadMapImgManifest, loadRoundPositions, state } from './data.js';
import { mapLabel, formatNumber, escapeHtml, gamemodeLabel, weaponKind } from './utils.js';
import { MAP_IMG_URL } from './config.js';

const VIEW = 1024;          // canvas backing size (logical map space at fit-scale)
const DENSITY = 2048;       // density buffer resolution
const MAX_SCALE = 4;        // 4096px minimap / VIEW → native at 4× zoom
const SNIPER_MIN_DIST = 150; // m, debe coincidir con el scraper (SNIPER_MIN_DIST)
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

/** Extract [[gx,gy,value], …] for a layer + team (+ phase para movement).
 *  deaths/sniper: cells [gx,gy,t1,t2]. spawns: {team1,team2}:[[gx,gy,c]].
 *  movement: {team1,team2}:[[ph,gx,gy,c]] → `phase` ('all'|0..N-1) filtra la etapa. */
function layerCells(hm, layer, team, phase) {
    if (layer === 'deaths' || layer === 'sniper') {
        // Fallback al formato viejo (cells de muertes en top-level) durante la transición.
        const cells = hm[layer]?.cells || (layer === 'deaths' ? hm.cells : null) || [];
        const idx = team === '1' ? 2 : team === '2' ? 3 : -1;
        return cells.map(c => [c[0], c[1], idx < 0 ? c[2] + c[3] : c[idx]]).filter(c => c[2] > 0);
    }
    const L = hm[layer] || {};
    const isMove = layer === 'movement';
    const ph = (phase == null || phase === 'all') ? null : Number(phase);
    const collapse = (arr) => {
        const m = new Map();
        for (const e of (arr || [])) {
            let gx, gy, c;
            if (isMove && e.length >= 4) { if (ph != null && e[0] !== ph) continue; gx = e[1]; gy = e[2]; c = e[3]; }
            else { gx = e[0]; gy = e[1]; c = e[2]; }  // spawns o movement v1 (sin fase)
            const k = gx + ',' + gy; m.set(k, (m.get(k) || 0) + c);
        }
        return [...m.entries()].map(([k, c]) => { const [gx, gy] = k.split(',').map(Number); return [gx, gy, c]; });
    };
    if (team === '1') return collapse(L.team1);
    if (team === '2') return collapse(L.team2);
    return collapse([...(L.team1 || []), ...(L.team2 || [])]);
}

/** Aggregate ONE round's raw positions into a layers object {deaths,movement,spawns,
 *  sniper} (same shape layerCells reads). Mirrors scraper _aggregate_heatmaps for a
 *  single round, centered-to-map normalization. */
function gridRound(round, gridSize) {
    const ms = round.map_size || 0;
    const grid = (x, z) => {
        if (ms <= 0) return null;
        // ±512·MapSize (ref. realitytracker: fullSize = MapSize*1024), no ±500.
        const full = ms * 1024, nx = (x + ms * 512) / full, nz = (z + ms * 512) / full;
        if (nx < 0 || nx > 1 || nz < 0 || nz > 1) return null;
        return [Math.min(gridSize - 1, nx * gridSize | 0), Math.min(gridSize - 1, nz * gridSize | 0)];
    };
    const deaths = new Map(), sniper = new Map();
    const bump = (map, key, slot) => { const v = map.get(key) || [0, 0]; v[slot] += 1; map.set(key, v); };
    for (const e of (round.kill_positions || [])) {
        const c = grid(e[0], e[1]);
        if (c) bump(deaths, c[0] + ',' + c[1], e[2] === 2 ? 1 : 0);
        if (e.length >= 8 && e[3] != null && (e[6] || -1) >= SNIPER_MIN_DIST
            && e[7] !== '?' && weaponKind(e[7]) !== 'vehicle') {
            const a = grid(e[3], e[4]);
            if (a) bump(sniper, a[0] + ',' + a[1], e[5] === 2 ? 1 : 0);
        }
    }
    const cells2 = (m) => [...m.entries()].map(([k, v]) => { const [gx, gy] = k.split(',').map(Number); return [gx, gy, v[0], v[1]]; });
    // movement: ya viene gridado (move_grid_size), por fase [ph,gx,gy,c]. Pasa directo.
    const mv = round.movement || {};
    const mg = mv.grid || gridSize;
    const rescale = (arr) => (mg === gridSize) ? (arr || []) : (arr || []).map(e =>
        e.length >= 4 ? [e[0], e[1] * gridSize / mg | 0, e[2] * gridSize / mg | 0, e[3]]
                      : [e[0] * gridSize / mg | 0, e[1] * gridSize / mg | 0, e[2]]);
    // spawns: raw [[x,z,team]] → grid por equipo.
    const sp = { 1: new Map(), 2: new Map() };
    for (const [x, z, team] of (round.spawns || [])) {
        if (team !== 1 && team !== 2) continue;
        const c = grid(x, z); if (!c) continue;
        const k = c[0] + ',' + c[1]; sp[team].set(k, (sp[team].get(k) || 0) + 1);
    }
    const cells1 = (m) => [...m.entries()].map(([k, c]) => { const [gx, gy] = k.split(',').map(Number); return [gx, gy, c]; });
    return {
        deaths: { cells: cells2(deaths) },
        sniper: { cells: cells2(sniper) },
        movement: { phases: mv.phases, team1: rescale(mv.team1), team2: rescale(mv.team2) },
        spawns: { team1: cells1(sp[1]), team2: cells1(sp[2]) },
    };
}

/** Colorize a [[gx,gy,value]] cell list into an offscreen canvas (or null). */
function buildDensity(cells, grid) {
    if (!cells.length) return null;
    let maxV = 0;
    for (const c of cells) if (c[2] > maxV) maxV = c[2];
    if (!maxV) return null;

    const off = document.createElement('canvas'); off.width = DENSITY; off.height = DENSITY;
    const octx = off.getContext('2d');
    const radius = Math.max(10, (DENSITY / grid) * 2.6);
    octx.globalCompositeOperation = 'lighter';
    for (const c of cells) {
        const v = c[2]; if (!v) continue;
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
const LAYER_LABEL = {
    deaths: 'muertes (dónde cae cada equipo)',
    movement: 'rutas más transitadas',
    spawns: 'puntos de aparición (spawns)',
    sniper: `bajas a >${SNIPER_MIN_DIST}m con arma personal (posición del tirador)`,
};

/** Layers object para un (gamemode) o el formato viejo top-level (backward-compat). */
function gamemodeLayers(hm, gamemode) {
    if (hm.gamemodes) return hm.gamemodes[gamemode] || {};
    return hm;  // formato viejo: deaths/movement/spawns/sniper en top-level
}

function defaultGamemode(hm) {
    if (!hm.gamemodes) return null;
    let best = null, bestK = -1;
    for (const [gm, L] of Object.entries(hm.gamemodes)) {
        const k = L.deaths?.kills || 0;
        if (k > bestK) { bestK = k; best = gm; }
    }
    return best;
}

export async function initHeatmaps() {
    const mapSel = document.getElementById('heatmap-map');
    const gmSel = document.getElementById('heatmap-gamemode');
    const roundSel = document.getElementById('heatmap-round');
    const canvas = document.getElementById('heatmap-canvas');
    const meta = document.getElementById('heatmap-meta');
    if (!mapSel || !canvas) return;

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
    mapSel.innerHTML = maps.map(e =>
        `<option value="${escapeHtml(e.map)}">${escapeHtml(mapLabel(e.map))} (${formatNumber(e.kills || 0)})</option>`).join('');

    const phaseRow = document.getElementById('heatmap-phase-row');
    const phaseSlider = document.getElementById('heatmap-phase');
    const phaseLbl = document.getElementById('heatmap-phase-label');
    let team = 'all', layer = 'deaths', hm = null;

    const PHASE_NAMES = (n) => ['Apertura', 'Inicio', 'Desarrollo', 'Mitad', 'Avance', 'Cierre'][n] || `Fase ${n + 1}`;

    // Re-render con el estado actual (gamemode/round/layer/team/etapa). round='all' → agregado.
    async function render() {
        if (!hm) return;
        const round = roundSel ? roundSel.value : 'all';
        let layers, ctxNote = '';
        if (round && round !== 'all') {
            const r = Array.isArray(hm.rounds) ? hm.rounds.find(x => x.filename === round) : null;
            const full = r ? await loadRoundPositions(r.date, r.filename) : null;
            if (gmSel) gmSel.disabled = true;
            if (!full) { vp.density = null; resetView(); if (meta) meta.innerHTML = '<span class="empty-state">No se pudo cargar esa ronda.</span>'; return; }
            layers = gridRound(full, hm.grid_size || 128);
            ctxNote = `ronda ${escapeHtml(r.date)} · ${escapeHtml(gamemodeLabel(r.gamemode))}`;
        } else {
            if (gmSel) gmSel.disabled = false;
            const gm = gmSel ? gmSel.value : null;
            layers = gamemodeLayers(hm, gm);
            const rounds = (hm.gamemodes ? (hm.gamemodes[gm]?.rounds) : hm.rounds) || 0;
            ctxNote = (gm ? `${escapeHtml(gamemodeLabel(gm))} · ` : '') + `${formatNumber(rounds)} rondas`;
        }

        // Slider de etapas: solo para recorridos. value 0 = todas; 1..N = fase 0..N-1.
        const phases = (layer === 'movement') ? (layers.movement?.phases || 6) : 0;
        if (phaseRow) phaseRow.hidden = !phases;
        let phase = 'all';
        if (phases && phaseSlider) {
            phaseSlider.max = String(phases);
            if (Number(phaseSlider.value) > phases) phaseSlider.value = '0';
            const v = Number(phaseSlider.value);
            phase = v === 0 ? 'all' : v - 1;
            if (phaseLbl) phaseLbl.textContent = v === 0 ? 'Todas las etapas' : `${PHASE_NAMES(v - 1)} (${v}/${phases})`;
        }

        const cells = layerCells(layers, layer, team, phase);
        vp.density = buildDensity(cells, hm.grid_size || 128);
        resetView();
        if (meta) {
            const phaseNote = (phases && phase !== 'all') ? ` · etapa ${Number(phaseSlider.value)}/${phases}` : '';
            const empty = vp.density ? '' : ' <span class="muted">· sin datos en esta capa</span>';
            meta.innerHTML = `${escapeHtml(mapLabel(mapSel.value))} — ${LAYER_LABEL[layer] || ''} · ${ctxNote}${phaseNote}`
                + (vp.img ? '' : ' <span class="muted">· sin minimapa</span>') + empty
                + ' <span class="muted">· rueda/pellizco: zoom · arrastrá: mover · doble-click: reset</span>';
        }
    }
    if (phaseSlider) phaseSlider.addEventListener('input', render);

    // Cargar un mapa: trae el archivo + minimapa, puebla gamemode/ronda, y renderiza.
    async function selectMap() {
        const entry = index.find(e => e.map === mapSel.value);
        if (!entry) return;
        const [data, img] = await Promise.all([loadHeatmap(entry.file), mapImage(mapSel.value)]);
        hm = data; vp.img = img || null;
        if (!hm) { vp.density = null; resetView(); if (meta) meta.innerHTML = '<span class="empty-state">⏳ Sin datos de este mapa todavía.</span>'; return; }
        if (gmSel) {
            const gms = hm.gamemodes ? Object.keys(hm.gamemodes) : [];
            gmSel.innerHTML = gms.length
                ? gms.sort((a, b) => (hm.gamemodes[b].deaths?.kills || 0) - (hm.gamemodes[a].deaths?.kills || 0))
                     .map(gm => `<option value="${escapeHtml(gm)}">${escapeHtml(gamemodeLabel(gm))}</option>`).join('')
                : '<option value="">Todos los modos</option>';   // formato viejo (v1): un solo set
            gmSel.value = defaultGamemode(hm) || '';
            gmSel.disabled = !gms.length;
        }
        if (roundSel) {
            // hm.rounds es un array (v2) o un número (v1); solo iteramos el array.
            const rs = Array.isArray(hm.rounds) ? hm.rounds.slice(0, 80) : [];
            roundSel.innerHTML = '<option value="all">Todas las rondas</option>'
                + rs.map(r => `<option value="${escapeHtml(r.filename)}">${escapeHtml(r.date)} · ${escapeHtml(gamemodeLabel(r.gamemode))}</option>`).join('');
            roundSel.value = 'all';
            roundSel.disabled = !rs.length;
        }
        await render();
    }

    mapSel.addEventListener('change', selectMap);
    if (gmSel) gmSel.addEventListener('change', render);
    if (roundSel) roundSel.addEventListener('change', render);
    const teamGroup = document.querySelector('.heatmap-teams');
    if (teamGroup) teamGroup.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-team]'); if (!btn) return;
        team = btn.dataset.team;
        teamGroup.querySelectorAll('button').forEach(b => b.classList.toggle('active', b === btn));
        render();
    });
    const layerGroup = document.querySelector('.heatmap-layers');
    if (layerGroup) layerGroup.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-layer]'); if (!btn) return;
        layer = btn.dataset.layer;
        layerGroup.querySelectorAll('button').forEach(b => b.classList.toggle('active', b === btn));
        render();
    });

    await selectMap();
}
