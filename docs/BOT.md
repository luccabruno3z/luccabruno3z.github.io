# Bot de Discord

Bot en `discord.py` 2.7 que muestra las estadísticas del proyecto en Discord. El
prefijo es `-`, y la mayoría de los comandos también existen como slash (`/`).
Las respuestas usan **Components V2** (contenedores, secciones y botones
persistentes).

- Invitación: [link de OAuth](https://discord.com/oauth2/authorize?client_id=1344003302859800637&permissions=277025770560&integration_type=0&scope=bot)
- Deploy y operación: [RUNBOOK.md](RUNBOOK.md)

## Correrlo localmente

```bash
pip install -r requirements-bot.txt
```

```bash
echo DISCORD_TOKEN=tu_token > .env
```

```bash
python -m bot
```

| Variable | Obligatoria | Para qué |
|---|---|---|
| `DISCORD_TOKEN` | sí | Token del bot |
| `BOT_DATA_DIR` | no | Carpeta del estado persistente. Si no está se usa `RAILWAY_VOLUME_MOUNT_PATH` y, si tampoco, `bot/data/` |
| `LOG_LEVEL` | no | `INFO` por defecto |

El bot lee los datos de juego de GitHub Pages (`bot/config.py`, `BASE_URL`). Corriendo
local también usa los datos publicados, no los de tu checkout.

## Por dónde empezar: `-menu`

`-menu` (o `/menu`) abre un panel con pantallas Inicio, Perfil, Rankings, Clanes,
Clanes activos, Partidas y Equipos. Es la forma más fácil de recorrer el bot sin
saberse los comandos. Con `-vincular <IGN>` cada usuario asocia su cuenta de Discord a
su nombre en el juego; desde ahí `-perfil` sin argumentos muestra el suyo.

## Comandos

Entre corchetes van los alias.

### Jugadores
| Comando | Qué hace |
|---|---|
| `-perfil` [`profile`, `p`] / `-estadisticas` [`stats`, `st`, `e`] | Perfil con pestañas: Resumen, Récords, Perfil, Historial y selector de demos |
| `-vincular <IGN>` [`link`, `soy`] / `-desvincular` [`unlink`] | Asocia o quita tu IGN |
| `-buscar_usuario` [`buscar`, `search`, `find`] | Busca jugadores por nombre parcial |
| `-tendencia` [`trend`, `evolucion`] · `-historial` [`hist`] | Evolución del Performance |
| `-plan_mejora` [`mejora`, `goals`] | Qué mejorar para subir de tier |
| `-rivales` [`rivals`, `similares`] | Jugadores de nivel parecido |
| `-perfil_demo`, `-kits`, `-armas`, `-vehiculos`, `-assets`, `-revives`, `-rol` | Detalle de demos: kits, armas, vehículos y tipos de medio |
| `-combate` [`ritmo`] · `-teamwork` [`tw`] · `-sinergia` [`duo`] · `-consistencia` | Racha, clutch, cohesión de escuadra, mejores compañeros |
| `-winrate` [`wr`] · `-mapa` · `-mapa_perfil` [`mapas`] | Resultados por modo y por mapa |

### Rankings
| Comando | Qué hace |
|---|---|
| `-top` [`ranking`, `lb`] | Top por Performance. `-top activos` filtra a los activos de los últimos 30 días |
| `-top_periodo` [`top_dia`, `top_semana`, `top_mes`] | Ranking de demos por período, con selects de período y métrica |
| `-ranking_semanal` [`semanal`] | Ranking de la semana |
| `-mvp` [`mvp_semana`] | Jugador de la semana |

### Clanes
| Comando | Qué hace |
|---|---|
| `-promedios` [`avg`] | Ranking histórico de clanes (todos los jugadores) |
| `-promedios_activos` [`clanes_activos`] | Ranking con los 50 mejores activos de cada clan |
| `-promedios_tops` [`avgtop`] | Promedios del top N de cada clan |
| `-clan_roster` [`roster`, `plantel`] · `-clan_fortalezas` [`clan_foda`] | Plantel y fortalezas o debilidades de un clan |
| `-grafico` [`graph`, `g`] | Gráfico de un clan |

### Comparaciones y equipos
| Comando | Qué hace |
|---|---|
| `-compare` [`vs`, `comparar`] | Jugador contra jugador o clan contra clan, con barras divididas |
| `-compare_tops` [`topvs`] · `-comparar_equipos` [`teamvs`] | Tops o equipos enfrentados |
| `-analizar_equipo` [`equipo`] · `-sugerir_equipo` [`sugerir`] · `-prediccion` [`pred`] | Análisis, armado y predicción de equipos |

### Utilidades
`-ayuda` [`h`], `-glosario`, `-modo` (fuente de datos del servidor), `-tips` / `-tips_para`,
`-encuesta` [`poll`], `-countdown` [`cd`], `-sugerencia` [`sug`], `-pagina`, `-guias`,
`-visualizador`, `-hola`.

### Administración
| Comando | Permiso | Qué hace |
|---|---|---|
| `-set_leaderboard_channel` / `-remove_leaderboard_channel` | Administrador | Canal del leaderboard automático de los lunes |
| `-message`, `-boton_rol` | — | Mensajes de rol por reacción o botón |
| `-setup_emojis` | Dueño del bot | Sube los Application Emojis (logos de clan, barras `tb_*`). Se corre una vez |
| `-expsug` | Dueño del bot | Exporta las sugerencias |
| `-apagar` | Dueño del bot | Apaga el bot |

## Estructura del código

```
bot/
├── main.py          # arranque: carga los cogs (EXTENSIONS) y registra los DynamicItems
├── config.py        # URLs de datos, prefijo, MIN_ROUNDS
├── cogs/            # un archivo por grupo de comandos (12 cogs)
├── services/        # datos y estado
│   ├── data_fetcher.py   # baja los JSON de Pages, con caché
│   ├── storage.py        # DATA_DIR + load_json/save_json atómicos
│   ├── links.py          # vínculos Discord → IGN
│   └── guild_settings.py # modo de datos por servidor
└── ui/              # vistas Components V2
    ├── theme.py          # tiers, colores, barras de emoji, RANK_CUTS
    ├── player_profile.py # perfil con pestañas
    ├── menu.py           # -menu
    ├── top_card.py, leaderboard_card.py, versus.py, comparison_card.py, demo_card.py
    └── glossary.py, help_view.py
```

### Botones que sobreviven a un reinicio
Los botones y selects del perfil y del menú son `DynamicItem`: el `custom_id` lleva el
estado (jugador, pestaña) y `main.py` los registra al arrancar. Así un mensaje viejo
sigue respondiendo después de un redeploy. Si agregás un componente interactivo nuevo,
seguí el mismo patrón (`ProfileTabButton` en `bot/ui/player_profile.py`) y registralo
en `main.py`.

### Barras de colores
Las barras se dibujan con Application Emojis `tb_*` (subidos por `-setup_emojis`), con
el color según el percentil del jugador en esa métrica (`theme.rank_meter`) o según su
tier en el caso del Performance (`theme.meter`). Los límites de Discord que conviene
tener presentes: 4000 caracteres de texto y 40 componentes por mensaje.

### Estado persistente (`DATA_DIR`)
| Archivo | Contenido |
|---|---|
| `links.json` | Vínculos Discord → IGN |
| `automation.json` | Canales del leaderboard semanal |
| `guild_settings.json` | Modo de datos por servidor |
| `roles.json` | Configuración de botones de rol |
| `suggestions.json` | Sugerencias recibidas |

En Railway esa carpeta es el volumen `/data`. Si el volumen no está montado, el bot
escribe en `bot/data/` dentro del contenedor y **pierde todo en cada deploy**.

## Probar cambios
No hay tests automáticos del bot. Antes de pushear un cambio grande, recorré la
[checklist de smoke test](../bot/SMOKE_TEST_CHECKLIST.md) en un servidor de prueba.
