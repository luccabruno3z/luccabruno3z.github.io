/* ═══════════════════════════════════════════════════════════════════════════
   utils.js — formatting, scoring, badges and small HTML helpers.
   Logic ported 1:1 from the previous app.js (see .rebuild/CONTRACT.md §4) so
   rankings / badges / predictions stay identical.

   Note: imports `state` from data.js only to read `state.tierConfigData` inside
   tierBadge(); the reference is used at call-time, so the (intentional) cycle
   utils <-> data is safe.
   ═══════════════════════════════════════════════════════════════════════════ */

import { NORM_CAPS } from './config.js';
import { state } from './data.js';

// ── Number / string formatting ───────────────────────────────────────────────

/** Format a number with es-AR thousands separators; floats get 2 decimals. */
export function formatNumber(n) {
    if (n == null) return 'N/A';
    if (typeof n === 'number' && !Number.isInteger(n)) {
        if (n === Math.floor(n) && Math.abs(n) > 100) {
            return Math.floor(n).toLocaleString('es-AR');
        }
        return n.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return n.toLocaleString('es-AR');
}

/** Filesystem-safe player name → matches the generator's naming of per-player files. */
export function normalizeName(name) {
    return String(name).replace(/[^a-zA-Z0-9_-]/g, '_');
}

/** Escape a string for safe innerHTML insertion. */
export function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/** Turn a snake_case token (map/gamemode) into a readable, escaped label. */
export function prettifyToken(token) {
    return escapeHtml(String(token ?? '').replace(/_/g, ' ').trim());
}

// ── Tiers / badges ───────────────────────────────────────────────────────────

/** Performance tier badge. Uses dynamic thresholds from tier_config.json if loaded. */
export function tierBadge(score) {
    const t = state.tierConfigData?.thresholds
        || { elite: 0.70, veterano: 0.55, experimentado: 0.40, soldado: 0.25 };
    if (score >= t.elite)         return { emoji: '\u{1F947}', name: 'Elite',         cssClass: 'tier-elite' };
    if (score >= t.veterano)      return { emoji: '\u{1F948}', name: 'Veterano',      cssClass: 'tier-veterano' };
    if (score >= t.experimentado) return { emoji: '\u{1F949}', name: 'Experimentado', cssClass: 'tier-experimentado' };
    if (score >= t.soldado)       return { emoji: '⚔️', name: 'Soldado',    cssClass: 'tier-soldado' };
    return { emoji: '\u{1F530}', name: 'Recluta', cssClass: 'tier-recluta' };
}

export function tierEmoji(score) {
    return tierBadge(score).emoji;
}

export function rankMedal(position) {
    if (position === 1) return '\u{1F947}';
    if (position === 2) return '\u{1F948}';
    if (position === 3) return '\u{1F949}';
    return `#${position}`;
}

/** Classify playstyle from raw stats (ordered cascade). */
export function classifyPlaystyle(kd, kpr, dpr, rounds) {
    if (kd >= 2.0 && kpr < 3.0)          return { emoji: '\u{1F3AF}', name: 'Francotirador' };
    if (kpr >= 5.0 && dpr >= 4.0)        return { emoji: '\u{1F5E1}️', name: 'Asesino' };
    if (dpr < 2.5 && kd >= 1.2)          return { emoji: '\u{1F6E1}️', name: 'Superviviente' };
    if (rounds >= 500 && kd >= 0.8 && kd <= 1.8) return { emoji: '⭐', name: 'Veterano' };
    if (kpr >= 4.0 && rounds >= 200)     return { emoji: '\u{1F3CB}️', name: 'Tanque' };
    if (rounds < 50)                     return { emoji: '\u{1F331}', name: 'Novato' };
    return { emoji: '⚔️', name: 'Soldado' };
}

/** Prefer stored archetype, else derive from stats. */
export function getPlayerArchetype(player) {
    const arch = player.archetype;
    if (arch && typeof arch === 'object') {
        return { emoji: arch.emoji || '⚔️', name: arch.name || 'Soldado', desc: arch.desc || '' };
    }
    const kd = player['K/D Ratio'] || 0;
    const kpr = player['Kills per Round'] || 0;
    const rounds = player['Rounds'] || 0;
    const dpr = rounds > 0 ? (player['Total Deaths'] || 0) / rounds : 0;
    return classifyPlaystyle(kd, kpr, dpr, rounds);
}

export function experienceBadge(rounds) {
    if (rounds >= 1000) return { emoji: '\u{1F396}️', name: 'Leyenda' };
    if (rounds >= 500)  return { emoji: '⭐', name: 'Veterano' };
    if (rounds >= 200)  return { emoji: '⚔️', name: 'Experimentado' };
    if (rounds >= 50)   return { emoji: '\u{1F6E1}️', name: 'Regular' };
    if (rounds >= 10)   return { emoji: '\u{1F331}', name: 'Novato' };
    return { emoji: '❓', name: 'Sin datos suficientes' };
}

export function sampleReliability(rounds) {
    if (rounds >= 200) return { emoji: '\u{1F7E2}', text: 'Alta confiabilidad', cssClass: 'reliability-high' };
    if (rounds >= 50)  return { emoji: '\u{1F7E1}', text: 'Confiabilidad media', cssClass: 'reliability-medium' };
    if (rounds >= 10)  return { emoji: '\u{1F7E0}', text: 'Baja confiabilidad', cssClass: 'reliability-low' };
    return { emoji: '\u{1F534}', text: 'Datos insuficientes', cssClass: 'reliability-none' };
}

/** Activity index 0..100 (40% volume log + 30% engagement + 30% impact). */
export function activityIndex(rounds, spr, kpr) {
    const volumeLog = Math.min(Math.log10(Math.max(rounds, 1)) / Math.log10(NORM_CAPS.rounds), 1.0);
    const engagement = Math.min(spr / NORM_CAPS.spr, 1.0);
    const impact = Math.min(kpr / NORM_CAPS.kpr, 1.0);
    return Math.round((0.4 * volumeLog + 0.3 * engagement + 0.3 * impact) * 100);
}

/** Display tier for an activity index value. */
export function activityTier(idx) {
    if (idx >= 80) return { emoji: '\u{1F525}', name: 'Muy Activo' };
    if (idx >= 60) return { emoji: '✅', name: 'Activo' };
    if (idx >= 40) return { emoji: '\u{1F7E1}', name: 'Moderado' };
    if (idx >= 20) return { emoji: '\u{1F7E0}', name: 'Bajo' };
    return { emoji: '❄️', name: 'Inactivo' };
}

/** "top X%" of a value among a population. */
export function percentile(playerValue, allValues) {
    if (!allValues || allValues.length === 0) return 'N/A';
    const countBelow = allValues.filter(v => v < playerValue).length;
    const pct = (countBelow / allValues.length) * 100;
    const topPct = 100 - pct;
    if (topPct < 1) return 'top 1%';
    return `top ${Math.round(topPct)}%`;
}

/** 95th percentile of a numeric array (nulls filtered). */
export function p95(values) {
    const sorted = (values || []).filter(v => v != null).sort((a, b) => a - b);
    if (sorted.length === 0) return 1;
    return sorted[Math.floor(sorted.length * 0.95)] || 1;
}

/** Logistic confidence penalty by rounds played. */
export function sigmoidPenalty(rounds) {
    return 1 / (1 + Math.exp(-((rounds - 25) / 10)));
}

// ── HTML fragment helpers ────────────────────────────────────────────────────

/** A clamped 0..100% progress bar. */
export function progressBarHTML(value, maxValue, label, color) {
    const pct = Math.max(0, Math.min(100, (value / maxValue) * 100));
    return `
        <div class="progress-row" title="${escapeHtml(label)}: ${value.toFixed(2)}">
            <span class="progress-label">${escapeHtml(label)}</span>
            <div class="progress-track">
                <div class="progress-fill" style="width:${pct}%; background:${color};"></div>
            </div>
            <span class="progress-value">${value.toFixed(2)}</span>
        </div>`;
}

/** The 4-bar normalized-score breakdown with bottleneck (⚠️) / best (⭐) marks. */
export function scoreBreakdown(player) {
    const comps = [
        { key: 'Normalized_KD',               name: 'Combate',     color: '#00FFFF' },
        { key: 'Normalized_Score',            name: 'Puntuación',  color: '#FFA500' },
        { key: 'Normalized_Kills_Per_Round',  name: 'Agresividad', color: '#FF4444' },
        { key: 'Normalized_Rounds',           name: 'Experiencia', color: '#44FF44' },
    ].map(c => ({ ...c, value: player[c.key] || 0 }));

    let minIdx = 0, maxIdx = 0;
    comps.forEach((c, i) => {
        if (c.value < comps[minIdx].value) minIdx = i;
        if (c.value > comps[maxIdx].value) maxIdx = i;
    });

    return comps.map((c, i) => {
        let mark = '';
        if (i === minIdx && c.value < 0.7) mark = ' ⚠️';
        else if (i === maxIdx) mark = ' ⭐';
        return progressBarHTML(c.value, 1.0, c.name + mark, c.color);
    }).join('');
}

// Clans that actually ship a logo file (and its extension). Everything else
// uses Logo_default.png, so we never request a 404 or show a broken-image icon.
// onerror still degrades to the default as a safety net if a file goes missing.
const CLAN_LOGOS = {
    '300': 'png', 'ADG': 'gif', 'E-LAM': 'png', 'FASO': 'png',
    'FI': 'png', 'LDH': 'png', 'RIM:LA': 'png', 'SAE': 'png',
};

/** Clan logo: a real <img> when the clan has a logo file, otherwise a clean
 *  monogram chip with the clan tag (avoids the ugly loose default-image box). */
export function clanLogoHTML(clan, size = 24) {
    const safe = escapeHtml(clan);
    const ext = CLAN_LOGOS[clan];
    if (ext) {
        return `<img class="clan-logo" src="logos/Logo_${safe}.${ext}" alt="" width="${size}" height="${size}" ` +
            `loading="lazy" onerror="this.onerror=null;this.src='logos/Logo_default.png';">`;
    }
    const mono = escapeHtml(String(clan).replace(/[^a-zA-Z0-9]/g, '').slice(0, 3).toUpperCase() || '?');
    const fs = Math.max(8, Math.round(size * 0.38));
    return `<span class="clan-logo clan-mono" style="width:${size}px;height:${size}px;font-size:${fs}px;" ` +
        `title="${safe}" aria-hidden="true">${mono}</span>`;
}

// ── Comparison helpers ───────────────────────────────────────────────────────

/** Returns {class1,class2} marking the winner/loser/tie between two values. */
export function highlightWinner(v1, v2, higherBetter = true) {
    if (v1 === v2) return { class1: 'compare-tie', class2: 'compare-tie' };
    const oneWins = higherBetter ? v1 > v2 : v1 < v2;
    return oneWins
        ? { class1: 'compare-winner', class2: 'compare-loser' }
        : { class1: 'compare-loser', class2: 'compare-winner' };
}

/** "+25.3%" style advantage of v1 over v2. */
export function advantagePct(v1, v2) {
    if (v2 === 0) return v1 > 0 ? '+∞%' : '0%';
    const diff = ((v1 - v2) / Math.abs(v2)) * 100;
    const sign = diff >= 0 ? '+' : '';
    return `${sign}${diff.toFixed(1)}%`;
}

// ── Lookup ───────────────────────────────────────────────────────────────────

/** Find a player by name: exact (case-sensitive) → exact (case-insensitive) → partial. */
export function findPlayer(data, name) {
    if (!data || !name) return null;
    const exact = data.find(p => p.Player === name);
    if (exact) return exact;
    const lower = name.toLowerCase();
    const ci = data.find(p => p.Player && p.Player.toLowerCase() === lower);
    if (ci) return ci;
    return data.find(p => p.Player && p.Player.toLowerCase().includes(lower)) || null;
}
