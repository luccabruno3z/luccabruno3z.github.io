/* ═══════════════════════════════════════════════════════════════════════════
   demos.js — demo-derived player tool + map tool + per-player rounds timeline.
   See .rebuild/CONTRACT.md §2.10 / §1.5 / §1.6 / §1.12 and FEATURE_API.md.
   ═══════════════════════════════════════════════════════════════════════════ */

import { state, loadDemoData, loadPlayerRounds, getDemoInfo } from './data.js';
import { setupAutocomplete } from './autocomplete.js';
import { escapeHtml, prettifyToken, formatNumber } from './utils.js';

// ── Player demo tool ─────────────────────────────────────────────────────────

/** Top kits from a kits_used dict (descending count). */
function topKits(kits, limit = 5) {
    if (!kits || typeof kits !== 'object') return [];
    return Object.entries(kits).sort((a, b) => b[1] - a[1]).slice(0, limit);
}

async function renderDemoPlayer(name) {
    const results = document.getElementById('demo-player-results');
    if (!results) return;

    const p = getDemoInfo(name);
    if (!p) {
        results.innerHTML = `<div class="empty-state">No se encontraron datos de demos para "${escapeHtml(name)}".</div>`;
        return;
    }

    const kits = topKits(p.kits_used);
    const kitsHTML = kits.length
        ? kits.map(([k, n]) => `<li>${prettifyToken(k)} <span class="stat-value">${formatNumber(n)}</span></li>`).join('')
        : '<li class="empty-state">Sin datos de kits.</li>';

    results.innerHTML = `
        <div class="card demo-player-card">
            <h3>${escapeHtml(p.ign)}</h3>
            <div class="stat-row"><span class="stat-label">Rondas jugadas</span><span class="stat-value">${formatNumber(p.rounds_played || 0)}</span></div>
            <div class="stat-row"><span class="stat-label">Kills</span><span class="stat-value">${formatNumber(p.total_kills || 0)}</span></div>
            <div class="stat-row"><span class="stat-label">Muertes</span><span class="stat-value">${formatNumber(p.total_deaths || 0)}</span></div>
            <div class="stat-row"><span class="stat-label">Score</span><span class="stat-value">${formatNumber(p.total_score || 0)}</span></div>
            <div class="stat-row"><span class="stat-label">Revives dados</span><span class="stat-value">${formatNumber(p.total_revives_given || 0)}</span></div>
            <div class="stat-row"><span class="stat-label">Vehículos destruidos</span><span class="stat-value">${formatNumber(p.total_vehicles_destroyed || 0)}</span></div>
            <h4>Kits más usados</h4>
            <ul class="demo-kits-list">${kitsHTML}</ul>
            <div class="demo-rounds-timeline"><div class="empty-state">Cargando timeline…</div></div>
        </div>`;

    // Append the per-round timeline (newest first, up to 20).
    const timelineHost = results.querySelector('.demo-rounds-timeline');
    const data = await loadPlayerRounds(p.ign);
    const rounds = Array.isArray(data?.rounds) ? [...data.rounds].reverse().slice(0, 20) : [];
    if (!rounds.length) {
        if (timelineHost) timelineHost.innerHTML = '<div class="empty-state">Sin historial de rondas.</div>';
        return;
    }

    const rows = rounds.map((r) => {
        const result = r.won ? '<span class="round-win">Victoria</span>' : '<span class="round-loss">Derrota</span>';
        return `
            <tr>
                <td>${escapeHtml(r.date)}</td>
                <td>${prettifyToken(r.map)}</td>
                <td>${prettifyToken(r.gamemode)}</td>
                <td>${formatNumber(r.kills || 0)}</td>
                <td>${formatNumber(r.deaths || 0)}</td>
                <td>${formatNumber(r.score || 0)}</td>
                <td>${result}</td>
            </tr>`;
    }).join('');

    if (timelineHost) {
        timelineHost.innerHTML = `
            <h4>Últimas rondas</h4>
            <table class="data-table">
                <thead><tr><th>Fecha</th><th>Mapa</th><th>Modo</th><th>K</th><th>D</th><th>Score</th><th>Resultado</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>`;
    }
}

// ── Map demo tool ────────────────────────────────────────────────────────────

function renderDemoMap(name) {
    const results = document.getElementById('demo-map-results');
    if (!results) return;

    const list = state.demoMapStats;
    if (!Array.isArray(list)) {
        results.innerHTML = '<div class="error-state">No se pudieron cargar las estadísticas de mapas.</div>';
        return;
    }

    const lower = name.toLowerCase();
    const matches = list.filter(m => m.map_name && m.map_name.toLowerCase() === lower);
    if (!matches.length) {
        results.innerHTML = `<div class="empty-state">No se encontraron datos para el mapa "${escapeHtml(name)}".</div>`;
        return;
    }

    const boxes = matches.map((m) => {
        const rounds = m.rounds_played || 0;
        const bluforWins = m.blufor_wins || 0;
        const opforWins = m.opfor_wins || 0;
        const bluforWR = rounds > 0 ? (bluforWins / rounds) * 100 : 0;
        const opforWR = rounds > 0 ? (opforWins / rounds) * 100 : 0;
        return `
            <div class="card demo-map-card">
                <h4>${prettifyToken(m.map_name)} · ${prettifyToken(m.gamemode)}</h4>
                <div class="stat-row"><span class="stat-label">Rondas jugadas</span><span class="stat-value">${formatNumber(rounds)}</span></div>
                <div class="stat-row"><span class="stat-label">Winrate BLUFOR</span><span class="stat-value">${bluforWR.toFixed(1)}%</span></div>
                <div class="stat-row"><span class="stat-label">Winrate OPFOR</span><span class="stat-value">${opforWR.toFixed(1)}%</span></div>
                <div class="stat-row"><span class="stat-label">Kills totales</span><span class="stat-value">${formatNumber(m.total_kills || 0)}</span></div>
                <div class="stat-row"><span class="stat-label">Tickets BLUFOR (prom.)</span><span class="stat-value">${formatNumber(Number((m.avg_tickets1_final || 0).toFixed(2)))}</span></div>
                <div class="stat-row"><span class="stat-label">Tickets OPFOR (prom.)</span><span class="stat-value">${formatNumber(Number((m.avg_tickets2_final || 0).toFixed(2)))}</span></div>
            </div>`;
    }).join('');

    results.innerHTML = `<div class="demo-map-cards">${boxes}</div>`;
}

// ── Init ─────────────────────────────────────────────────────────────────────

/** Demo stats init: load demo data, then wire both tools' autocompletes + forms. */
export async function initDemoStats() {
    await loadDemoData();

    // Player tool: autocomplete on `ign`.
    const playerInput = document.getElementById('demo-player-name');
    const playerSug = document.getElementById('demo-suggestions');
    if (playerInput && playerSug) {
        const source = (query) => {
            const q = query.toLowerCase();
            const list = state.demoPlayerDetails || [];
            return list
                .filter(p => p.ign && p.ign.toLowerCase().includes(q))
                .slice(0, 8)
                .map(p => ({ label: p.ign, value: p.ign }));
        };
        setupAutocomplete(playerInput, playerSug, source, (value) => {
            playerInput.value = value;
            renderDemoPlayer(value);
        });
    }
    const playerForm = document.getElementById('demo-player-form');
    if (playerForm) {
        playerForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const name = playerInput?.value.trim();
            if (name) renderDemoPlayer(name);
        });
    }

    // Map tool: autocomplete on unique map_name.
    const mapInput = document.getElementById('demo-map-name');
    const mapSug = document.getElementById('demo-map-suggestions');
    if (mapInput && mapSug) {
        const source = (query) => {
            const q = query.toLowerCase();
            const list = state.demoMapStats || [];
            const seen = new Set();
            const out = [];
            for (const m of list) {
                if (!m.map_name) continue;
                const key = m.map_name.toLowerCase();
                if (seen.has(key) || !key.includes(q)) continue;
                seen.add(key);
                out.push({ label: m.map_name, value: m.map_name });
                if (out.length >= 8) break;
            }
            return out;
        };
        setupAutocomplete(mapInput, mapSug, source, (value) => {
            mapInput.value = value;
            renderDemoMap(value);
        });
    }
    const mapForm = document.getElementById('demo-map-form');
    if (mapForm) {
        mapForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const name = mapInput?.value.trim();
            if (name) renderDemoMap(name);
        });
    }
}
