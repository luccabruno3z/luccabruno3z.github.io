/* ═══════════════════════════════════════════════════════════════════════════
   main.js — entry point. Loads core data, then wires every feature module.
   Loaded as <script type="module"> (deferred), so the DOM is ready here.
   ═══════════════════════════════════════════════════════════════════════════ */

import { loadData, loadTierConfig } from './data.js';

import { initHero } from './hero.js';
import { initDashboard } from './dashboard.js';
import { initPlayerSearch } from './player.js';
import { initComparison } from './comparison.js';
import { initRankings } from './rankings.js';
import { initLeaderboards } from './leaderboards.js';
import { initPredictor } from './predictor.js';
import { initTeamAnalysis } from './team.js';
import { initClanAverages } from './clans.js';
import { initDemoStats } from './demos.js';
import { initRecentMatches } from './matches.js';

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
    setupReveal();

    try {
        await loadData();
    } catch (e) {
        console.error('[loadData]', e);
        showCoreError();
    }
    await loadTierConfig(); // non-fatal

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
    safe('demos', initDemoStats);

    // Lazy sections (self-managed IntersectionObserver).
    safe('leaderboards', initLeaderboards);
    safe('matches', initRecentMatches);
}

boot();
