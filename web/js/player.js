/* ═══════════════════════════════════════════════════════════════════════════
   player.js — player search: full profile card, radar, history, demo enrichment.
   See .rebuild/CONTRACT.md §2.3 / §4 and FEATURE_API.md (player notes).
   ═══════════════════════════════════════════════════════════════════════════ */

import {
    state, loadDemoData, getDemoInfo, loadPlayerHistory,
} from './data.js';
import {
    escapeHtml, formatNumber, findPlayer, tierBadge, getPlayerArchetype,
    experienceBadge, sampleReliability,
    activityIndex, sigmoidPenalty, clanLogoHTML, mapLabel, gamemodeLabel,
} from './utils.js';
import { barHTML, tierBarHTML, tierChipHTML } from './ui.js';
import { renderRadarChart, renderHistoryChart, clearPlayerCharts, clearHistoryChart } from './charts.js';
import { setupAutocomplete, playerSource } from './autocomplete.js';

/** Fracción de jugadores con un valor menor (0-1) y su texto "top N%". */
function rankOf(value, values) {
    if (!values.length) return { below: 0, label: '' };
    const below = values.filter(v => v < value).length / values.length;
    const top = Math.max(1, Math.round((1 - below) * 100));
    return { below, label: `top ${top}%` };
}

/** Tarjeta de KPI: etiqueta, valor grande, barra y percentil. */
function kpiHTML(label, value, bar, note) {
    return `<div class="kpi-card">
        <span class="kpi-label">${escapeHtml(label)}</span>
        <span class="kpi-value">${value}</span>
        ${bar}
        ${note ? `<span class="kpi-note">${escapeHtml(note)}</span>` : ''}
    </div>`;
}

/** Desglose del puntaje con barras coloreadas por tier (como en el bot). */
function breakdownHTML(player) {
    const comps = [
        ['Normalized_KD', 'Combate (K/D)'], ['Normalized_Score', 'Puntuación (SPR)'],
        ['Normalized_Kills_Per_Round', 'Agresividad (KPR)'], ['Normalized_Rounds', 'Experiencia'],
    ].map(([k, name]) => ({ name, value: player[k] || 0 }));
    const max = Math.max(...comps.map(c => c.value));
    const min = Math.min(...comps.map(c => c.value));
    return comps.map(c => {
        const mark = c.value === max ? ' ⭐' : (c.value === min && c.value < 0.7 ? ' ⚠️' : '');
        return `<div class="meter-row">
            <span class="meter-label">${escapeHtml(c.name)}${mark}</span>
            ${tierBarHTML(c.value)}
            <span class="meter-value">${Math.round(c.value * 100)}</span>
        </div>`;
    }).join('');
}

/** Build and render the full profile card for a player. */
async function renderPlayerProfile(player) {
    const host = document.getElementById('player-profile-card');
    if (!host) return;

    const players = state.playersData || [];
    const rank = players.indexOf(player) + 1;
    const rounds = player['Rounds'] || 0;
    const kd = player['K/D Ratio'] || 0;
    const kpr = player['Kills per Round'] || 0;
    const spr = player['Score per Round'] || 0;
    const ps = player['Performance Score'] || 0;

    const tier = tierBadge(ps);
    const arch = getPlayerArchetype(player);
    const exp = experienceBadge(rounds);
    const rel = sampleReliability(rounds);

    // Percentiles sobre la población.
    const rPS = rankOf(ps, players.map(p => p['Performance Score'] || 0));
    const rKD = rankOf(kd, players.map(p => p['K/D Ratio'] || 0));
    const rKPR = rankOf(kpr, players.map(p => p['Kills per Round'] || 0));
    const rSPR = rankOf(spr, players.map(p => p['Score per Round'] || 0));
    const rKills = rankOf(player['Total Kills'] || 0, players.map(p => p['Total Kills'] || 0));

    // "Participación" = índice de volumen/rendimiento (no mira fechas). La actividad
    // real (última partida) la completa enrichWithDemo con last_round_date.
    const actIdx = activityIndex(rounds, spr, kpr);

    // Penalización por muestra chica (sigmoide).
    const penalty = sigmoidPenalty(rounds);
    const warnings = [];
    if (penalty * 100 < 95) {
        const needed = Math.ceil(25 + 10 * Math.log(19)); // ~54
        const remaining = Math.max(0, needed - rounds);
        warnings.push(`Confianza del puntaje: ${(penalty * 100).toFixed(0)}%. Faltan ~${remaining} rondas para alcanzar el 95%.`);
    }
    if (rounds < 50) warnings.push('Menos de 50 rondas: el jugador no califica para los rankings.');

    const f2 = (v) => formatNumber(Number((v || 0).toFixed(2)));
    host.innerHTML = `
        <div class="profile-v2">
            <section class="card profile-hero ${tier.cssClass}-border">
                <div class="profile-logo">${player.Clan ? clanLogoHTML(player.Clan, 72) : ''}</div>
                <div class="profile-id">
                    <div class="profile-title">
                        <h3 class="profile-name">${escapeHtml(player.Player)}</h3>
                        <span class="profile-rank">#${rank} global${player.Clan ? ` · ${escapeHtml(player.Clan)}` : ''}</span>
                    </div>
                    <div class="profile-badges">
                        ${tierChipHTML(ps)}
                        <span class="profile-tag">${arch.emoji} ${escapeHtml(arch.name)}</span>
                        <span class="profile-tag">${exp.emoji} ${escapeHtml(exp.name)}</span>
                        <span class="profile-tag ${rel.cssClass}">${rel.emoji} ${escapeHtml(rel.text)}</span>
                    </div>
                    ${arch.desc ? `<p class="profile-desc">${escapeHtml(arch.desc)}</p>` : ''}
                </div>
            </section>

            ${warnings.map(w => `<div class="profile-warning">⚠️ ${escapeHtml(w)}</div>`).join('')}

            <div class="kpi-grid">
                ${kpiHTML('Performance', f2(ps), tierBarHTML(ps), rPS.label)}
                ${kpiHTML('K/D', f2(kd), tierBarHTML(rKD.below), rKD.label)}
                ${kpiHTML('Kills por ronda', f2(kpr), tierBarHTML(rKPR.below), rKPR.label)}
                ${kpiHTML('Score por ronda', formatNumber(Math.round(spr)), tierBarHTML(rSPR.below), rSPR.label)}
            </div>

            <div class="profile-grid">
                <section class="card profile-records" id="profile-demo-block">
                    <h4 class="profile-subtitle">Récords</h4>
                    <p class="profile-muted">Cargando datos de demos…</p>
                </section>
                <section class="card profile-side">
                    <h4 class="profile-subtitle">Desglose del puntaje</h4>
                    ${breakdownHTML(player)}
                    <h4 class="profile-subtitle">Actividad</h4>
                    <p class="profile-last-seen" id="profile-last-seen">Buscando la última partida…</p>
                    <div class="meter-row">
                        <span class="meter-label" title="Índice de volumen y rendimiento; no mide si juega hace poco">Participación</span>
                        ${barHTML(actIdx)}
                        <span class="meter-value">${actIdx}</span>
                    </div>
                </section>
            </div>

            <div class="kpi-grid kpi-grid-3">
                ${kpiHTML('Total kills', formatNumber(player['Total Kills'] || 0), '', rKills.label)}
                ${kpiHTML('Total muertes', formatNumber(player['Total Deaths'] || 0), '', `K/D ${f2(kd)}`)}
                ${kpiHTML('Rondas', formatNumber(rounds), '', 'PRStats')}
            </div>
        </div>`;

    // Radar vs clan average.
    renderRadarChart(player, player.Clan);

    // Demo enrichment (loose-wired in current data; keyed by ign). Best-effort.
    enrichWithDemo(player);

    // History line chart (best-effort; hidden if absent).
    const history = await loadPlayerHistory(player.Player);
    if (Array.isArray(history) && history.length) {
        renderHistoryChart(history, document.getElementById('historyChart'));
    } else {
        // No history: tear down only the history chart + trend note (keep the
        // radar just rendered above) so the previous player's "Tendencia…" doesn't linger.
        clearHistoryChart();
    }
}

const DEMO_RE = /tracker_(\d{4})_(\d{2})_(\d{2})_\d{2}_\d{2}_\d{2}_(.+?)_(gpm_[a-z_]+?)_\d+\.PRdemo$/;

/** "Battle of Debrecen · AAS · 27/06/2026" a partir de best_round. */
function roundWhere(rnd) {
    const parts = [mapLabel(rnd.map || '')];
    const m = DEMO_RE.exec(String(rnd.filename || ''));
    if (m) parts.push(gamemodeLabel(m[5]), `${m[3]}/${m[2]}/${m[1]}`);
    return parts.filter(Boolean).join(' · ');
}

/** Actividad real a partir de la fecha de la última ronda con demo (como en el bot). */
function lastSeenText(last) {
    if (!last) return 'Sin partidas registradas en demos';
    const [y, m, dd] = String(last).slice(0, 10).split('-').map(Number);
    const days = Math.floor((Date.now() - new Date(y, m - 1, dd).getTime()) / 86400000);
    if (Number.isNaN(days)) return `Última partida: ${last}`;
    const ago = days <= 0 ? 'hoy' : days === 1 ? 'ayer' : days < 60 ? `hace ${days} días` : `hace ${Math.floor(days / 30)} meses`;
    const status = days <= 14 ? '🟢 Activo' : days <= 60 ? '🟡 Poco activo' : '❄️ Inactivo';
    const date = `${String(dd).padStart(2, '0')}/${String(m).padStart(2, '0')}/${y}`;
    return `${status} · última partida ${date} (${ago})`;
}

/** Bloque de récords (mismo contenido que la pestaña Récords del bot). */
async function enrichWithDemo(player) {
    const block = document.getElementById('profile-demo-block');
    if (!block) return;
    try {
        await loadDemoData();
    } catch (_) { /* non-fatal */ }
    const d = getDemoInfo(player.Player);
    const seen = document.getElementById('profile-last-seen');
    if (seen) seen.textContent = lastSeenText(d && d.last_round_date);
    if (!d || !d.rounds_played) {
        block.innerHTML = '<h4 class="profile-subtitle">Récords</h4><p class="profile-muted">Todavía no hay rondas con demo para este jugador.</p>';
        return;
    }

    const best = d.best_round && d.best_round.kills > 0 ? d.best_round : null;
    const items = [];
    const add = (label, value) => { if (value) items.push([label, value]); };
    add('Racha de kills', d.best_killstreak);
    add('Racha de victorias', d.longest_win_streak);
    add('Clutch kills', d.total_clutch_kills);
    add('First bloods', d.total_first_bloods);
    add('Vehículos destruidos', d.total_vehicles_destroyed);
    add('Revives dados', d.total_revives_given);
    const maps = Object.entries(d.maps_played || {}).sort((a, b) => b[1] - a[1]);
    if (maps.length) items.push(['Mapa más jugado', `${mapLabel(maps[0][0])} (${maps[0][1]})`]);
    if ((d.played_seconds || 0) >= 3600) items.push(['Tiempo registrado', `${Math.round(d.played_seconds / 3600)} h`]);

    const bars = [];
    const w = d.wins || 0, l = d.losses || 0;
    if (w + l) bars.push([`Winrate · ${w}–${l}`, w / (w + l)]);
    const modes = Object.entries(d.gamemode_stats || {}).filter(([, s]) => (s.rounds || 0) >= 5)
        .sort((a, b) => (b[1].winrate || 0) - (a[1].winrate || 0));
    if (modes.length) bars.push([`Mejor modo · ${gamemodeLabel(modes[0][0])}`, (modes[0][1].winrate || 0) / 100]);

    block.innerHTML = `
        <div class="profile-records-head">
            <h4 class="profile-subtitle">Récords</h4>
            <span class="profile-muted">De ${formatNumber(d.rounds_played)} rondas con demo</span>
        </div>
        ${best ? `<div class="best-round">
            <div class="best-round-where">
                <span class="best-round-label">Mejor ronda</span>
                <span class="best-round-map">${escapeHtml(roundWhere(best).split(' · ')[0])}</span>
                <span class="profile-muted">${escapeHtml(roundWhere(best).split(' · ').slice(1).join(' · '))}</span>
            </div>
            <div class="best-round-nums">
                <div><b class="is-gold">${formatNumber(best.kills)}</b><span>kills</span></div>
                <div><b>${formatNumber(best.deaths || 0)}</b><span>muertes</span></div>
                <div><b>${formatNumber(best.score || 0)}</b><span>puntos</span></div>
            </div>
        </div>` : ''}
        <div class="record-grid">
            ${items.map(([k, v]) => `<div class="record-item"><b>${escapeHtml(String(v))}</b><span>${escapeHtml(k)}</span></div>`).join('')}
        </div>
        ${bars.map(([label, frac]) => `<div class="meter-row">
            <span class="meter-label">${escapeHtml(label)}</span>${tierBarHTML(frac)}
            <span class="meter-value">${Math.round(frac * 100)}%</span></div>`).join('')}`;
}

/** Player search init: form submit + autocomplete. */
export function initPlayerSearch() {
    const form = document.getElementById('search-form');
    const input = document.getElementById('player-name');
    const suggestions = document.getElementById('suggestions');

    if (input && suggestions) {
        setupAutocomplete(input, suggestions, playerSource(() => state.playersData || []), (value) => {
            input.value = value;
            const player = findPlayer(state.playersData, value);
            if (player) renderPlayerProfile(player);
        });
    }

    if (form && input) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const name = input.value.trim();
            if (!name) return;
            const player = findPlayer(state.playersData, name);
            const host = document.getElementById('player-profile-card');
            if (!player) {
                if (host) host.innerHTML = `<div class="empty-state">No se encontró ningún jugador con "${escapeHtml(name)}".</div>`;
                clearPlayerCharts();
                return;
            }
            renderPlayerProfile(player);
        });
    }
}
