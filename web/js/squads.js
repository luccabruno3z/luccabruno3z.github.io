/* ═══════════════════════════════════════════════════════════════════════════
   squads.js — escuadras de clan: los 8 mejores de cada clan como una escuadra.

   Por clan se toman los 8 jugadores con más Performance (50+ rondas; opcional:
   solo activos en los últimos 30 días) y se calculan las estadísticas de la
   escuadra: PRStats (Performance, K/D, kills y score por ronda), demos (winrate,
   revives, teamwork, escuadra, vida, fuego amigo, clutch), cobertura de roles y
   sinergia (cuántos pares de la escuadra jugaron juntos y cómo les fue). Después se
   rankean y se comparan escuadra contra escuadra con la probabilidad de victoria
   del predictor.
   ═══════════════════════════════════════════════════════════════════════════ */

import { state, loadDemoData, getDemoInfo, loadSynergy } from './data.js';
import { NORM_CAPS } from './config.js';
import { escapeHtml, formatNumber, clanLogoHTML, playerLinkHTML, fmtDuration, avgLife, NEAR_MIN_SAMPLES, COHESION_MIN_SAMPLES, glossaryLinkHTML } from './utils.js';
import { barHTML, versusBarHTML, tierChipHTML, posHTML } from './ui.js';

const SIZE = 8;
const MIN_ROUNDS = 50;
const MIN_MEMBERS = 5;          // menos que esto no es una escuadra para rankear
const MIN_PAIR_ROUNDS = 3;      // rondas juntos para contar un par en la sinergia

// Lo que una escuadra de infantería necesita tener (manual de campo / guía de líder).
// "apoyo" es el kit de AR y "ametrallador" el de MG: cualquiera de los dos cubre.
const NEEDED = [[['oficial'], 'Oficial'], [['medico'], 'Médico'], [['ar', 'ametrallador'], 'AR o MG'], [['at'], 'Anti-tanque']];

/** Etiqueta del rol tal como la trae la demo (Médico, Apoyo, Anti-tanque…). */
function roleLabel(d, key) {
    return d?.roles?.find(r => r.key === key)?.label || key;
}

const f2 = (v) => formatNumber(Number((v || 0).toFixed(2)));
const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)} %`);
const sum = (arr, fn) => arr.reduce((s, x) => s + (fn(x) || 0), 0);
const avg = (arr, fn) => (arr.length ? sum(arr, fn) / arr.length : null);

// ── Modelo de fuerza ───────────────────────────────────────────────────────
// Fuerza = Performance, K/D y kills por ronda de cada jugador (pesos de
// tier_config), con dos ajustes:
//  - Muestra: con pocas rondas el jugador cuenta cerca de la mediana de la
//    comunidad (n / (n + PRIOR_ROUNDS)), así 2 rondas buenas no hacen favorito.
//  - Tamaño (solo equipos armados a mano): un equipo con menos jugadores
//    suma menos, como si los lugares vacíos valieran cero.
// La probabilidad es una curva sobre la diferencia de fuerza (no un cociente,
// que dejaba todo entre 45 % y 65 %).
const PRIOR_ROUNDS = 50;
const PROB_K = 6;               // pendiente: 0,1 de diferencia ≈ 65 %
export const FEW_ROUNDS = 50;   // por debajo se avisa que cuenta cerca del promedio

function weights() {
    const w = state.tierConfigData?.predictor_weights;
    if (w && (w.ps + w.kd + w.kpr) > 0) {
        const t = w.ps + w.kd + w.kpr;
        return { ps: w.ps / t, kd: w.kd / t, kpr: w.kpr / t };
    }
    return { ps: 0.5, kd: 0.3, kpr: 0.2 };
}

let medCache = null;
function medians() {
    if (medCache && medCache.src === state.playersData) return medCache;
    const pop = (state.playersData || []).filter(p => (p.Rounds || 0) >= MIN_ROUNDS);
    const med = (key) => {
        const v = pop.map(p => p[key] || 0).sort((x, y) => x - y);
        return v.length ? v[Math.floor(v.length / 2)] : 0;
    };
    medCache = { src: state.playersData, ps: med('Performance Score'), kd: med('K/D Ratio'), kpr: med('Kills per Round') };
    return medCache;
}

/** Valor del jugador ajustado por muestra hacia la mediana de la comunidad. */
function shrunk(p, key, med) {
    const n = p.Rounds || 0, w = n / (n + PRIOR_ROUNDS);
    return w * (p[key] || 0) + (1 - w) * med;
}

/** Fuerza de un jugador (la del equipo es el promedio de la de sus jugadores). */
export function strength(p) {
    const w = weights(), m = medians();
    return w.ps * shrunk(p, 'Performance Score', m.ps)
        + w.kd * (shrunk(p, 'K/D Ratio', m.kd) / NORM_CAPS.kd)
        + w.kpr * (shrunk(p, 'Kills per Round', m.kpr) / NORM_CAPS.kpr);
}

/** Probabilidad de que gane `a`. `bySize`: el equipo más chico suma menos. */
export function winProb(a, b, bySize = false) {
    let sa = a.score, sb = b.score;
    if (bySize) {
        const n = Math.max(a.members.length, b.members.length) || 1;
        sa *= a.members.length / n; sb *= b.members.length / n;
    }
    return 1 / (1 + Math.exp(-PROB_K * (sa - sb)));
}

/** Cómo leer la probabilidad del favorito (0,5–1). */
function probBand(p) {
    return p < 0.55 ? 'parejo' : p < 0.65 ? 'ventaja leve' : p < 0.8 ? 'ventaja clara' : 'muy desbalanceado';
}

/** Estadísticas de un grupo de jugadores. `clan` es el nombre que se muestra; con
 *  `isClan` en false (equipos armados a mano) no se muestra logo. */
export function buildSquad(clan, members, synergy, isClan = true) {
    const demos = members.map(p => ({ p, d: getDemoInfo(p.Player) })).filter(x => x.d && x.d.rounds_played);
    const D = demos.map(x => x.d);
    const kills = sum(members, p => p['Total Kills']), deaths = sum(members, p => p['Total Deaths']);
    const wins = sum(D, d => d.wins), losses = sum(D, d => d.losses);
    const dr = sum(D, d => d.rounds_played);
    const sq = {
        clan, isClan, members, demos,
        ps: avg(members, p => p['Performance Score']),
        kd: kills / Math.max(deaths, 1),
        kdAvg: avg(members, p => p['K/D Ratio']),
        kpr: avg(members, p => p['Kills per Round']),
        spr: avg(members, p => p['Score per Round']),
        rounds: avg(members, p => p.Rounds),
        winrate: wins + losses >= 10 ? wins / (wins + losses) : null,
        record: [wins, losses],
        revives: dr ? sum(D, d => d.total_revives_given) / dr : null,
        teamwork: D.length ? avg(D, d => d.teamwork_ratio) : null,
        near: sum(D, d => d.near_samples) >= NEAR_MIN_SAMPLES * 3 ? sum(D, d => d.near_hits) / sum(D, d => d.near_samples) : null,
        dist: sum(D, d => d.cohesion_samples) >= COHESION_MIN_SAMPLES * 3 ? sum(D, d => d.cohesion_sum) / sum(D, d => d.cohesion_samples) : null,
        life: (() => { const L = D.filter(d => avgLife(d)); return sum(L, d => d.lives) ? sum(L, d => d.alive_seconds) / sum(L, d => d.lives) : null; })(),
        tk: sum(D, d => d.total_kills) >= 30 ? sum(D, d => d.total_teamkills) / sum(D, d => d.total_kills) * 100 : null,
        clutch: dr ? sum(D, d => d.total_clutch_kills) / dr : null,
        streak: D.length ? Math.max(...D.map(d => d.best_killstreak || 0)) : null,
        active: members.filter(p => p['Active 30d']).length,
    };
    // Roles: "juega de" = el mejor rol de cada uno; "puede cubrir" = cuántos jugaron
    // ese rol de verdad (10+ rondas con confianza media o alta y al menos el 10 % de
    // su actividad: jugarlo de vez en cuando no alcanza).
    sq.roles = {};
    sq.coverCount = {};
    demos.forEach(({ d }) => {
        if (d.best_role) {
            const label = roleLabel(d, d.best_role);
            sq.roles[label] = (sq.roles[label] || 0) + 1;
        }
        const plays = new Set((d.roles || []).filter(r => r.eligible && (r.share || 0) >= 0.1).map(r => r.key));
        NEEDED.forEach(([keys, label]) => { if (keys.some(k => plays.has(k))) sq.coverCount[label] = (sq.coverCount[label] || 0) + 1; });
    });
    sq.noDemos = members.length - demos.length;
    sq.missing = demos.length ? NEEDED.map(([, l]) => l).filter(l => !sq.coverCount[l]) : [];
    const m = medians();
    sq.model = {
        ps: avg(members, p => shrunk(p, 'Performance Score', m.ps)),
        kd: avg(members, p => shrunk(p, 'K/D Ratio', m.kd)),
        kpr: avg(members, p => shrunk(p, 'Kills per Round', m.kpr)),
    };
    sq.few = members.filter(p => (p.Rounds || 0) < FEW_ROUNDS);
    // Sinergia: pares de la escuadra que jugaron juntos en la misma escuadra del juego.
    const names = new Set(members.map(p => p.Player));
    let pairs = 0, pr = 0, pw = 0;
    const seen = new Set();
    members.forEach((p) => {
        const mates = synergy?.[p.Player]?.mates || {};
        Object.entries(mates).forEach(([q, s]) => {
            if (!names.has(q) || s.rounds < MIN_PAIR_ROUNDS) return;
            const key = [p.Player, q].sort().join('|');
            if (seen.has(key)) return;
            seen.add(key); pairs += 1; pr += s.rounds; pw += s.wins;
        });
    });
    const possible = members.length * (members.length - 1) / 2;
    sq.chem = { pairs, possible, share: possible ? pairs / possible : 0, rounds: pr, winrate: pr ? pw / pr : null };
    const w = weights();
    sq.score = w.ps * sq.model.ps + w.kd * (sq.model.kd / NORM_CAPS.kd) + w.kpr * (sq.model.kpr / NORM_CAPS.kpr);
    return sq;
}

function buildAll(onlyActive, synergy) {
    const byClan = new Map();
    (state.playersData || []).forEach((p) => {
        if (!p.Clan || (p.Rounds || 0) < MIN_ROUNDS) return;
        if (onlyActive && !p['Active 30d']) return;
        if (!byClan.has(p.Clan)) byClan.set(p.Clan, []);
        byClan.get(p.Clan).push(p);
    });
    const squads = [];
    byClan.forEach((list, clan) => {
        list.sort((a, b) => (b['Performance Score'] || 0) - (a['Performance Score'] || 0));
        const members = list.slice(0, SIZE);
        if (members.length >= MIN_MEMBERS) squads.push(buildSquad(clan, members, synergy));
    });
    return squads;
}

const SORTS = {
    score: ['Fuerza (predictor)', sq => sq.score],
    ps: ['Performance', sq => sq.ps],
    kd: ['K/D', sq => sq.kd],
    winrate: ['Winrate', sq => sq.winrate ?? -1],
    chem: ['Pares que jugaron juntos', sq => sq.chem.share],
};

function rolesHTML(sq) {
    if (!sq.demos.length) {
        return '<span class="sq-role">Sin datos de partidas: no se pueden ver los roles</span>';
    }
    const plays = Object.entries(sq.roles).sort((a, b) => b[1] - a[1])
        .map(([label, n]) => `<span class="sq-role">${n}× ${escapeHtml(label)}</span>`).join('');
    const cover = NEEDED.map(([, label]) => {
        const n = sq.coverCount[label] || 0;
        return `<span class="sq-role ${n ? 'is-ok' : 'is-miss'}">${escapeHtml(label)}: ${n ? `${n} ${n === 1 ? 'jugador' : 'jugadores'}` : 'nadie'}</span>`;
    }).join('');
    const nod = sq.noDemos ? `<span class="sq-sub">${sq.noDemos} sin datos de partidas</span>` : '';
    return `<div class="sq-roles-row"><span class="sq-roles-lbl">Juega de</span>${plays || '<span class="sq-sub">—</span>'}</div>
        <div class="sq-roles-row"><span class="sq-roles-lbl">Puede cubrir</span>${cover}${nod}</div>`;
}

function rankingHTML(squads, sortKey) {
    const [label, fn] = SORTS[sortKey] || SORTS.score;
    const list = [...squads].sort((a, b) => fn(b) - fn(a));
    const top = Math.max(...list.map(s => s.score), 0.0001);
    const rows = list.map((sq, i) => `
        <tr class="sq-row" data-clan="${escapeHtml(sq.clan)}">
            <td>${posHTML(i + 1)}</td>
            <td><span class="sq-clan">${clanLogoHTML(sq.clan, 20)} ${escapeHtml(sq.clan)}</span><span class="sq-sub">${sq.members.length} jugadores · ${sq.active} de ${sq.members.length} activos</span></td>
            <td class="sq-barcell">${barHTML(sq.score / top * 100)}<span class="sq-sub">${(sq.score * 100).toFixed(1).replace('.', ',')}</span></td>
            <td class="n">${tierChipHTML(sq.ps)} ${f2(sq.ps)}</td>
            <td class="n">${f2(sq.kd)}</td>
            <td class="n">${f2(sq.kpr)}</td>
            <td class="n">${pct(sq.winrate)}</td>
            <td class="n">${sq.chem.pairs}/${sq.chem.possible}</td>
            <td><button type="button" class="sq-open" data-clan="${escapeHtml(sq.clan)}">Ver escuadra</button></td>
        </tr>`).join('');
    return `<div class="rankings-header">${list.length} escuadras · ordenadas por ${escapeHtml(label)}</div>
        <div class="pv-scroll"><table class="pv-table sq-table">
            <thead><tr><th>#</th><th>Clan</th><th>Fuerza (de 100)</th><th class="n">Performance</th><th class="n">K/D</th><th class="n">Kills/ronda</th><th class="n">Winrate</th><th class="n">Pares que jugaron juntos</th><th></th></tr></thead>
            <tbody>${rows}</tbody>
        </table></div>
        <p class="rankings-excluded">Escuadra = los ${SIZE} jugadores con más Performance de cada clan (${MIN_ROUNDS}+ rondas). Fuerza (de 100) = el cálculo del predictor de Equipos: Performance, K/D y kills por ronda de cada jugador, ajustados por muestra. Pares que jugaron juntos: de los 28 pares posibles, cuántos compartieron escuadra en ${MIN_PAIR_ROUNDS}+ rondas con demo. ${glossaryLinkHTML()}</p>`;
}

const logo = (sq, size) => (sq.isClan ? clanLogoHTML(sq.clan, size) : '');

/** Plantilla con todas las estadísticas del grupo. */
export function rosterHTML(sq, closable = true) {
    const rows = sq.members.map((p) => {
        const d = getDemoInfo(p.Player);
        const role = d?.best_role ? roleLabel(d, d.best_role) : '—';
        const g = d ? (d.wins || 0) + (d.losses || 0) : 0;
        return `<tr>
            <td><span class="dtable-name">${playerLinkHTML(p.Player)}</span></td>
            <td>${tierChipHTML(p['Performance Score'])}</td>
            <td class="n">${f2(p['Performance Score'])}</td>
            <td class="n">${f2(p['K/D Ratio'])}</td>
            <td class="n">${f2(p['Kills per Round'])}</td>
            <td class="n">${g >= 10 ? pct(d.wins / g) : '—'}</td>
            <td>${escapeHtml(role)}</td>
            <td>${p['Active 30d'] ? '<span class="sq-on">activo</span>' : '<span class="sq-sub">inactivo</span>'}</td>
        </tr>`;
    }).join('');
    const stat = (label, v) => `<div class="sq-stat"><span class="kpi-label">${label}</span><b>${v}</b></div>`;
    return `<div class="sq-roster card">
        <div class="pv-head"><h4 class="profile-subtitle">${logo(sq, 22)} ${sq.isClan ? 'Escuadra ' : ''}${escapeHtml(sq.clan)}</h4>
            ${closable ? '<button type="button" class="sq-close">Cerrar</button>' : ''}</div>
        <div class="sq-stats">
            ${stat('Performance', f2(sq.ps))}${stat('K/D', f2(sq.kd))}${stat('Kills/ronda', f2(sq.kpr))}${stat('Score/ronda', formatNumber(Math.round(sq.spr)))}
            ${stat('Winrate (demos)', `${pct(sq.winrate)}<small> ${sq.record[0]} ganadas, ${sq.record[1]} perdidas</small>`)}${stat('Revives/ronda', sq.revives == null ? '—' : f2(sq.revives))}
            ${sq.near == null ? '' : stat('Junto a su escuadra', pct(sq.near))}${stat('Distancia a su escuadra', sq.dist == null ? '—' : `${Math.round(sq.dist)} m`)}${stat('Vida promedio', sq.life ? fmtDuration(sq.life) : '—')}
            ${stat('Teamkills c/100 kills', sq.tk == null ? '—' : sq.tk.toFixed(1).replace('.', ','))}${stat('Mejor racha', sq.streak == null ? '—' : `${sq.streak} kills`)}
            ${stat('Pares que jugaron juntos', `${sq.chem.pairs} de ${sq.chem.possible}`)}${stat('Winrate juntos', pct(sq.chem.winrate))}
        </div>
        <div class="sq-roles">${rolesHTML(sq)}</div>
        <div class="pv-scroll"><table class="pv-table">
            <thead><tr><th>Jugador</th><th>Tier</th><th class="n">Performance</th><th class="n">K/D</th><th class="n">Kills/ronda</th><th class="n">Winrate</th><th>Mejor rol</th><th>Actividad</th></tr></thead>
            <tbody>${rows}</tbody>
        </table></div>
    </div>`;
}

// [etiqueta, valor, formato, más es mejor]. Tres grupos: lo que usa la
// probabilidad, el resto del rendimiento (se cuenta quién gana más) y contexto
// (experiencia y actividad: se muestra, no se cuenta).
const VS_MODEL = [
    ['Performance (ajustada)', sq => sq.model.ps, f2, true],
    ['K/D promedio (ajustado)', sq => sq.model.kd, f2, true],
    ['Kills por ronda (ajustadas)', sq => sq.model.kpr, f2, true],
];
const VS_CONTEXT = [
    ['Rondas promedio', sq => sq.rounds, v => formatNumber(Math.round(v)), true],
    ['Jugadores activos (30 días)', sq => sq.active, v => String(v), true],
];
const VS_ROWS = [
    ['K/D del grupo (kills / muertes totales)', sq => sq.kd, f2, true],
    ['Score por ronda', sq => sq.spr, v => formatNumber(Math.round(v)), true],
    ['Winrate (demos)', sq => sq.winrate, pct, true],
    ['Revives por ronda', sq => sq.revives, f2, true],
    ['Teamwork (parte del score)', sq => sq.teamwork, pct, true],
    ['Junto a su escuadra (compañero a ≤ 50 m)', sq => sq.near, pct, true],
    ['Distancia al centro de su escuadra', sq => sq.dist, v => `${Math.round(v)} m`, false],
    ['Vida promedio', sq => sq.life, v => fmtDuration(v), true],
    ['Teamkills c/100 kills', sq => sq.tk, v => v.toFixed(1).replace('.', ','), false],
    ['Clutch kills por ronda', sq => sq.clutch, f2, true],
    ['Pares que jugaron juntos', sq => sq.chem.share, v => pct(v), true],
    ['Winrate jugando juntos', sq => sq.chem.winrate, pct, true],
];

/** Filas de comparación; `tally` = [ganadas A, ganadas B, empates] o null (no cuenta). */
function vsRows(defs, a, b, tally) {
    return defs.map(([label, fn, fmt, hb]) => {
        const v1 = fn(a), v2 = fn(b);
        if (v1 == null && v2 == null) return '';   // métrica sin dato todavía (p.ej. junto a la escuadra)
        if (v1 == null || v2 == null) {
            const none = '<span class="sq-sub">sin datos de partidas</span>';
            return `<div class="compare-row"><span class="compare-cell">${v1 == null ? none : fmt(v1)}</span><span class="compare-metric">${escapeHtml(label)}</span><span class="compare-cell">${v2 == null ? none : fmt(v2)}</span></div>`;
        }
        const tie = fmt(v1) === fmt(v2);
        const better1 = !tie && (hb ? v1 > v2 : v1 < v2), better2 = !tie && !better1;
        if (tally) { if (tie) tally[2] += 1; else if (better1) tally[0] += 1; else tally[1] += 1; }
        return `<div class="compare-row">
            <span class="compare-cell ${better1 ? 'compare-winner' : ''}">${fmt(v1)}</span>
            <span class="compare-metric">${escapeHtml(label)}${versusBarHTML(v1, v2, hb)}</span>
            <span class="compare-cell ${better2 ? 'compare-winner' : ''}">${fmt(v2)}</span>
        </div>`;
    }).join('');
}

/** Comparación A vs B con la probabilidad del predictor. `bySize`: equipos armados
 *  a mano (el más chico suma menos). */
export function versusHTML(a, b, bySize = false) {
    const pa = winProb(a, b, bySize);
    const pf = Math.max(pa, 1 - pa), fav = pa >= 0.5 ? a : b;
    const tally = [0, 0, 0];
    const model = vsRows(VS_MODEL, a, b, null);
    const rest = vsRows(VS_ROWS, a, b, tally);
    const ctx = vsRows(VS_CONTEXT, a, b, null);
    const verdict = pf < 0.55
        ? `Parejo (${Math.round(pa * 100)}–${Math.round((1 - pa) * 100)})`
        : `Favorita: <strong>${escapeHtml(fav.clan)}</strong> con ${Math.round(pf * 100)} %, ${probBand(pf)}`;
    const notes = [];
    if (bySize && a.members.length !== b.members.length) {
        notes.push(`Equipos de distinto tamaño (${a.members.length} contra ${b.members.length}): el más chico suma menos.`);
    }
    const few = [...a.few, ...b.few];
    if (few.length) {
        notes.push(`Con menos de ${FEW_ROUNDS} rondas cuentan cerca del promedio de la comunidad: ${few.map(p => `${escapeHtml(p.Player)} (${p.Rounds || 0})`).join(', ')}.`);
    }
    const sec = (title, sub) => `<div class="sq-vs-sec"><b>${title}</b>${sub ? `<span class="sq-sub">${sub}</span>` : ''}</div>`;
    return `<div class="compare-header">
            <span class="compare-entity side-1">${logo(a, 24)} ${escapeHtml(a.clan)}</span>
            <span class="compare-vs">VS</span>
            <span class="compare-entity side-2">${logo(b, 24)} ${escapeHtml(b.clan)}</span>
        </div>
        <div class="compare-verdict">${verdict}</div>
        <div class="sq-prob"><span style="width:${(pa * 100).toFixed(1)}%"></span></div>
        <div class="sq-prob-lbl"><span>${escapeHtml(a.clan)} ${Math.round(pa * 100)} %</span><span>${Math.round((1 - pa) * 100)} % ${escapeHtml(b.clan)}</span></div>
        <p class="sq-scale">Cómo leerlo: hasta 55 % es parejo · 55–65 % ventaja leve · 65–80 % ventaja clara · más de 80 % muy desbalanceado.</p>
        ${notes.length ? `<ul class="sq-notes">${notes.map(n => `<li>${n}</li>`).join('')}</ul>` : ''}
        <div class="compare-table">
            ${sec('Lo que usa la probabilidad', 'promedio de cada equipo, ajustado por muestra')}${model}
            ${sec('Otras métricas', `no entran en la probabilidad · ${escapeHtml(a.clan)} gana ${tally[0]}, ${escapeHtml(b.clan)} ${tally[1]}${tally[2] ? `, ${tally[2]} empate${tally[2] > 1 ? 's' : ''}` : ''}`)}${rest}
            ${sec('Contexto', 'experiencia y actividad: no se cuentan')}${ctx}
        </div>
        <div class="sq-vs-roles"><div>${rolesHTML(a)}</div><div>${rolesHTML(b)}</div></div>`;
}

/** Reparte los jugadores en dos equipos del mismo tamaño lo más parejos posible
 *  (prueba todas las combinaciones: con 16 jugadores son 12.870). */
export function balanceTeams(players) {
    const n = players.length;
    if (n < 2 || n > 16) return null;
    // La fuerza del equipo es el promedio de la de cada jugador: se calcula una vez.
    const s = players.map(strength);
    const total = s.reduce((x, y) => x + y, 0);
    const half = Math.floor(n / 2), big = n - half;
    let best = null;
    const pick = [];
    const rec = (start) => {
        if (pick.length === half) {
            const sa = pick.reduce((x, i) => x + s.at(i), 0);
            // Mismo cálculo que winProb con tamaño: cada equipo suma / el más grande.
            const d = Math.abs(sa / big - (total - sa) / big);
            if (!best || d < best.d) {
                const set = new Set(pick);
                best = { d, A: pick.map(i => players.at(i)), B: players.filter((_, i) => !set.has(i)) };
            }
            return;
        }
        for (let i = start; i <= n - (half - pick.length); i++) {
            if (n % 2 === 0 && pick.length === 0 && i > 0) break;   // el primero siempre en A: evita espejos
            pick.push(i); rec(i + 1); pick.pop();
        }
    };
    rec(0);
    return best;
}

let squads = [];

function fillSelects() {
    const opts = [...squads].sort((x, y) => x.clan.localeCompare(y.clan))
        .map(sq => `<option value="${escapeHtml(sq.clan)}">${escapeHtml(sq.clan)}</option>`).join('');
    ['squad-a', 'squad-b'].forEach((id, k) => {
        const sel = document.getElementById(id);
        if (!sel) return;
        const prev = sel.value;
        sel.innerHTML = opts;
        const ranked = [...squads].sort((x, y) => y.score - x.score);
        sel.value = squads.some(s => s.clan === prev) ? prev : (ranked[k] || ranked[0])?.clan;
    });
}

function renderVersus() {
    const out = document.getElementById('squad-vs-results');
    const a = squads.find(s => s.clan === document.getElementById('squad-a')?.value);
    const b = squads.find(s => s.clan === document.getElementById('squad-b')?.value);
    if (!out) return;
    out.innerHTML = a && b && a !== b ? versusHTML(a, b) : '<div class="empty-state">Elegí dos clanes distintos.</div>';
}

async function render() {
    const results = document.getElementById('squad-results');
    if (!results) return false;
    results.innerHTML = '<div class="empty-state">Armando las escuadras…</div>';
    try { await loadDemoData(); } catch (_) { /* las demos son opcionales */ }
    const synergy = await loadSynergy().catch(() => null);
    const onlyActive = document.getElementById('squad-scope')?.value === 'activos';
    squads = buildAll(onlyActive, synergy);
    if (!squads.length) {
        results.innerHTML = '<div class="empty-state">No hay clanes con suficientes jugadores.</div>';
        return true;
    }
    results.innerHTML = rankingHTML(squads, document.getElementById('squad-sort')?.value || 'score')
        + '<div id="squad-roster"></div>';
    fillSelects();
    renderVersus();
    return true;
}

export function initSquads() {
    const section = document.getElementById('clan-squads');
    if (!section) return;
    let rendered = false;
    const ensure = async () => { if (!rendered) rendered = await render(); };
    ['squad-scope', 'squad-sort'].forEach(id => document.getElementById(id)
        ?.addEventListener('change', () => { if (rendered) render(); }));
    ['squad-a', 'squad-b'].forEach(id => document.getElementById(id)?.addEventListener('change', renderVersus));
    section.addEventListener('click', (e) => {
        const open = e.target.closest('.sq-open');
        const box = document.getElementById('squad-roster');
        if (open && box) {
            const sq = squads.find(s => s.clan === open.dataset.clan);
            if (sq) { box.innerHTML = rosterHTML(sq); box.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }
        }
        if (e.target.closest('.sq-close') && box) box.innerHTML = '';
    });
    if (typeof IntersectionObserver !== 'undefined') {
        const obs = new IntersectionObserver((entries) => {
            if (entries.some(en => en.isIntersecting)) ensure().then(() => { if (rendered) obs.disconnect(); });
        }, { threshold: 0.05 });
        obs.observe(section);
    } else {
        ensure();
    }
}
