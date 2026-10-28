/* ═══════════════════════════════════════════════════════════════════════════
   guides.js — lector de guías dentro de la vista Guías.

   Cada guía es un fragmento HTML en web/guides/<slug>.html y se abre en
   #/guias/<slug>. El router ya muestra la vista Guías con esa ruta (el segundo
   segmento no es un id del DOM, así que no scrollea); acá se baja el fragmento,
   se arma el índice con sus h2 y se oculta la grilla. Sin slug vuelve la grilla.
   Los saltos del índice son botones (no #anchors) para no pelear con el router.
   ═══════════════════════════════════════════════════════════════════════════ */

import { escapeHtml } from './utils.js';

export const GUIDES = [
    { slug: 'kits', title: 'Kits de Project Reality', short: 'Kits' },
    { slug: 'infanteria', title: 'Fundamentos de infantería', short: 'Infantería' },
    { slug: 'lider', title: 'Líder de escuadra', short: 'Líder de escuadra' },
    { slug: 'urbano', title: 'Combate urbano', short: 'Combate urbano' },
    { slug: 'cqb', title: 'CQB: combate en espacios cerrados', short: 'CQB' },
    { slug: 'mapas', title: 'Guía de mapas', short: 'Mapas' },
    { slug: 'assets', title: 'Assets: vehículos, emplazamientos y logística', short: 'Assets' },
];

const SITE_TITLE = 'Legión de Hierro — Stats Tracker';
const cache = {};

function currentSlug() {
    const m = /^#\/guias\/([a-z]+)/.exec(location.hash);
    return m && GUIDES.some(g => g.slug === m[1]) ? m[1] : null;
}

async function loadGuide(slug) {
    if (cache[slug]) return cache[slug];
    const res = await fetch(`web/guides/${slug}.html`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    cache[slug] = await res.text();
    return cache[slug];
}

function render(reader, guide, html) {
    const i = GUIDES.indexOf(guide);
    const next = GUIDES[(i + 1) % GUIDES.length];
    reader.innerHTML = `
        <div class="guide-top">
            <a href="#/guias" class="guide-back">← Todas las guías</a>
            <span class="guide-count">Guía ${i + 1} de ${GUIDES.length}</span>
        </div>
        <div class="guide-layout">
            <nav class="guide-toc" aria-label="Índice de la guía">
                <details open>
                    <summary>Índice</summary>
                    <ol class="guide-toc-list"></ol>
                </details>
            </nav>
            <article class="guide-body">${html}
                <footer class="guide-end">
                    <a href="#/guias/${next.slug}" class="cta-button">Siguiente: ${escapeHtml(next.short)} →</a>
                    <a href="#/guias" class="cta-button ghost">Todas las guías</a>
                </footer>
            </article>
        </div>`;

    const body = reader.querySelector('.guide-body');
    const list = reader.querySelector('.guide-toc-list');
    body.querySelectorAll('h2').forEach((h, k) => {
        h.id = `guia-${guide.slug}-${k + 1}`;
        const li = document.createElement('li');
        const b = document.createElement('button');
        b.type = 'button';
        b.textContent = h.textContent;
        b.addEventListener('click', () => {
            h.scrollIntoView({ behavior: 'smooth', block: 'start' });
            // En celular el índice se cierra para dejar ver el texto.
            if (window.matchMedia('(max-width: 900px)').matches) reader.querySelector('.guide-toc details').open = false;
        });
        li.appendChild(b);
        list.appendChild(li);
    });
    if (window.matchMedia('(max-width: 900px)').matches) reader.querySelector('.guide-toc details').open = false;
    prepareFigures(body);
}

/** Diagramas: los que no tienen animación se marcan como estáticos; con "reducir
 *  movimiento" los animados se muestran quietos en su estado final (data-end). */
function prepareFigures(body) {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    body.querySelectorAll('figure.g-fig').forEach((fig) => {
        const svg = fig.querySelector('svg');
        const end = svg && parseFloat(svg.dataset.end);
        if (!svg || !end) { fig.classList.add('is-static'); return; }
        if (reduce && typeof svg.pauseAnimations === 'function') {
            svg.pauseAnimations();
            svg.setCurrentTime(end - 0.05);
            fig.classList.add('is-static');
        }
    });
}

async function route() {
    const reader = document.getElementById('guide-reader');
    const index = document.getElementById('guides');
    const social = document.getElementById('social');
    if (!reader || !index) return;
    const slug = currentSlug();
    if (!slug) {
        reader.hidden = true;
        index.hidden = false;
        if (social) social.hidden = false;
        return;
    }
    const guide = GUIDES.find(g => g.slug === slug);
    index.hidden = true;
    if (social) social.hidden = true;
    reader.hidden = false;
    reader.classList.add('visible');
    document.title = `${guide.title} — ${SITE_TITLE}`;
    if (reader.dataset.slug !== slug) {
        reader.innerHTML = '<div class="empty-state">Cargando guía…</div>';
        try {
            render(reader, guide, await loadGuide(slug));
            reader.dataset.slug = slug;
        } catch (e) {
            reader.innerHTML = `<div class="error-state">No se pudo cargar la guía. <a href="#/guias">Volver a las guías</a></div>`;
            return;
        }
    }
    reader.scrollIntoView({ block: 'start' });
}

export function initGuides() {
    window.addEventListener('hashchange', route);
    route();
}
