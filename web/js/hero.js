/* ═══════════════════════════════════════════════════════════════════════════
   hero.js — animated community counters + featured #1 player + last-updated.
   See .rebuild/CONTRACT.md §2.1 and FEATURE_API.md (hero notes).
   ═══════════════════════════════════════════════════════════════════════════ */

import { state } from './data.js';
import {
    escapeHtml, clanLogoHTML, tierBadge, getPlayerArchetype, formatNumber,
} from './utils.js';

/** Ease-out cubic count-up for a single counter element. */
function animateCounter(id, target, duration = 1500) {
    const el = document.getElementById(id);
    if (!el) return;
    const start = performance.now();
    function frame(now) {
        const t = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
        const value = Math.round(target * eased);
        el.textContent = value.toLocaleString('es-AR');
        if (t < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
}

/** Run all three community counters. */
function animateCounters() {
    const players = state.playersData || [];
    const totalPlayers = players.length;
    const totalClans = new Set(players.map(p => p.Clan).filter(Boolean)).size;
    const totalRounds = players.reduce((s, p) => s + (p.Rounds || 0), 0);

    animateCounter('counter-players', totalPlayers);
    animateCounter('counter-clans', totalClans);
    animateCounter('counter-rounds', totalRounds);
}

/** Populate the featured #1 player aside. */
function renderFeatured() {
    const host = document.getElementById('hero-featured');
    if (!host) return;
    const players = state.playersData || [];
    if (!players.length) {
        host.innerHTML = '<div class="empty-state">Sin datos de jugadores.</div>';
        return;
    }

    const top = players[0]; // sorted desc by Performance Score
    const tier = tierBadge(top['Performance Score'] || 0);
    const arch = getPlayerArchetype(top);
    const kd = top['K/D Ratio'] || 0;
    const ps = top['Performance Score'] || 0;
    const name = escapeHtml(top.Player);
    const clan = top.Clan ? `${clanLogoHTML(top.Clan, 22)} <span class="featured-clan">${escapeHtml(top.Clan)}</span>` : '';

    host.innerHTML = `
        <div class="card featured-card">
            <div class="featured-rank">#1 · Jugador destacado</div>
            <div class="featured-name">${name}</div>
            <div class="featured-meta">${clan}</div>
            <div class="badge tier-badge ${tier.cssClass}">${tier.emoji} ${escapeHtml(tier.name)}</div>
            <div class="badge featured-archetype">${arch.emoji} ${escapeHtml(arch.name)}</div>
            <div class="featured-stats">
                <div class="stat-row"><span class="stat-label">Performance</span><span class="stat-value">${formatNumber(ps)}</span></div>
                <div class="stat-row"><span class="stat-label">K/D</span><span class="stat-value">${formatNumber(kd)}</span></div>
            </div>
        </div>`;
}

/** Set the last-updated <time> from the max `Last Updated` across players. */
function renderLastUpdated() {
    const el = document.getElementById('last-updated-time');
    if (!el) return;
    const players = state.playersData || [];
    let max = '';
    for (const p of players) {
        const lu = p['Last Updated'];
        if (lu && lu > max) max = lu;
    }
    if (!max) {
        el.textContent = 'N/A';
        return;
    }
    el.textContent = max;
    // "2026-06-14 01:58:41" → valid datetime attr.
    el.setAttribute('datetime', max.replace(' ', 'T'));
}

/** Hero init: counters (load + IntersectionObserver), featured player, last-updated. */
export function initHero() {
    renderFeatured();
    renderLastUpdated();
    animateCounters();

    // Re-trigger the count-up when the hero scrolls into view.
    const hero = document.getElementById('hero');
    if (hero && typeof IntersectionObserver !== 'undefined') {
        const obs = new IntersectionObserver((entries) => {
            entries.forEach((e) => {
                if (e.isIntersecting) {
                    animateCounters();
                    obs.unobserve(e.target);
                }
            });
        }, { threshold: 0.3 });
        obs.observe(hero);
    }
}
