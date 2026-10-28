/* ═══════════════════════════════════════════════════════════════════════════
   roles.js — top por rol (médicos, anti-tanques, tripulantes…), de
   graphs/demos/role_leaderboards.json (scraper/roles.py).

   Cada rol se mide por lo que le toca hacer y el orden usa el valor ajustado por
   muestra, así una ronda excepcional no pone a nadie primero. Solo entran
   jugadores con 10+ rondas con el rol y confianza media o alta.
   ═══════════════════════════════════════════════════════════════════════════ */

import { loadRoleLeaderboards } from './data.js';
import { escapeHtml, formatNumber, clanLogoHTML } from './utils.js';
import { barHTML, podiumHTML, tableHTML, posHTML } from './ui.js';

const CONF = { alta: 'Alta', media: 'Media', baja: 'Baja' };

function fmtValue(board, v) {
    if (v == null) return '—';
    if (board.metric === 'winrate') return `${Math.round(v * 100)} %`;
    return formatNumber(Number(v.toFixed(2)));
}

function fillRoleSelect(data) {
    const sel = document.getElementById('role-board');
    const boards = data?.periods?.todo;
    if (!sel || !boards || sel.options.length) return;
    sel.innerHTML = Object.entries(boards)
        .map(([k, b]) => `<option value="${escapeHtml(k)}">${escapeHtml(b.label)}</option>`).join('');
}

async function renderRoleBoard() {
    const results = document.getElementById('role-results');
    if (!results) return false;
    const data = await loadRoleLeaderboards();
    if (!data?.periods) {
        results.innerHTML = '<div class="empty-state">Todavía no hay datos por rol.</div>';
        return false;
    }
    fillRoleSelect(data);
    const key = document.getElementById('role-board')?.value || 'medico';
    const period = document.getElementById('role-period')?.value || 'todo';
    const count = Math.max(3, Math.min(30, parseInt(document.getElementById('role-count')?.value, 10) || 15));
    const board = data.periods[period]?.[key];
    const players = (board?.players || []).slice(0, count);
    if (!board || !players.length) {
        results.innerHTML = `<div class="empty-state">Nadie llega a ${data.min_rounds || 10} rondas como ${escapeHtml(board?.label || key)} con confianza suficiente en este período.</div>`;
        return true;
    }

    const top = Math.max(...players.map(p => p.adjusted), 0.0001);
    const clan = (p) => (p.clan ? `${clanLogoHTML(p.clan, 18)} ${escapeHtml(p.clan)}` : '');
    const record = (p) => (board.metric === 'winrate'
        ? `${p.wins}–${p.losses}`
        : `K/D ${formatNumber(Number((p.kills / Math.max(p.deaths, 1)).toFixed(2)))}`);
    const podium = podiumHTML(players.slice(0, 3).map(p => ({
        title: p.player,
        sub: `${clan(p)} · ${formatNumber(p.rounds)} rondas · real ${fmtValue(board, p.value)}`,
        value: fmtValue(board, p.adjusted),
        logo: '',
    })));
    const rest = players.slice(3);
    const table = rest.length ? tableHTML(
        [
            { label: '#', width: '56px' },
            { label: 'Jugador', width: 'minmax(0,1.5fr)' },
            { label: 'Clan', width: 'minmax(0,0.9fr)' },
            { label: `${board.metric_label} (ajustado)`, width: 'minmax(0,1.6fr)' },
            { label: 'Real', width: '80px', align: 'end' },
            { label: 'Rondas', width: '80px', align: 'end' },
            { label: board.metric === 'winrate' ? 'Récord' : 'K/D', width: '90px', align: 'end' },
            { label: 'Confianza', width: '96px' },
        ],
        rest.map((p, i) => [
            posHTML(i + 4),
            `<span class="dtable-name">${escapeHtml(p.player)}</span>`,
            p.clan ? `${clanLogoHTML(p.clan, 20)} <span class="dtable-muted">${escapeHtml(p.clan)}</span>` : '',
            `<span class="dtable-val-o">${fmtValue(board, p.adjusted)}</span>${barHTML((p.adjusted / top) * 100, 'orange')}`,
            `<span class="dtable-muted">${fmtValue(board, p.value)}</span>`,
            formatNumber(p.rounds),
            record(p),
            `<span class="pv-conf is-${p.confidence}">${CONF[p.confidence] || ''}</span>`,
        ]),
        { minWidth: 760, caption: `Top ${board.label}` },
    ) : '';

    results.innerHTML = `
        <div class="rankings-header">Top ${players.length} · ${escapeHtml(board.label)} · ${escapeHtml(board.metric_label)} · mediana del rol ${fmtValue(board, board.median)}</div>
        ${podium}${table}
        <p class="rankings-excluded">El número grande es el valor ajustado por muestra (con pocas rondas se acerca a la mediana del rol) y "real" es el valor sin ajustar. Entran jugadores con ${data.min_rounds || 10}+ rondas con el rol y confianza media o alta (ninguna ronda explica más del 40 % del resultado).</p>`;
    return true;
}

/** Top por rol: se carga al llegar a la sección y se rehace al cambiar los controles. */
export function initRoleLeaderboards() {
    const section = document.getElementById('role-leaderboards');
    if (!section) return;
    let rendered = false;
    const ensure = async () => {
        if (!rendered) rendered = await renderRoleBoard();
    };
    ['role-board', 'role-period'].forEach(id => document.getElementById(id)
        ?.addEventListener('change', () => { if (rendered) renderRoleBoard(); }));
    document.getElementById('role-count')
        ?.addEventListener('input', () => { if (rendered) renderRoleBoard(); });
    if (typeof IntersectionObserver !== 'undefined') {
        const obs = new IntersectionObserver((entries) => {
            if (entries.some(e => e.isIntersecting)) ensure().then(() => { if (rendered) obs.disconnect(); });
        }, { threshold: 0.1 });
        obs.observe(section);
    } else {
        ensure();
    }
}
