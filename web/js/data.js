/* ═══════════════════════════════════════════════════════════════════════════
   data.js — fetching, caching and the shared in-memory data store.

   Everything that needs data imports `state` (a live singleton — read its
   properties, never reassign the object) and the loader functions below.
   See .rebuild/CONTRACT.md §1 for every file's schema.
   ═══════════════════════════════════════════════════════════════════════════ */

import {
    ALL_PLAYERS_URL, CLAN_AVERAGES_URL, TIER_CONFIG_URL, LOGO_MANIFEST_URL,
    DEMOS_URL, LEADERBOARDS_URL, ROUNDS_URL, PLAYER_ROUNDS_URL, HISTORY_URL,
    CACHE_TTL,
} from './config.js';
import { normalizeName } from './utils.js';

// ── Shared store (mutated in place by loaders) ───────────────────────────────
export const state = {
    playersData: [],          // all_players_clusters.json, sorted desc by Performance Score
    clanAveragesData: [],     // clan_averages.json
    tierConfigData: null,     // tier_config.json (or null → hardcoded fallbacks)
    demoPlayerDetails: null,  // demos/player_details.json (list keyed by `ign`)
    demoMapStats: null,       // demos/map_stats.json
    leaderboardCache: {},     // period → leaderboard json
    logoManifest: null,       // logos/manifest.json: {clan: ext} (or null → built-in fallback)
};

// ── 3-layer cache (in-memory + stale fallback) ───────────────────────────────
const memoryCache = new Map();

/** Fetch JSON with in-memory caching and graceful degradation. */
export async function cachedFetch(url, options = {}) {
    const { ttl = CACHE_TTL, silent = false } = options;
    const cached = memoryCache.get(url);
    if (cached && Date.now() - cached.time < ttl) return cached.data;

    try {
        const resp = await fetch(url);
        if (!resp.ok) {
            if (silent) return null;
            throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
        }
        const data = await resp.json();
        memoryCache.set(url, { data, time: Date.now() });
        return data;
    } catch (err) {
        if (cached) return cached.data;   // stale-while-error
        if (silent) return null;
        throw err;
    }
}

// ── Core data: players + clan averages (with localStorage layer) ─────────────

/** Load players + clan averages. Uses a 5-min localStorage cache, then network. */
export async function loadData() {
    if (state.playersData.length && state.clanAveragesData.length) return;

    // 1) localStorage fast path
    try {
        const t = localStorage.getItem('playersDataTime');
        if (t && Date.now() - Number(t) < CACHE_TTL) {
            const p = localStorage.getItem('playersData');
            const c = localStorage.getItem('clanAveragesData');
            if (p && c) {
                state.playersData = JSON.parse(p);
                state.clanAveragesData = JSON.parse(c);
                memoryCache.set(ALL_PLAYERS_URL, { data: state.playersData, time: Date.now() });
                return;
            }
        }
    } catch (_) { /* ignore quota / parse errors */ }

    // 2) network
    const [playersResp, clansResp] = await Promise.all([
        fetch(ALL_PLAYERS_URL),
        fetch(CLAN_AVERAGES_URL),
    ]);
    const players = await playersResp.json();
    const clans = await clansResp.json();

    players.sort((a, b) => (b['Performance Score'] || 0) - (a['Performance Score'] || 0));
    state.playersData = players;
    state.clanAveragesData = clans;

    // 3) persist
    try {
        localStorage.setItem('playersData', JSON.stringify(players));
        localStorage.setItem('clanAveragesData', JSON.stringify(clans));
        localStorage.setItem('playersDataTime', String(Date.now()));
    } catch (_) { /* quota — non-fatal */ }
    memoryCache.set(ALL_PLAYERS_URL, { data: players, time: Date.now() });
}

/** Load dynamic tier/predictor config. Non-fatal on failure. */
export async function loadTierConfig() {
    try {
        state.tierConfigData = await cachedFetch(TIER_CONFIG_URL);
    } catch (_) {
        console.warn('tier_config.json no disponible; usando umbrales por defecto');
    }
}

/** Load the logo manifest ({clan: ext}) so clanLogoHTML knows which clans ship a
 *  logo file without a hardcoded list. Non-fatal: falls back to the built-in map. */
export async function loadLogoManifest() {
    const data = await cachedFetch(LOGO_MANIFEST_URL, { silent: true });
    if (data && typeof data === 'object') state.logoManifest = data;
}

// ── Demo data (player details + map stats) ───────────────────────────────────

/** Load demos/player_details.json + demos/map_stats.json once (shared by profile + demo section). */
export async function loadDemoData() {
    if (state.demoPlayerDetails && state.demoMapStats) return;
    const [details, maps] = await Promise.all([
        cachedFetch(`${DEMOS_URL}/player_details.json`, { silent: true }),
        cachedFetch(`${DEMOS_URL}/map_stats.json`, { silent: true }),
    ]);
    if (details) state.demoPlayerDetails = details;
    if (maps) state.demoMapStats = maps;
}

/** Look up a player's demo details by `ign` (exact then case-insensitive). */
export function getDemoInfo(name) {
    const list = state.demoPlayerDetails;
    if (!Array.isArray(list) || !name) return null;
    const exact = list.find(p => p.ign === name);
    if (exact) return exact;
    const lower = name.toLowerCase();
    return list.find(p => p.ign && p.ign.toLowerCase() === lower) || null;
}

// ── Leaderboards ─────────────────────────────────────────────────────────────

/** Load a period leaderboard (memoized). Falls back to empty. */
export async function loadLeaderboard(period) {
    if (state.leaderboardCache[period]) return state.leaderboardCache[period];
    const data = await cachedFetch(`${LEADERBOARDS_URL}/${period}.json`, { silent: true })
        || { players: [], total_rounds: 0 };
    state.leaderboardCache[period] = data;
    return data;
}

// ── Recent matches (rounds) ──────────────────────────────────────────────────

/** Walk the most recent day files until `limit` rounds are collected. */
export async function loadRecentMatches(limit = 25) {
    const index = await cachedFetch(`${ROUNDS_URL}/index.json`, { silent: true });
    if (!index || !Array.isArray(index.dates)) return [];
    const dates = [...index.dates].sort((a, b) => b.localeCompare(a));
    const collected = [];
    for (const d of dates) {
        if (collected.length >= limit) break;
        const day = await cachedFetch(`${ROUNDS_URL}/${d}.json`, { silent: true });
        if (Array.isArray(day)) collected.push(...day);
    }
    collected.sort((a, b) => String(b.filename || '').localeCompare(String(a.filename || '')));
    return collected.slice(0, limit);
}

// ── Per-player time series ───────────────────────────────────────────────────

/** Performance-score history for a player (or null). */
export async function loadPlayerHistory(playerName) {
    return cachedFetch(`${HISTORY_URL}/${normalizeName(playerName)}_history.json`, { silent: true });
}

/** Per-round demo timeline for a player (or null). */
export async function loadPlayerRounds(playerName) {
    return cachedFetch(`${PLAYER_ROUNDS_URL}/${normalizeName(playerName)}.json`, { silent: true });
}
