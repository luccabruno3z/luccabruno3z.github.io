/* ═══════════════════════════════════════════════════════════════════════════
   autocomplete.js — one reusable typeahead used by every player/clan input.
   Debounced, keyboard-navigable (↑/↓/Enter/Esc), accessible (role=option).
   ═══════════════════════════════════════════════════════════════════════════ */

import { AUTOCOMPLETE_DEBOUNCE_MS } from './config.js';
import { escapeHtml } from './utils.js';

/**
 * Wire an input + suggestions container.
 * @param {HTMLInputElement} input
 * @param {HTMLElement} container  the .suggestions listbox
 * @param {(query:string)=>Array<string|{label:string,value?:string,meta?:string}>} source
 * @param {(value:string, item:any)=>void} [onSelect]  default: fill the input
 */
export function setupAutocomplete(input, container, source, onSelect) {
    if (!input || !container) return;

    let items = [];
    let active = -1;
    let timer = null;

    const norm = it => (typeof it === 'string' ? { label: it, value: it } : { value: it.label, ...it });

    function close() {
        container.innerHTML = '';
        container.classList.remove('open');
        active = -1;
        items = [];
    }

    function pick(item) {
        const it = norm(item);
        if (onSelect) onSelect(it.value, it);
        else input.value = it.value;
        close();
        input.focus();
    }

    function render() {
        if (!items.length) { close(); return; }
        container.innerHTML = items.map((raw, i) => {
            const it = norm(raw);
            const meta = it.meta ? `<span class="ac-meta">${escapeHtml(it.meta)}</span>` : '';
            return `<div class="suggestion-item${i === active ? ' active' : ''}" role="option" data-i="${i}" id="${container.id}-opt-${i}" aria-selected="${i === active}">` +
                `<span class="ac-label">${escapeHtml(it.label)}</span>${meta}</div>`;
        }).join('');
        container.classList.add('open');
    }

    function update() {
        const q = input.value.trim();
        if (!q) { close(); return; }
        try { items = (source(q) || []).slice(0, 8); }
        catch (_) { items = []; }
        active = -1;
        render();
    }

    input.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(update, AUTOCOMPLETE_DEBOUNCE_MS);
    });

    input.addEventListener('keydown', (e) => {
        if (!items.length) return;
        if (e.key === 'ArrowDown') { e.preventDefault(); active = (active + 1) % items.length; render(); input.setAttribute('aria-activedescendant', `${container.id}-opt-${active}`); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); active = (active - 1 + items.length) % items.length; render(); input.setAttribute('aria-activedescendant', `${container.id}-opt-${active}`); }
        else if (e.key === 'Enter') { if (active >= 0) { e.preventDefault(); pick(items[active]); } }
        else if (e.key === 'Escape') { close(); }
    });

    container.addEventListener('mousedown', (e) => {
        const el = e.target.closest('.suggestion-item');
        if (!el) return;
        e.preventDefault();
        pick(items[Number(el.dataset.i)]);
    });

    input.addEventListener('blur', () => setTimeout(close, 120));
}

/** Convenience: a source that filters a list of player objects by name. */
export function playerSource(getPlayers) {
    return (query) => {
        const q = query.toLowerCase();
        return getPlayers()
            .filter(p => p.Player && p.Player.toLowerCase().includes(q))
            .slice(0, 8)
            .map(p => ({ label: p.Player, value: p.Player, meta: p.Clan || '' }));
    };
}
