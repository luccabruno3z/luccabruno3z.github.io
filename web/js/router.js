/* ═══════════════════════════════════════════════════════════════════════════
   router.js — una vista por pestaña, ruteada por hash.

   Rutas: #/<vista> y #/<vista>/<id-de-sección> (scrollea a esa sección).
   Compatibilidad: los anchors viejos (#rankings, #heatmaps, …) y #guias (link
   del bot) siguen andando: se resuelven a su vista y se reescriben a la ruta nueva.
   Cualquier otro hash (p.ej. #main del skip-link) no cambia de vista.
   ═══════════════════════════════════════════════════════════════════════════ */

import { state } from './data.js';
import { setupAutocomplete, playerSource } from './autocomplete.js';

const DEFAULT_VIEW = 'inicio';
const SITE_TITLE = 'Legión de Hierro — Stats Tracker';
const ALIASES = { guias: 'guias', guides: 'guias' };

let panels = {};

/** Resuelve un hash a {view, section, canonical} o null si no es una ruta. */
function resolve(hash) {
    const h = (hash || '').replace(/^#/, '');
    if (!h || h === '/') return { view: DEFAULT_VIEW, section: null, canonical: false };

    if (h.startsWith('/')) {
        const [view, section] = h.slice(1).split('/');
        if (panels[view]) return { view, section: section || null, canonical: false };
        return { view: DEFAULT_VIEW, section: null, canonical: true };
    }

    // Anchor viejo: alias explícito o id de una sección dentro de una vista.
    if (ALIASES[h]) return { view: ALIASES[h], section: null, canonical: true };
    const el = document.getElementById(h);
    const panel = el && el.closest('[data-view-panel]');
    if (panel) {
        const view = panel.dataset.viewPanel;
        const section = el === panel ? null : h;
        return { view, section, canonical: true };
    }
    return null;
}

function show(view) {
    Object.entries(panels).forEach(([name, panel]) => {
        const on = name === view;
        panel.classList.toggle('is-active', on);
        // Las secciones de la vista recién mostrada entran sin esperar al scroll.
        if (on) panel.querySelectorAll('.hero, .section').forEach(s => s.classList.add('visible'));
    });
    document.querySelectorAll('[data-view]').forEach(a => {
        if (a.dataset.view === view) a.setAttribute('aria-current', 'page');
        else a.removeAttribute('aria-current');
    });
    const panel = panels[view];
    const title = panel && panel.querySelector('.view-title');
    document.title = title ? `${title.textContent} — ${SITE_TITLE}` : SITE_TITLE;
}

let currentView = null;
let stopAligning = null;

/** Scrollea a la sección y la mantiene alineada mientras las secciones de arriba
 *  terminan de cargar (leaderboards, partidas y heatmaps crecen al llegar sus
 *  datos y la empujarían hacia abajo). Corta apenas el usuario interactúa. */
function keepAligned(panel, target) {
    if (stopAligning) stopAligning();
    const align = () => target.scrollIntoView({ block: 'start', behavior: 'instant' });
    const events = ['wheel', 'touchstart', 'keydown', 'mousedown'];
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(align) : null;
    const stop = () => {
        if (ro) ro.disconnect();
        clearTimeout(timer);
        events.forEach(ev => window.removeEventListener(ev, stop));
        stopAligning = null;
    };
    const timer = setTimeout(stop, 2500);
    align();
    if (ro) ro.observe(panel);
    events.forEach(ev => window.addEventListener(ev, stop, { passive: true }));
    stopAligning = stop;
}

function apply() {
    const route = resolve(location.hash);
    if (!route) return;
    if (route.canonical) {
        const path = route.section ? `#/${route.view}/${route.section}` : `#/${route.view}`;
        history.replaceState(null, '', path);
    }
    const changed = route.view !== currentView;
    show(route.view);
    currentView = route.view;

    const target = route.section && document.getElementById(route.section);
    if (target) keepAligned(panels[route.view], target);
    else if (changed) window.scrollTo({ top: 0, behavior: 'instant' });
}

/** Buscador del header: autocompleta y abre el perfil en la vista Jugadores. */
function initHeaderSearch() {
    const form = document.getElementById('header-search');
    const input = document.getElementById('header-player');
    const suggestions = document.getElementById('header-suggestions');
    if (!form || !input) return;

    const open = (name) => {
        const target = document.getElementById('player-name');
        const playerForm = document.getElementById('search-form');
        if (!target || !playerForm || !name) return;
        location.hash = '#/jugadores';
        target.value = name;
        playerForm.requestSubmit();
        input.value = '';
        input.blur();
    };

    setupAutocomplete(input, suggestions, playerSource(() => state.playersData || []), open);
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        open(input.value.trim());
    });
}

export function initRouter() {
    panels = {};
    document.querySelectorAll('[data-view-panel]').forEach(p => { panels[p.dataset.viewPanel] = p; });
    if (!Object.keys(panels).length) return;

    window.addEventListener('hashchange', apply);
    // Click en un link al hash actual (p.ej. el chip de la sección en la que ya
    // estás): no dispara hashchange, así que se re-aplica a mano para scrollear.
    document.addEventListener('click', (e) => {
        const a = e.target.closest('a[href^="#/"]');
        if (a && a.getAttribute('href') === location.hash) { e.preventDefault(); apply(); }
    });
    apply();
    initHeaderSearch();
}
