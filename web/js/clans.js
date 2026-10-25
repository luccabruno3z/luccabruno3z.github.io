/* ═══════════════════════════════════════════════════════════════════════════
   clans.js — promedios de clanes: gráfico de barras + podio top 3 + tabla
   ordenable (o tarjetas, a elección). See .rebuild/CONTRACT.md §2.9 / §1.2.
   ═══════════════════════════════════════════════════════════════════════════ */

import { state, loadClanAveragesActive } from './data.js';
import { renderClanAveragesChart } from './charts.js';
import { escapeHtml, clanLogoHTML, formatNumber } from './utils.js';
import { tierBarHTML, barHTML, tierChipHTML, podiumHTML, tableHTML, posHTML } from './ui.js';

const SORTS = {
    performance: { key: 'Performance Score', label: 'Performance' },
    kd: { key: 'K/D Ratio', label: 'K/D' },
    kpr: { key: 'Kills per Round', label: 'KPR' },
    spr: { key: 'Score per Round', label: 'SPR' },
};

const ui = { sort: 'performance', view: 'table', scope: 'historico' };
let activeData = null;   // clan_averages_active.json, se baja la primera vez que se elige

const f2 = (v) => formatNumber(Number((v || 0).toFixed(2)));
const int = (v) => formatNumber(Math.round(v || 0));

/** Tarjeta de un clan (vista "Tarjetas"). */
function clanCard(c) {
    return `
        <div class="card clan-card">
            <div class="clan-card-header">
                ${clanLogoHTML(c.Clan, 36)}
                <div class="clan-card-id">
                    <span class="clan-card-name">${escapeHtml(c.Clan)}</span>
                    ${tierChipHTML(c['Performance Score'])}
                </div>
            </div>
            <div class="stat-row"><span class="stat-label">Performance Score</span><span class="stat-value">${f2(c['Performance Score'])}</span></div>
            <div class="stat-row"><span class="stat-label">K/D Ratio</span><span class="stat-value">${f2(c['K/D Ratio'])}</span></div>
            <div class="stat-row"><span class="stat-label">Kills por Ronda</span><span class="stat-value">${f2(c['Kills per Round'])}</span></div>
            <div class="stat-row"><span class="stat-label">Score por Ronda</span><span class="stat-value">${int(c['Score per Round'])}</span></div>
            <div class="stat-row"><span class="stat-label">Rondas prom.</span><span class="stat-value">${int(c['Rounds'])}</span></div>
        </div>`;
}

function toolbarHTML() {
    const seg = (label, attr, entries, current) => `<div class="segmented" role="group" aria-label="${label}">${
        entries.map(([v, l]) => `<button type="button" data-${attr}="${v}" aria-pressed="${v === current}">${escapeHtml(l)}</button>`).join('')}</div>`;
    return `<div class="clan-toolbar">
        ${seg('Alcance', 'scope', [['historico', 'Histórico'], ['activos', 'Activos (top 50)']], ui.scope)}
        ${seg('Ordenar por', 'sort', Object.entries(SORTS).map(([k, s]) => [k, s.label]), ui.sort)}
        ${seg('Vista', 'view', [['table', 'Tabla'], ['cards', 'Tarjetas']], ui.view)}
    </div>`;
}

function scopeNoteHTML() {
    if (ui.scope !== 'activos') {
        return '<p class="clan-scope-note">Promedio de <b>todos</b> los jugadores de cada clan, activos o no.</p>';
    }
    const p = activeData || {};
    return `<p class="clan-scope-note">Promedio de los <b>${p.top_n || 50} mejores jugadores activos</b> de cada clan
        (por Performance). Activo = jugó en los últimos ${p.window_days || 30} días según PRStats o las demos.
        Clanes con menos de ${p.min_active || 5} activos no aparecen.</p>`;
}

function render(results, controls, clans) {
    // Los selectores van arriba del gráfico (controls) porque también lo cambian.
    controls.innerHTML = toolbarHTML() + scopeNoteHTML();
    const canvas = document.getElementById('clanAveragesChart');
    const chartBox = canvas && canvas.parentElement;
    if (ui.scope === 'activos') {
        clans = (activeData && activeData.clans) || [];
        if (!clans.length) {
            if (chartBox) chartBox.style.display = 'none';
            results.innerHTML = '<div class="empty-state">Todavía no hay datos de clanes activos: se generan en la próxima actualización.</div>';
            return;
        }
    }
    if (chartBox) chartBox.style.display = '';
    if (canvas) renderClanAveragesChart(clans, canvas);
    const sort = SORTS[ui.sort] || SORTS.performance;
    const sorted = [...clans].sort((a, b) => (b[sort.key] || 0) - (a[sort.key] || 0));
    const fmt = (c) => (ui.sort === 'spr' ? int(c[sort.key]) : f2(c[sort.key]));

    let body;
    if (ui.view === 'cards') {
        body = `<div class="clan-cards-grid">${sorted.map(clanCard).join('')}</div>`;
    } else {
        const max = sorted.reduce((m, c) => Math.max(m, c[sort.key] || 0), 0) || 1;
        const podium = podiumHTML(sorted.slice(0, 3).map((c) => ({
            title: c.Clan,
            sub: tierChipHTML(c['Performance Score']),
            value: fmt(c),
            logo: clanLogoHTML(c.Clan, 44),
        })));
        const table = tableHTML(
            [
                { label: '#', width: '56px' },
                { label: 'Clan', width: 'minmax(0,1.3fr)' },
                { label: 'Tier', width: '140px' },
                { label: sort.label, width: 'minmax(0,2fr)' },
                { label: 'K/D', width: '80px', align: 'end' },
                { label: 'KPR', width: '80px', align: 'end' },
                { label: 'SPR', width: '80px', align: 'end' },
                { label: 'Rondas prom.', width: '120px', align: 'end' },
                ...(ui.scope === 'activos' ? [{ label: 'Activos', width: '90px', align: 'end' }] : []),
            ],
            sorted.map((c, i) => {
                const v = c[sort.key] || 0;
                // Performance: color por tier. El resto: cian, relativo al primero.
                const bar = ui.sort === 'performance' ? tierBarHTML(v) : barHTML((v / max) * 100);
                return [
                    posHTML(i + 1),
                    `${clanLogoHTML(c.Clan, 22)} <span class="dtable-name">${escapeHtml(c.Clan)}</span>`,
                    tierChipHTML(c['Performance Score']),
                    `<span class="dtable-val">${fmt(c)}</span>${bar}`,
                    `<span class="${(c['K/D Ratio'] || 0) < 1 ? 'dtable-bad' : ''}">${f2(c['K/D Ratio'])}</span>`,
                    f2(c['Kills per Round']),
                    `<span class="dtable-muted">${int(c['Score per Round'])}</span>`,
                    `<span class="dtable-muted">${int(c['Rounds'])}</span>`,
                    ...(ui.scope === 'activos' ? [`<span class="dtable-muted">${int(c['Active Players'])}</span>`] : []),
                ];
            }),
            { minWidth: ui.scope === 'activos' ? 970 : 880, caption: `Clanes ordenados por ${sort.label}` },
        );
        body = podium + table;
    }
    results.innerHTML = body;
}

/** Clan averages init: gráfico + podio/tabla (o tarjetas), con orden y vista elegibles. */
export function initClanAverages() {
    const clans = state.clanAveragesData || [];

    const results = document.getElementById('clan-averages-results');
    if (!results) return;

    if (!clans.length) {
        results.innerHTML = '<div class="empty-state">No hay datos de clanes disponibles.</div>';
        return;
    }

    // Barra de selectores antes del gráfico.
    const container = results.closest('.clan-averages-container') || results.parentElement;
    const controls = document.createElement('div');
    controls.className = 'clan-controls';
    container.insertBefore(controls, container.firstChild);

    container.addEventListener('click', async (e) => {
        const btn = e.target.closest('button[data-sort], button[data-view], button[data-scope]');
        if (!btn) return;
        if (btn.dataset.sort) ui.sort = btn.dataset.sort;
        if (btn.dataset.view) ui.view = btn.dataset.view;
        if (btn.dataset.scope) {
            ui.scope = btn.dataset.scope;
            if (ui.scope === 'activos' && !activeData) activeData = await loadClanAveragesActive();
        }
        render(results, controls, clans);
    });
    render(results, controls, clans);
}
