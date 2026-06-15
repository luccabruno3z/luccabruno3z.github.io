# Feature module API — how to build the JS feature modules

You are writing **ES module** feature files under `web/js/`. The foundation is DONE — read these
files to see exact signatures, then import from them. DO NOT re-implement helpers or fetching.

ALSO READ: `.rebuild/CONTRACT.md` — it has every data file schema (§1), the per-feature DOM IDs &
behavior (§2), the Chart.js specs (§3), and the exact computed logic (§4). Treat it as law.

## Foundation modules (import, don't reinvent)

### `./config.js`
Constants: `BASE_URL, GRAPHS_URL, ALL_PLAYERS_URL, CLAN_AVERAGES_URL, DEMOS_URL, HISTORY_URL,
LEADERBOARDS_URL, ROUNDS_URL, PLAYER_ROUNDS_URL, TIER_CONFIG_URL, MIN_ROUNDS_FOR_RANKING,
NORM_CAPS, CACHE_TTL, AUTOCOMPLETE_DEBOUNCE_MS, COLORS`.

### `./data.js`
- `state` — live singleton; read `state.playersData` (sorted desc by Performance Score),
  `state.clanAveragesData`, `state.tierConfigData`, `state.demoPlayerDetails`, `state.demoMapStats`.
  **Never reassign `state`**; read its props at call time (data may load after your init runs —
  but main.js awaits `loadData()` before calling inits, so `state.playersData` is populated).
- `cachedFetch(url, {ttl, silent})`
- `loadData()`, `loadTierConfig()`, `loadDemoData()`, `getDemoInfo(ign)`,
  `loadLeaderboard(period)`, `loadRecentMatches(limit=25)`,
  `loadPlayerHistory(name)`, `loadPlayerRounds(name)`.

### `./utils.js`
`formatNumber, normalizeName, escapeHtml, prettifyToken, tierBadge, tierEmoji, rankMedal,
classifyPlaystyle, getPlayerArchetype, experienceBadge, sampleReliability, activityIndex,
activityTier, percentile, p95, sigmoidPenalty, progressBarHTML, scoreBreakdown, clanLogoHTML,
highlightWinner, advantagePct, findPlayer`.

### `./charts.js`
`renderRadarChart(player, clan)`, `renderHistoryChart(historyData, canvas)`,
`renderTeamRadar(team, container)`, `renderClanAveragesChart(clanAveragesData, canvas)`.

### `./autocomplete.js`
`setupAutocomplete(input, container, source, onSelect?)` and `playerSource(getPlayers)`.
Example: `setupAutocomplete(inp, sug, playerSource(() => state.playersData))`.

## Conventions (MANDATORY — main.js depends on them)

1. **One file per feature**, each exporting exactly one init function (named below). The init:
   attaches event listeners and renders any initial content. It may be `async`.
2. main.js runs `await loadData(); await loadTierConfig();` then calls every init. So
   `state.playersData` IS available when your init runs. `loadDemoData()` you call yourself.
3. **Lazy sections** (`leaderboards`, `recent-matches`): inside your init, set up an
   `IntersectionObserver` (threshold 0.1) to defer the first fetch until the section scrolls into
   view; if `IntersectionObserver` is undefined, render immediately. Guard against double-render.
4. Use `escapeHtml()` on ALL player/map/clan names before `innerHTML` (fixes a real bug — names
   like `juan*ARG*` are common). Use `prettifyToken()` for map/gamemode tokens.
5. Match the exact DOM IDs in CONTRACT.md §2. Reproduce computed logic from §4 exactly via the
   utils imports. Keep all JSON values as numbers (no String coercion).
6. Style hooks: emit semantic class names; the CSS is written separately. Reuse these where they
   fit so styling is shared: `.stat-row`, `.stat-label`, `.stat-value`, `.badge`, `.tier-badge`,
   `.rank-row`, `.rank-pos`, `.rank-name`, `.rank-value`, `.progress-row/.progress-track/.progress-fill`,
   `.data-table`, `.empty-state`, `.error-state`, `.card`. Tier badges: add the `cssClass` from
   `tierBadge()` (e.g. `tier-elite`).

## Required filenames + exported init names

Group 1:
- `web/js/hero.js`        → `export function initHero()`
- `web/js/dashboard.js`   → `export function initDashboard()`
- `web/js/player.js`      → `export function initPlayerSearch()`
- `web/js/comparison.js`  → `export function initComparison()`

Group 2:
- `web/js/rankings.js`    → `export function initRankings()`
- `web/js/leaderboards.js`→ `export function initLeaderboards()`
- `web/js/predictor.js`   → `export function initPredictor()`
- `web/js/team.js`        → `export function initTeamAnalysis()`
- `web/js/clans.js`       → `export function initClanAverages()`
- `web/js/demos.js`       → `export function initDemoStats()`
- `web/js/matches.js`     → `export function initRecentMatches()`

## Feature notes / bug-fixes to apply

- **hero.js**: count-up of `#counter-players` (players length), `#counter-clans`
  (unique `Clan`), `#counter-rounds` (sum of `Rounds`), ease-out cubic, `toLocaleString('es-AR')`.
  Populate `#hero-featured` with the #1 player (top of sorted `state.playersData`): name, clan logo,
  tier badge, PS, K/D, archetype. Set `#last-updated-time` from the max `Last Updated` across players
  (also set its `datetime` attr). Replace the skeleton on render.
- **dashboard.js**: fill the 4 bento tiles — `#tile-top-body` (top 5 by PS from `state.playersData`),
  `#tile-lb-body` (top 5 by kills from `await loadLeaderboard('semana')`), `#tile-clans-body`
  (top 5 clans by PS from `state.clanAveragesData`), `#tile-matches-body` (5 from
  `await loadRecentMatches(5)`). Remove skeletons; handle empty/error with `.empty-state`.
- **player.js**: full profile in `#player-profile-card` (badges, stat rows with `percentile()` over
  the population, `scoreBreakdown()`, activity bar via `activityIndex()`+`activityTier()`,
  `sigmoidPenalty()` warning when penalty*100<95, low-rounds warning). Call `renderRadarChart`.
  Load history via `loadPlayerHistory()` → `renderHistoryChart(historyData, document.getElementById('historyChart'))`.
  Enrich with `getDemoInfo(player.Player)` (now works — keyed by `ign`). Autocomplete on `#player-name`/`#suggestions`.
- **comparison.js**: `findPlayer` both inputs → player-vs-player (7 metrics + verdict via
  `highlightWinner`/`advantagePct`); else filter `state.playersData` by `Clan` (case-insensitive)
  → clan-vs-clan aggregates. Autocomplete both inputs (players + clan names).
- **rankings.js**: filter by clan dropdown value (lowercased; map `rim-la`→`RIM:LA`, case-insensitive
  match on `Clan`), exclude `Rounds < MIN_ROUNDS_FOR_RANKING` and report excluded count, sort desc by
  metric, progress bars normalized to max, medals top 3.
- **leaderboards.js**: `#lb-period`/`#lb-metric` change + `#lb-count` input re-render. `kd` metric =
  kills/deaths (or kills if deaths 0). Lazy-load. Show rounds/kills/deaths in detail.
- **predictor.js**: read up to 8 inputs per team (`#teamA-pN`/`#teamB-pN`), resolve via `findPlayer`.
  Composite per team = `wPS*avgPS + wKD*(avgKD/NORM_CAPS.kd) + wKPR*(avgKPR/NORM_CAPS.kpr)` with
  weights from `state.tierConfigData.predictor_weights` (drop `winrate`, renormalize {ps,kd,kpr} to
  sum 1; fallback {ps:.50,kd:.30,kpr:.20}). Probabilities = composite/sum. Animate bars.
- **team.js**: 2..8 players; team K/D from totals, avg PS/KPR/DPR, per-player cards; call
  `renderTeamRadar(team, document.getElementById('team-results'))` (append into results).
- **clans.js**: call `renderClanAveragesChart(state.clanAveragesData, document.getElementById('clanAveragesChart'))`
  + per-clan stat cards in `#clan-averages-results` (sorted desc by PS).
- **demos.js**: `await loadDemoData()`. Player tool: autocomplete on `ign` (case-insensitive), render
  rounds_played/kills/deaths/score/revives/vehicles + top kits from `kits_used`; then append
  `await loadPlayerRounds(ign)` timeline (reverse, up to 20; `won` is bool). Map tool: autocomplete
  unique `map_name`; show one box per matching gamemode row with winrate/kills/tickets.
- **matches.js**: `await loadRecentMatches(25)` → table: date (parse from `filename`
  `tracker_YYYY_MM_DD_...`), map (prettify), gamemode, winner (1=blufor,2=opfor,-1=none → show
  `blufor_team`/`opfor_team`), total_kills. Lazy-load with retry on error.
