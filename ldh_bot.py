import os
from dotenv import load_dotenv
import json
import discord
from discord.ext import commands
import requests
import random

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
GITHUB_GRAPH_WD = "https://luccabruno3z.github.io/graphs/WD_interactive_chart.html"
GITHUB_GRAPH_300 = "https://luccabruno3z.github.io/graphs/300_interactive_chart.html"
GITHUB_GRAPH_E_LAM = "https://luccabruno3z.github.io/graphs/E-LAM_interactive_chart.html"
GITHUB_GRAPH_PLAYERS = "https://luccabruno3z.github.io/graphs/all_players_interactive_chart.html"

GITHUB_JSON_LDH = "https://luccabruno3z.github.io/graphs/LDH_players.json"
GITHUB_JSON_SAE = "https://luccabruno3z.github.io/graphs/SAE_players.json"
GITHUB_JSON_FI = "https://luccabruno3z.github.io/graphs/FI_players.json"
GITHUB_JSON_FI_R = "https://luccabruno3z.github.io/graphs/FI-R_players.json"
GITHUB_JSON_141 = "https://luccabruno3z.github.io/graphs/141_players.json"
GITHUB_JSON_R_LDH = "https://luccabruno3z.github.io/graphs/R-LDH_players.json"
GITHUB_JSON_WD = "https://luccabruno3z.github.io/graphs/WD_players.json"
GITHUB_JSON_300 = "https://luccabruno3z.github.io/graphs/300_players.json"
GITHUB_JSON_E_LAM = "https://luccabruno3z.github.io/graphs/E-LAM_players.json"
GITHUB_JSON_PLAYERS = "https://luccabruno3z.github.io/graphs/all_players_clusters.json"

GITHUB_JSON_CLANS = "https://luccabruno3z.github.io/graphs/clan_averages.json"

GITHUB_INDEX = "https://luccabruno3z.github.io"

# URL de las guías y el visualizador 2D
GITHUB_GUIDES = "https://luccabruno3z.github.io/#guias"
GITHUB_VISUALIZER_2D = "https://luccabruno3z.github.io/realitytracker.github.io/"

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

    # Buscar al jugador y su ranking
    jugador_encontrado = next((entry for entry in jugadores_ordenados if entry["Player"].lower() == jugador.lower()), None)
    ranking = next((index + 1 for index, entry in enumerate(jugadores_ordenados) if entry["Player"].lower() == jugador.lower()), "N/A")

    if jugador_encontrado:
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

        # Calcular la tasa de muertes por ronda
        total_deaths = jugador_encontrado.get("Total Deaths", 0)
        rounds_played = jugador_encontrado.get("Rounds", 1)  # Evitar división por cero
        deaths_per_round = total_deaths / rounds_played if rounds_played > 0 else 0

        # Crear embed con el ranking incluido
        embed = discord.Embed(
            title=f"📊 Estadísticas de {jugador}",
            description=f"**Ranking Global:** #{ranking}",
            color=color
        )
        embed.set_thumbnail(url=clan_image_url)  # Imagen del clan

        # Agregar estadísticas agrupadas
        embed.add_field(name="📊 Datos Totales", value=(
            f"💥 **K/D Ratio**: {jugador_encontrado['K/D Ratio']:.2f}\n"
            f"☠️ **Total Kills**: {jugador_encontrado.get('Total Kills', 'N/A')}\n"
            f"🏆 **Total Score**: {jugador_encontrado.get('Total Score', 'N/A')}\n"
            f"💀 **Total Muertes**: {total_deaths}\n"
            f"🎮 **Rounds Jugados**: {jugador_encontrado.get('Rounds', 'N/A')}"
        ), inline=False)

        embed.add_field(name="📉 Tasas", value=(
            f"📉 **Tasa de Muertes**: {deaths_per_round:.2f}\n"
            f"🔫 **Tasa de Kills**: {jugador_encontrado.get('Kills per Round', 'N/A')}\n"
            f"🎯 **Tasa de Score**: {jugador_encontrado['Score per Round']:.2f}"
        ), inline=False)

        embed.add_field(name="🌟 Otros", value=(
            f"🌟 **Performance Score**: {performance_score:.2f}\n"
            f"🎖️ **Clan**: {clan}"
        ), inline=False)

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
        title="📜 Lista de Comandos Disponibles",
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
            "  📉 **Tasa de Muertes**\n\n"
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
            "`-graficowd` - Muestra el gráfico interactivo de la WD.\n"
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
            "`-top <cantidad de jugadores> <categoría>` - Muestra el top de jugadores según la categoría especificada:\n"
            "  `general`, `ldh`, `sae`, `fi`, `141`, `fi-r`, `r-ldh`.\n"
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
        for clan_data in data:
            clan_name = clan_data.get("Clan", "Desconocido")
            kd_ratio = clan_data.get('K/D Ratio')
            score_per_round = clan_data.get('Score per Round')
            kills_per_round = clan_data.get('Kills per Round')

            # Convertir valores a flotante y manejar valores faltantes
            kd_ratio_str = f"{float(kd_ratio):.2f}" if isinstance(kd_ratio, (int, float)) else "N/A"
            score_per_round_str = f"{float(score_per_round):.2f}" if isinstance(score_per_round, (int, float)) else "N/A"
            kills_per_round_str = f"{float(kills_per_round):.2f}" if isinstance(kills_per_round, (int, float)) else "N/A"

            # Formato más estético
            embed.add_field(
                name=f"🏅 {clan_name}",
                value=(
                    f"**🔹 Promedio K/D:** {kd_ratio_str}\n"
                    f"**🔹 Promedio Score:** {score_per_round_str}\n"
                    f"**🔹 Promedio Kills:** {kills_per_round_str}"
                ),
                inline=False
            )
        await ctx.send(embed=embed)
    else:
        await ctx.send("El formato de los datos no es válido.")


@bot.command()
async def compare(ctx, player1: str, player2: str):
    """
    Compara las estadísticas de dos jugadores usando el archivo JSON alojado en GitHub Pages.
    """
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

    # Buscar los jugadores en la base de datos
    p1 = next((p for p in data if p['Player'].lower() == player1.lower()), None)
    p2 = next((p for p in data if p['Player'].lower() == player2.lower()), None)

    if p1 and p2:
        # Determinar colores para cada jugador según su Performance Score
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

        # Crear embed para la comparación
        embed = discord.Embed(
            title=f"🔍 Comparación entre {player1} y {player2}",
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
            name=f"🎮 {player1}",
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
            name=f"🎮 {player2}",
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

        # Resolución sobre el mejor jugador
        if p1['Performance Score'] > p2['Performance Score']:
            resolution = f"🌟 **{player1}** parece ser mejor que **{player2}**."
        elif p1['Performance Score'] < p2['Performance Score']:
            resolution = f"🌟 **{player2}** parece ser mejor que **{player1}**."
        else:
            resolution = "🤝 Ambos jugadores tienen un desempeño similar."

        embed.add_field(name="Resolución", value=resolution, inline=False)
        embed.set_footer(text="📅 Datos actualizados recientemente.")

        await ctx.send(embed=embed)
    else:
        await ctx.send("⚠️ No se encontraron estadísticas para uno o ambos jugadores.")


@bot.command()
async def top(ctx, cantidad: int = 15, categoria: str = "general"):
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
        "300": GITHUB_JSON_300
    }

    # Validar la categoría ingresada
    if categoria.lower() not in categorias_validas:
        await ctx.send(
            "❗ **Categoría inválida.** Las categorías válidas son:\n"
            "`general`, `ldh`, `sae`, `fi`, `141`, `fi-r`, `r-ldh`."
        )
        return

    # Validar la cantidad de jugadores solicitados
    if cantidad <= 0:
        await ctx.send("❗ **La cantidad debe ser mayor a 0.**")
        return

    # Obtener la URL del archivo JSON según la categoría
    url_json = categorias_validas[categoria.lower()]

    # Intentar obtener y procesar los datos
    try:
        response = requests.get(url_json)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        await ctx.send("❌ **Error al conectar con la base de datos.** Inténtalo más tarde.")
        print(f"Error: {e}")
        return
    except json.JSONDecodeError:
        await ctx.send("❌ **Error al procesar los datos del archivo JSON.**")
        return

    # Ordenar los jugadores por Performance Score
    jugadores_ordenados = sorted(
        data, 
        key=lambda x: x.get("Performance Score", 0), 
        reverse=True
    )

    # Limitar al número total de jugadores disponibles
    cantidad = min(cantidad, len(jugadores_ordenados))
    top_jugadores = jugadores_ordenados[:cantidad]

    # Crear el embed
    embed = discord.Embed(
        title=f"🏆 **Top {cantidad} Jugadores** ({categoria.upper()})",
        description=(
            "Clasificación basada en **Performance Score**.\n"
            f"Aquí están los mejores {cantidad} jugadores en esta categoría:"
        ),
        color=discord.Color.orange()
    )
    embed.set_thumbnail(url="https://luccabruno3z.github.io/LDH_BOY2.png")  # Imagen representativa

    # Agregar los jugadores al embed con formato más limpio
    jugadores_lista = ""
    for index, jugador in enumerate(top_jugadores, start=1):
        nombre = jugador.get("Player", "Desconocido")
        performance_score = jugador.get("Performance Score", 0)
        jugadores_lista += f"**#{index}** - {nombre} (🌟 {performance_score:.2f})\n"

    embed.add_field(
        name="🔝 **Ranking**",
        value=jugadores_lista if jugadores_lista else "No hay jugadores en esta categoría.",
        inline=False
    )

    # Agregar pie de página
    embed.set_footer(text="📅 Datos actualizados recientemente.")

    # Enviar el embed
    await ctx.send(embed=embed)



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


# Comando para apagar el bot (solo el dueño del bot puede usarlo)
@bot.command()
@commands.is_owner()
async def apagar(ctx):
    try:
        await ctx.send("¡Apagando el bot!")
        await bot.close()
    except Exception as e:
        await ctx.send(f"Ocurrió un error al intentar apagar el bot: {e}")

# Ejecutar el bot
bot.run(TOKEN)
