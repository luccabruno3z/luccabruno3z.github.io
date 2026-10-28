# Web

Sitio estático en GitHub Pages: `index.html` + `web/` (CSS y ES modules, sin paso de
build) y Chart.js por CDN. Está en vivo en <https://luccabruno3z.github.io/>.

## Correrla localmente

Los módulos ES no cargan desde `file://`, así que hace falta un servidor estático:

```bash
python -m http.server 8000
```

y abrís <http://localhost:8000/>. Los datos se piden siempre a
`https://luccabruno3z.github.io/graphs/…` (`web/js/config.js`), así que localmente
ves los datos publicados aunque no tengas `graphs/` en el checkout.

## Vistas y rutas

Cada pestaña del menú es una vista. `web/js/router.js` las rutea por hash:
`#/<vista>` muestra la vista y `#/<vista>/<id-de-sección>` además scrollea a esa
sección.

| Vista | Ruta | Secciones (`id`) | Módulos |
|---|---|---|---|
| Inicio | `#/inicio` | `hero`, `dashboard` | `hero.js`, `dashboard.js` |
| Jugadores | `#/jugadores` | `player-search-section`, `comparison` | `player.js`, `comparison.js` |
| Rankings | `#/rankings` | `rankings`, `leaderboards`, `role-leaderboards` | `rankings.js`, `leaderboards.js`, `roles.js` |
| Clanes | `#/clanes` | `clan-averages`, `charts` | `clans.js`, `charts.js` |
| Partidas | `#/partidas` | `recent-matches`, `heatmaps`, `demo-stats` | `matches.js`, `heatmaps.js`, `demos.js` |
| Equipos | `#/equipos` | `match-predictor`, `team-analysis` | `predictor.js`, `team.js`, `chips.js` |
| Guías | `#/guias` | `guides`, `social` | — |

Los anchors viejos (`#rankings`, `#heatmaps`, `#guias`…) siguen funcionando: el router
los traduce a la ruta nueva. El bot y algunos links externos todavía los usan.

## Módulos compartidos

| Archivo | Para qué |
|---|---|
| `main.js` | Arranque: router, íconos y carga de datos, y después cada feature dentro de `safe()` para que un error en una no tire abajo la página |
| `data.js` | Carga y caché de los JSON (`state.playersData`, tier config, alias, logos) |
| `config.js` | URLs de datos y constantes (`MIN_ROUNDS_FOR_RANKING`, `NORM_CAPS`) |
| `ui.js` | Componentes HTML reutilizables: `barHTML`, `tierBarHTML`, `rankBarHTML` (por percentil), `versusBarHTML`, `tierChipHTML`, `podiumHTML`, `tableHTML`, `posHTML` |
| `utils.js` | Formato, nombres legibles de assets (`kitLabel`, `weaponLabel`…), tiers, `clanLogoHTML`, `escapeHtml` |
| `icons.js` | Reemplaza emojis por íconos SVG (ver abajo) |
| `chips.js` | Selector de jugadores con chips para Equipos |
| `autocomplete.js` | Autocompletado de jugadores y clanes |

### Íconos: emojis → SVG
Los textos (HTML, JS y hasta datos del scraper como los arquetipos) pueden traer
emojis. `icons.js` recorre la página y reemplaza cada emoji conocido por un SVG de
trazo, incluido lo que se pinte después, gracias a un `MutationObserver`. Para sumar
uno, agregá el trazo en `PATHS` y el emoji en `EMOJI`. Un emoji que no esté en el mapa
se muestra tal cual.

### Selector con chips
En Equipos, `chips.js` reemplaza las grillas de 8 campos por un único campo con
chips. Los campos originales siguen en el DOM, ocultos, y el selector los llena en
orden. Así `predictor.js` y `team.js` los leen por id sin saber que hay chips.

### Perfil de jugador
`player.js` arma primero lo que sale de PRStats (cabecera con las fuentes de datos,
KPIs, camino al próximo tier con los 7 componentes del Performance y contexto de clan)
y después, cuando llegan las demos, completa forma reciente, fortalezas y a mejorar,
roles, datos de demos y récords. Cada bloque de demos se oculta si no hay muestra
suficiente.

## Estilos

Todo está en `web/css/styles.css`, organizado en secciones numeradas. Las más
recientes:

| Sección | Contenido |
|---|---|
| 28 | Componentes de datos (barras, podios, tablas) |
| 29 | Perfil de jugador |
| 31 | Un solo título por vista |
| 32 | Botones unificados (44 px de alto, radio 10) |
| 33 | Íconos `.ico` |
| 34 | Chips |
| 35 | Comparación, demos y guías |
| 36 | Perfil v2 (fuentes, camino al próximo tier, forma reciente, clan, roles) |

Los colores y espacios salen de variables CSS en `:root`. Usalas en vez de valores
sueltos.

## Caché y service worker

`sw.js` es *network-first*: siempre intenta la red y usa la caché solo sin conexión.
Si después de un deploy seguís viendo una versión vieja, el problema suele ser la
caché HTTP del navegador con los módulos. Probá con recarga forzada (Ctrl+F5). Si
cambiás la lógica del service worker, subí `CACHE_NAME` para limpiar las cachés
viejas.

## Publicar

Hacer push a `main` publica la web: GitHub Pages sirve la rama tal cual, sin build.
Antes de pushear:
1. Abrí cada vista que tocaste y revisá la consola (que no haya errores).
2. Probá en ancho de celular (375 px): no tiene que aparecer scroll horizontal.
3. Si tocaste datos que usa el bot, revisá también que el bot los lea bien.
