/* ═══════════════════════════════════════════════════════════════════════════
   chips.js — selector de jugadores con chips para Equipos (predictor y análisis).

   Reemplaza las grillas de 8 campos por equipo por UN campo con autocompletado
   ("+ agregar jugador") y los elegidos como chips. Los campos originales siguen en
   el DOM, ocultos: el selector los llena en orden, así predictor.js y team.js los
   leen igual que antes (por id) sin cambios.
   ═══════════════════════════════════════════════════════════════════════════ */

import { state } from './data.js';
import { escapeHtml } from './utils.js';
import { setupAutocomplete, playerSource } from './autocomplete.js';

let uid = 0;

/**
 * @param {HTMLElement} host   dónde va el selector (se inserta al principio)
 * @param {string[]} inputIds  ids de los campos originales, en orden
 * @param {string} label       texto accesible del campo ("Equipo A", "Jugadores")
 */
function mountChipPicker(host, inputIds, label) {
    const inputs = inputIds.map(id => document.getElementById(id)).filter(Boolean);
    if (!host || !inputs.length) return;
    const max = inputs.length;
    inputs.forEach(i => i.closest('.input-group')?.classList.add('chip-hidden'));

    const sugId = `chip-sug-${++uid}`;
    const box = document.createElement('div');
    box.className = 'chip-picker';
    box.innerHTML = `
        <div class="chip-picker-head">
            <span class="chip-picker-label">${escapeHtml(label)}</span>
            <span class="chip-picker-count" aria-live="polite"></span>
        </div>
        <ul class="chip-list" aria-label="${escapeHtml(label)}: jugadores elegidos"></ul>
        <div class="chip-input-wrap">
            <input type="text" class="chip-input" placeholder="+ agregar jugador" autocomplete="off"
                aria-label="${escapeHtml(label)}: agregar jugador" aria-autocomplete="list" aria-controls="${sugId}">
            <div class="suggestions" id="${sugId}" role="listbox" aria-label="Sugerencias"></div>
        </div>`;
    // Después del título del equipo si lo hay (predictor), si no al principio.
    const title = host.querySelector(':scope > h3');
    if (title) title.after(box); else host.insertBefore(box, host.firstChild);

    const list = box.querySelector('.chip-list');
    const count = box.querySelector('.chip-picker-count');
    const field = box.querySelector('.chip-input');
    const names = () => inputs.map(i => i.value.trim()).filter(Boolean);

    // Vuelca la lista en los campos originales (en orden, sin huecos) y repinta.
    function write(list_) {
        inputs.forEach((inp, k) => { inp.value = list_[k] || ''; });
        render();
    }

    function render() {
        const cur = names();
        list.innerHTML = cur.map((n, k) => `<li class="chip-item">
            <span>${escapeHtml(n)}</span>
            <button type="button" class="chip-remove" data-k="${k}" aria-label="Quitar a ${escapeHtml(n)}">×</button>
        </li>`).join('');
        count.textContent = `${cur.length}/${max}`;
        field.disabled = cur.length >= max;
        field.placeholder = cur.length >= max ? 'Equipo completo' : '+ agregar jugador';
    }

    function add(name) {
        const n = (name || '').trim();
        if (!n) return;
        const cur = names();
        if (cur.length >= max || cur.some(x => x.toLowerCase() === n.toLowerCase())) { field.value = ''; return; }
        write([...cur, n]);
        field.value = '';
    }

    setupAutocomplete(field, box.querySelector('.suggestions'), playerSource(() => state.playersData || []), add);
    // Enter con texto agrega el chip (sin mandar el formulario); vacío, deja enviar.
    field.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && field.value.trim()) { e.preventDefault(); add(field.value); }
        if (e.key === 'Backspace' && !field.value) { const cur = names(); if (cur.length) write(cur.slice(0, -1)); }
    });
    list.addEventListener('click', (e) => {
        const b = e.target.closest('.chip-remove');
        if (!b) return;
        const cur = names(); cur.splice(Number(b.dataset.k), 1); write(cur);
        field.focus();
    });
    render();
}

/** Monta los selectores en el predictor (equipo A y B) y en el análisis de equipo. */
export function initTeamChips() {
    const ids = (pre) => Array.from({ length: 8 }, (_, i) => `${pre}${i + 1}`);
    for (const side of ['A', 'B']) {
        const box = document.querySelector(`.predictor-team-box[data-team="${side}"]`);
        mountChipPicker(box, ids(`team${side}-p`), `Equipo ${side}`);
    }
    const grid = document.querySelector('#team-analysis-form .team-inputs-grid');
    mountChipPicker(grid?.parentElement, ids('player'), 'Jugadores');
    grid?.classList.add('chip-hidden');  // la grilla queda vacía: los campos van ocultos
}
