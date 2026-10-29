# Legion de Hierro — Stats Tracker

Plataforma de analytics para **Project Reality** (BF2). Rastrea +2000 jugadores de 26 clanes latinoamericanos con estadisticas avanzadas, scoring propio y analisis de demos.

**Hecho por W4RR10R para la comunidad de Project Reality LATAM.**

> *"Mejorar como clanes y como jugadores."*

[Ver el sitio](https://luccabruno3z.github.io/) | [Invitar al bot de Discord](https://discord.com/oauth2/authorize?client_id=1344003302859800637&permissions=277025770560&integration_type=0&scope=bot) | [Discord LDH](https://discord.gg/S9ugnuRVsD)

## Documentación

| Documento | Para quién / para qué |
|---|---|
| [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) | Cómo se conectan scraper → `graphs/` → web y bot; Performance, tiers, actividad |
| [docs/BOT.md](docs/BOT.md) | Comandos del bot, `-menu`, estructura del código, estado persistente |
| [docs/WEB.md](docs/WEB.md) | Vistas y rutas, módulos compartidos, íconos, estilos |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | Deploys, logs y qué hacer cuando algo falla |
| [.rebuild/CONTRACT.md](.rebuild/CONTRACT.md) | Contrato de formato de los JSON de `graphs/` |

---

## Arquitectura

```
luccabruno3z.github.io/
├── index.html + web/          # Frontend (vanilla JS en ES modules + Chart.js)
│   ├── css/styles.css         #   Design system (dark/cyan, bento, glassmorphism)
│   └── js/                    #   Módulos ES: config, data, utils, charts,
│                              #   autocomplete, main + un módulo por feature
├── bot/                       # Bot de Discord (discord.py 2.7, 12 cogs, Components V2)
├── scraper/                   # Pipeline de datos (scraping + parser de demos)
├── docs/                      # Documentación (arquitectura, bot, web, runbook)
├── graphs/                    # Datos generados (JSONs, charts Plotly, historial)
│   ├── history/               #   Historial de Performance Score por jugador
│   ├── activity/              #   rounds_log.json: actividad real (30 días)
│   └── demos/                 #   Datos derivados de .PRdemo:
│       ├── rounds/            #     Rondas particionadas por dia + index.json
│       ├── leaderboards/      #     Rankings precalculados (dia/semana/mes/todo)
│       ├── player_rounds/     #     Timeline de rondas por jugador
│       ├── player_details.json   #     Agregados por jugador (incl. kit_performance, gamemode_stats)
│       ├── map_stats.json
│       └── aliases.json          #     Nombres legibles de assets (kits/armas/vehiculos/mapas/modos)
├── guides/                    # Paginas de guias HTML
└── logos/                     # Logos de clanes
```

| Componente | Stack | Lineas |
|---|---|---|
| **Frontend** | HTML5, CSS3 (dark/cyan, bento, glassmorphism), Vanilla JS (ES modules), Chart.js | ~5,500 |
| **Bot** | discord.py 2.7 (Components V2), aiohttp, matplotlib | ~8,400 |
| **Scraper** | BeautifulSoup, pandas, numpy, plotly, cloudscraper | ~3,400 |

## Features

### Web Dashboard
Organizada en pestañas con rutas por hash (`#/inicio`, `#/jugadores`, `#/rankings`,
`#/clanes`, `#/partidas`, `#/equipos`, `#/guias`) — ver [docs/WEB.md](docs/WEB.md).
- **Dashboard bento** con vistazo en vivo (top jugadores, lideres, top clanes, partidas)
- Busqueda de jugadores con radar chart de 6 ejes y 4 indices de rating
- Comparacion lado a lado (jugador vs jugador, clan vs clan)
- Rankings filtrables por clan y metrica, con podio y barras por percentil
- **Dos rankings de clanes**: histórico (todos los jugadores) y **activos** (top 50
  jugadores activos en los últimos 30 días), con gráfico que sigue la métrica elegida
- Predictor de partidas 8v8
- Analisis de equipo y composicion de squad
- **Perfil de demos por jugador con pestañas** (Resumen, Combate, Armas & Vehículos,
  Assets, Kits & Modos, Sinergia, Rondas) — espeja los comandos del bot con nombres
  legibles de assets, K/D por kit, vehículos honestos, desglose por tipo de medio,
  vida promedio/racha/clutch, y **sinergia de dúo** (mejores/peores compañeros)
- **Heatmaps por mapa** (`#heatmaps`): 5 capas (🔥 muertes, 🧭 recorridos, 📍 spawns,
  🎯 francotiradores, 🔫 líneas de fuego) en canvas (sin dependencias) con **zoom/pan**,
  filtrables por **equipo, gamemode** (AAS/Insurgencia/Skirmish… separados para no mezclar
  zonas) y **ronda** (todas o una específica), sobre el **minimapa real** de cada mapa (81 en
  `web/img/maps/`, del Map Gallery por `scraper/fetch_minimaps.py`; fallback a fondo neutro).
  Overlay de **🚩 banderas/CPs**, **heatmap por jugador** (👤 dónde mata vs dónde muere) e
  **iconos oficiales** de vehículos (atlas del realitytracker, `scraper/fetch_atlas.py`)
- **Leaderboards por periodo** (dia/semana/mes/todo) filtrables por metrica
- **Feed de partidas recientes** (mapa, modo, ganador, kills) + duración/kills-min por mapa
- **Historial de rondas por jugador** en su perfil de demos
- Graficos interactivos Plotly (uno por clan + global), con tema dark/cyan

### Sistema de Scoring (v3)
- **Performance Score**: 7 componentes ponderados (Combat 20%, Effectiveness 15%, Score 10%, Winrate 20%, Teamwork 15%, Consistency 10%, Experience 10%)
- **11 arquetipos de jugador**: Francotirador, Asesino, Superviviente, Veterano, etc.
- **5 tiers dinamicos** por percentil: Elite (~5%), Veterano (~20%), Experimentado (~35%), Soldado (~30%), Recluta (~10%)

### Bot de Discord
12 cogs, respuestas con Components V2 y botones persistentes. Lo principal:
- `-menu` — panel navegable (perfil, rankings, clanes, partidas, equipos)
- `-perfil` / `-stats` — perfil con pestañas (Resumen, Récords, Perfil, Historial) y barras de color por percentil
- `-vincular <IGN>` — asocia tu cuenta de Discord a tu jugador
- `-top` (`-top activos`), `-top_periodo`, `-top_rol` (mejores médicos, AT, tripulantes…), `-promedios`, `-promedios_activos`
- `-compare`, `-prediccion`, `-analizar_equipo`
- Detalle de demos: `-kits`, `-armas`, `-vehiculos`, `-assets`, `-combate`, `-sinergia`, `-winrate`, `-mapa`
- Leaderboard automático los lunes (`-set_leaderboard_channel`)

Lista completa y estructura del código en [docs/BOT.md](docs/BOT.md).

### Pipeline de Datos
1. **Scraping** de [prstats.realitymod.org](https://prstats.realitymod.org) (26 clanes, siguiendo la paginacion del roster de cada clan — 50 por pagina)
2. **Parsing** de archivos `.PRdemo` (formato binario BF2) de varios servidores —
   RealityBrasil, LATAMSQUAD, ARES Brasil, TikTok War y Russian Frontier — soportando
   listados Apache planos, particionados por mes (`YYYY_MM/`) y la API JSON de HFS.
   Descarga con reintentos/backoff; hosts inestables se difieren. Se **excluye gungame**.
3. **Scoring** con normalizacion y clustering
4. **Generacion** de JSONs, charts Plotly, historial, aliases de assets y agregados
   por kit/gamemode
5. **Auto-discovery** de servidores con demos + fuentes curadas en `scraper/config.py`

### Almacenamiento de rondas (escalable)
Las rondas de demos se guardan **particionadas por dia** (`graphs/demos/rounds/<fecha>.json`)
en vez de un unico archivo monolitico. Los dias pasados son inmutables, asi que cada
corrida del scraper solo reescribe el archivo del dia actual: el historial de git se
mantiene chico y **ningun archivo se acerca al limite de 100 MB de GitHub**. Un
`index.json` lista las fechas disponibles.

El matching de IGN de demo → cuenta de prstats es **case-sensitive de dos niveles**
(`ClanMatcher`): respeta cuentas distintas que solo difieren en mayusculas
(p. ej. `Dev.CO` vs `Dev.Co`), con fallback case-insensitive solo cuando es inequivoco.

Sobre esas rondas se precalculan:
- **Leaderboards** por periodo (`leaderboards/{dia,semana,mes,todo}.json`) — el bot y la
  web leen un archivo de pocos KB en vez de procesar todo el historial.
- **player_rounds/** — timeline por jugador (escritura por diff, sin churn). Cada ronda:
  `date`, `time`, `map`, `gamemode`, `server` (nombre corto, `server_label()`),
  `faction`, `kit` (el más usado de la ronda), `kills`, `deaths`, `score`, `revives`,
  `won`. Las rondas guardadas antes de octubre de 2026 no traen `kit`; `server`, `time` y
  `faction` aparecen al reconstruirse con la próxima corrida.
- **player_details.json** y **map_stats.json** — agregados por jugador y por mapa.

### Humanizacion de assets (aliases)
Los `.PRdemo` traen codes internos del juego (`mec_rifleman`, `rurif_ak74m_1p78`,
`ru_jep_tigr_pkp`, `albasrah_2`, `gpm_cq`). `scraper/aliases.py` es la **fuente unica**
que los traduce a nombres legibles en español (Fusilero, AK-74M (1P78), GAZ Tigr (PKP),
Al Basrah, AAS); el scraper genera `graphs/demos/aliases.json` cada corrida y **la web
y el bot lo consumen** (con fallback si falta). Las armas se agrupan por modelo, los
kits por rol (sin caer en "Otro"), y el `?` (entorno) y armas de vehiculo se excluyen
del "arma favorita". Cada arma montada se etiqueta ademas con el vehiculo que la porta
(`vehicle`), su clase (`vclass`: vehiculo tripulado vs emplazamiento) y su tipo amplio
(`vtype`: terrestre/aereo/naval/emplazamiento) — base de `-vehiculos` y `-assets`.

### Kills con vehiculos (honesto)
Las "kills con vehiculos" se derivan de `kill_weapons` (el arma que hizo la baja),
**no** de `vehicle_kills` (que atribuia las kills a pie tras desmontar de un transporte
— de ahi que antes un camion de logistica desarmado liderara el ranking). Como un camion
de apoyo no tiene `kill_weapons`, la contaminacion desaparece. Ademas el parser ahora
limpia el vehiculo del jugador al desmontar (`vehicle.id < 0`), asi que `vehicle_kills`
tambien queda correcto de ahora en mas.

### Desempeño por kit y por modo
- **kit_performance** (en `player_details.json`): K/D por kit, atribuyendo cada baja al
  kit que el jugador tenia puesto en ese momento (solo rondas nuevas; se acumula). Se ve
  en `-kits`.
- **gamemode_stats**: rondas, K/D, KPR y winrate por modo (AAS, Insurgencia, Skirmish…),
  calculado sobre toda la data. Se ve en `-winrate`.

### Datos nuevos extraidos de las demos
El parser ahora aprovecha campos del `.PRdemo` que antes se descartaban (se acumulan
desde las rondas nuevas):
- **vehicles_destroyed_by_type**: que vehiculo destruyo cada jugador (tanque/heli/jeep…),
  no solo el conteo. Se ve en `-vehiculos`.
- **seat_kills**: kills segun el asiento del vehiculo (artillero/conductor/piloto…),
  humanizado via `aliases.json["seats"]`. Se ve en `-vehiculos`.
- **squad** (por jugador) + **squad_names** (por ronda): escuadra predominante. El byte
  de escuadra trae el bit `0x80` para el **líder** (129 = SL de la escuadra 1, 128 =
  comandante): el parser lo enmascara (`& 0x7F`) para que el SL cuente dentro de su
  escuadra. `rounds_in_squad` / `rounds_with_squad_data` se siguen publicando pero no se
  muestran: por reglamento todos juegan en una escuadra (~95 % para cualquiera).
- **kill_positions** (por ronda): posicion `[x, z, equipo]` de cada muerte — se captura
  ya (las demos se borran tras procesarse) para un **heatmap por mapa** a futuro en la web.
- **Logger de mensajes desconocidos**: el decoder cuenta los `msg_type` que el protocolo
  no reconoce y los loguea, para descubrir contenido nuevo de versiones recientes de PR.

### Combate fino, tiempo y cohesion (`-combate`, `-teamwork`, `-mapa`)
Más señales por jugador, todas acumuladas desde las rondas nuevas:
- **Duración de ronda**: el mensaje TICKS se leía como uint16 cuando es uint8 → se
  descartaba y `duration_ticks` quedaba en 0. Corregido: `duration_seconds =
  nº de TICKS × demo_time_per_tick`. Habilita **kills/min** y duración por mapa (`-mapa`).
- **Vida promedio** y **kills/min con vida**: de las transiciones `is_alive`. (`-combate`)
- **Mejor racha** (kills sin morir), **first blood**, **kills clutch** (con el equipo a
  ≤25 tickets), **teamkills/suicidios por jugador**. (`-combate`)
- **Juego con la escuadra** (`-teamwork`, perfil, escuadras de clan): lo que importa es
  si el jugador va con su escuadra o juega solo.
  - `near_hits` / `near_samples`: cada ~10 s, con el jugador **vivo**, si tiene un
    compañero de escuadra vivo a **≤ 50 m** (`SQUAD_NEAR_M`). El que está solo en su
    escuadra cuenta como lejos; si sus compañeros están todos muertos no se mide. Se
    muestra con 600+ muestras (~3 rondas vivo). Solo rondas desde octubre de 2026.
  - `cohesion_sum` / `cohesion_samples`: distancia media al centro de su escuadra. Tiene
    historial pero es más gruesa (cuenta muertos, castiga a la escuadra partida en dos
    equipos de fuego y, antes de la máscara del líder, dejaba al SL afuera). Se usa
    mientras no hay muestra de la otra. Cuartiles de la comunidad: ~205 / 255 / 315 m.
- **Tiempos validados**: algunos demos traen el encabezado del servidor corrupto (p. ej.
  35 millones de segundos por tick). `round_time_per_tick()` y `round_duration()`
  (`scraper/rounds_store.py`) descartan valores fuera de rango (> 2 s por tick, > 8 h
  por ronda) al sumar `alive_seconds`, `played_seconds` y la duración por mapa; el parser
  también lo filtra al leer `ServerDetails`.

### Sinergia de dúo (`synergy.json`, `-sinergia`)
Por jugador, su rendimiento jugando en la **misma escuadra** que cada compañero
frecuente: dos jugadores son compañeros en una ronda si comparten `(equipo, escuadra>0)`.
Se acumulan las stats del jugador en las rondas con cada compañero y se comparan contra
su baseline (rondas sin ese compañero) → impacto en KPR + winrate juntos. Mínimo 3
rondas compartidas para mostrarse. Se reconstruye desde todas las rondas con dato de squad
(con la máscara del líder, así el SL cuenta con su escuadra también en las rondas viejas).

### Heatmaps por mapa (`graphs/demos/heatmaps/` + `web/img/maps/`)
Grilla de densidad de muertes por mapa a partir de `kill_positions`. El origen del
mundo (0,0) es el centro del mapa y este abarca `map_size` km, así que se normaliza
`nx = (x + map_size*500) / (map_size*1000)` (eje horizontal `x,z`; `y` es altitud) a una
grilla de 128×128. **Cada ronda nueva de ese mapa suma** (se reconstruye desde todas las
rondas). Celdas dispersas con muertes por equipo `[gx, gy, t1, t2]` → un archivo por mapa
+ `index.json`. El **render web** (`web/js/heatmaps.js`) dibuja la densidad con suavizado
(blobs + LUT de color) sobre el **minimapa real** del mapa, con **zoom/pan**; el minimapa
y la densidad comparten la misma normalización centrada al mapa, así que se alinean sin
recalibrar (BF2 invierte el eje Z → `FLIP_Y`). Los minimapas (`web/img/maps/`, 4096px JPEG)
los baja `scraper/fetch_minimaps.py` del Map Gallery oficial.

Cada `heatmaps/<mapa>.json` separa las capas **por modo y capa del mapa**
(`gamemodes: {gpm_cq_64, gpm_cq_16, gpm_skirmish_16, …}`, de `_mode_layer()`): el mismo
modo se juega con zonas y banderas distintas según la capa (AAS 16 es la de infantería,
parecida a Skirmish; AAS 64 la estándar), así que no se mezclan. La web los muestra como
"AAS · Estándar (64)" (`modeLayerLabel`). Lista sus rondas
(`rounds: [{filename,date,gamemode}]`, con `gamemode` = esa misma clave) para el selector
de ronda (la web carga esa ronda de `rounds/<fecha>.json` y la agrega en cliente). Cada
modo y capa tiene **4 capas de datos** (radio en la web), acumuladas de todas sus rondas,
filtrables por equipo:
- **deaths**: dónde muere cada equipo (`kill_positions` víctima).
- **movement**: rutas más transitadas por equipo (densidad de paso — se cuenta al entrar
  a una celda nueva, así traza recorridos y no campeo; muestreada cada ~10s).
- **spawns**: puntos de aparición por equipo (posición al revivir, evento `is_alive`).
- **sniper**: posición del atacante en bajas con **arma personal a >150m** (de la distancia
  atacante↔víctima guardada por kill). Excluye armas de vehículo (jets/tanques) para que
  sean tiradores reales, no CAS.

## Clanes rastreados

LDH, FI, FI-R, R-LDH, WD, 300, E-LAM, RIM:LA, ADG, A-LDH, FASO, PORN, E-102, ARA, TANGO, SF, KKCK, SPTS, DARE, FEB, EASY, U777, OSO, LA-9, WK, FAL

## Setup local

### Requisitos
- Python 3.12+
- Node no requerido (frontend vanilla)

### Scraper
```bash
pip install -r requirements-scraper.txt
python -m scraper
```

### Bot de Discord
```bash
pip install -r requirements-bot.txt
# Configurar .env con DISCORD_TOKEN
python -m bot
```

### Frontend
Servir la raíz con cualquier servidor estático (los ES modules no cargan desde `file://`):
```bash
python -m http.server 8000
```

## Deployment

- **Frontend**: GitHub Pages (rama `main`)
- **Bot**: Railway (`nixpacks.toml` → `python -m bot`), con volumen en `/data` para el
  estado persistente. `.dockerignore` deja `graphs/`, `web/` y `scraper/` fuera de la imagen.
  Operación y fallas comunes: [docs/RUNBOOK.md](docs/RUNBOOK.md)
- **Scraper**: GitHub Actions (cron programado; GitHub puede espaciar las corridas de
  cron de alta frecuencia), commitea datos actualizados a `main`

> **Nota:** los datos NO usan Git LFS (Pages sirve el puntero, no el contenido).
> Si agregas datasets grandes, particionalos como `graphs/demos/rounds/`.

### Migracion del historial de rondas
Para partir un `round_history.json` monolitico antiguo a la estructura por dia:
```bash
python -m scraper.migrate_rounds
```

## Sugerencias y contacto

Abierto a sugerencias. Cualquier duda:

- [Discord de Legion de Hierro](https://discord.gg/S9ugnuRVsD)
- Email: luccabruno96@gmail.com
