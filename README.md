# Legion de Hierro — Stats Tracker

Plataforma de analytics para **Project Reality** (BF2). Rastrea +2000 jugadores de 21 clanes latinoamericanos con estadisticas avanzadas, scoring propio y analisis de demos.

**Hecho por W4RR10R para la comunidad de Project Reality LATAM.**

> *"Mejorar como clanes y como jugadores."*

[Ver el sitio](https://luccabruno3z.github.io/) | [Invitar al bot de Discord](https://discord.com/oauth2/authorize?client_id=1344003302859800637&permissions=277025770560&integration_type=0&scope=bot) | [Discord LDH](https://discord.gg/S9ugnuRVsD)

---

## Arquitectura

```
luccabruno3z.github.io/
├── index.html + web/          # Frontend (SPA vanilla JS + Chart.js)
├── bot/                       # Bot de Discord (discord.py 2.0, 8 cogs)
├── scraper/                   # Pipeline de datos (scraping + parser de demos)
├── graphs/                    # Datos generados (JSONs, charts Plotly, historial)
│   ├── history/               #   Historial de Performance Score por jugador
│   └── demos/                 #   Datos derivados de .PRdemo:
│       ├── rounds/            #     Rondas particionadas por dia + index.json
│       ├── leaderboards/      #     Rankings precalculados (dia/semana/mes/todo)
│       ├── player_rounds/     #     Timeline de rondas por jugador
│       ├── player_details.json
│       └── map_stats.json
├── guides/                    # Paginas de guias HTML
└── logos/                     # Logos de clanes
```

| Componente | Stack | Lineas |
|---|---|---|
| **Frontend** | HTML5, CSS3 (glassmorphism), Vanilla JS, Chart.js | ~5,100 |
| **Bot** | discord.py 2.0, aiohttp, matplotlib | ~8,400 |
| **Scraper** | BeautifulSoup, pandas, numpy, plotly, cloudscraper | ~3,400 |

## Features

### Web Dashboard
- Busqueda de jugadores con radar chart de 6 ejes y 4 indices de rating
- Comparacion lado a lado (jugador vs jugador, clan vs clan)
- Rankings filtrables por clan y metrica
- Predictor de partidas 8v8
- Analisis de equipo y composicion de squad
- Estadisticas de demos (rondas, mapas, rachas)
- **Leaderboards por periodo** (dia/semana/mes/todo) filtrables por metrica
- **Feed de partidas recientes** (mapa, modo, ganador, kills)
- **Historial de rondas por jugador** en su perfil de demos
- 21 graficos interactivos Plotly (uno por clan + global)

### Sistema de Scoring (v3)
- **Performance Score**: 7 componentes ponderados (Combat 20%, Effectiveness 15%, Score 10%, Winrate 20%, Teamwork 15%, Consistency 10%, Experience 10%)
- **11 arquetipos de jugador**: Francotirador, Asesino, Superviviente, Veterano, etc.
- **5 tiers dinamicos** por percentil: Elite (~5%), Veterano (~20%), Experimentado (~35%), Soldado (~30%), Recluta (~10%)

### Bot de Discord
8 modulos (cogs):
- `stats` — `-stats`, `-top10`, `-rival`, `-vs`
- `detailed_stats` — `-demo`, `-advanced` (historial de rondas)
- `compare` — `-compare` (analisis bulk de jugadores/clanes)
- `charts` — `-graph` (graficos renderizados)
- `tips` — `-tip` (150+ tips de gameplay)
- `roles` — Asignacion de roles por guild
- `automation` — Tareas automatizadas
- `countdown` — Countdowns

### Pipeline de Datos
1. **Scraping** de [prstats.realitymod.org](https://prstats.realitymod.org) (21 clanes)
2. **Parsing** de archivos `.PRdemo` (formato binario BF2) de servidores LATAM
3. **Scoring** con normalizacion y clustering
4. **Generacion** de JSONs, charts Plotly e historial de jugadores
5. **Auto-discovery** de servidores con demos disponibles

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

## Clanes rastreados

LDH, FI, SAE, FI-R, R-LDH, 141, WD, 300, E-LAM, RIM:LA, ADG, A-LDH, FASO, PORN, E-102, PTFS, ARA, TANGO, SF, KKCK, SPTS

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
- **Scraper**: GitHub Actions — corre cada hora, commitea datos actualizados a `main`

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
