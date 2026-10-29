# Arquitectura

Cómo se conectan las tres piezas del proyecto y por dónde viajan los datos.
Para operar el sistema (deploys, fallas comunes) ver [RUNBOOK.md](RUNBOOK.md).

## Vista general

```
                 prstats.realitymod.org          servidores con .PRdemo
                 (rosters de 26 clanes)          (RealityBrasil, LATAMSQUAD, …)
                            │                              │
                            └──────────────┬───────────────┘
                                           ▼
                     ┌───────────────────────────────────────────┐
                     │ scraper/  (GitHub Actions, cron)          │
                     │ python -m scraper                         │
                     └───────────────────────────────────────────┘
                                           │ commit a main
                                           ▼
                     ┌───────────────────────────────────────────┐
                     │ graphs/   (JSON generados, versionados)   │
                     └───────────────────────────────────────────┘
                                           │ GitHub Pages sirve todo
                         ┌─────────────────┴─────────────────┐
                         ▼                                   ▼
     ┌──────────────────────────────────┐   ┌──────────────────────────────────┐
     │ Web  (index.html + web/)         │   │ Bot de Discord  (bot/)           │
     │ GitHub Pages, JS sin build       │   │ Railway, lee graphs/ por HTTP    │
     └──────────────────────────────────┘   │ estado propio en el volumen /data│
                                            └──────────────────────────────────┘
```

Puntos clave:

- **Una sola fuente de datos.** El scraper es lo único que escribe datos de juego.
  La web y el bot solo leen `graphs/` desde `https://luccabruno3z.github.io/graphs/…`.
- **No hay backend ni base de datos.** Los JSON versionados en git son la base de
  datos, y GitHub Pages es la API.
- **El bot no lleva los datos en su imagen.** Los baja por HTTP con caché
  (refresco cada 5 min). Por eso `.dockerignore` excluye `graphs/`, `web/` y `scraper/`.
- **El bot solo guarda su propio estado** (vínculos Discord→IGN, canales, roles,
  sugerencias) en el volumen persistente `/data` de Railway.

## Pipeline del scraper

`scraper/main.py::run()` hace, en orden:

| # | Paso | Salida |
|---|---|---|
| 1–3 | Baja y parsea los rosters de cada clan (paginación de 50) y arma un DataFrame | — |
| 4 | Calcula el Performance Score (`scraper/scoring.py`) | — |
| 5 | Calcula los cortes de tier por percentil | `graphs/tier_config.json` |
| 6 | Marca actividad real (`scraper/activity.py`) | `graphs/activity/rounds_log.json` |
| 6 | JSON de jugadores y promedios | `all_players_clusters.json`, `clan_averages.json`, `clan_averages_active.json`, `<CLAN>_players.json` |
| 7 | Gráficos Plotly | `graphs/*_interactive_chart.html` |
| 8 | Historial de Performance por jugador | `graphs/history/` |
| 9 | Descubre servidores con demos | `graphs/demos/discovered_servers.json` |
| 10 | Baja y parsea `.PRdemo` nuevos, y recalcula agregados | `graphs/demos/…` (ver abajo) |

Cada corrida procesa como mucho `MAX_DEMOS_PER_RUN` demos dentro de
`DEMO_TIME_BUDGET` segundos (`scraper/config.py`). Lo que no entra queda para la
siguiente corrida; `processed.json` evita repetir demos.

### Datos derivados de demos (`graphs/demos/`)

| Archivo | Qué tiene | Lo usan |
|---|---|---|
| `rounds/<fecha>.json` + `index.json` | Rondas particionadas por día (los días pasados no se reescriben) | web (partidas, heatmap por ronda) |
| `leaderboards/{dia,semana,mes,todo}.json` | Rankings precalculados por período | web, bot (`-top_periodo`, leaderboard semanal) |
| `player_rounds/` | Timeline de rondas por jugador: fecha y hora, mapa, modo, servidor, bando, kit, K, D, score, revives y resultado | web (perfil: forma reciente e historial), bot (historial, última ronda) |
| `player_details.json` | Agregados por jugador: kits, armas, vehículos, combate, modos | web, bot |
| `map_stats.json` | Duración, kills y resultados por mapa | web, bot (`-mapa`) |
| `synergy.json` | Rendimiento con cada compañero de escuadra | web, bot (`-sinergia`) |
| `role_leaderboards.json` | Top por rol, histórico y últimos 30 días (`scraper/roles.py`) | web (Rankings → Por rol), bot (`-top_rol`) |
| `heatmaps/<mapa>.json` | Grillas de densidad por modo y capa del mapa (`gpm_cq_64`, `gpm_cq_16`…) | web (heatmaps) |
| `aliases.json` | Códigos internos del juego → nombres legibles | web, bot |

El detalle de cada campo está en el [README](../README.md#pipeline-de-datos) y el
contrato de formatos en [.rebuild/CONTRACT.md](../.rebuild/CONTRACT.md).

## Conceptos del dominio

### Performance Score y tiers
- **Performance Score** (0–1): siete componentes ponderados (Combat, Effectiveness,
  Score, Winrate, Teamwork, Consistency, Experience). Ver `scraper/scoring.py`.
  Cada jugador trae `ps_components` (el nivel 0–1 de cada uno, `null` si falta demo y
  cuenta neutro) y `tier_config.json` trae el orden y el peso en `ps_components`; con
  eso la web arma el desglose sin recalcular percentiles.
- **Tiers** (Elite, Veterano, Experimentado, Soldado, Recluta): cortes por percentil
  del Performance, recalculados en cada corrida y publicados en `tier_config.json`.
  El tier solo describe el Performance.
- **Barras por percentil.** Las demás métricas (K/D, letalidad, combate…) se muestran
  según la posición del jugador frente al resto, con los cortes `RANK_CUTS`
  (10 %, 40 %, 75 %, 95 %), en la web y en el bot. Antes se coloreaban con los cortes
  de tier del Performance, y por eso alguien podía verse "Veterano" en una métrica
  y "Recluta" en otra sin que tuviera sentido.
- Para entrar en los rankings hacen falta **50 rondas** (`MIN_ROUNDS` /
  `LOW_ROUNDS_THRESHOLD`).

### Actividad (últimos 30 días)
Un jugador cuenta como **activo** si pasa al menos una de estas dos cosas:
1. Sus rondas en PRStats subieron en los últimos 30 días. `rounds_log.json` guarda
   cuándo cambió por última vez el contador de cada jugador.
2. Su última ronda con demo (`last_round_date`) es de los últimos 30 días.

Con eso se arman los dos rankings de clanes:
- **Histórico** (`clan_averages.json`): todos los jugadores del clan.
- **Activos** (`clan_averages_active.json`): los 50 mejores jugadores activos de cada
  clan por Performance. El clan necesita al menos 5 activos para aparecer.

### Roles
El rol de cada kill y cada muerte sale del kit que el jugador tenía puesto en ese
momento (`kit_kills`, `kit_deaths` y, en rondas nuevas, `kit_alive_ticks`). No se usa
`kits_used`, porque cuenta también los kits que se miran en el menú antes de reaparecer
y los que se levantan del piso: con ese dato, la mitad de la comunidad salía médico.
Para mostrar qué juega alguien está `kit_activity` (kills + muertes con cada kit).

Los nombres de los kits siguen el [manual oficial de PR](https://www.realitymod.org/manual/en/kits.html)
(`scraper/aliases.py`, `KIT_ROLES`). Algunos códigos internos no dicen el kit; se
comprobaron con las armas con que matan los jugadores de cada uno:

| Código | Kit (manual) | En el sitio |
|---|---|---|
| `support` | Automatic Rifleman | Fusilero automático |
| `assault` | Grenadier | Granadero |
| `specialist` | Breacher | Breacher |
| `riflemanat` | Light Anti-Tank (LAT) | Anti-tanque ligero |
| `at` | Heavy Anti-Tank (HAT) | Anti-tanque pesado |
| `engineer` | Combat Engineer | Ingeniero de combate |

Los arquetipos (`scraper/scoring.py`) no son kits: Médico, Oficial, Tripulante y
Anti-tanque se asignan por el kit que más juega alguien, y Preciso, Asesino,
Superviviente, Dominante, Todoterreno e Infante por su perfil de estadísticas.

`scraper/roles.py` mide cada rol por lo que le toca hacer: revives por ronda para el
médico, kills con lanzador para el AT, kills con armas de vehículo para el tripulante,
kills desde aeronaves para el piloto, victorias para el oficial y K/D para el resto.
Para que una ronda excepcional no defina a nadie:
- el valor se **ajusta por muestra**: con pocas rondas o muertes se acerca a la
  mediana del rol;
- la **confianza** es alta con 15+ rondas, y baja con menos de 8 o si una sola ronda
  explica más del 40 % del resultado;
- al top entran jugadores con 10+ rondas con el rol y confianza media o alta. El
  "mejor rol" del perfil sigue la misma regla.

Cada jugador de `player_details.json` trae `roles` (actividad, valor, mediana,
percentil y confianza por rol) y `best_role`.

### Kills en vehículos
El parser olvida el vehículo de un jugador cuando muere o reaparece. Antes solo lo
olvidaba al bajarse, así que las kills a pie de la vida siguiente se sumaban al último
vehículo (por ejemplo, 14 kills "con mortero" hechas con un AK-74M). Las rondas viejas
mantienen ese error en `vehicle_kills`, así que la web y el bot cuentan las kills con
vehículos a partir del arma de cada kill (`kill_weapons`).

### Matching de nombres
Las demos traen el IGN con el tag del clan (`[LDH] juan*ARG*`) y PRStats lo trae sin
tag. `ClanMatcher` los cruza respetando mayúsculas y minúsculas, y solo usa la
comparación sin distinguirlas cuando no hay ambigüedad.

## Decisiones y compromisos

| Decisión | Por qué | Costo |
|---|---|---|
| JSON en git en lugar de una base de datos | Gratis, con historial y servido por Pages | El repo pesa (~2,7 GB); hay que particionar lo grande (por ejemplo `rounds/`) |
| Sin Git LFS | Pages serviría el puntero de LFS y no el archivo | Ningún archivo puede pasar de 100 MB |
| Web sin build (ES modules) | Cero tooling y se publica con solo pushear | Sin bundling; cuidado con la caché del navegador |
| El bot lee por HTTP | Imagen chica y deploys rápidos; siempre ve los últimos datos | Si Pages se cae, el bot usa la caché |
| Cortes por percentil y no fijos | Se adaptan a la población | Un jugador puede cambiar de tier sin jugar |
