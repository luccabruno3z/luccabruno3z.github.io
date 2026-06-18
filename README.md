# Legion de Hierro — Stats Tracker

Plataforma de analytics para **Project Reality** (BF2). Rastrea +2000 jugadores de 28 clanes latinoamericanos con estadisticas avanzadas, scoring propio y analisis de demos.

**Hecho por W4RR10R para la comunidad de Project Reality LATAM.**

> *"Mejorar como clanes y como jugadores."*

[Ver el sitio](https://luccabruno3z.github.io/) | [Invitar al bot de Discord](https://discord.com/oauth2/authorize?client_id=1344003302859800637&permissions=277025770560&integration_type=0&scope=bot) | [Discord LDH](https://discord.gg/S9ugnuRVsD)

---

## Arquitectura

```
luccabruno3z.github.io/
├── index.html + web/          # Frontend (vanilla JS en ES modules + Chart.js)
│   ├── css/styles.css         #   Design system (dark/cyan, bento, glassmorphism)
│   └── js/                    #   Módulos ES: config, data, utils, charts,
│                              #   autocomplete, main + un módulo por feature
├── bot/                       # Bot de Discord (discord.py 2.0, 8 cogs)
├── scraper/                   # Pipeline de datos (scraping + parser de demos)
├── graphs/                    # Datos generados (JSONs, charts Plotly, historial)
│   ├── history/               #   Historial de Performance Score por jugador
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
| **Bot** | discord.py 2.0, aiohttp, matplotlib | ~8,400 |
| **Scraper** | BeautifulSoup, pandas, numpy, plotly, cloudscraper | ~3,400 |

## Features

### Web Dashboard
- **Dashboard bento** con vistazo en vivo (top jugadores, lideres, top clanes, partidas)
- Busqueda de jugadores con radar chart de 6 ejes y 4 indices de rating
- Comparacion lado a lado (jugador vs jugador, clan vs clan)
- Rankings filtrables por clan y metrica
- Predictor de partidas 8v8
- Analisis de equipo y composicion de squad
- Estadisticas de demos (rondas, mapas, rachas) con **nombres legibles** de assets (kits, armas, vehiculos, mapas, modos) + kit y arma favoritos
- **Leaderboards por periodo** (dia/semana/mes/todo) filtrables por metrica
- **Feed de partidas recientes** (mapa, modo, ganador, kills)
- **Historial de rondas por jugador** en su perfil de demos
- Graficos interactivos Plotly (uno por clan + global), con tema dark/cyan

### Sistema de Scoring (v3)
- **Performance Score**: 7 componentes ponderados (Combat 20%, Effectiveness 15%, Score 10%, Winrate 20%, Teamwork 15%, Consistency 10%, Experience 10%)
- **11 arquetipos de jugador**: Francotirador, Asesino, Superviviente, Veterano, etc.
- **5 tiers dinamicos** por percentil: Elite (~5%), Veterano (~20%), Experimentado (~35%), Soldado (~30%), Recluta (~10%)

### Bot de Discord
8 modulos (cogs):
- `stats` — `-stats`, `-top10`, `-rival`, `-vs`
- `detailed_stats` — `-demo`, `-kits` (uso + K/D por kit), `-armas`, `-vehiculos`, `-mapas`, `-winrate` (W/L + K/D/KPR por modo), `-advanced`
- `compare` — `-compare` (analisis bulk de jugadores/clanes)
- `charts` — `-graph` (graficos renderizados)
- `tips` — `-tip` (150+ tips de gameplay)
- `roles` — Asignacion de roles por guild
- `automation` — Tareas automatizadas
- `countdown` — Countdowns

### Pipeline de Datos
1. **Scraping** de [prstats.realitymod.org](https://prstats.realitymod.org) (28 clanes, siguiendo la paginacion del roster de cada clan — 50 por pagina)
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
- **player_rounds/** — timeline por jugador (escritura por diff, sin churn).
- **player_details.json** y **map_stats.json** — agregados por jugador y por mapa.

### Humanizacion de assets (aliases)
Los `.PRdemo` traen codes internos del juego (`mec_rifleman`, `rurif_ak74m_1p78`,
`ru_jep_tigr_pkp`, `albasrah_2`, `gpm_cq`). `scraper/aliases.py` es la **fuente unica**
que los traduce a nombres legibles en español (Fusilero, AK-74M (1P78), GAZ Tigr (PKP),
Al Basrah, AAS); el scraper genera `graphs/demos/aliases.json` cada corrida y **la web
y el bot lo consumen** (con fallback si falta). Las armas se agrupan por modelo, los
kits por rol (sin caer en "Otro"), y el `?` (entorno) y armas de vehiculo se excluyen
del "arma favorita".

### Desempeño por kit y por modo
- **kit_performance** (en `player_details.json`): K/D por kit, atribuyendo cada baja al
  kit que el jugador tenia puesto en ese momento (solo rondas nuevas; se acumula). Se ve
  en `-kits`.
- **gamemode_stats**: rondas, K/D, KPR y winrate por modo (AAS, Insurgencia, Skirmish…),
  calculado sobre toda la data. Se ve en `-winrate`.

## Clanes rastreados

LDH, FI, SAE, FI-R, R-LDH, 141, WD, 300, E-LAM, RIM:LA, ADG, A-LDH, FASO, PORN, E-102, PTFS, ARA, TANGO, SF, KKCK, SPTS, DARE, FEB, EASY, U777, OSO, LA-9, WK

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
Abrir `index.html` en un navegador o servir con cualquier servidor estatico.

## Deployment

- **Frontend**: GitHub Pages (rama `main`)
- **Bot**: Heroku / Railway (via `Procfile` o `nixpacks.toml`)
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
