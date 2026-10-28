/* ═══════════════════════════════════════════════════════════════════════════
   main.js — entry point. Loads core data, then wires every feature module.
   Loaded as <script type="module"> (deferred), so the DOM is ready here.
   ═══════════════════════════════════════════════════════════════════════════ */

import { loadData, loadTierConfig, loadLogoManifest, loadAliases, loadAtlas } from './data.js';
import { initRouter } from './router.js';
import { initIcons } from './icons.js';
import { initTeamChips } from './chips.js';

import { initHero } from './hero.js';
import { initDashboard } from './dashboard.js';
import { initPlayerSearch } from './player.js';
import { initComparison } from './comparison.js';
import { initRankings } from './rankings.js';
import { initLeaderboards } from './leaderboards.js';
import { initRoleLeaderboards } from './roles.js';
import { initSquads } from './squads.js';
import { initPredictor } from './predictor.js';
import { initTeamAnalysis } from './team.js';
import { initClanAverages } from './clans.js';
import { initDemoStats } from './demos.js';
import { initHeatmaps } from './heatmaps.js';
import { initRecentMatches } from './matches.js';
import { initGuides } from './guides.js';

// Run one init in isolation so a single broken feature can't take down the page.
function safe(name, fn) {
    try {
        const r = fn();
        if (r && typeof r.catch === 'function') r.catch(e => console.error(`[${name}]`, e));
    } catch (e) {
        console.error(`[${name}]`, e);
    }
}

// Reveal-on-scroll. The `js` flag gates the hidden initial state in CSS, so
// content stays visible if JS never runs.
function setupReveal() {
    document.documentElement.classList.add('js');
    const targets = document.querySelectorAll('.hero, .section');
    if (!('IntersectionObserver' in window)) {
        targets.forEach(t => t.classList.add('visible'));
        return;
    }
    const io = new IntersectionObserver((entries, obs) => {
        entries.forEach(e => {
            if (e.isIntersecting) { e.target.classList.add('visible'); obs.unobserve(e.target); }
        });
    }, { threshold: 0.08 });
    targets.forEach(t => io.observe(t));
    // Safety net: never leave anything hidden.
    setTimeout(() => targets.forEach(t => t.classList.add('visible')), 4000);
}

function showCoreError() {
    const card = document.getElementById('player-profile-card');
    if (card) card.innerHTML = '<div class="error-state">No se pudieron cargar los datos. Revisá tu conexión y recargá la página.</div>';
}

async function boot() {
    // Primero la vista: un deep link (#/clanes) no muestra Inicio mientras cargan los datos.
    safe('router', initRouter);
    // Las guías no dependen de los datos: se abren aunque falle la carga.
    safe('guides', initGuides);
    // Emojis → íconos SVG (también en lo que se pinte después).
    safe('icons', initIcons);
    setupReveal();

    try {
        await loadData();
    } catch (e) {
        console.error('[loadData]', e);
        showCoreError();
    }
    // Non-fatal config/manifest, in parallel, before the immediate renders below
    // (so clan logos use the manifest on first paint).
    await Promise.all([loadTierConfig(), loadLogoManifest(), loadAliases(), loadAtlas()]);

    // Features that render immediately from core data.
    safe('hero', initHero);
    safe('dashboard', initDashboard);
    safe('clans', initClanAverages);

    // Features that attach listeners / autocompletes.
    safe('player', initPlayerSearch);
    safe('comparison', initComparison);
    safe('rankings', initRankings);
    safe('predictor', initPredictor);
    safe('team', initTeamAnalysis);
    safe('chips', initTeamChips);  // después: usa los campos que arman predictor/team
    safe('demos', initDemoStats);

    // Lazy sections (self-managed IntersectionObserver).
    safe('leaderboards', initLeaderboards);
    safe('roles', initRoleLeaderboards);
    safe('squads', initSquads);
    safe('heatmaps', initHeatmaps);
    safe('matches', initRecentMatches);
}

boot();
