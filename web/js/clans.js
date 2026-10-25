/* ═══════════════════════════════════════════════════════════════════════════
   clans.js — promedios de clanes: gráfico de barras + podio top 3 + tabla
   ordenable (o tarjetas, a elección). See .rebuild/CONTRACT.md §2.9 / §1.2.
   ═══════════════════════════════════════════════════════════════════════════ */

import { state } from './data.js';
import { renderClanAveragesChart } from './charts.js';
import { escapeHtml, clanLogoHTML, tierBadge, formatNumber } from './utils.js';
import { tierBarHTML, barHTML, tierChipHTML, podiumHTML, tableHTML, posHTML } from './ui.js';

const SORTS = {
    performance: { key: 'Performance Score', label: 'Performance' },
    kd: { key: 'K/D Ratio', label: 'K/D' },
    kpr: { key: 'Kills per Round', label: 'KPR' },
    spr: { key: 'Score per Round', label: 'SPR' },
};

const ui = { sort: 'performance', view: 'table' };

const f2 = (v) => formatNumber(Number((v || 0).toFixed(2)));
const int = (v) => formatNumber(Math.round(v || 0));

/** Tarjeta de un clan (vista "Tarjetas"). */
function clanCard(c) {
    const tier = tierBadge(c['Performance Score'] || 0);
    return `
        <div class="card clan-card">
            <div class="clan-card-header">${clanLogoHTML(c.Clan, 28)} <span class="clan-card-name">${escapeHtml(c.Clan)}</span></div>
            <div class="badge tier-badge ${tier.cssClass}">${tier.emoji} ${escapeHtml(tier.name)}</div>
            <div class="stat-row"><span class="stat-label">Performance Score</span><span class="stat-value">${f2(c['Performance Score'])}</span></div>
            <div class="stat-row"><span class="stat-label">K/D Ratio</span><span class="stat-value">${f2(c['K/D Ratio'])}</span></div>
            <div class="stat-row"><span class="stat-label">Kills por Ronda</span><span class="stat-value">${f2(c['Kills per Round'])}</span></div>
            <div class="stat-row"><span class="stat-label">Score por Ronda</span><span class="stat-value">${int(c['Score per Round'])}</span></div>
            <div class="stat-row"><span class="stat-label">Rondas prom.</span><span class="stat-value">${int(c['Rounds'])}</span></div>
        </div>`;
}

function toolbarHTML() {
    const seg = (group, entries, current) => `<div class="segmented" role="group" aria-label="${group}">${
        entries.map(([v, l]) => `<button type="button" data-${group === 'Ordenar por' ? 'sort' : 'view'}="${v}" aria-pressed="${v === current}">${escapeHtml(l)}</button>`).join('')}</div>`;
    return `<div class="clan-toolbar">
        ${seg('Ordenar por', Object.entries(SORTS).map(([k, s]) => [k, s.label]), ui.sort)}
        ${seg('Vista', [['table', 'Tabla'], ['cards', 'Tarjetas']], ui.view)}
    </div>`;
}

function render(results, clans) {
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
                ];
            }),
            { minWidth: 880, caption: `Clanes ordenados por ${sort.label}` },
        );
        body = podium + table;
    }
    results.innerHTML = toolbarHTML() + body;
}

/** Clan averages init: gráfico + podio/tabla (o tarjetas), con orden y vista elegibles. */
export function initClanAverages() {
    const clans = state.clanAveragesData || [];

    const canvas = document.getElementById('clanAveragesChart');
    if (canvas) renderClanAveragesChart(clans, canvas);

    const results = document.getElementById('clan-averages-results');
    if (!results) return;

    if (!clans.length) {
        results.innerHTML = '<div class="empty-state">No hay datos de clanes disponibles.</div>';
        return;
    }

    results.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-sort], button[data-view]');
        if (!btn) return;
        if (btn.dataset.sort) ui.sort = btn.dataset.sort;
        if (btn.dataset.view) ui.view = btn.dataset.view;
        render(results, clans);
    });
    render(results, clans);
}
