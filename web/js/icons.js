/* ═══════════════════════════════════════════════════════════════════════════
   icons.js — íconos SVG de trazo (mismo estilo que el menú) en lugar de emojis.

   Los emojis se veían distintos en cada sistema y desentonaban con el diseño.
   Hay emojis en el HTML fijo, en textos que arma el JS y en datos que vienen del
   scraper (arquetipos), así que en vez de tocar cada lugar, `initIcons()` recorre
   el texto de la página y reemplaza cada emoji conocido por su SVG — también lo
   que se pinte después (MutationObserver). Un emoji nuevo se agrega en EMOJI.
   ═══════════════════════════════════════════════════════════════════════════ */

// Trazos 24×24 (stroke = currentColor); los rellenos se marcan explícitamente.
const PATHS = {
    chart: '<path d="M4 20V10M10 20V4M16 20v-7M2 20h20"/>',
    trophy: '<path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H4v1a3 3 0 0 0 4 3M16 6h4v1a3 3 0 0 1-4 3M12 13v4M8 21h8M10 17h4"/>',
    target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/>',
    crosshair: '<circle cx="12" cy="12" r="7"/><path d="M12 2v5M12 17v5M2 12h5M17 12h5"/>',
    swords: '<path d="M4 4l11 11M20 4L9 15M13 17l4 4M11 17l-4 4M14 14l3 3M10 14l-3 3"/>',
    dagger: '<path d="M20 4l-9 9M14 4h6v6M11 13l-2 2 4 4 2-2M7 17l-3 3"/>',
    clipboard: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1M9 10h6M9 14h6M9 18h4"/>',
    map: '<path d="M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2zM9 4v14M15 6v14"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
    flag: '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>',
    users: '<circle cx="9" cy="9" r="3"/><circle cx="17" cy="10" r="2.5"/><path d="M3 20c.6-3 3-5 6-5s5.4 2 6 5M15 15.5c2.5-.5 5 1 6 4.5"/>',
    flame: '<path d="M12 3c3 4 6 6 6 11a6 6 0 0 1-12 0c0-3 2-5 3-6 0 2 1 3 2 3 0-3-1-5 1-8z"/>',
    compass: '<circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2 5-5 2 2-5z"/>',
    pin: '<path d="M12 21s-7-6-7-11a7 7 0 0 1 14 0c0 5-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    drop: '<path d="M12 3s6 7 6 11a6 6 0 0 1-12 0c0-4 6-11 6-11z"/>',
    burst: '<path d="M12 2l2 6 6-2-4 5 6 3-7 1 1 7-4-5-4 5 1-7-7-1 6-3-4-5 6 2z"/>',
    skull: '<path d="M5 11a7 7 0 0 1 14 0v4l-2 1v3H7v-3l-2-1z"/><circle cx="9.5" cy="11.5" r="1.5"/><circle cx="14.5" cy="11.5" r="1.5"/>',
    medal: '<path d="M7 3l3 6M17 3l-3 6"/><circle cx="12" cy="15" r="6"/><path d="M12 12v6"/>',
    truck: '<path d="M2 7h12v9H2zM14 10h4l3 3v3h-7"/><circle cx="6" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>',
    plane: '<path d="M21 3L3 10l7 3 3 7z"/>',
    heli: '<path d="M3 4h18M12 4v4M5 12c0 2 3 4 7 4h4a3 3 0 0 0 0-6H9M16 16v3M10 19h8"/>',
    boat: '<path d="M3 15h18l-3 5H6zM6 15V9h8l3 6"/>',
    helmet: '<path d="M3 16a9 9 0 0 1 18 0zM2 16h20M12 7v4"/>',
    gamepad: '<rect x="2" y="7" width="20" height="11" rx="5"/><path d="M7 11v3M5.5 12.5h3M15 12h.01M18 13h.01"/>',
    trendUp: '<path d="M3 17l6-6 4 4 8-8M15 7h6v6"/>',
    trendDown: '<path d="M3 7l6 6 4-4 8 8M15 17h6v-6"/>',
    arrowRight: '<path d="M4 12h16M14 6l6 6-6 6"/>',
    dot: '<circle cx="12" cy="12" r="5" fill="currentColor" stroke="none"/>',
    puzzle: '<path d="M4 7h4a2 2 0 1 1 4 0h4v4a2 2 0 1 1 0 4v4h-4a2 2 0 1 0-4 0H4v-4a2 2 0 1 0 0-4z"/>',
    shield: '<path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z"/>',
    sprout: '<path d="M12 21v-9M12 12c0-4 3-6 7-6 0 4-3 6-7 6zM12 14c0-3-2-5-6-5 0 3 2 5 6 5z"/>',
    dumbbell: '<path d="M6 6v12M18 6v12M3 9v6M21 9v6M6 12h12"/>',
    star: '<path d="M12 3l2.8 5.8 6.2.9-4.5 4.4 1 6.2L12 17.4 6.5 20.3l1-6.2L3 9.7l6.2-.9z"/>',
    check: '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>',
    alert: '<path d="M12 3l10 18H2zM12 10v5M12 18h.01"/>',
    question: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.7M12 17h.01"/>',
    snow: '<path d="M12 2v20M4 6l16 12M20 6L4 18"/>',
    tape: '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="8" cy="12" r="2"/><circle cx="16" cy="12" r="2"/><path d="M8 14h8"/>',
    radio: '<path d="M4 20l5-9M9 11a5 5 0 0 1 6-6M7 9a8 8 0 0 1 10-4"/><circle cx="16" cy="8" r="1"/>',
    bandage: '<path d="M7 17L17 7a3.5 3.5 0 0 1 5 5L12 22a3.5 3.5 0 0 1-5-5zM2 12L12 2a3.5 3.5 0 0 1 5 5"/>',
};

// emoji (sin selector de variación) → [ícono, clase de color opcional]
const EMOJI = {
    '📊': ['chart'], '🏆': ['trophy', 'ico-gold'], '🎯': ['target'], '🔫': ['crosshair'],
    '⚔': ['swords'], '🗡': ['dagger'], '📋': ['clipboard'], '🗺': ['map'], '🌎': ['globe'],
    '🚩': ['flag', 'ico-red'], '👤': ['user'], '👥': ['users'], '🤝': ['users'],
    '🔥': ['flame', 'ico-orange'], '🧭': ['compass'], '📍': ['pin'], '🩸': ['drop', 'ico-red'],
    '💥': ['burst', 'ico-orange'], '💀': ['skull'], '🎖': ['medal'],
    '🥇': ['medal', 'ico-gold'], '🥈': ['medal', 'ico-silver'], '🥉': ['medal', 'ico-bronze'],
    '🚛': ['truck'], '✈': ['plane'], '🚁': ['heli'], '🚤': ['boat'], '🪖': ['helmet'],
    '🎮': ['gamepad'], '📈': ['trendUp', 'ico-green'], '📉': ['trendDown', 'ico-red'],
    '➡': ['arrowRight'], '🟢': ['dot', 'ico-green'], '🟡': ['dot', 'ico-yellow'],
    '🟠': ['dot', 'ico-orange'], '🔴': ['dot', 'ico-red'], '🧩': ['puzzle'], '🛡': ['shield'],
    '🌱': ['sprout', 'ico-green'], '🔰': ['sprout', 'ico-green'], '🏋': ['dumbbell'],
    '⭐': ['star', 'ico-gold'], '✅': ['check', 'ico-green'], '⚠': ['alert', 'ico-yellow'],
    '❓': ['question'], '❄': ['snow', 'ico-blue'], '📼': ['tape'], '📡': ['radio'],
    '🩹': ['bandage'], '💉': ['bandage'],
};

/** SVG inline de un ícono (decorativo: aria-hidden). */
export function icon(name, cls = '') {
    const body = PATHS[name];
    if (!body) return '';
    return `<svg class="ico${cls ? ' ' + cls : ''}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${body}</svg>`;
}

// Un emoji del mapa, con su selector de variación (U+FE0F) opcional.
const KEYS = Object.keys(EMOJI).sort((a, b) => b.length - a.length);
const RE = new RegExp(`(${KEYS.join('|')})️?`, 'gu');
const SKIP = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'INPUT', 'SELECT', 'OPTION', 'CANVAS', 'svg', 'TITLE']);

/** Reemplaza los emojis del mapa por SVG en los nodos de texto bajo `root`. */
export function iconize(root) {
    if (!root) return;
    if (root.nodeType === Node.TEXT_NODE) { replaceTextNode(root); return; }
    if (root.nodeType !== Node.ELEMENT_NODE || SKIP.has(root.nodeName)) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        acceptNode(n) {
            for (let p = n.parentNode; p && p !== root.parentNode; p = p.parentNode) {
                if (SKIP.has(p.nodeName)) return NodeFilter.FILTER_REJECT;
            }
            RE.lastIndex = 0;
            return RE.test(n.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
        },
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(replaceTextNode);
}

function replaceTextNode(node) {
    const text = node.nodeValue;
    RE.lastIndex = 0;
    if (!node.parentNode || SKIP.has(node.parentNode.nodeName) || !RE.test(text)) return;
    RE.lastIndex = 0;
    const frag = document.createDocumentFragment();
    let last = 0;
    for (const m of text.matchAll(RE)) {
        if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
        const [name, cls] = EMOJI[m[1]];
        const tpl = document.createElement('template');
        tpl.innerHTML = icon(name, cls);
        frag.appendChild(tpl.content);
        last = m.index + m[0].length;
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    node.parentNode.replaceChild(frag, node);
}

/** Iconiza la página y todo lo que se pinte después. */
export function initIcons() {
    iconize(document.body);
    const obs = new MutationObserver((muts) => {
        for (const m of muts) {
            if (m.type === 'characterData') replaceTextNode(m.target);
            m.addedNodes.forEach((n) => iconize(n));
        }
    });
    obs.observe(document.body, { childList: true, subtree: true, characterData: true });
}
