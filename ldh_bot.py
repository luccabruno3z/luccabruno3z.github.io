import os
from datetime import datetime, timedelta
import pytz
import asyncio
from dotenv import load_dotenv
import json
import discord
from discord.ext import commands, tasks
import requests
import random
import matplotlib.pyplot as plt
import io
import plotly.express as px  # Asegúrate de tener plotly instalado

# Solo cargar .env si está en local
if os.path.exists(".env"):
    load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# Validación del token
if not TOKEN:
    raise ValueError("El token del bot no está definido en las variables de entorno")
else:
    print("Token detectado correctamente")

# Configurar permisos del bot (acceso total)
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="-", intents=intents)

# URLs de los recursos
GITHUB_GRAPH_LDH = "https://luccabruno3z.github.io/graphs/LDH_interactive_chart.html"
GITHUB_GRAPH_SAE = "https://luccabruno3z.github.io/graphs/SAE_interactive_chart.html"
GITHUB_GRAPH_FI = "https://luccabruno3z.github.io/graphs/FI_interactive_chart.html"
GITHUB_GRAPH_FI_R = "https://luccabruno3z.github.io/graphs/FI-R_interactive_chart.html"
GITHUB_GRAPH_141 = "https://luccabruno3z.github.io/graphs/141_interactive_chart.html"
GITHUB_GRAPH_R_LDH = "https://luccabruno3z.github.io/graphs/R-LDH_interactive_chart.html"
GITHUB_GRAPH_A_LDH = "https://luccabruno3z.github.io/graphs/A-LDH_interactive_chart.html"
GITHUB_GRAPH_WD = "https://luccabruno3z.github.io/graphs/WD_interactive_chart.html"
GITHUB_GRAPH_300 = "https://luccabruno3z.github.io/graphs/300_interactive_chart.html"
GITHUB_GRAPH_E_LAM = "https://luccabruno3z.github.io/graphs/E-LAM_interactive_chart.html"
GITHUB_GRAPH_RIM_LA = "https://luccabruno3z.github.io/graphs/RIM:LA_interactive_chart.html"
GITHUB_GRAPH_ADG = "https://luccabruno3z.github.io/graphs/ADG_interactive_chart.html"
GITHUB_GRAPH_FASO = "https://luccabruno3z.github.io/graphs/FASO_interactive_chart.html"
GITHUB_GRAPH_PLAYERS = "https://luccabruno3z.github.io/graphs/all_players_interactive_chart.html"

GITHUB_JSON_LDH = "https://luccabruno3z.github.io/graphs/LDH_players.json"
GITHUB_JSON_SAE = "https://luccabruno3z.github.io/graphs/SAE_players.json"
GITHUB_JSON_FI = "https://luccabruno3z.github.io/graphs/FI_players.json"
GITHUB_JSON_FI_R = "https://luccabruno3z.github.io/graphs/FI-R_players.json"
GITHUB_JSON_141 = "https://luccabruno3z.github.io/graphs/141_players.json"
GITHUB_JSON_R_LDH = "https://luccabruno3z.github.io/graphs/R-LDH_players.json"
GITHUB_JSON_A_LDH = "https://luccabruno3z.github.io/graphs/A-LDH_players.json"
GITHUB_JSON_WD = "https://luccabruno3z.github.io/graphs/WD_players.json"
GITHUB_JSON_300 = "https://luccabruno3z.github.io/graphs/300_players.json"
GITHUB_JSON_E_LAM = "https://luccabruno3z.github.io/graphs/E-LAM_players.json"
GITHUB_JSON_RIM_LA = "https://luccabruno3z.github.io/graphs/RIM:LA_players.json"
GITHUB_JSON_ADG = "https://luccabruno3z.github.io/graphs/ADG_players.json"
GITHUB_JSON_FASO = "https://luccabruno3z.github.io/graphs/FASO_players.json"
GITHUB_JSON_PLAYERS = "https://luccabruno3z.github.io/graphs/all_players_clusters.json"

GITHUB_JSON_CLANS = "https://luccabruno3z.github.io/graphs/clan_averages.json"

GITHUB_INDEX = "https://luccabruno3z.github.io"

# URL de las guías y el visualizador 2D
GITHUB_GUIDES = "https://luccabruno3z.github.io/#guias"
GITHUB_VISUALIZER_2D = "https://luccabruno3z.github.io/realitytracker.github.io/"

# Diccionario de emojis de clanes personalizados con IDs
CLAN_EMOJIS = {
    "LDH": "<a:Logo_LDH:1331795086169866290>",  # Reemplaza emoji_id1 con el ID del emoji
    "SAE": "<:Logo_SAE:1330790573061312542>",
    "FI": "<:Logo_FI:1330790559601659924>",
    "FI-R": "<:Logo_FI:1330790559601659924>",
    "141": "<:Logo_141:emoji_id5>",
    "R-LDH": "<:Logo_R_LDH:1331795559291551877>",
    "A-LDH": "<:Logo_R_LDH:1331795559291551877>",
    "WD": "<:Logo_WD:emoji_id7>",
    "300": "<:Logo_300:1330790501460213770>",
    "E-LAM": "<:Logo_E_LAM:1330790544263217243>",
    "RIM:LA": "<:Logo_RIM_LA:1330790529214185472>",
    "ADG": "<a:Logo_ADG:1331778693949034516>",  # Añadir el emoji para el nuevo clan
    "FASO": "<:Logo_FASO:1344203061907689482>"
}

KD = "K/D Ratio"

@bot.command()
async def guias(ctx):
    await ctx.send(f"[Aquí tienes acceso a las guías de la página!]({GITHUB_GUIDES})")

@bot.command()
async def visualizador(ctx):
    await ctx.send(f"[Aquí tienes acceso al visualizador 2D!]({GITHUB_VISUALIZER_2D})")

@bot.command()
async def pagina(ctx):
    await ctx.send(f"[Aquí tienes la pagina de la LDH!]({GITHUB_INDEX})")

@bot.command()
async def graficoldh(ctx):
    await ctx.send(f"[Aquí tienes el gráfico interactivo de la LDH!]({GITHUB_GRAPH_LDH})")

@bot.command()
async def grafico300(ctx):
    await ctx.send(f"[Aquí tienes el gráfico interactivo de 300!]({GITHUB_GRAPH_300})")

@bot.command()
async def graficoe_lam(ctx):
    await ctx.send(f"[Aquí tienes el gráfico interactivo de la E-LAM!]({GITHUB_GRAPH_E_LAM})")

@bot.command()
async def graficosae(ctx):
    await ctx.send(f"[Aquí tienes el gráfico interactivo de la SAE!]({GITHUB_GRAPH_SAE})")

@bot.command()
async def graficofi(ctx):
    await ctx.send(f"[Aquí tienes el gráfico interactivo de la FI!]({GITHUB_GRAPH_FI})")

@bot.command()
async def graficofi_r(ctx):
    await ctx.send(f"[Aquí tienes el gráfico interactivo de la FI-R!]({GITHUB_GRAPH_FI_R})")

@bot.command()
async def grafico141(ctx):
    await ctx.send(f"[Aquí tienes el gráfico interactivo del 141!]({GITHUB_GRAPH_141})")

@bot.command()
async def graficoadg(ctx):
    await ctx.send(f"[Aquí tienes el gráfico interactivo de la ADG!]({GITHUB_GRAPH_ADG})")
    
@bot.command()
async def graficor_ldh(ctx):
    await ctx.send(f"[Aquí tienes el gráfico interactivo de la R-LDH!]({GITHUB_GRAPH_R_LDH})")

@bot.command()
async def graficowd(ctx):
    await ctx.send(f"[Aquí tienes el gráfico interactivo de la WD!]({GITHUB_GRAPH_WD})")

@bot.command()
async def grafico(ctx):
    await ctx.send(f"[Aquí tienes el gráfico interactivo de los usuarios!]({GITHUB_GRAPH_PLAYERS})")

@bot.command()
async def estadisticas(ctx, jugador: str = None):
    if not jugador:
        await ctx.send("❗ Por favor, proporciona un nombre de jugador. Ejemplo: `-estadisticas W4RR10R`.")
        return
    try:
        response = requests.get(GITHUB_JSON_PLAYERS)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        await ctx.send("❌ Error al conectar con la base de datos. Inténtalo más tarde.")
        print(f"Error: {e}")
        return
    except json.JSONDecodeError:
        await ctx.send("❌ Error al procesar los datos del archivo JSON.")
        return

    # Ordenar por Performance Score y obtener el ranking general
    jugadores_ordenados = sorted(data, key=lambda x: x.get("Performance Score", 0), reverse=True)

    # Buscar al jugador y su ranking global
    jugador_encontrado = next((entry for entry in jugadores_ordenados if entry["Player"] == jugador), None)
    ranking_global = next((index + 1 for index, entry in enumerate(jugadores_ordenados) if entry["Player"] == jugador), "N/A")

    if jugador_encontrado:
        # Filtrar jugadores del mismo clan
        jugadores_clan = [entry for entry in jugadores_ordenados if entry.get("Clan") == jugador_encontrado.get("Clan")]
        ranking_clan = next((index + 1 for index, entry in enumerate(jugadores_clan) if entry["Player"] == jugador), "N/A")

        # Determinar color del embed basado en Performance Score
        performance_score = jugador_encontrado.get('Performance Score', 0)
        if performance_score >= 0.85:
            color = discord.Color.gold()
        elif performance_score >= 0.70:
            color = discord.Color.green()
        elif performance_score >= 0.50:
            color = discord.Color.blue()
        elif performance_score >= 0.30:
            color = discord.Color.orange()
        else:
            color = discord.Color.red()

        # Obtener imagen del clan
        clan = jugador_encontrado.get("Clan", "N/A")
        clan_image_url = f"https://luccabruno3z.github.io/logos/Logo_{clan}.png"
        # Verificar si la imagen en formato .png no existe, entonces intentar con .gif
        if requests.head(clan_image_url).status_code != 200:
            clan_image_url = f"https://luccabruno3z.github.io/logos/Logo_{clan}.gif"

        # Calcular la tasa de muertes por ronda
        total_deaths = jugador_encontrado.get("Total Deaths", 0)
        rounds_played = jugador_encontrado.get("Rounds", 1)  # Evitar división por cero
        deaths_per_round = total_deaths / rounds_played if rounds_played > 0 else 0

        # Crear embed con el ranking incluido
        embed = discord.Embed(
            title=f"📊 Estadísticas de {jugador}",
            description=(f"**Ranking Global:** #{ranking_global}\n"
                         f"**Ranking en el Clan:** #{ranking_clan}"),
            color=color
        )
        embed.set_thumbnail(url=clan_image_url)  # Imagen del clan

        # Agregar estadísticas agrupadas en columnas con más espacio
        embed.add_field(name="**📊 Datos Totales 📊**", value=(
            f"💥 **K/D Ratio**: {jugador_encontrado['K/D Ratio']:.2f}\n\n"
            f"☠️ **Total Kills**: {jugador_encontrado.get('Total Kills', 'N/A')}\n\n"
            f"💀 **Total Muertes**: {total_deaths}\n\n"
            f"🏆 **Total Score**: {jugador_encontrado.get('Total Score', 'N/A')}\n\n"
            f"🎮 **Rounds Jugados**: {jugador_encontrado.get('Rounds', 'N/A')}"
        ), inline=True)

        embed.add_field(name="**📉 Tasas 📉**", value=(
            f"🔫 **Tasa de Kills**: {jugador_encontrado.get('Kills per Round', 'N/A')}\n\n"
            f"📉 **Tasa de Muertes**: {deaths_per_round:.2f}\n\n"
            f"🎯 **Tasa de Score**: {jugador_encontrado['Score per Round']:.2f}"
        ), inline=True)

        embed.add_field(name="**🌟 Otros 🌟**", value=(
            f"🌟 **Performance Score**: {performance_score:.2f}\n\n"
            f"🎖️ **Clan**: {clan}"
        ), inline=True)

        # Pie de actualización
        embed.set_footer(text="📅 Datos actualizados recientemente.")

        await ctx.send(embed=embed)

    else:
        await ctx.send(f"⚠️ Jugador '{jugador}' no encontrado en la base de datos.")
        
@bot.command()
async def tips(ctx, kit: str = None):
    """
    Proporciona consejos aleatorios para los jugadores según el kit seleccionado.
    Si no se especifica un kit, se muestran consejos generales.
    """
    # Consejos generales ampliados
    consejos_generales = [
        
        # Básicos
        "👀 **Mantén siempre una conciencia situacional**: Mira a tu alrededor constantemente y comunícate con tu escuadrón sobre la posición del enemigo.",
        "🎯 **Apunta con calma**: Disparar en ráfagas cortas y con paciencia mejora tu precisión. No dispares en movimiento a menos que sea absolutamente necesario.",
        "🗣️ **Comunica todo**: Usa el chat de voz para reportar enemigos, avisar sobre amenazas o coordinar movimientos con tu escuadrón.",
        "🏃 **Cúbrete siempre**: Nunca corras en campo abierto sin cobertura. Usa muros, árboles y colinas para protegerte del fuego enemigo.",
        "🔧 **Construye FOBs estratégicas**: Las Bases de Operaciones Avanzadas son esenciales para mantener la presión en el enemigo y asegurar puntos de reaparición.",
        "🎮 **Sigue las órdenes del líder de escuadrón**: Escucha al líder y no tomes decisiones impulsivas que pongan en riesgo al equipo.",

        # CQB (Close Quarters Battle)
        "🏠 **CQB: Usa la cobertura a tu favor**: Avanza entre esquinas y puertas con cuidado. Nunca te expongas completamente al enemigo.",
        "🔫 **CQB: Apunta al pecho**: En combate cercano, apuntar al torso es más efectivo que intentar disparos a la cabeza.",
        "👟 **CQB: Muévete rápido y mantén el control**: En espacios cerrados, la rapidez es clave, pero evita correr si puedes caminar silenciosamente.",
        "🛑 **CQB: Limpia habitación por habitación**: Al entrar a un edificio, siempre revisa esquinas y espacios ocultos antes de avanzar.",
        "🎙️ **CQB: Coordina con tu equipo**: Si estás atacando un edificio, asigna roles claros: uno cubre mientras otro avanza o lanza granadas.",
        "💣 **CQB: Usa granadas de manera efectiva**: Lanza granadas para limpiar habitaciones antes de entrar, pero asegúrate de no dañar a aliados.",
        
        # Combate en equipo
        "🛡️ **Crea líneas de fuego seguras**: Nunca dispares sin saber dónde están tus compañeros para evitar bajas por fuego amigo.",
        "👥 **Flanquea con tu equipo**: En lugar de atacar de frente, envía un grupo para rodear al enemigo mientras los distraes.",
        "📻 **Comunica amenazas prioritarias**: Si ves un francotirador, un vehículo blindado o una emboscada, informa inmediatamente.",
        "🎯 **Usa marcadores**: Marca posiciones enemigas en el mapa para que tu escuadrón y el equipo puedan reaccionar rápidamente.",
        "⚙️ **Carga siempre suministros**: Llevar un kit de munición o de reparaciones puede salvar a tu equipo en momentos críticos.",
        
        # Vehículos
        "🚁 **Comunica con el piloto**: Antes de abordar un helicóptero o transporte, coordina tu punto de aterrizaje y objetivos.",
        "🛠️ **Mantén tus vehículos reparados**: Si usas tanques o vehículos blindados, planea pausas para reparaciones y reabastecimiento.",
        "🔍 **Reconocimiento con vehículos ligeros**: Usa jeeps y vehículos rápidos para explorar áreas antes de comprometer unidades más grandes.",
        "🚨 **Nunca uses vehículos solos**: Especialmente los vehículos pesados, deben ser operados en equipo para maximizar su efectividad y supervivencia.",

        # Avanzados
        "🕒 **Gestiona tu tiempo en batalla**: No te apresures. Cada decisión debe enfocarse en maximizar tu ventaja táctica.",
        "🏹 **Usa el terreno como ventaja**: Colinas, ríos y edificios pueden convertirse en posiciones defensivas cruciales.",
        "💾 **Aprende de tus errores**: Después de cada partida, reflexiona sobre lo que salió mal y busca mejorar tus habilidades.",
        "📋 **Conoce las reglas del servidor**: Algunos servidores tienen restricciones específicas (kits, roles, vehículos). Evita sanciones innecesarias.",
        "🎮 **Practica en servidores cooperativos**: Usa modos cooperativos para entrenar con vehículos y aprender mapas antes de jugar en PVP.",

        # Objetivos
        "🎯 **Prioriza los objetivos estratégicos**: Atacar o defender objetivos clave asegura la victoria más que simplemente buscar enfrentamientos.",
        "🔍 **Espía posiciones enemigas**: Usa binoculares para observar antes de atacar o moverte hacia un objetivo.",
        "📦 **Suministros primero**: Sin municiones ni médicos, el equipo colapsa. Asegúrate de mantener las líneas de suministro abiertas.",
        
        # Liderazgo
        "⚔️ **Como líder, asigna roles claros**: Divide tareas como flanqueo, defensa y asalto para que tu escuadrón opere eficientemente.",
        "🗺️ **Planifica con el mapa**: Usa el mapa para coordinar ataques con otros escuadrones y evitar choques internos.",
        "🛠️ **Construye donde importa**: Ubica FOBs y puntos defensivos cerca de objetivos estratégicos, pero lo suficientemente lejos para evitar destrucción inmediata."
    ]

    
    # Consejos por kit
    consejos_kits = {
        "rifleman": [
            "🎯 **Usa tu rifle con precisión:** Dispara en ráfagas cortas o individuales para mejor precisión.",
            "📦 **Reparte munición:** Apoya a compañeros como médicos, ametralladores y antitanques.",
            "🛡️ **Mantente en las líneas:** Eres el núcleo del escuadrón, no vayas solo.",
            "🕶️ **Usa granadas de humo:** Cubre avances y extracciones con humo.",
            "🔋 **Gestiona tu stamina:** Evita correr innecesariamente en combate."
        ],
        "medic": [
            "💉 **Prioriza la supervivencia:** No te arriesgues innecesariamente para revivir.",
            "🛡️ **Usa humo para cubrir:** Antes de revivir, lanza humo para evitar ser un blanco fácil.",
            "🏃 **Mantente cerca del escuadrón:** Apoya desde la retaguardia.",
            "⏳ **Sé eficiente al curar:** Usa ráfagas cortas con el botiquín para ahorrar suministros.",
            "🗣️ **Comunica tus movimientos:** Coordina con tu escuadrón a quién atender primero."
        ],
        "automatic rifleman": [
            "🔫 **Encuentra una buena posición defensiva:** Usa cobertura y terreno elevado para maximizar control.",
            "🏋️ **Dispara en ráfagas cortas:** Controla el retroceso para mantener precisión.",
            "🛡️ **Fuego de supresión:** Mantén al enemigo bajo presión, incluso sin matar.",
            "🚩 **Defiende puntos clave:** Ideal para proteger banderas o FOBs.",
            "🎯 **Cambia de posición:** No seas predecible después de disparar."
        ],
        "grenadier": [
            "📍 **Ajusta la mira:** Usa el telémetro para disparos precisos a larga distancia.",
            "🏠 **Ataca detrás de cobertura:** Usa tus granadas para eliminar enemigos tras muros o trincheras.",
            "🛡️ **Usa granadas de humo:** Proporciona cobertura en objetivos importantes.",
            "🌍 **Coordina con el líder:** Apunta a los puntos indicados por tu líder.",
            "🎮 **Entrena la puntería:** Familiarízate con el comportamiento de las granadas."
        ],
        "sniper": [
            "🎯 **Apunta siempre a la cabeza:** Maximiza la eficacia eliminando enemigos clave.",
            "🕶️ **Mantente oculto:** Usa vegetación y terreno para no ser detectado.",
            "📻 **Informa al equipo:** Reporta posiciones enemigas para asistir a tu escuadrón.",
            "⏳ **Sé paciente:** No dispares a menos que sea necesario.",
            "🏃 **Cambia de posición:** Después de disparar, muévete para evitar ser localizado."
        ],
        "lat": [
            "🚀 **Prioriza vehículos ligeros:** Guarda tus misiles para transportes y vehículos pequeños.",
            "🔭 **Ajusta tu mira:** Evalúa la distancia antes de disparar.",
            "🛡️ **Usa cobertura:** Dispara desde posiciones protegidas.",
            "🏃 **Muévete después de disparar:** Evita represalias al cambiar de ubicación.",
            "🎮 **Practica con el lanzacohetes:** Familiarízate con la caída del proyectil."
        ],
        "hat": [
            "🔍 **Planifica cada disparo:** Asegúrate de que cada misil impacte.",
            "🛡️ **Usa terreno elevado:** Maximiza tu ventaja con buena visibilidad.",
            "🚁 **Coordina con el equipo:** Avísales antes de disparar para evitar confusión.",
            "🎯 **Apunta a puntos débiles:** Lados y traseras de tanques son más vulnerables.",
            "🔄 **Reabastece frecuentemente:** Mantente cerca de cajas de munición."
        ],
        "combat engineer": [
            "🛠️ **Coloca minas y C4 estratégicamente:** Embosca vehículos en rutas frecuentes.",
            "🚧 **Construye defensas rápidamente:** Protege FOBs con alambre o sacos de arena.",
            "🚜 **Repara vehículos:** Mantén los activos del equipo operativos.",
            "🏃 **No te expongas:** Mantén un perfil bajo al colocar trampas.",
            "📻 **Coordina con tu líder:** Ubica explosivos en lugares clave."
        ]
    }

    # Seleccionar consejos aleatorios
    if kit is None:
        consejos = random.sample(consejos_generales, k=min(5, len(consejos_generales)))
        embed = discord.Embed(
            title="Consejos Generales Aleatorios",
            description="\n".join([f"- {c}" for c in consejos]),
            color=discord.Color.blue()
        )
    else:
        kit = kit.lower()
        if kit in consejos_kits:
            consejos = random.sample(consejos_kits[kit], k=min(5, len(consejos_kits[kit])))
            embed = discord.Embed(
                title=f"Consejos Aleatorios para {kit.capitalize()}",
                description="\n".join([f"- {c}" for c in consejos]),
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="Kit no reconocido",
                description="Por favor, elige uno de los siguientes kits:\n"
                            "`rifleman`, `medic`, `automatic rifleman`, `grenadier`, `sniper`, `lat`, `hat`, `combat engineer`.",
                color=discord.Color.red()
            )

    embed.set_footer(text="¡Practica y mejora tus habilidades en el campo de batalla!")
    embed.set_thumbnail(url="https://luccabruno3z.github.io/LDH_BOY2.png")  # Cambia por una imagen temática si lo deseas

    await ctx.send(embed=embed)

@bot.command()
async def ayuda(ctx):
    embed = discord.Embed(
        title="📜 **Lista de Comandos Disponibles**",
        description="Aquí tienes todos los comandos organizados por categorías:",
        color=discord.Color.blue()
    )

    # Sección: Comandos básicos
    embed.add_field(
        name="🔧 **Comandos Básicos**",
        value=(
            "`-hola` - Saluda al bot.\n"
            "`-tips <kit>` - Tips para tener en cuenta en el juego. Si no especificas kit se te daran consejos generales.\n"
            "`-apagar` - Apaga el bot (solo el dueño del bot puede usar este comando)."
        ),
        inline=False
    )

    # Sección: Estadísticas de jugadores
    embed.add_field(
        name="📊 **Estadísticas de Jugadores**",
        value=(
            "`-estadisticas <jugador>` - Muestra estadísticas detalladas de un jugador, incluyendo:\n"
            "  💥 **K/D Ratio**\n"
            "  🔫 **Tasa de kills**\n"
            "  🎯 **Tasa de score**\n"
            "  🌟 **Performance Score**\n"
            "  🎮 **Rounds Jugados**\n"
            "  ☠️ **Total Kills**\n"
            "  🏆 **Total Score**\n"
            "  🎖️ **Clan**\n"
            "  💀 **Total Muertes**\n"
            "  📉 **Tasa de Muertes**\n"
            "  🏅 **Ranking en el Clan**\n\n"
            "`-compare <jugador1> <jugador2>` - Compara estadísticas de dos jugadores."
        ),
        inline=False
    )

    # Sección: Gráficos interactivos
    embed.add_field(
        name="📈 **Gráficos Interactivos**",
        value=(
            "`-grafico` - Muestra el gráfico interactivo con estadísticas de todos los jugadores.\n"
            "`-graficoldh` - Muestra el gráfico interactivo de la LDH.\n"
            "`-graficosae` - Muestra el gráfico interactivo de la SAE.\n"
            "`-graficofi` - Muestra el gráfico interactivo de la FI.\n"
            "`-graficofi_r` - Muestra el gráfico interactivo de la FI-R.\n"
            "`-grafico141` - Muestra el gráfico interactivo del 141.\n"
            "`-graficoe_lam` - Muestra el gráfico interactivo de la E-LAM.\n"
            "`-grafico300` - Muestra el gráfico interactivo de 300.\n"
            "`-graficoe_lam` - Muestra el gráfico interactivo de la E-LAM.\n"
            "`-graficor_ldh` - Muestra el gráfico interactivo de la R-LDH."
        ),
        inline=False
    )

    # Sección: Rankings y promedios
    embed.add_field(
        name="🏅 **Rankings y Promedios**",
        value=(
            "`-top <cantidad de jugadores> <categoría> <métrica>` - Muestra el top de jugadores según la categoría y métrica especificada:\n"
            "  `general`, `ldh`, `sae`, `fi`, `141`, `fi-r`, `r-ldh`, `e-lam`, `300`, `rim-la`, `adg`.\n"
            "  Métricas: `performance`, `kd`, `kills`, `deaths`, `rounds`.\n"
            "`-promedios` - Muestra los promedios de estadísticas por clan."
        ),
        inline=False
    )

    # Sección: Recursos adicionales
    embed.add_field(
        name="📚 **Recursos Adicionales**",
        value=(
            "`-guias` - Accede a las guías de la página.\n"
            "`-visualizador` - Accede al visualizador 2D."
        ),
        inline=False
    )

    # Pie de página
    embed.set_footer(
        text="Usa los comandos con el prefijo `-` para interactuar con el bot. ¡Diviértete!"
    )

    await ctx.send(embed=embed)

# Mensaje al iniciar el bot
@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')

# Comando básico de prueba
@bot.command()
async def hola(ctx):
    await ctx.send('¡Hola! ¿En qué puedo ayudarte?')

@bot.command()
async def promedios(ctx):
    try:
        response = requests.get(GITHUB_JSON_CLANS)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        await ctx.send("Error al conectar con la base de datos. Inténtalo más tarde.")
        print(f"Error: {e}")
        return
    except json.JSONDecodeError:
        await ctx.send("Error al procesar los datos del archivo JSON.")
        return

    if isinstance(data, list):
        embed = discord.Embed(
            title="Promedios de Clanes",
            description="Promedios calculados para cada clan:",
            color=discord.Color.blue()
        )

        # Variables para el gráfico
        clan_names = []
        performance_scores = []

        for clan_data in data:
            clan_name = clan_data.get("Clan", "Desconocido")
            kd_ratio = clan_data.get('K/D Ratio', 0)
            score_per_round = clan_data.get('Score per Round', 0)
            kills_per_round = clan_data.get('Kills per Round', 0)
            performance_score = clan_data.get('Performance Score', 0)

            # Agregar datos a las listas
            clan_names.append(clan_name)
            performance_scores.append(performance_score)

            # Formato más estético
            embed.add_field(
                name=f"🏅 {clan_name}",
                value=(
                    f"**🔹 Promedio K/D:** {kd_ratio:.2f}\n"
                    f"**🔹 Promedio Score:** {score_per_round:.2f}\n"
                    f"**🔹 Promedio Kills:** {kills_per_round:.2f}\n"
                    f"**🔹 Performance Score:** {performance_score:.2f}"
                ),
                inline=False
            )

        # Crear el gráfico de barras
        fig, ax = plt.subplots(figsize=(10, 6))
        bar_width = 0.5
        index = range(len(clan_names))

        bars = plt.bar(index, performance_scores, bar_width, label='Performance Score')

        plt.xlabel('Clanes')
        plt.ylabel('Performance Score')
        plt.title('Performance Score de Clanes')
        plt.xticks(index, clan_names)
        plt.legend()

        # Guardar el gráfico en un buffer de bytes
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)

        # Adjuntar el gráfico al mensaje
        file = discord.File(buf, filename="performance_scores_clanes.png")
        embed.set_image(url="attachment://performance_scores_clanes.png")

        await ctx.send(embed=embed, file=file)
    else:
        await ctx.send("El formato de los datos no es válido.")

@bot.command()
async def compare(ctx, entity1: str, entity2: str):
    """
    Compara las estadísticas de dos jugadores o clanes usando los archivos JSON alojados en GitHub Pages.
    """
    try:
        response_players = requests.get(GITHUB_JSON_PLAYERS)
        response_players.raise_for_status()
        data_players = response_players.json()
        
    except requests.exceptions.RequestException as e:
        await ctx.send("❌ Error al conectar con la base de datos. Inténtalo más tarde.")
        print(f"Error: {e}")
        return
    except json.JSONDecodeError:
        await ctx.send("❌ Error al procesar los datos del archivo JSON.")
        return

    # Buscar los jugadores en la base de datos
    p1 = next((p for p in data_players if p['Player'] == entity1), None)
    p2 = next((p for p in data_players if p['Player'] == entity2), None)
    
    if p1 and p2:
        # Comparar jugadores
        def determinar_color(performance_score):
            if performance_score >= 0.85:
                return discord.Color.gold()
            elif performance_score >= 0.70:
                return discord.Color.green()
            elif performance_score >= 0.50:
                return discord.Color.blue()
            elif performance_score >= 0.30:
                return discord.Color.orange()
            else:
                return discord.Color.red()

        color1 = determinar_color(p1.get('Performance Score', 0))
        color2 = determinar_color(p2.get('Performance Score', 0))

        embed = discord.Embed(
            title=f"🔍 Comparación entre {entity1} y {entity2}",
            description="Estadísticas detalladas comparadas:",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="Estadística",
            value=(
                "💥 **K/D Ratio**\n"
                "🔫 **Kills per Round**\n"
                "🎯 **Score per Round**\n"
                "🌟 **Performance Score**\n"
                "🎮 **Rounds Jugados**\n"
                "☠️ **Total Kills**\n"
                "🏆 **Total Score**"
            ),
            inline=True
        )
        embed.add_field(
            name=f"🎮 {entity1}",
            value=(
                f"{p1['K/D Ratio']:.2f}\n"
                f"{p1.get('Kills per Round', 'N/A')}\n"
                f"{p1.get('Score per Round', 'N/A'):.2f}\n"
                f"{p1.get('Performance Score', 'N/A'):.2f}\n"
                f"{p1.get('Rounds', 'N/A')}\n"
                f"{p1.get('Total Kills', 'N/A')}\n"
                f"{p1.get('Total Score', 'N/A')}"
            ),
            inline=True
        )
        embed.add_field(
            name=f"🎮 {entity2}",
            value=(
                f"{p2['K/D Ratio']:.2f}\n"
                f"{p2.get('Kills per Round', 'N/A')}\n"
                f"{p2.get('Score per Round', 'N/A'):.2f}\n"
                f"{p2.get('Performance Score', 'N/A'):.2f}\n"
                f"{p2.get('Rounds', 'N/A')}\n"
                f"{p2.get('Total Kills', 'N/A')}\n"
                f"{p2.get('Total Score', 'N/A')}"
            ),
            inline=True
        )

        if p1['Performance Score'] > p2['Performance Score']:
            resolution = f"🌟 **{entity1}** parece ser mejor que **{entity2}**."
        elif p1['Performance Score'] < p2['Performance Score']:
            resolution = f"🌟 **{entity2}** parece ser mejor que **{entity1}**."
        else:
            resolution = "🤝 Ambos jugadores tienen un desempeño similar."

        embed.add_field(name="Resolución", value=resolution, inline=False)
        embed.set_footer(text="📅 Datos actualizados recientemente.")

        await ctx.send(embed=embed)

    else:
        # Comparar clanes sumando estadísticas de sus miembros
        def sumar_estadisticas(clan_name):
            total_kills = 0
            total_deaths = 0
            total_score = 0
            total_rounds = 0
            for player in data_players:
                if player.get('Clan', '') == clan_name:
                    total_kills += player.get('Total Kills', 0)
                    total_deaths += player.get('Total Deaths', 0)
                    total_score += player.get('Total Score', 0)
                    total_rounds += player.get('Rounds', 0)
            return total_kills, total_deaths, total_score, total_rounds

        kills1, deaths1, score1, rounds1 = sumar_estadisticas(entity1)
        kills2, deaths2, score2, rounds2 = sumar_estadisticas(entity2)

        embed = discord.Embed(
            title=f"🔍 Comparación entre los clanes {entity1} y {entity2}",
            description="Totales de estadísticas comparadas:",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="Estadística",
            value=(
                "☠️ **Total Kills**\n"
                "💀 **Total Deaths**\n"
                "🏆 **Total Score**\n"
                "🎮 **Total Rounds**"
            ),
            inline=True
        )
        embed.add_field(
            name=f"🏅 {entity1}",
            value=(
                f"{kills1}\n"
                f"{deaths1}\n"
                f"{score1}\n"
                f"{rounds1}"
            ),
            inline=True
        )
        embed.add_field(
            name=f"🏅 {entity2}",
            value=(
                f"{kills2}\n"
                f"{deaths2}\n"
                f"{score2}\n"
                f"{rounds2}"
            ),
            inline=True
        )

        if score1 > score2:
            resolution = f"🌟 **{entity1}** parece ser mejor que **{entity2}**."
        elif score1 < score2:
            resolution = f"🌟 **{entity2}** parece ser mejor que **{entity1}**."
        else:
            resolution = "🤝 Ambos clanes tienen un desempeño similar."

        embed.add_field(name="Resolución", value=resolution, inline=False)
        embed.set_footer(text="📅 Datos actualizados recientemente.")

        await ctx.send(embed=embed)

# Agrega el comando para enviar un mensaje con una reacción de emoji y asignar un rol
@bot.command()
async def message(ctx, emoji: str, role_name: str, *, message: str):
    """
    Envía un mensaje con una reacción de emoji.
    Los usuarios que reaccionen con el emoji recibirán un rol específico.
    """
    # Comprueba si el autor del mensaje tiene permisos de administrador
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ No tienes permisos para usar este comando.")
        return

    # Obtener el rol del nombre
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        await ctx.send(f"❌ El rol '{role_name}' no existe.")
        return

    # Enviar el mensaje
    msg = await ctx.send(message)

    # Añadir reacción de emoji al mensaje
    await msg.add_reaction(emoji)

    # Almacenar el mensaje, el emoji y el rol en el contexto del bot para manejar las reacciones
    bot.message_id = msg.id
    bot.emoji = emoji
    bot.role = role

    await ctx.send(f"✅ Mensaje enviado y reacción {emoji} añadida. Los usuarios que reaccionen recibirán el rol '{role_name}'.")

# Manejar reacciones añadidas
@bot.event
async def on_raw_reaction_add(payload):
    # Ignorar reacciones del propio bot
    if payload.user_id == bot.user.id:
        return

    # Verificar si la reacción es al mensaje configurado y el emoji coincide
    if payload.message_id == bot.message_id and str(payload.emoji) == bot.emoji:
        guild = bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)

        if bot.role:
            await member.add_roles(bot.role)
            await member.send(f"🎉 ¡Has recibido el rol '{bot.role.name}' por reaccionar con {payload.emoji}!")
        else:
            await member.send("❌ El rol no existe o no se pudo asignar.")

# Manejar reacciones eliminadas (opcional, para remover el rol si se quita la reacción)
@bot.event
async def on_raw_reaction_remove(payload):
    # Ignorar reacciones del propio bot
    if payload.user_id == bot.user.id:
        return

    # Verificar si la reacción es al mensaje configurado y el emoji coincide
    if payload.message_id == bot.message_id and str(payload.emoji) == bot.emoji:
        guild = bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)

        if bot.role:
            await member.remove_roles(bot.role)
            await member.send(f"❌ El rol '{bot.role.name}' ha sido removido al quitar la reacción de {payload.emoji}.")
            
@bot.command()
async def top(ctx, cantidad: int = 15, categoria: str = "general", metrica: str = "performance"):
    # Diccionario de categorías válidas y sus URLs correspondientes
    categorias_validas = {
        "general": GITHUB_JSON_PLAYERS,
        "ldh": GITHUB_JSON_LDH,
        "sae": GITHUB_JSON_SAE,
        "fi": GITHUB_JSON_FI,
        "141": GITHUB_JSON_141,
        "fi-r": GITHUB_JSON_FI_R,
        "r-ldh": GITHUB_JSON_R_LDH,
        "e-lam": GITHUB_JSON_E_LAM,
        "300": GITHUB_JSON_300,
        "rim-la": GITHUB_JSON_RIM_LA,
        "adg": GITHUB_JSON_ADG,
        "faso": GITHUB_JSON_FASO,
        "a-ldh": GITHUB_JSON_A_LDH
    }

    # Validar la categoría ingresada
    if categoria.lower() not in categorias_validas:
        await ctx.send(
            "❗ **Categoría inválida.** Las categorías válidas son:\n"
            "`general`, `ldh`, `sae`, `fi`, `141`, `fi-r`, `r-ldh`, `e-lam`, `300`, `rim-la`, `adg`."
        )
        return

    # Validar la cantidad de jugadores solicitados
    if cantidad <= 0:
        await ctx.send("❗ **La cantidad debe ser mayor a 0.**")
        return

    # Validar la métrica ingresada
    metricas_validas = ["performance", "kd", "kills", "deaths", "rounds"]
    if metrica not in metricas_validas:
        await ctx.send(
            "❗ **Métrica inválida.** Las métricas válidas son:\n"
            "`performance`, `kd`, `kills`, `deaths`, `rounds`."
        )
        return

    # Obtener la URL del archivo JSON según la categoría
    url_json = categorias_validas[categoria.lower()]

    # Intentar obtener y procesar los datos
    try:
        response = requests.get(url_json)
        response.raise_for_status()
        data = response.json()
        print(f"Datos obtenidos correctamente de {url_json}")
    except requests.exceptions.RequestException as e:
        await ctx.send("❌ **Error al conectar con la base de datos.** Inténtalo más tarde.")
        print(f"Error al conectar con la base de datos: {e}")
        return
    except json.JSONDecodeError:
        await ctx.send("❌ **Error al procesar los datos del archivo JSON.**")
        print("Error al procesar los datos del archivo JSON.")
        return

    # Ensure the metric key matches the JSON data structure
    metric_key_mapping = {
        "performance": "Performance Score",
        "kd": "K/D Ratio",
        "kills": "Total Kills",
        "deaths": "Total Deaths",
        "rounds": "Rounds"
    }
    metric_key = metric_key_mapping.get(metrica, metrica)

    # Ordenar los jugadores por la métrica seleccionada
    try:
        jugadores_ordenados = sorted(
            data, 
            key=lambda x: x.get(metric_key, 0), 
            reverse=True
        )
        print("Jugadores ordenados correctamente.")
    except Exception as e:
        await ctx.send("❌ **Error al ordenar los jugadores.**")
        print(f"Error al ordenar los jugadores: {e}")
        return

    # Limitar al número total de jugadores disponibles
    cantidad = min(cantidad, len(jugadores_ordenados))
    top_jugadores = jugadores_ordenados[:cantidad]

    # Crear el embed
    embed = discord.Embed(
        title=f"🏆 **Top {cantidad} Jugadores** ({categoria.upper()} - {metrica})",
        description=(
            f"Clasificación basada en **{metrica}**.\n"
            f"Aquí están los mejores {cantidad} jugadores en esta categoría:"
        ),
        color=discord.Color.orange()
    )
    embed.set_thumbnail(url="https://luccabruno3z.github.io/LDH_BOY2.png")  # Imagen representativa

    # Agregar los jugadores al embed con formato más limpio
    jugadores_lista = ""
    for index, jugador in enumerate(top_jugadores, start=1):
        nombre = jugador.get("Player", "Desconocido")
        valor_metrica = jugador.get(metric_key, 0)
        clan = jugador.get("Clan", "N/A")
        clan_emoji = CLAN_EMOJIS.get(clan, "")

        jugadores_lista += f"**#{index}** - {clan_emoji} {nombre} ({valor_metrica:.2f})\n"

    embed.add_field(
        name="🔝 **Ranking**",
        value=jugadores_lista if jugadores_lista else "No hay jugadores en esta categoría.",
        inline=False
    )

    # Agregar pie de página
    embed.set_footer(text="📅 Datos actualizados recientemente.")

    # Enviar el embed
    await ctx.send(embed=embed)
    print("Embed enviado correctamente.")

# Manejar errores globalmente
@bot.event
async def on_command_error(ctx, error):
    # Error cuando el comando no existe
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ **Comando no reconocido.** Usa `-ayuda` para ver la lista de comandos disponibles.")
    
    # Error cuando faltan argumentos en un comando
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❗ Faltan argumentos. Asegúrate de usar el comando correctamente. Ejemplo: `-estadisticas <jugador>`.")
        
    # Error cuando un usuario no tiene permisos para usar un comando
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("🚫 No tienes permisos para ejecutar este comando.")
        
    # Error si el comando es usado incorrectamente
    elif isinstance(error, commands.BadArgument):
        await ctx.send("⚠️ Argumento inválido. Revisa los parámetros del comando.")
        
    # Otros errores
    else:
        await ctx.send("❗ Ocurrió un error inesperado. Intenta de nuevo más tarde.")
        print(f"Error inesperado: {error}")  # Esto imprime el error en la consola para diagnóstico.

import matplotlib.pyplot as plt
import io
import discord

@bot.command()
async def analizar_equipo(ctx, *jugadores: str):
    # Verificar que se haya proporcionado al menos un jugador
    if len(jugadores) < 1:
        await ctx.send("❗ Por favor, proporciona al menos un jugador. Ejemplo: `-analizar_equipo Jugador1 Jugador2 ... JugadorN`.")
        return

    try:
        response = requests.get(GITHUB_JSON_PLAYERS)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        await ctx.send("❌ Error al conectar con la base de datos. Inténtalo más tarde.")
        print(f"Error: {e}")
        return
    except json.JSONDecodeError:
        await ctx.send("❌ Error al procesar los datos del archivo JSON.")
        return

    equipo = []
    for jugador in jugadores:
        jugador_encontrado = next((entry for entry in data if entry["Player"].lower() == jugador.lower()), None)
        if not jugador_encontrado:
            await ctx.send(f"⚠️ Jugador '{jugador}' no encontrado en la base de datos.")
            return
        equipo.append(jugador_encontrado)

    # Calcular métricas del equipo
    total_score = sum(jugador['Total Score'] for jugador in equipo)
    total_kills = sum(jugador['Total Kills'] for jugador in equipo)
    total_deaths = sum(jugador['Total Deaths'] for jugador in equipo)
    total_rounds = sum(jugador['Rounds'] for jugador in equipo)
    total_performance_score = sum(jugador['Performance Score'] for jugador in equipo) / len(equipo)
    
    # Calcular promedio de kills por partida y promedio de muertes por partida
    avg_kills_per_round = total_kills / total_rounds if total_rounds > 0 else 0
    avg_deaths_per_round = total_deaths / total_rounds if total_rounds > 0 else 0

    # Calcular K/D ratio del equipo
    team_kd_ratio = total_kills / total_deaths if total_deaths > 0 else 0

    # Generar el gráfico de barras solo con K/D Ratio
    nombres = [jugador['Player'] for jugador in equipo]
    kd_ratios = [jugador['K/D Ratio'] for jugador in equipo]

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6))
    bar_width = 0.5
    index = range(len(nombres))

    bars = plt.bar(index, kd_ratios, bar_width, color='#00FF00', edgecolor='white')

    plt.xlabel('Jugadores', color='white')
    plt.ylabel('K/D Ratio', color='white')
    plt.title('K/D Ratio de Jugadores', color='white')
    plt.xticks(index, nombres, rotation=45, ha='right', color='white')
    plt.yticks(color='white')
    plt.grid(axis='y', linestyle='--', color='gray')

    # Añadir etiquetas en las barras
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval + 0.01, round(yval, 2), ha='center', color='white')

    # Guardar el gráfico en un buffer de bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)

    # Crear embed con el análisis del equipo
    embed = discord.Embed(
        title="📊 Análisis de Composición de Equipo",
        description="Aquí tienes el análisis del equipo seleccionado:",
        color=discord.Color.blue()
    )

    embed.add_field(name="**📊 Métricas del Equipo**", value=(
        f"**Total Score**: {total_score}\n"
        f"**Total Kills**: {total_kills}\n"
        f"**Total Deaths**: {total_deaths}\n"
        f"**Total Rounds**: {total_rounds}\n"
        f"**Average Kills per Round**: {avg_kills_per_round:.2f}\n"
        f"**Average Deaths per Round**: {avg_deaths_per_round:.2f}\n"
        f"**Team K/D Ratio**: {team_kd_ratio:.2f}\n"
        f"**Average Performance Score**: {total_performance_score:.2f}"
    ), inline=False)

    # Adjuntar el gráfico al mensaje
    file = discord.File(buf, filename="team_analysis.png")
    embed.set_image(url="attachment://team_analysis.png")

    await ctx.send(embed=embed, file=file)

@bot.command()
async def sugerir_equipo(ctx, clan: str, num_jugadores: int = 8):
    """
    Sugiere un equipo de jugadores de un clan específico buscando una media entre mayor score por partida,
    mayor kills por partida y menor muertes por partida, mostrando el performance score total.
    """
    if num_jugadores < 2 or num_jugadores > 8:
        await ctx.send("❗ Por favor, selecciona entre 2 y 8 jugadores. Ejemplo: `-sugerir_equipo LDH 5`.")
        return

    # Diccionario para mapear clanes a sus URLs JSON
    clan_json_urls = {
        "LDH": GITHUB_JSON_LDH,
        "SAE": GITHUB_JSON_SAE,
        "FI": GITHUB_JSON_FI,
        "FI-R": GITHUB_JSON_FI_R,
        "141": GITHUB_JSON_141,
        "R-LDH": GITHUB_JSON_R_LDH,
        "WD": GITHUB_JSON_WD,
        "300": GITHUB_JSON_300,
        "E-LAM": GITHUB_JSON_E_LAM,
        "RIM:LA": GITHUB_JSON_RIM_LA,
        "ADG": GITHUB_JSON_ADG,
    }

    # Verificar si el clan existe
    if clan not in clan_json_urls:
        await ctx.send(f"❗ Clan '{clan}' no reconocido. Los clanes válidos son: {', '.join(clan_json_urls.keys())}.")
        return

    try:
        response = requests.get(clan_json_urls[clan])
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        await ctx.send("❌ Error al conectar con la base de datos. Inténtalo más tarde.")
        print(f"Error: {e}")
        return
    except json.JSONDecodeError:
        await ctx.send("❌ Error al procesar los datos del archivo JSON.")
        return

    # Ordenar jugadores por las métricas ponderadas (mayor kills por partida y menor muertes por partida)
    jugadores_ordenados = sorted(data, key=lambda x: (x.get("Kills per Round", 0), -x.get("Deaths per Round", 0)), reverse=True)

    # Seleccionar los mejores jugadores
    equipo_sugerido = jugadores_ordenados[:num_jugadores]

    # Calcular métricas del equipo sugerido
    total_score = sum(jugador['Total Score'] for jugador in equipo_sugerido)
    total_kills = sum(jugador['Total Kills'] for jugador in equipo_sugerido)
    total_deaths = sum(jugador['Total Deaths'] for jugador in equipo_sugerido)
    total_rounds = sum(jugador['Rounds'] for jugador in equipo_sugerido)
    avg_performance_score = sum(jugador['Performance Score'] for jugador in equipo_sugerido) / len(equipo_sugerido)

    avg_kills_per_round = total_kills / total_rounds if total_rounds > 0 else 0
    avg_deaths_per_round = total_deaths / total_rounds if total_rounds > 0 else 0
    team_kd_ratio = total_kills / total_deaths if total_deaths > 0 else 0

    # Crear embed con el análisis del equipo sugerido
    embed = discord.Embed(
        title=f"📊 Equipo Sugerido para {clan}",
        description=f"Aquí tienes el equipo sugerido del clan {clan}:",
        color=discord.Color.blue()
    )

    for jugador in equipo_sugerido:
        embed.add_field(
            name=f"🎮 {jugador['Player']}",
            value=(
                f"**K/D Ratio**: {jugador['K/D Ratio']:.2f}\n"
                f"**Kills per Round**: {jugador['Kills per Round']:.2f}\n"
                f"**Deaths per Round**: {jugador['Deaths per Round']:.2f}\n"
                f"**Total Kills**: {jugador['Total Kills']}\n"
                f"**Total Deaths**: {jugador['Total Deaths']}\n"
                f"**Rounds Jugados**: {jugador['Rounds']}\n"
                f"**Performance Score**: {jugador['Performance Score']:.2f}"
            ),
            inline=True
        )

    embed.add_field(name="**📊 Métricas del Equipo**", value=(
        f"**Total Score**: {total_score}\n"
        f"**Total Kills**: {total_kills}\n"
        f"**Total Deaths**: {total_deaths}\n"
        f"**Total Rounds**: {total_rounds}\n"
        f"**Average Kills per Round**: {avg_kills_per_round:.2f}\n"
        f"**Average Deaths per Round**: {avg_deaths_per_round:.2f}\n"
        f"**Team K/D Ratio**: {team_kd_ratio:.2f}\n"
        f"**Average Performance Score**: {avg_performance_score:.2f}"
    ), inline=False)

    await ctx.send(embed=embed)

@bot.command()
async def comparar_equipos(ctx, equipo1: str, equipo2: str, *jugadores: str):
    # Verificar que se haya proporcionado un número par de jugadores
    if len(jugadores) < 2 or len(jugadores) % 2 != 0:
        await ctx.send("❗ Por favor, proporciona un número par de jugadores. Ejemplo: `-comparar_equipos Equipo1 Equipo2 Jugador1_E1 Jugador2_E1 ... Jugador1_E2 Jugador2_E2 ...`.")
        return

    mitad = len(jugadores) // 2
    jugadores_equipo1 = jugadores[:mitad]
    jugadores_equipo2 = jugadores[mitad:]

    equipos = {
        equipo1: jugadores_equipo1,
        equipo2: jugadores_equipo2
    }

    resultados = {}

    try:
        response = requests.get(GITHUB_JSON_PLAYERS)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        await ctx.send("❌ Error al conectar con la base de datos. Inténtalo más tarde.")
        print(f"Error: {e}")
        return
    except json.JSONDecodeError:
        await ctx.send("❌ Error al procesar los datos del archivo JSON.")
        return

    for equipo, jugadores in equipos.items():
        equipo_data = []
        for jugador in jugadores:
            jugador_encontrado = next((entry for entry in data if entry["Player"].lower() == jugador.lower()), None)
            if not jugador_encontrado:
                await ctx.send(f"⚠️ Jugador '{jugador}' no encontrado en la base de datos.")
                return
            equipo_data.append(jugador_encontrado)

        # Calcular métricas del equipo
        total_score = sum(jugador['Total Score'] for jugador in equipo_data)
        total_kills = sum(jugador['Total Kills'] for jugador in equipo_data)
        total_deaths = sum(jugador['Total Deaths'] for jugador in equipo_data)
        total_rounds = sum(jugador['Rounds'] for jugador in equipo_data)
        avg_performance_score = sum(jugador['Performance Score'] for jugador in equipo_data) / len(equipo_data)

        avg_kills_per_round = total_kills / total_rounds if total_rounds > 0 else 0
        avg_deaths_per_round = total_deaths / total_rounds if total_rounds > 0 else 0
        team_kd_ratio = total_kills / total_deaths if total_deaths > 0 else 0

        resultados[equipo] = {
            "total_score": total_score,
            "total_kills": total_kills,
            "total_deaths": total_deaths,
            "total_rounds": total_rounds,
            "avg_performance_score": avg_performance_score,
            "avg_kills_per_round": avg_kills_per_round,
            "avg_deaths_per_round": avg_deaths_per_round,
            "team_kd_ratio": team_kd_ratio,
            "jugadores": equipo_data
        }

    # Generar gráficos comparativos
    plt.style.use('dark_background')
    fig, ax = plt.subplots(2, 1, figsize=(12, 12))

    for index, (equipo, datos) in enumerate(resultados.items()):
        nombres = [jugador['Player'] for jugador in datos["jugadores"]]
        kd_ratios = [jugador['K/D Ratio'] for jugador in datos["jugadores"]]

        ax[index].bar(nombres, kd_ratios, color='#00FF00', edgecolor='white')
        ax[index].set_xlabel('Jugadores', color='white')
        ax[index].set_ylabel('K/D Ratio', color='white')
        ax[index].set_title(f'K/D Ratio de Jugadores - {equipo}', color='white')
        ax[index].tick_params(axis='x', rotation=45, colors='white')
        ax[index].tick_params(axis='y', colors='white')

        # Añadir líneas horizontales de referencia
        for y in range(0, int(max(kd_ratios)) + 2):
            ax[index].axhline(y=y, color='gray', linestyle='--', linewidth=0.5)

    plt.tight_layout()

    # Guardar el gráfico en un buffer de bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)

    # Crear embed con el análisis comparativo
    embed = discord.Embed(
        title="📊 Comparación de Equipos",
        description="Aquí tienes la comparación de los equipos seleccionados:",
        color=discord.Color.blue()
    )

    for equipo, datos in resultados.items():
        embed.add_field(name=f"**📊 Métricas del Equipo {equipo}**", value=(
            f"**Total Score**: {datos['total_score']}\n"
            f"**Total Kills**: {datos['total_kills']}\n"
            f"**Total Deaths**: {datos['total_deaths']}\n"
            f"**Total Rounds**: {datos['total_rounds']}\n"
            f"**Average Kills per Round**: {datos['avg_kills_per_round']:.2f}\n"
            f"**Average Deaths per Round**: {datos['avg_deaths_per_round']:.2f}\n"
            f"**Team K/D Ratio**: {datos['team_kd_ratio']:.2f}\n"
            f"**Average Performance Score**: {datos['avg_performance_score']:.2f}"
        ), inline=False)

    # Adjuntar el gráfico al mensaje
    file = discord.File(buf, filename="team_comparison.png")
    embed.set_image(url="attachment://team_comparison.png")

    await ctx.send(embed=embed, file=file)
    
# Función para generar nombres de archivo seguros
def safe_filename(filename):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', filename)

# Esta función se usa para generar un gráfico histórico de Performance Score de un jugador
def generar_grafico_historico(player_name):
    safe_player_name = safe_filename(player_name)
    player_history_file = f"graphs/history/{safe_player_name}_history.json"
    
    if os.path.exists(player_history_file):
        with open(player_history_file, 'r') as f:
            history_data = json.load(f)
        
        dates = [entry['Date'] for entry in history_data]
        scores = [entry['Performance Score'] for entry in history_data]
        
        plt.figure(figsize=(10, 6))
        plt.plot(dates, scores, marker='o')
        plt.title(f"Performance Score Histórico de {player_name}")
        plt.xlabel('Fecha')
        plt.ylabel('Performance Score')
        plt.grid(True)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()

        return buf
    else:
        return None

@bot.command()
async def historial(ctx, jugador: str):
    """
    Muestra un gráfico histórico del Performance Score de un jugador.
    """
    try:
        grafico_file = generar_grafico_historico(jugador)
        
        if grafico_file:
            await ctx.send(f"Aquí tienes el gráfico histórico del Performance Score de {jugador}:", file=discord.File(grafico_file, f"{jugador}_history_chart.png"))
        else:
            await ctx.send(f"No se encontró historial de performance para el jugador {jugador}.")
    except Exception as e:
        await ctx.send(f"❗ Ocurrió un error inesperado. Intenta de nuevo más tarde.")
        print(f"Error: {e}")

        
# Define la zona horaria UTC-3
timezone = pytz.timezone('America/Sao_Paulo')

# Diccionario de emojis de banderas hispanohablantes y sus zonas horarias
FLAG_EMOJIS = {
    "🇦🇷": "America/Argentina/Buenos_Aires",
    "🇲🇽": "America/Mexico_City",
    "🇪🇸": "Europe/Madrid",
    "🇨🇱": "America/Santiago",
    "🇨🇴": "America/Bogota",
    "🇵🇪": "America/Lima",
    "🇻🇪": "America/Caracas",
    "🇵🇾": "America/Asuncion",
    "🇺🇾": "America/Montevideo"
}

# Comando para iniciar un countdown
@bot.command()
async def countdown(ctx, date: str, time: str):
    """
    Inicia un countdown hasta una fecha y hora específica en la zona horaria UTC-3.
    Ejemplo: -countdown 28/02/2025 16:30
    """
    try:
        # Parsea la fecha y hora ingresadas en la zona horaria UTC-3
        target_datetime = timezone.localize(datetime.strptime(f"{date} {time}", "%d/%m/%Y %H:%M"))

        # Verifica si la fecha y hora ingresadas son válidas y están en el futuro
        if target_datetime <= datetime.now(timezone):
            await ctx.send("❗ La fecha y hora deben estar en el futuro.")
            return

        # Calcula el tiempo restante
        time_remaining = target_datetime - datetime.now(timezone)

        # Crea un embed para mostrar el countdown
        embed = discord.Embed(
            title="⏳ Countdown",
            description=f"Tiempo restante hasta `{target_datetime.strftime('%d/%m/%Y %H:%M %Z')}`",
            color=discord.Color.blue()
        )

        # Actualiza el embed con el tiempo restante en tiempo real
        message = await ctx.send(embed=embed)

        while time_remaining.total_seconds() > 0:
            # Calcula el tiempo restante
            time_remaining = target_datetime - datetime.now(timezone)

            # Actualiza el embed
            embed.description = f"**{time_remaining.days}** días, **{time_remaining.seconds // 3600}** horas, **{(time_remaining.seconds // 60) % 60}** minutos, **{time_remaining.seconds % 60}** segundos."
            await message.edit(embed=embed)

            # Espera 1 segundo antes de actualizar nuevamente
            await asyncio.sleep(1)

        # Mensaje final cuando el countdown llega a 0
        embed.description = "¡El tiempo ha llegado!"
        await message.edit(embed=embed)

    except ValueError:
        await ctx.send("❗ Formato de fecha y hora inválido. Usa el formato `DD/MM/YYYY HH:MM`.")

# Función para manejar reacciones
@bot.event
async def on_raw_reaction_add(payload):
    # Ignorar reacciones del propio bot
    if payload.user_id == bot.user.id:
        return

    # Obtener el emoji de la reacción
    emoji = str(payload.emoji)

    # Verificar si el emoji es una bandera hispanohablante
    if emoji in FLAG_EMOJIS:
        # Obtener la zona horaria correspondiente
        user_timezone = pytz.timezone(FLAG_EMOJIS[emoji])

        # Definir una fecha y hora de ejemplo para el countdown
        example_target_datetime = timezone.localize(datetime.strptime("28/02/2025 16:30", "%d/%m/%Y %H:%M"))

        # Calcular el tiempo restante en la zona horaria del usuario
        time_remaining = example_target_datetime - datetime.now(user_timezone)

        # Crear un embed para mostrar el countdown
        embed = discord.Embed(
            title="⏳ Countdown Personalizado",
            description=f"Tiempo restante hasta `{example_target_datetime.strftime('%d/%m/%Y %H:%M %Z')}` en tu zona horaria ({user_timezone.zone})",
            color=discord.Color.blue()
        )

        # Actualizar el embed con el tiempo restante
        embed.description = f"**{time_remaining.days}** días, **{time_remaining.seconds // 3600}** horas, **{(time_remaining.seconds // 60) % 60}** minutos, **{time_remaining.seconds % 60}** segundos."
        await message.edit(embed=embed)

        # Enviar un mensaje privado al usuario con el countdown
        user = await bot.fetch_user(payload.user_id)
        await user.send(embed=embed)

        # Responder en el mismo canal para confirmar que se ha enviado el mensaje privado
        channel = await bot.fetch_channel(payload.channel_id)
        await channel.send(f"{user.mention}, te he enviado un mensaje privado con el countdown personalizado.")

# Nuevo comando para buscar nombres de usuarios
@bot.command()
async def buscar_usuario(ctx, *, nombre_parcial: str = None):
    if not nombre_parcial:
        await ctx.send("❗ Por favor, proporciona una parte del nombre de usuario que deseas buscar. Ejemplo: `-buscar_usuario parte_del_nombre`.")
        return

    try:
        response = requests.get(GITHUB_JSON_PLAYERS)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        await ctx.send("❌ Error al conectar con la base de datos. Inténtalo más tarde.")
        print(f"Error: {e}")
        return
    except json.JSONDecodeError:
        await ctx.send("❌ Error al procesar los datos del archivo JSON.")
        return

    # Buscar usuarios cuyos nombres contengan la cadena de búsqueda
    resultados = [jugador for jugador in data if nombre_parcial.lower() in jugador["Player"].lower()]

    if resultados:
        embed = discord.Embed(
            title="🔍 Resultados de la Búsqueda de Usuarios",
            description=f"Usuarios que contienen '{nombre_parcial}' en su nombre:",
            color=discord.Color.green()
        )

        for jugador in resultados:
            embed.add_field(
                name=jugador["Player"],
                value=(
                    f"**Clan**: {jugador['Clan']}\n"
                    f"**K/D Ratio**: {jugador['K/D Ratio']:.2f}\n"
                    f"**Performance Score**: {jugador['Performance Score']:.2f}"
                ),
                inline=True
            )
        
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"⚠️ No se encontraron usuarios que contengan '{nombre_parcial}' en su nombre.")

# Ejecutar el bot
bot.run(TOKEN)

# Comando para apagar el bot (solo el dueño del bot puede usarlo)
@bot.command()
@commands.is_owner()
async def apagar(ctx):
    try:
        await ctx.send("¡Apagando el bot!")
        await bot.close()
    except Exception as e:
        await ctx.send(f"Ocurrió un error al intentar apagar el bot: {e}")
