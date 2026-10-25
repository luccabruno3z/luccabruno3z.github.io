/* ═══════════════════════════════════════════════════════════════════════════
   ui.js — piezas de UI compartidas por rankings, leaderboards, clanes, el
   dashboard y el perfil: barra de valor, podio top 3 y tabla con columnas.
   Devuelven HTML (string), como el resto de los renderers. Estilos: sección
   "Componentes de datos" de styles.css.
   ═══════════════════════════════════════════════════════════════════════════ */

import { escapeHtml, tierBadge } from './utils.js';

/** Barra horizontal. pct 0-100; variant: 'accent' | 'orange' | clase tier-*. */
export function barHTML(pct, variant = 'accent') {
    const w = Math.max(0, Math.min(100, Number(pct) || 0));
    return `<span class="dbar" aria-hidden="true"><span class="dbar-fill dbar-${variant}" style="width:${w.toFixed(1)}%"></span></span>`;
}

/** Barra coloreada por el tier de un valor 0-1 (mismos umbrales que el rango). */
export function tierBarHTML(fraction) {
    const v = Number(fraction) || 0;
    return barHTML(v * 100, tierBadge(v).cssClass);
}

/** Chip de tier (texto, sin emoji). */
export function tierChipHTML(score) {
    const t = tierBadge(score || 0);
    return `<span class="tier-chip ${t.cssClass}">${escapeHtml(t.name)}</span>`;
}

/**
 * Podio de los 3 primeros, en orden visual 2 · 1 · 3.
 * items: [{ title, sub, value, logo }] ya en orden 1, 2, 3 (HTML ya escapado en
 * `sub`/`logo`; `title` y `value` se escapan acá).
 */
export function podiumHTML(items) {
    const order = [1, 0, 2].filter(i => items[i]);
    return `<div class="podium">${order.map((i) => {
        const it = items[i];
        return `<div class="podium-card podium-${i + 1}">
            <span class="podium-place">#${i + 1}</span>
            ${it.logo || ''}
            <span class="podium-title">${escapeHtml(it.title)}</span>
            ${it.sub ? `<span class="podium-sub">${it.sub}</span>` : ''}
            <span class="podium-value">${escapeHtml(String(it.value))}</span>
        </div>`;
    }).join('')}</div>`;
}

/**
 * Tabla con columnas alineadas (grid). columns: [{ label, width, align }]
 * (width = valor de grid-template-columns, align 'end' para números);
 * rows: [[celdaHTML, …]]. Se desplaza horizontalmente en pantallas chicas.
 */
export function tableHTML(columns, rows, { minWidth = 640, caption = '' } = {}) {
    const tpl = columns.map(c => c.width || 'minmax(0,1fr)').join(' ');
    const head = columns.map(c => `<span class="dtable-th${c.align === 'end' ? ' is-num' : ''}" role="columnheader">${escapeHtml(c.label)}</span>`).join('');
    const body = rows.map(r => `<div class="dtable-row" role="row">${r.map((cell, i) =>
        `<span class="dtable-td${columns[i]?.align === 'end' ? ' is-num' : ''}" role="cell">${cell}</span>`).join('')}</div>`).join('');
    return `<div class="dtable-wrap"><div class="dtable" role="table"${caption ? ` aria-label="${escapeHtml(caption)}"` : ''} style="--cols:${tpl};min-width:${minWidth}px">
        <div class="dtable-row dtable-head" role="row">${head}</div>${body}</div></div>`;
}

/** Posición: 01, 02… con color de medalla para el top 3. */
export function posHTML(pos) {
    const cls = pos <= 3 ? ` pos-${pos}` : '';
    return `<span class="pos${cls}">${String(pos).padStart(2, '0')}</span>`;
}
