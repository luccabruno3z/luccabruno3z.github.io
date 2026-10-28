/* ═══════════════════════════════════════════════════════════════════════════
   player.js — player search: full profile card, radar, history, demo enrichment.
   See .rebuild/CONTRACT.md §2.3 / §4 and FEATURE_API.md (player notes).

   El perfil arma primero lo que sale de PRStats (cabecera, KPIs, de qué sale el
   Performance, contexto de clan) y después, cuando llegan las demos, completa
   forma reciente, fortalezas, roles, datos de demos y récords.
   ═══════════════════════════════════════════════════════════════════════════ */

import {
    state, loadDemoData, getDemoInfo, loadPlayerHistory, loadPlayerRounds, loadSynergy,
} from './data.js';
import {
    escapeHtml, formatNumber, findPlayer, tierBadge, getPlayerArchetype,
    experienceBadge, sampleReliability, fmtDuration, aggregateByLabel, weaponModel,
    weaponKind, sigmoidPenalty, clanLogoHTML, mapLabel, gamemodeLabel,
    avgLife, squadNear, squadDistance, squadDistanceLabel,
} from './utils.js';
import { barHTML, tierBarHTML, rankBarHTML, tierChipHTML } from './ui.js';
import { renderRadarChart, renderHistoryChart, clearPlayerCharts, clearHistoryChart } from './charts.js';
import { setupAutocomplete, playerSource } from './autocomplete.js';

const f2 = (v) => formatNumber(Number((v || 0).toFixed(2)));
const pctTxt = (frac) => `${Math.round(frac * 100)} %`;

/** Fracción de jugadores con un valor menor (0-1). */
function rankOf(value, values) {
    if (!values.length) return { below: 0 };
    return { below: values.filter(v => v < value).length / values.length };
}

/** "Top 16 %" en la mitad de arriba; abajo, "Debajo de la media · mejor que el 26 %"
 *  (un "top 74 %" se leía como algo bueno). */
function posNote(below) {
    if (below >= 0.5) return { text: `Top ${Math.max(1, Math.round((1 - below) * 100))} %`, cls: below >= 0.75 ? 'up' : 'mid' };
    return { text: `Debajo de la media · mejor que el ${Math.round(below * 100)} %`, cls: 'down' };
}

const srcTag = (src) => `<span class="pv-src ${src === 'demos' ? 'is-demo' : ''}">${src === 'demos' ? 'Demos' : 'PRStats'}</span>`;

/** Tarjeta de KPI: etiqueta, valor grande, barra, posición y una línea extra opcional. */
function kpiHTML(label, value, bar, note, { src = '', extra = '' } = {}) {
    return `<div class="kpi-card">
        <span class="kpi-label">${escapeHtml(label)}${src ? ' ' + srcTag(src) : ''}</span>
        <span class="kpi-value">${value}</span>
        ${bar}
        ${note ? `<span class="pv-pos is-${note.cls}">${escapeHtml(note.text)}</span>` : ''}
        ${extra}
    </div>`;
}

// ── De qué sale el Performance + camino al próximo tier ─────────────────────

const TIER_ORDER = [['soldado', 'Soldado'], ['experimentado', 'Experimentado'], ['veterano', 'Veterano'], ['elite', 'Elite']];
const COMP_WHAT = {
    combat: (p) => `K/D ${f2(p['K/D Ratio'])} frente al resto`,
    effectiveness: (p) => `${f2(p['Kills per Round'])} kills por ronda`,
    score: (p) => `${formatNumber(Math.round(p['Score per Round'] || 0))} de score por ronda`,
    winrate: () => 'Victorias en demos, ajustadas por muestra',
    teamwork: () => 'Parte de tu score que es teamwork',
    consistency: () => 'Qué tan parejo jugás entre rondas',
    experience: (p) => `${formatNumber(p.Rounds || 0)} rondas`,
};

// Qué hacer en el juego para subir cada componente (se muestra para los dos con más margen).
const COMP_HOW = {
    combat: ['Morí menos', 'Peleá desde cobertura y con tu escuadra cerca, no cruces abierto sin humo, y después de disparar cambiá de posición.'],
    effectiveness: ['Más kills por ronda', 'Jugá donde está la pelea: con tu escuadra sobre los objetivos activos. El kit cuenta: AR, MG y tirador matan más que un fusilero.'],
    score: ['Más score por ronda', 'Capturá y defendé banderas con tu escuadra, construí el FOB y sus defensas y destruí vehículos: todo suma score además de las kills.'],
    winrate: ['Ganá más', 'Lo que más mueve el resultado es jugar el objetivo: escuadra organizada, FOBs y rally para no perder tiempo caminando, y no regalar tickets con vehículos.'],
    teamwork: ['Más teamwork', 'El score de teamwork sale de revivir y curar, reabastecer con la bolsa de munición, reparar vehículos, construir con la pala en el FOB y llevar a tu escuadra en vehículo. Tomá el kit de médico o fusilero de vez en cuando y ayudá a armar el FOB.'],
    consistency: ['Más parejo', 'Las rondas malas pesan: buscá una escuadra con líder y comunicación, y evitá las rondas en solitario o en kits que no dominás.'],
    experience: ['Más rondas', 'Se completa jugando: cuenta cada ronda, hasta el máximo de experiencia.'],
};

function levelClass(v) {
    return v >= 0.9 ? 'tier-elite' : v >= 0.7 ? 'tier-veterano' : v >= 0.45 ? 'tier-experimentado' : v >= 0.25 ? 'tier-soldado' : 'tier-recluta';
}

/** Camino al próximo tier + tabla de los 7 componentes (publicados por el scraper). */
function performanceHTML(player) {
    const ps = player['Performance Score'] || 0;
    const t = state.tierConfigData?.thresholds;
    const defs = state.tierConfigData?.ps_components;
    const levels = player.ps_components;

    let path = '';
    let title = 'De qué sale tu Performance';
    if (t) {
        const cur = TIER_ORDER.filter(([k]) => ps >= t[k]).pop();
        const next = TIER_ORDER.find(([k]) => ps < t[k]);
        if (next) {
            title = `Camino a ${next[1]}`;
            const from = cur ? t[cur[0]] : 0;
            const prog = Math.max(0, Math.min(1, (ps - from) / (t[next[0]] - from)));
            path = `<div class="pv-path">
                <div class="pv-path-track"><span class="pv-path-dot" style="left:${(prog * 100).toFixed(1)}%"></span></div>
                <div class="pv-path-ends"><span>${escapeHtml(cur ? cur[1] : 'Recluta')} <b>${f2(from)}</b></span><span>${escapeHtml(next[1])} <b>${f2(t[next[0]])}</b></span></div>
                <p class="pv-path-msg">Te faltan <b>${(t[next[0]] - ps).toFixed(3).replace('.', ',')}</b> para ${escapeHtml(next[1])}.<span id="pv-levers"></span></p>
            </div>`;
        } else {
            title = 'Tu Performance';
            path = `<p class="pv-path-msg">Estás en <b>Elite</b>, ${(ps - t.elite).toFixed(3).replace('.', ',')} por encima del corte.</p>`;
        }
    }

    // Datos de antes de que el scraper publicara los componentes: solo el camino.
    if (!Array.isArray(defs) || !('ps_components' in player)) return { title, html: path, levers: [] };
    if (!Array.isArray(levels) || levels.length !== defs.length) {
        return { title, html: path + '<p class="profile-muted">El desglose del Performance aparece con 10+ rondas.</p>', levers: [] };
    }
    const lv = levels.map(v => (v == null ? 0.5 : v));
    const raw = defs.reduce((s, d, i) => s + lv[i] * d.weight, 0) || 1;
    const penalty = ps / raw;
    const rows = defs.map((d, i) => ({
        ...d, level: lv[i], missing: levels[i] == null,
        gives: lv[i] * d.weight * penalty, room: (1 - lv[i]) * d.weight * penalty,
    }));
    const levers = [...rows].sort((a, b) => b.room - a.room).slice(0, 2);
    const isLever = (r) => levers.includes(r);
    const n3 = (v) => v.toFixed(3).replace('.', ',');
    const table = `<div class="pv-scroll"><table class="pv-table">
        <thead><tr><th>Componente</th><th>Tu nivel</th><th class="n">Peso</th><th class="n">Aporta</th><th class="n">Podés sumar</th></tr></thead>
        <tbody>${rows.map(r => `<tr class="${isLever(r) ? 'is-lever' : ''}">
            <td><span class="pv-name">${escapeHtml(r.label)} ${srcTag(r.source)}</span>
                <span class="pv-what">${escapeHtml(r.missing ? 'Sin demos: cuenta como neutro' : COMP_WHAT[r.key]?.(player) || '')}</span></td>
            <td class="pv-barcell">${barHTML(r.level * 100, levelClass(r.level))}</td>
            <td class="n">${Math.round(r.weight * 100)} %</td>
            <td class="n">${n3(r.gives)}</td>
            <td class="n pv-room">+${n3(r.room)}</td>
        </tr>`).join('')}</tbody>
        <tfoot><tr><td colspan="3">Total</td><td class="n">${n3(ps)}</td><td></td></tr></tfoot>
    </table></div>
    <p class="profile-muted">"Podés sumar" es lo que le falta a cada componente para llegar al máximo, por su peso. Las filas marcadas son las dos con más margen.</p>`;
    const how = levers.filter(r => COMP_HOW[r.key] && r.room > 0.005).map(r => `<li><b>${escapeHtml(COMP_HOW[r.key][0])}</b> (+${n3(r.room)}): ${escapeHtml(COMP_HOW[r.key][1])}</li>`);
    const howHTML = how.length ? `<div class="pv-how"><h5>Cómo sumar</h5><ul>${how.join('')}</ul></div>` : '';
    return { title, html: path + table + howHTML, levers };
}

// ── Contexto de clan ─────────────────────────────────────────────────────────

function clanHTML(player) {
    if (!player.Clan) return '';
    const members = (state.playersData || []).filter(p => p.Clan === player.Clan);
    const pos = members.indexOf(player) + 1;  // playersData viene ordenado por Performance
    const ref = members.filter(p => (p.Rounds || 0) >= 50);
    if (!pos || ref.length < 3) return '';
    const avg = (k) => ref.reduce((s, p) => s + (p[k] || 0), 0) / ref.length;
    const rows = [
        ['Performance', 'Performance Score', f2],
        ['K/D', 'K/D Ratio', f2],
        ['Kills/ronda', 'Kills per Round', f2],
        ['Score/ronda', 'Score per Round', (v) => formatNumber(Math.round(v))],
    ].map(([label, k, fmt]) => {
        const me = player[k] || 0, a = avg(k);
        const scale = Math.max(me, a) * 1.3 || 1;
        return `<div class="pv-cmp-row">
            <span>${escapeHtml(label)}</span>
            <div class="pv-cmp-track"><span class="pv-cmp-avg" style="left:${(a / scale * 100).toFixed(1)}%"></span>
                <span class="pv-cmp-me ${me >= a ? 'is-up' : 'is-down'}" style="left:${(me / scale * 100).toFixed(1)}%"></span></div>
            <span class="pv-cmp-vals">${fmt(me)} <span>/ ${fmt(a)}</span></span>
        </div>`;
    }).join('');
    return `<section class="card pv-card">
        <h4 class="profile-subtitle">Dentro de ${escapeHtml(player.Clan)}</h4>
        <div class="pv-clan-rank"><span class="pv-big">#${pos}</span><span class="profile-muted">de ${formatNumber(members.length)} jugadores del clan</span></div>
        <div class="pv-cmp">${rows}</div>
        <p class="profile-muted">Tu valor / promedio del clan (jugadores con 50+ rondas). La línea gris marca el promedio.</p>
    </section>`;
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

    // Población de comparación: jugadores con 50+ rondas (los que entran en rankings).
    const pop = players.filter(p => (p.Rounds || 0) >= 50);
    const cmp = pop.length ? pop : players;
    const rPS = rankOf(ps, cmp.map(p => p['Performance Score'] || 0));
    const rKD = rankOf(kd, cmp.map(p => p['K/D Ratio'] || 0));
    const rKPR = rankOf(kpr, cmp.map(p => p['Kills per Round'] || 0));
    const rSPR = rankOf(spr, cmp.map(p => p['Score per Round'] || 0));

    // Penalización por muestra chica (sigmoide).
    const penalty = sigmoidPenalty(rounds);
    const warnings = [];
    if (penalty * 100 < 95) {
        const needed = Math.ceil(25 + 10 * Math.log(19)); // ~54
        const remaining = Math.max(0, needed - rounds);
        warnings.push(`Confianza del puntaje: ${(penalty * 100).toFixed(0)}%. Faltan ~${remaining} rondas para alcanzar el 95%.`);
    }
    if (rounds < 50) warnings.push('Menos de 50 rondas: el jugador no califica para los rankings.');

    const perf = performanceHTML(player);
    const clanPos = player.Clan ? (players.filter(p => p.Clan === player.Clan).indexOf(player) + 1) : 0;

    host.innerHTML = `
        <div class="profile-v2">
            <section class="card profile-hero ${tier.cssClass}-border">
                <div class="profile-logo">${player.Clan ? clanLogoHTML(player.Clan, 72) : ''}</div>
                <div class="profile-id">
                    <div class="profile-title">
                        <h3 class="profile-name">${escapeHtml(player.Player)}</h3>
                        <span class="profile-rank">#${rank} global${player.Clan ? ` · #${clanPos} en ${escapeHtml(player.Clan)}` : ''}</span>
                    </div>
                    <div class="profile-badges">
                        ${tierChipHTML(ps)}
                        <span class="profile-tag">${arch.emoji} ${escapeHtml(arch.name)}</span>
                        <span class="profile-tag">${exp.emoji} ${escapeHtml(exp.name)}</span>
                        <span class="profile-tag ${rel.cssClass}">${rel.emoji} ${escapeHtml(rel.text)}</span>
                    </div>
                    <p class="profile-desc" id="pv-reading">${escapeHtml(arch.desc || '')}</p>
                    <div class="pv-sources">
                        <span class="pv-source">PRStats · <b>${formatNumber(rounds)}</b> rondas</span>
                        <span class="pv-source" id="pv-src-demos">Demos · <b>…</b></span>
                        <span class="pv-source" id="profile-last-seen">Buscando la última partida…</span>
                    </div>
                </div>
            </section>

            ${warnings.map(w => `<div class="profile-warning">⚠️ ${escapeHtml(w)}</div>`).join('')}

            <div class="kpi-grid">
                ${kpiHTML('Performance', f2(ps), tierBarHTML(ps), posNote(rPS.below))}
                ${kpiHTML('K/D', f2(kd), rankBarHTML(rKD.below), posNote(rKD.below), { src: 'prstats', extra: '<span class="pv-alt" id="pv-kd-demo"></span>' })}
                ${kpiHTML('Kills por ronda', f2(kpr), rankBarHTML(rKPR.below), posNote(rKPR.below), { src: 'prstats' })}
                ${kpiHTML('Score por ronda', formatNumber(Math.round(spr)), rankBarHTML(rSPR.below), posNote(rSPR.below), { src: 'prstats' })}
            </div>

            <div class="profile-grid">
                <section class="card pv-card">
                    <h4 class="profile-subtitle">${escapeHtml(perf.title)}</h4>
                    ${perf.html}
                </section>
                <div class="pv-stack">
                    <section class="card pv-card" id="pv-form">
                        <h4 class="profile-subtitle">Forma reciente</h4>
                        <p class="profile-muted">Cargando rondas…</p>
                    </section>
                    ${clanHTML(player)}
                </div>
            </div>

            <section class="card pv-card" id="pv-glance" hidden></section>
            <section class="card pv-card" id="pv-roles" hidden></section>
            <section class="card pv-card" id="pv-insights" hidden></section>
            <section class="card pv-card" id="pv-history" hidden></section>
            <section class="card profile-records" id="profile-demo-block">
                <h4 class="profile-subtitle">Récords</h4>
                <p class="profile-muted">Cargando datos de demos…</p>
            </section>
        </div>`;

    const leversEl = document.getElementById('pv-levers');
    if (leversEl && perf.levers.length) {
        leversEl.textContent = ` Donde más podés sumar: ${perf.levers.map(l => l.label).join(' y ')}.`;
    }

    // Radar vs clan average.
    renderRadarChart(player, player.Clan);

    // Demo enrichment (keyed by ign). Best-effort.
    enrichWithDemo(player, cmp);

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

const ddmm = (iso) => { const [, m, d] = String(iso || '').split('-'); return d && m ? `${d}/${m}` : ''; };

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

// ── Bloques de demos ─────────────────────────────────────────────────────────

/** K/D de las últimas 10 rondas sobre el del jugador en demos (null con < 5 rondas). */
function formTrend(pr, d) {
    const list = (pr && Array.isArray(pr.rounds) ? pr.rounds : []).slice(-10);
    if (list.length < 5) return null;
    const k = list.reduce((s, r) => s + (r.kills || 0), 0), de = list.reduce((s, r) => s + (r.deaths || 0), 0);
    const now = k / Math.max(de, 1), base = (d.total_kills || 0) / Math.max(d.total_deaths || 0, 1);
    return base > 0 ? now / base : null;
}

/** Últimas 10 rondas contra el promedio del jugador en demos. */
function formHTML(pr, d) {
    const list = (pr && Array.isArray(pr.rounds) ? pr.rounds : []).slice(-10);
    if (list.length < 5) return '<h4 class="profile-subtitle">Forma reciente</h4><p class="profile-muted">Hacen falta 5+ rondas con demo.</p>';
    const k = list.reduce((s, r) => s + (r.kills || 0), 0), de = list.reduce((s, r) => s + (r.deaths || 0), 0);
    const wins = list.filter(r => r.won).length;
    const max = Math.max(...list.map(r => r.kills || 0), 1);
    const baseKD = (d.total_kills || 0) / Math.max(d.total_deaths || 0, 1);
    const baseKPR = (d.total_kills || 0) / Math.max(d.rounds_played || 0, 1);
    const g = (d.wins || 0) + (d.losses || 0), baseWR = g ? d.wins / g : null;
    const delta = (now, base, digits) => {
        const diff = now - base;
        const cls = Math.abs(diff) < 0.05 * Math.max(base, 0.01) ? 'is-flat' : diff > 0 ? 'is-up' : 'is-down';
        return `<span class="pv-delta ${cls}">${diff >= 0 ? '+' : ''}${diff.toFixed(digits).replace('.', ',')} vs ${base.toFixed(digits).replace('.', ',')}</span>`;
    };
    const bars = list.map(r => `<div class="pv-spark-col" title="${escapeHtml(`${mapLabel(r.map || '')} · ${r.kills || 0} kills · ${r.won ? 'victoria' : 'derrota'}`)}">
        <span class="pv-spark-k" style="height:${((r.kills || 0) / max * 100).toFixed(0)}%"></span>
        <span class="pv-spark-r ${r.won ? 'is-win' : 'is-loss'}"></span></div>`).join('');
    return `<div class="pv-head"><h4 class="profile-subtitle">Forma reciente</h4><span class="profile-muted">Últimas ${list.length} rondas con demo</span></div>
        <div class="pv-spark" role="img" aria-label="Kills por ronda en las últimas rondas: ${list.map(r => r.kills || 0).join(', ')}">${bars}</div>
        <div class="pv-spark-axis"><span>${ddmm(list[0].date)}</span><span>Kills por ronda · verde victoria, rojo derrota</span><span>${ddmm(list[list.length - 1].date)}</span></div>
        <div class="pv-vs"><span>K/D</span><b>${f2(k / Math.max(de, 1))}</b>${delta(k / Math.max(de, 1), baseKD, 2)}</div>
        <div class="pv-vs"><span>Kills por ronda</span><b>${(k / list.length).toFixed(1).replace('.', ',')}</b>${delta(k / list.length, baseKPR, 1)}</div>
        <div class="pv-vs"><span>Victorias</span><b>${wins} de ${list.length}</b>${baseWR == null ? '' : `<span class="profile-muted">tu promedio: ${pctTxt(baseWR)}</span>`}</div>`;
}

const HISTORY_PAGE = 15;

/** Historial de partidas (las más nuevas primero). Las rondas viejas no traen
 *  servidor, hora, bando ni kit: esas celdas quedan con "—". */
function historyHTML(pr, shown = HISTORY_PAGE) {
    // Sin kills, muertes ni score: entró y se fue (o se quedó en el menú), no la jugó.
    const all = (pr && Array.isArray(pr.rounds) ? pr.rounds : [])
        .filter(r => r.kills || r.deaths || r.score).reverse();
    if (!all.length) return '';
    const dash = '<span class="pv-sub">—</span>';
    const rows = all.slice(0, shown).map((r) => {
        const kd = (r.kills || 0) / Math.max(r.deaths || 0, 1);
        return `<tr>
            <td class="pv-nowrap">${escapeHtml(ddmm(r.date))}/${escapeHtml(String(r.date || '').slice(2, 4))}${r.time ? `<span class="pv-sub">${escapeHtml(r.time)}</span>` : ''}</td>
            <td><span class="dtable-name">${escapeHtml(mapLabel(r.map || ''))}</span><span class="pv-sub">${escapeHtml(gamemodeLabel(r.gamemode) || '')}</span></td>
            <td>${r.server ? escapeHtml(r.server) : dash}</td>
            <td>${r.kit ? escapeHtml(r.kit) : dash}${r.faction ? `<span class="pv-sub">${escapeHtml(r.faction)}</span>` : ''}</td>
            <td class="n">${r.kills || 0}–${r.deaths || 0}<span class="pv-sub">K/D ${f2(kd)}</span></td>
            <td class="n">${formatNumber(r.score || 0)}</td>
            <td class="n">${r.revives == null ? dash : r.revives}</td>
            <td>${r.won ? '<span class="round-win">Victoria</span>' : '<span class="round-loss">Derrota</span>'}</td>
        </tr>`;
    }).join('');
    const more = all.length > shown
        ? `<button type="button" class="sq-open pv-history-more" data-shown="${shown}">Ver ${Math.min(HISTORY_PAGE, all.length - shown)} más</button>` : '';
    return `<div class="pv-head"><h4 class="profile-subtitle">Historial de partidas</h4>
            <span class="profile-muted">${formatNumber(all.length)} rondas con demo · mostrando ${Math.min(shown, all.length)}</span></div>
        <div class="pv-scroll"><table class="pv-table">
            <thead><tr><th>Fecha</th><th>Mapa y modo</th><th>Servidor</th><th>Kit y bando</th><th class="n">K–D</th><th class="n">Score</th><th class="n">Revives</th><th>Resultado</th></tr></thead>
            <tbody>${rows}</tbody>
        </table></div>${more}`;
}

/** Métricas de demos para fortalezas / a mejorar: [clave, valor(d), más es mejor]. */
const GLANCE = [
    { key: 'winrate', label: 'Ganás seguido', weak: 'Te cuesta ganar', val: d => { const g = (d.wins || 0) + (d.losses || 0); return g >= 10 ? d.wins / g : null; },
      fmt: v => pctTxt(v), unit: 'de victorias', tip: 'Jugar en escuadra y sobre los objetivos es lo que más mueve el winrate.',
      say: { que: 'gana seguido' }, sayWeak: 'pierde seguido' },
    { key: 'kd', label: 'Letal', weak: 'Morís más de lo que matás', val: d => (d.total_kills || 0) / Math.max(d.total_deaths || 0, 1),
      fmt: v => f2(v), unit: 'K/D en demos', tip: 'Elegí mejor los enfrentamientos y moverte con cobertura.',
      say: { adj: 'letal' }, sayWeak: 'muere más de lo que mata' },
    { key: 'teamwork', label: 'Jugás para el equipo', weak: 'Poco teamwork', val: d => ((d.rounds_played || 0) >= 10 && d.teamwork_ratio != null ? d.teamwork_ratio : null),
      fmt: v => pctTxt(v), unit: 'de tu score es teamwork',
      tip: 'El score de teamwork sale de revivir y curar, reabastecer con la bolsa de munición, reparar vehículos, construir con la pala en el FOB y llevar a tu escuadra en vehículo.',
      say: { que: 'juega para el equipo' }, sayWeak: 'suma poco teamwork' },
    { key: 'revives', label: 'Levantás compañeros', val: d => (d.total_revives_given || 0) / Math.max(d.rounds_played || 0, 1),
      fmt: v => f2(v), unit: 'revives por ronda', strengthOnly: true, say: { que: 'levanta compañeros' } },
    { key: 'life', label: 'Sobrevivís', weak: 'Vida corta', val: d => avgLife(d),
      fmt: v => fmtDuration(v), unit: 'por vida', tip: 'Más tiempo vivo es más score por ronda: avanzá con tu escuadra y con cobertura.',
      say: { que: 'sobrevive mucho' }, sayWeak: 'muere rápido' },
    // Junto a la escuadra: la medida nueva cuando hay muestra; si no, la distancia al
    // centro de la escuadra (con historial). Nunca las dos a la vez.
    { key: 'near', label: 'Vas con tu escuadra', weak: 'Jugás separado de tu escuadra', val: d => squadNear(d),
      fmt: v => pctTxt(v), unit: 'del tiempo vivo con un compañero a 50 m o menos',
      tip: 'Moverte con tu escuadra (o con tu equipo de fuego) te da quién te reviva, quién cubra y más score de teamwork.',
      say: { que: 'se mueve con su escuadra' }, sayWeak: 'se aleja de su escuadra' },
    { key: 'coh', label: 'Vas con tu escuadra', weak: 'Jugás separado de tu escuadra', lowerBetter: true,
      val: d => (squadNear(d) == null ? squadDistance(d) : null),
      fmt: v => `${Math.round(v)} m`, unit: 'al centro de tu escuadra en promedio',
      tip: 'Moverte con tu escuadra (o con tu equipo de fuego) te da quién te reviva, quién cubra y más score de teamwork.',
      say: { que: 'se mueve con su escuadra' }, sayWeak: 'se aleja de su escuadra' },
    { key: 'tk', label: 'Disciplina de fuego', weak: 'Fuego amigo', lowerBetter: true,
      // Por cada 100 kills y no por ronda: el que más mata también hace más teamkills,
      // y por ronda casi todo jugador bueno salía con "mucho fuego amigo".
      val: d => ((d.total_kills || 0) >= 30 ? (d.total_teamkills || 0) / d.total_kills * 100 : null),
      fmt: v => v.toFixed(1).replace('.', ','), unit: 'teamkills cada 100 kills', tip: 'Confirmá el blanco antes de disparar cerca de tu escuadra, sobre todo con vehículos y explosivos.',
      say: { adj: 'disciplinado' }, sayWeak: 'tiene mucho fuego amigo' },
];

function median(arr) {
    const s = [...arr].sort((a, b) => a - b);
    return s.length ? s[Math.floor(s.length / 2)] : 0;
}

/** Fortalezas y a mejorar: cada métrica contra los jugadores con 10+ rondas con demo.
 *  Devuelve null si no hay población suficiente para comparar. */
function glanceItems(d, player, cmp) {
    const popD = (state.demoPlayerDetails || []).filter(p => (p.rounds_played || 0) >= 10);
    if (popD.length < 20) return null;
    const items = [];
    for (const m of GLANCE) {
        const v = m.val(d);
        if (v == null || !Number.isFinite(v)) continue;
        const vals = popD.map(m.val).filter(x => x != null && Number.isFinite(x));
        if (vals.length < 20) continue;   // métrica nueva todavía sin población
        const below = vals.filter(x => x < v).length / vals.length;
        const good = m.lowerBetter ? 1 - below - vals.filter(x => x === v).length / vals.length : below;
        items.push({ m, v, good, below, med: median(vals) });
    }
    // Score por ronda (PRStats): el componente con menos nivel de la mayoría.
    const spr = player['Score per Round'] || 0;
    const sprBelow = rankOf(spr, cmp.map(p => p['Score per Round'] || 0)).below;
    items.push({ m: { key: 'spr', label: 'Sumás score', weak: 'Score por ronda', fmt: v => formatNumber(Math.round(v)), unit: 'de score por ronda',
        tip: 'Capturar banderas, construir y destruir vehículos suma score.',
        say: { que: 'suma mucho score' }, sayWeak: 'le cuesta sumar score' }, v: spr, good: sprBelow, below: sprBelow,
        med: median(cmp.map(p => p['Score per Round'] || 0)) });

    const strengths = items.filter(i => i.good >= 0.7).sort((a, b) => b.good - a.good).slice(0, 3);
    const weaknesses = items.filter(i => i.good <= 0.35 && !i.m.strengthOnly).sort((a, b) => a.good - b.good).slice(0, 3);
    return { popSize: popD.length, strengths, weaknesses };
}

function glanceHTML(g) {
    if (!g || (!g.strengths.length && !g.weaknesses.length)) return '';
    const { strengths, weaknesses } = g;
    const posTxt = (i) => i.m.lowerBetter
        ? (i.below >= 0.5 ? `más que el ${pctTxt(i.below)}` : `menos que el ${pctTxt(1 - i.below)}`)
        : (i.below >= 0.5 ? `mejor que el ${pctTxt(i.below)}` : `menos que el ${pctTxt(1 - i.below)}`);
    const li = (i, weak) => `<li><b>${escapeHtml(weak ? (i.m.weak || i.m.label) : i.m.label)}</b>
        <span><span class="pv-mono">${escapeHtml(i.m.fmt(i.v))}</span> ${escapeHtml(i.m.unit)} · ${escapeHtml(posTxt(i))}</span>
        <span class="pv-tip">${escapeHtml(weak && i.m.tip ? `${i.m.tip} Mediana: ${i.m.fmt(i.med)}.` : `Mediana de la comunidad: ${i.m.fmt(i.med)}.`)}</span></li>`;
    return `<div class="pv-head"><h4 class="profile-subtitle">Tu juego en una mirada</h4>
            <span class="profile-muted">Comparado con ${formatNumber(g.popSize)} jugadores con 10+ rondas con demo</span></div>
        <div class="pv-sw">
            <div class="pv-sw-col is-good"><h5>Fortalezas</h5>${strengths.length ? `<ul>${strengths.map(i => li(i, false)).join('')}</ul>` : '<p class="profile-muted">Nada que se destaque todavía.</p>'}</div>
            <div class="pv-sw-col is-bad"><h5>A mejorar</h5>${weaknesses.length ? `<ul>${weaknesses.map(i => li(i, true)).join('')}</ul>` : '<p class="profile-muted">Nada por debajo de la mayoría.</p>'}</div>
        </div>`;
}

/** Distancia al próximo tier: { next, gap } o { elite: true }; null sin tier_config. */
function tierGap(ps) {
    const t = state.tierConfigData?.thresholds;
    if (!t) return null;
    const next = TIER_ORDER.find(([k]) => ps < t[k]);
    return next ? { next: next[1], gap: t[next[0]] - ps } : { elite: true };
}

const cap = (txt) => txt.charAt(0).toUpperCase() + txt.slice(1);

/**
 * Lectura del jugador en dos o tres frases, armada con datos reales: su rol, sus dos
 * fortalezas y debilidades principales (las de "Tu juego en una mirada"), la forma
 * reciente y su lugar en el clan o la distancia al próximo tier. Reemplaza la frase
 * fija del arquetipo, que era la misma para todos los de ese arquetipo.
 */
function readingText(d, g, trend, player) {
    const roleEntry = (d.roles || []).find(r => r.key === d.best_role) || (d.roles || [])[0];
    // "Anti-tanque (LAT/HAT)" → "Anti-tanque": el paréntesis no se lee bien en la frase.
    const role = roleEntry ? roleEntry.label.replace(/\s*\(.*\)$/, '') : 'Jugador';
    const parts = [];

    const top = (g?.strengths || []).filter(i => i.m.say).slice(0, 2);
    const adjs = top.filter(i => i.m.say.adj).map(i => i.m.say.adj);
    const ques = top.filter(i => i.m.say.que).map(i => i.m.say.que);
    if (adjs.length || ques.length) {
        parts.push(`${role}${adjs.length ? ' ' + adjs.join(' y ') : ''}${ques.length ? ' que ' + ques.join(' y ') : ''}.`);
    } else {
        parts.push(`${role} sin una fortaleza que se destaque todavía.`);
    }

    const weak = (g?.weaknesses || []).filter(i => i.m.sayWeak).slice(0, 2).map(i => i.m.sayWeak);
    if (weak.length) parts.push(`${cap(weak.join(' y '))}.`);

    const ctx = [];
    const members = player.Clan ? (state.playersData || []).filter(p => p.Clan === player.Clan) : [];
    const pos = members.indexOf(player) + 1;
    if (pos && pos <= 10) ctx.push(`#${pos} de ${player.Clan}`);
    const tg = tierGap(player['Performance Score'] || 0);
    if (tg?.elite) ctx.push('en Elite');
    else if (tg && tg.gap <= 0.1) ctx.push(`a ${tg.gap.toFixed(3).replace('.', ',')} de ${tg.next}`);

    const form = trend == null ? '' : trend >= 1.1 ? 'Viene en racha' : trend <= 0.9 ? 'Viene en baja' : 'Estable en las últimas rondas';
    if (form) parts.push(`${form}.`);
    if (ctx.length) parts.push(`${cap(ctx.join(', '))}.`);
    return parts.join(' ');
}

const CONF = { alta: 'Alta', media: 'Media', baja: 'Baja' };

function roleValue(r, v) {
    if (r.metric === 'winrate') return pctTxt(v);
    return f2(v);
}

/** Roles: actividad, métrica propia del rol, posición frente a ese rol y confianza. */
function rolesHTML(d) {
    const roles = (d.roles || []).filter(r => (r.share || 0) >= 0.03).slice(0, 7);
    if (!roles.length) return '';
    const best = (d.roles || []).find(r => r.key === d.best_role);
    const maxShare = Math.max(...roles.map(r => r.share || 0), 0.01);
    const rows = roles.map(r => {
        const low = r.confidence === 'baja';
        const why = low && r.best_round_share > 0.4 ? `${pctTxt(r.best_round_share)} sale de 1 ronda` : r.metric_label;
        return `<tr class="${r.key === d.best_role ? 'is-lever' : ''} ${low ? 'is-low' : ''}">
            <td><span class="pv-name">${escapeHtml(r.label)}</span><span class="pv-what ${low ? 'is-warn' : ''}">${escapeHtml(why)}</span></td>
            <td class="pv-barcell">${barHTML((r.share || 0) / maxShare * 100)}<span class="pv-sub">${pctTxt(r.share || 0)}</span></td>
            <td class="n">${formatNumber(r.rounds)}</td>
            <td class="n">${roleValue(r, r.value)}</td>
            <td class="n">${roleValue(r, r.median)}</td>
            <td class="pv-barcell">${r.pct == null ? '' : rankBarHTML(r.pct)}<span class="pv-sub">${r.pct == null ? '—' : pctTxt(r.pct)}</span></td>
            <td><span class="pv-conf is-${r.confidence}">${CONF[r.confidence] || r.confidence}</span></td>
        </tr>`;
    }).join('');
    return `<div class="pv-head"><h4 class="profile-subtitle">Tus roles</h4>
            <span class="profile-muted">Cada rol se compara con los demás jugadores de ese mismo rol</span></div>
        ${best ? `<div class="pv-best-role"><span class="kpi-label">Mejor rol</span><span class="pv-best-name">${escapeHtml(best.label)}</span>
            <span class="profile-muted">Mejor que el <b>${pctTxt(best.pct)}</b> de los jugadores de ese rol (${escapeHtml(best.metric_label)}) · ${formatNumber(best.rounds)} rondas · confianza ${escapeHtml((CONF[best.confidence] || '').toLowerCase())}</span></div>` : ''}
        <div class="pv-scroll"><table class="pv-table pv-roles">
            <thead><tr><th>Rol</th><th>Tu actividad</th><th class="n">Rondas</th><th class="n">Tu valor</th><th class="n">Mediana del rol</th><th>Frente al resto</th><th>Confianza</th></tr></thead>
            <tbody>${rows}</tbody>
        </table></div>
        <p class="profile-muted">Actividad = parte de tus kills y muertes con ese kit puesto. "Frente al resto" usa un valor ajustado por muestra: con pocas rondas se acerca a la mediana del rol, así una ronda excepcional no te define. Confianza alta con 15+ rondas; baja con menos de 8 o si una sola ronda explica más del 40 %. Solo un rol con confianza media o alta puede ser el mejor.</p>`;
}

/** Tarjetas cortas con datos de demos (cada una se omite si no hay muestra). */
async function insightsHTML(d) {
    const tiles = [];
    const tile = (label, value, desc, cls = '') => tiles.push(`<div class="pv-ins"><span class="kpi-label">${escapeHtml(label)}</span>
        <span class="pv-ins-v ${cls}">${escapeHtml(value)}</span><span class="pv-ins-d">${desc}</span></div>`);
    const main = (d.roles || [])[0];
    if (main) tile('Rol principal', main.label, `<b>${pctTxt(main.share)}</b> de tu actividad`);
    const near = squadNear(d), dist = squadDistance(d);
    if (near != null) tile('Junto a tu escuadra', pctTxt(near), 'del tiempo vivo con un compañero de escuadra a 50 m o menos');
    else if (dist != null) tile('Distancia a tu escuadra', `${Math.round(dist)} m`, `al centro de tu escuadra en promedio: ${squadDistanceLabel(dist)}`);
    const weapons = aggregateByLabel(d.kill_weapons, weaponModel, { exclude: c => c === '?' || ['vehicle', 'unknown'].includes(weaponKind(c)) });
    if (weapons.length) tile('Arma principal', weapons[0][0], `<b>${formatNumber(weapons[0][1])}</b> kills`);
    const maps = Object.entries(d.per_map_stats || {}).filter(([, s]) => (s.rounds || 0) >= 3 && (s.wins || 0) + (s.losses || 0) > 0)
        .map(([m, s]) => [m, s, s.wins / (s.wins + s.losses)]);
    if (maps.length >= 2) {
        maps.sort((a, b) => b[2] - a[2] || (b[1].avg_kpr || 0) - (a[1].avg_kpr || 0));
        const [bm, bs] = maps[0], [wm, ws] = maps[maps.length - 1];
        tile('Mejor mapa', mapLabel(bm), `<b>${bs.wins}–${bs.losses}</b> · ${f2(bs.avg_kpr)} kills por ronda`, 'is-good');
        if (wm !== bm) tile('Mapa difícil', mapLabel(wm), `<b>${ws.wins}–${ws.losses}</b> en ${ws.rounds} rondas`, 'is-warn');
    }
    try {
        const syn = (await loadSynergy())?.[d.ign];
        if (syn && syn.baseline?.rounds) {
            const mates = Object.entries(syn.mates || {}).filter(([, s]) => s.rounds >= 3)
                .map(([n, s]) => [n, s, s.wins / s.rounds]).sort((a, b) => b[2] - a[2] || b[1].rounds - a[1].rounds);
            if (mates.length) {
                const [n, s] = mates[0];
                tile('Mejor compañero', n, `<b>${s.wins}–${s.rounds - s.wins}</b> juntos · tu winrate sin él: ${pctTxt(syn.baseline.wins / syn.baseline.rounds)}`);
            }
        }
    } catch (_) { /* sinergia opcional */ }
    const f = d.faction_stats || {};
    const fw = (s) => { const g = (s?.wins || 0) + (s?.losses || 0); return g >= 5 ? s.wins / g : null; };
    const bw = fw(f.blufor), ow = fw(f.opfor);
    if (bw != null && ow != null) {
        const [best, bs, other, os] = ow >= bw ? ['OPFOR', f.opfor, 'BLUFOR', f.blufor] : ['BLUFOR', f.blufor, 'OPFOR', f.opfor];
        tile('Bando', best, `<b>${pctTxt(fw(bs))}</b> victorias y ${f2(bs.avg_kpr)} kills/ronda · ${other} ${pctTxt(fw(os))} y ${f2(os.avg_kpr)}`);
    }
    if (avgLife(d)) tile('Vida promedio', fmtDuration(avgLife(d)), 'por vida');
    if (tiles.length < 3) return '';
    return `<div class="pv-head"><h4 class="profile-subtitle">Datos de tus demos</h4><span class="profile-muted">${formatNumber(d.rounds_played)} rondas</span></div>
        <div class="pv-insights">${tiles.slice(0, 8).join('')}</div>
        ${mapsTableHTML(d)}`;
}

/** Tabla desplegable con el rendimiento en cada mapa jugado (no solo el mejor y el peor). */
function mapsTableHTML(d) {
    const rows = Object.entries(d.per_map_stats || {})
        .filter(([, s]) => (s.rounds || 0) > 0)
        .sort((a, b) => (b[1].rounds || 0) - (a[1].rounds || 0));
    if (rows.length < 2) return '';
    const body = rows.map(([m, s]) => {
        const g = (s.wins || 0) + (s.losses || 0);
        const wr = g >= 3 ? s.wins / g : null;
        const kd = (s.avg_kpr || 0) / Math.max(s.avg_dpr || 0, 0.01);
        return `<tr>
            <td>${escapeHtml(mapLabel(m))}</td>
            <td class="n">${formatNumber(s.rounds)}</td>
            <td class="n">${s.wins || 0}–${s.losses || 0}</td>
            <td class="pv-barcell">${wr == null ? '<span class="pv-sub">pocas partidas</span>' : `${barHTML(wr * 100, wr >= 0.5 ? 'tier-veterano' : 'orange')}<span class="pv-sub">${pctTxt(wr)}</span>`}</td>
            <td class="n">${f2(s.avg_kpr)}</td>
            <td class="n">${f2(s.avg_dpr)}</td>
            <td class="n ${kd < 1 ? 'pv-bad' : ''}">${f2(kd)}</td>
        </tr>`;
    }).join('');
    return `<details class="pv-maps">
        <summary>Ver rendimiento en los ${rows.length} mapas</summary>
        <div class="pv-scroll"><table class="pv-table">
            <thead><tr><th>Mapa</th><th class="n">Rondas</th><th class="n">V–D</th><th>Winrate</th><th class="n">Kills/ronda</th><th class="n">Muertes/ronda</th><th class="n">K/D</th></tr></thead>
            <tbody>${body}</tbody>
        </table></div>
        <p class="profile-muted">Ordenado por rondas jugadas. El winrate aparece con 3 o más partidas decididas; el K/D sale de kills y muertes por ronda.</p>
    </details>`;
}

function recordsHTML(d) {
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
    return `
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
        </div>`;
}

/** Completa el perfil con los datos de demos (si el jugador tiene). */
async function enrichWithDemo(player, cmp) {
    const block = document.getElementById('profile-demo-block');
    if (!block) return;
    try {
        await loadDemoData();
    } catch (_) { /* non-fatal */ }
    const d = getDemoInfo(player.Player);
    // El usuario pudo haber buscado a otro mientras cargaba.
    if (!block.isConnected) return;
    const seen = document.getElementById('profile-last-seen');
    if (seen) seen.textContent = lastSeenText(d && d.last_round_date);
    const src = document.getElementById('pv-src-demos');
    const form = document.getElementById('pv-form');
    if (!d || !d.rounds_played) {
        if (src) src.innerHTML = 'Demos · <b>0</b> rondas';
        if (form) form.innerHTML = '<h4 class="profile-subtitle">Forma reciente</h4><p class="profile-muted">Todavía no hay rondas con demo para este jugador.</p>';
        block.innerHTML = '<h4 class="profile-subtitle">Récords</h4><p class="profile-muted">Todavía no hay rondas con demo para este jugador.</p>';
        return;
    }
    if (src) src.innerHTML = `Demos · <b>${formatNumber(d.rounds_played)}</b> rondas`;
    const kdEl = document.getElementById('pv-kd-demo');
    if (kdEl) kdEl.innerHTML = `En demos: <b>${f2((d.total_kills || 0) / Math.max(d.total_deaths || 0, 1))}</b> ${srcTag('demos')}`;

    const fill = (id, html) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.innerHTML = html;
        el.hidden = !html;
    };
    const glance = glanceItems(d, player, cmp);
    fill('pv-glance', glanceHTML(glance));
    fill('pv-roles', rolesHTML(d));
    block.innerHTML = recordsHTML(d);

    const [pr, ins] = await Promise.all([loadPlayerRounds(player.Player).catch(() => null), insightsHTML(d)]);
    if (!block.isConnected) return;
    if (form) form.innerHTML = formHTML(pr, d);
    const reading = document.getElementById('pv-reading');
    if (reading) reading.textContent = readingText(d, glance, formTrend(pr, d), player);
    fill('pv-insights', ins);
    const hist = document.getElementById('pv-history');
    fill('pv-history', historyHTML(pr));
    if (hist) {
        hist.onclick = (e) => {
            const b = e.target.closest('.pv-history-more');
            if (b) hist.innerHTML = historyHTML(pr, Number(b.dataset.shown) + HISTORY_PAGE);
        };
    }
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
