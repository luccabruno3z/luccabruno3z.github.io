/* ═══════════════════════════════════════════════════════════════════════════
   Legión de Hierro — Stats Tracker
   config.js — URLs, constants and tuning knobs (no dependencies)
   ═══════════════════════════════════════════════════════════════════════════ */

// All data is served from the GitHub Pages origin, so fetches work even when
// the page is opened from another host (or a local static server).
export const BASE_URL          = 'https://luccabruno3z.github.io';
export const GRAPHS_URL        = `${BASE_URL}/graphs`;
export const ALL_PLAYERS_URL   = `${GRAPHS_URL}/all_players_clusters.json`;
export const CLAN_AVERAGES_URL = `${GRAPHS_URL}/clan_averages.json`;
export const DEMOS_URL         = `${GRAPHS_URL}/demos`;
export const HISTORY_URL       = `${GRAPHS_URL}/history`;
export const LEADERBOARDS_URL  = `${DEMOS_URL}/leaderboards`;
export const ROUNDS_URL        = `${DEMOS_URL}/rounds`;
export const PLAYER_ROUNDS_URL = `${DEMOS_URL}/player_rounds`;
export const TIER_CONFIG_URL   = `${GRAPHS_URL}/tier_config.json`;
export const LOGO_MANIFEST_URL = `${BASE_URL}/logos/manifest.json`;
export const ALIASES_URL       = `${DEMOS_URL}/aliases.json`;
export const SYNERGY_URL       = `${DEMOS_URL}/synergy.json`;
export const HEATMAPS_URL      = `${DEMOS_URL}/heatmaps`;
// Optional per-map minimap backgrounds (manifest like logos: {map: ext}). The
// heatmap renderer draws the image when present and falls back to a neutral grid.
export const MAP_IMG_URL       = `${BASE_URL}/web/img/maps`;
export const MAP_IMG_MANIFEST_URL = `${MAP_IMG_URL}/manifest.json`;
// Visor oficial de demos (replay 3D). Carga un demo con ?demo=<URL>.
export const REPLAY_VIEWER_URL = 'https://yossizap.github.io/realitytracker/';

// A player needs at least this many rounds to qualify for the rankings.
export const MIN_ROUNDS_FOR_RANKING = 50;

// Normalization caps used by activityIndex() and the predictor.
export const NORM_CAPS = { kd: 5.0, spr: 500.0, kpr: 10.0, rounds: 1000.0 };

// Cache lifetime (ms) shared by the in-memory cache and the localStorage cache.
export const CACHE_TTL = 300000; // 5 min

// Debounce for autocomplete inputs (ms).
export const AUTOCOMPLETE_DEBOUNCE_MS = 150;

// Shared palette (kept in sync with web/css/styles.css :root).
export const COLORS = {
    accent:  '#00FFFF',
    orange:  '#FFA500',
    green:   '#00FF88',
    red:     '#FF4444',
    yellow:  '#FFD700',
    grid:    'rgba(255, 255, 255, 0.1)',
    gridDim: 'rgba(255, 255, 255, 0.05)',
    text:    '#ffffff',
};
