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
import { escapeHtml, formatNumber, clanLogoHTML, fmtDuration } from './utils.js';
import { barHTML, versusBarHTML, tierChipHTML, posHTML } from './ui.js';

const SIZE = 8;
const MIN_ROUNDS = 50;
const MIN_MEMBERS = 5;          // menos que esto no es una escuadra para rankear
const MIN_PAIR_ROUNDS = 3;      // rondas juntos para contar un par en la sinergia

// Lo que una escuadra de infantería necesita tener (manual de campo / guía de líder).
// "apoyo" es el kit de AR y "ametrallador" el de MG: cualquiera de los dos cubre.
const NEEDED = [[['oficial'], 'Oficial'], [['medico'], 'Médico'], [['apoyo', 'ametrallador'], 'AR o MG'], [['at'], 'Anti-tanque']];

/** Etiqueta del rol tal como la trae la demo (Médico, Apoyo, Anti-tanque…). */
function roleLabel(d, key) {
    return d?.roles?.find(r => r.key === key)?.label || key;
}

const f2 = (v) => formatNumber(Number((v || 0).toFixed(2)));
const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)} %`);
const sum = (arr, fn) => arr.reduce((s, x) => s + (fn(x) || 0), 0);
const avg = (arr, fn) => (arr.length ? sum(arr, fn) / arr.length : null);

/** Probabilidad del predictor (PS, K/D, KPR renormalizados), como en Equipos. */
function composite(sq) {
    const w = state.tierConfigData?.predictor_weights;
    let ps = 0.5, kd = 0.3, kpr = 0.2;
    if (w && (w.ps + w.kd + w.kpr) > 0) {
        const t = w.ps + w.kd + w.kpr;
        ps = w.ps / t; kd = w.kd / t; kpr = w.kpr / t;
    }
    return ps * sq.ps + kd * (sq.kdAvg / NORM_CAPS.kd) + kpr * (sq.kpr / NORM_CAPS.kpr);
}

function buildSquad(clan, members, synergy) {
    const demos = members.map(p => ({ p, d: getDemoInfo(p.Player) })).filter(x => x.d && x.d.rounds_played);
    const D = demos.map(x => x.d);
    const kills = sum(members, p => p['Total Kills']), deaths = sum(members, p => p['Total Deaths']);
    const wins = sum(D, d => d.wins), losses = sum(D, d => d.losses);
    const dr = sum(D, d => d.rounds_played);
    const sq = {
        clan, members, demos,
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
        inSquad: sum(D, d => d.rounds_with_squad_data) >= 10 ? sum(D, d => d.rounds_in_squad) / sum(D, d => d.rounds_with_squad_data) : null,
        life: sum(D, d => d.lives) ? sum(D, d => d.alive_seconds) / sum(D, d => d.lives) : null,
        tk: sum(D, d => d.total_kills) >= 30 ? sum(D, d => d.total_teamkills) / sum(D, d => d.total_kills) * 100 : null,
        clutch: dr ? sum(D, d => d.total_clutch_kills) / dr : null,
        streak: D.length ? Math.max(...D.map(d => d.best_killstreak || 0)) : null,
        active: members.filter(p => p['Active 30d']).length,
    };
    // Roles: el mejor rol de cada uno, y qué roles puede cubrir la escuadra
    // (alguien con 10+ rondas y confianza media o alta en ese rol).
    sq.roles = {};
    sq.covers = new Set();
    demos.forEach(({ d }) => {
        if (d.best_role) {
            const label = roleLabel(d, d.best_role);
            sq.roles[label] = (sq.roles[label] || 0) + 1;
        }
        (d.roles || []).forEach(r => { if (r.eligible) sq.covers.add(r.key); });
    });
    sq.missing = NEEDED.filter(([keys]) => !keys.some(k => sq.covers.has(k))).map(([, l]) => l);
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
    sq.score = composite(sq);
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
    chem: ['Sinergia', sq => sq.chem.share],
};

function rolesHTML(sq) {
    const chips = Object.entries(sq.roles).sort((a, b) => b[1] - a[1])
        .map(([label, n]) => `<span class="sq-role">${n}× ${escapeHtml(label)}</span>`).join('');
    const miss = sq.missing.length
        ? `<span class="sq-role is-miss">Nadie cubre: ${escapeHtml(sq.missing.join(', '))}</span>`
        : '<span class="sq-role is-ok">Cubre oficial, médico, AR/MG y AT</span>';
    return chips + miss;
}

function rankingHTML(squads, sortKey) {
    const [label, fn] = SORTS[sortKey] || SORTS.score;
    const list = [...squads].sort((a, b) => fn(b) - fn(a));
    const top = Math.max(...list.map(s => s.score), 0.0001);
    const rows = list.map((sq, i) => `
        <tr class="sq-row" data-clan="${escapeHtml(sq.clan)}">
            <td>${posHTML(i + 1)}</td>
            <td><span class="sq-clan">${clanLogoHTML(sq.clan, 20)} ${escapeHtml(sq.clan)}</span><span class="sq-sub">${sq.members.length}/${SIZE} · ${sq.active} activos</span></td>
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
            <thead><tr><th>#</th><th>Clan</th><th>Fuerza</th><th class="n">Performance</th><th class="n">K/D</th><th class="n">Kills/ronda</th><th class="n">Winrate</th><th class="n">Pares que jugaron juntos</th><th></th></tr></thead>
            <tbody>${rows}</tbody>
        </table></div>
        <p class="rankings-excluded">Escuadra = los ${SIZE} jugadores con más Performance de cada clan (${MIN_ROUNDS}+ rondas). Fuerza = el mismo cálculo del predictor de Equipos (Performance, K/D y kills por ronda). Pares que jugaron juntos: de los 28 pares posibles, cuántos compartieron escuadra en ${MIN_PAIR_ROUNDS}+ rondas con demo.</p>`;
}

function rosterHTML(sq) {
    const rows = sq.members.map((p) => {
        const d = getDemoInfo(p.Player);
        const role = d?.best_role ? roleLabel(d, d.best_role) : '—';
        const g = d ? (d.wins || 0) + (d.losses || 0) : 0;
        return `<tr>
            <td><span class="dtable-name">${escapeHtml(p.Player)}</span></td>
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
        <div class="pv-head"><h4 class="profile-subtitle">${clanLogoHTML(sq.clan, 22)} Escuadra ${escapeHtml(sq.clan)}</h4>
            <button type="button" class="sq-close">Cerrar</button></div>
        <div class="sq-stats">
            ${stat('Performance', f2(sq.ps))}${stat('K/D', f2(sq.kd))}${stat('Kills/ronda', f2(sq.kpr))}${stat('Score/ronda', formatNumber(Math.round(sq.spr)))}
            ${stat('Winrate (demos)', `${pct(sq.winrate)}<small> ${sq.record[0]}–${sq.record[1]}</small>`)}${stat('Revives/ronda', sq.revives == null ? '—' : f2(sq.revives))}
            ${stat('En escuadra', pct(sq.inSquad))}${stat('Vida promedio', sq.life ? fmtDuration(sq.life) : '—')}
            ${stat('Teamkills c/100 kills', sq.tk == null ? '—' : sq.tk.toFixed(1).replace('.', ','))}${stat('Mejor racha', sq.streak ?? '—')}
            ${stat('Sinergia', `${sq.chem.pairs}/${sq.chem.possible} pares`)}${stat('Winrate juntos', pct(sq.chem.winrate))}
        </div>
        <div class="sq-roles">${rolesHTML(sq)}</div>
        <div class="pv-scroll"><table class="pv-table">
            <thead><tr><th>Jugador</th><th>Tier</th><th class="n">Performance</th><th class="n">K/D</th><th class="n">Kills/ronda</th><th class="n">Winrate</th><th>Mejor rol</th><th>Actividad</th></tr></thead>
            <tbody>${rows}</tbody>
        </table></div>
    </div>`;
}

const VS_ROWS = [
    ['Performance', sq => sq.ps, f2, true],
    ['K/D', sq => sq.kd, f2, true],
    ['Kills por ronda', sq => sq.kpr, f2, true],
    ['Score por ronda', sq => sq.spr, v => formatNumber(Math.round(v)), true],
    ['Rondas promedio', sq => sq.rounds, v => formatNumber(Math.round(v)), true],
    ['Winrate (demos)', sq => sq.winrate, pct, true],
    ['Revives por ronda', sq => sq.revives, f2, true],
    ['Teamwork (parte del score)', sq => sq.teamwork, pct, true],
    ['En escuadra', sq => sq.inSquad, pct, true],
    ['Vida promedio', sq => sq.life, v => fmtDuration(v), true],
    ['Teamkills c/100 kills', sq => sq.tk, v => v.toFixed(1).replace('.', ','), false],
    ['Clutch kills por ronda', sq => sq.clutch, f2, true],
    ['Sinergia (pares juntos)', sq => sq.chem.share, v => pct(v), true],
    ['Winrate jugando juntos', sq => sq.chem.winrate, pct, true],
    ['Jugadores activos', sq => sq.active, v => String(v), true],
];

function versusHTML(a, b) {
    const pa = a.score / (a.score + b.score || 1);
    const wins = [0, 0];
    const rows = VS_ROWS.map(([label, fn, fmt, hb]) => {
        const v1 = fn(a), v2 = fn(b);
        if (v1 == null || v2 == null) {
            return `<div class="compare-row"><span class="compare-cell">${v1 == null ? '—' : fmt(v1)}</span><span class="compare-metric">${escapeHtml(label)}</span><span class="compare-cell">${v2 == null ? '—' : fmt(v2)}</span></div>`;
        }
        const better1 = hb ? v1 > v2 : v1 < v2, better2 = hb ? v2 > v1 : v2 < v1;
        if (better1) wins[0] += 1; if (better2) wins[1] += 1;
        return `<div class="compare-row">
            <span class="compare-cell ${better1 ? 'compare-winner' : ''}">${fmt(v1)}</span>
            <span class="compare-metric">${escapeHtml(label)}${versusBarHTML(v1, v2, hb)}</span>
            <span class="compare-cell ${better2 ? 'compare-winner' : ''}">${fmt(v2)}</span>
        </div>`;
    }).join('');
    const fav = pa >= 0.5 ? a : b;
    return `<div class="compare-header">
            <span class="compare-entity side-1">${clanLogoHTML(a.clan, 24)} ${escapeHtml(a.clan)}</span>
            <span class="compare-vs">VS</span>
            <span class="compare-entity side-2">${clanLogoHTML(b.clan, 24)} ${escapeHtml(b.clan)}</span>
        </div>
        <div class="compare-verdict">Favorita: <strong>${escapeHtml(fav.clan)}</strong> con ${Math.round(Math.max(pa, 1 - pa) * 100)} % según el predictor · gana ${wins[0]} a ${wins[1]} en las métricas comparables</div>
        <div class="sq-prob"><span style="width:${(pa * 100).toFixed(1)}%"></span></div>
        <div class="sq-prob-lbl"><span>${escapeHtml(a.clan)} ${Math.round(pa * 100)} %</span><span>${Math.round((1 - pa) * 100)} % ${escapeHtml(b.clan)}</span></div>
        <div class="compare-table">${rows}</div>
        <div class="sq-vs-roles"><div>${rolesHTML(a)}</div><div>${rolesHTML(b)}</div></div>`;
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
