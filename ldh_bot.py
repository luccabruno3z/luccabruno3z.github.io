import os
from dotenv import load_dotenv
import json
import discord
from discord.ext import commands
import requests

# Cargar variables de entorno desde el archivo .env
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Validación del token
if not TOKEN:
    raise ValueError("El token del bot no está definido en las variables de entorno")
else:
    print("Token detectado correctamente")

# Configurar permisos del bot (acceso total)
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="l", intents=intents)

# URLs de los recursos
GITHUB_GRAPH_LDH = "https://luccabruno3z.github.io/LDH_interactive_chart.html"
GITHUB_GRAPH_SAE = "https://luccabruno3z.github.io/SAE_interactive_chart.html"
GITHUB_GRAPH_FI = "https://luccabruno3z.github.io/FI_interactive_chart.html"
GITHUB_GRAPH_FI_R = "https://luccabruno3z.github.io/FI-R_interactive_chart.html"
GITHUB_GRAPH_141 = "https://luccabruno3z.github.io/141_interactive_chart.html"
GITHUB_GRAPH_R_LDH = "https://luccabruno3z.github.io/R-LDH_interactive_chart.html"
GITHUB_GRAPH_PLAYERS = "https://luccabruno3z.github.io/all_players_interactive_chart.html"

GITHUB_JSON_LDH = "https://luccabruno3z.github.io/LDH_players.json"
GITHUB_JSON_SAE = "https://luccabruno3z.github.io/SAE_players.json"
GITHUB_JSON_FI = "https://luccabruno3z.github.io/FI_players.json"
GITHUB_JSON_FI_R = "https://luccabruno3z.github.io/FI-R_players.json"
GITHUB_JSON_141 = "https://luccabruno3z.github.io/141_players.json"
GITHUB_JSON_R_LDH = "https://luccabruno3z.github.io/R-LDH_players.json"
GITHUB_JSON_PLAYERS = "https://luccabruno3z.github.io/all_players_clusters.json"

GITHUB_JSON_CLANS = "https://luccabruno3z.github.io/clan_averages.json"

@bot.command()
async def graficoldh(ctx):
    await ctx.send(f"[Aquí tienes el gráfico interactivo de la LDH!]({GITHUB_GRAPH_LDH})")

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
async def grafico(ctx):
    await ctx.send(f"[Aquí tienes el gráfico interactivo de los usuarios!]({GITHUB_GRAPH_PLAYERS})")
@bot.command()
async def estadisticas(ctx, jugador: str = None):
    if not jugador:
        await ctx.send("❗ Por favor, proporciona un nombre de jugador. Ejemplo: `lestadisticas W4RR10R`.")
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

        # Crear embed con el ranking incluido
        embed = discord.Embed(
            title=f"📊 Estadísticas de {jugador}",
            description=f"**Ranking Global:** #{ranking}",
            color=color
        )
        embed.set_thumbnail(url="https://luccabruno3z.github.io/LDH_BOY2.png")  # Icono de gráfico
        embed.add_field(name="💥 K/D Ratio", value=f"{jugador_encontrado['K/D Ratio']:.2f}", inline=True)
        embed.add_field(name="🎯 Score per Round", value=f"{jugador_encontrado['Score per Round']:.2f}", inline=True)
        embed.add_field(name="🔫 Kills per Round", value=f"{jugador_encontrado.get('Kills per Round', 'N/A')}", inline=True)
        embed.add_field(name="🌟 Performance Score", value=f"{performance_score:.2f}", inline=True)
        embed.add_field(name="🎮 Rounds Jugados", value=jugador_encontrado.get("Rounds", "N/A"), inline=True)
        embed.add_field(name="☠️ Total Kills", value=jugador_encontrado.get("Total Kills", "N/A"), inline=True)
        embed.add_field(name="🏆 Total Score", value=jugador_encontrado.get("Total Score", "N/A"), inline=True)
        
        # Pie de actualización
        embed.set_footer(text="📅 Datos actualizados recientemente.")

        await ctx.send(embed=embed)

    else:
        await ctx.send(f"⚠️ Jugador '{jugador}' no encontrado en la base de datos.")



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
            "`lhola` - Saluda al bot.\n"
            "`lapagar` - Apaga el bot (solo el dueño del bot puede usar este comando)."
        ),
        inline=False
    )

    # Sección: Estadísticas de jugadores
    embed.add_field(
        name="📊 **Estadísticas de Jugadores**",
        value=(
            "`lestadisticas <jugador>` - Muestra estadísticas detalladas de un jugador, incluyendo:\n"
            "  💥 **K/D Ratio**\n"
            "  🔫 **Kills per Round**\n"
            "  🎯 **Score per Round**\n"
            "  🌟 **Performance Score**\n"
            "  🎮 **Rounds Jugados**\n"
            "  ☠️ **Total Kills**\n"
            "  🏆 **Total Score**\n\n"
            "`lcompare <jugador1> <jugador2>` - Compara estadísticas de dos jugadores."
        ),
        inline=False
    )

    # Sección: Gráficos interactivos
    embed.add_field(
        name="📈 **Gráficos Interactivos**",
        value=(
            "`lgrafico` - Muestra el gráfico interactivo con estadísticas de todos los jugadores.\n"
            "`lgraficoldh` - Muestra el gráfico interactivo de la LDH.\n"
            "`lgraficosae` - Muestra el gráfico interactivo de la SAE.\n"
            "`lgraficofi` - Muestra el gráfico interactivo de la FI.\n"
            "`lgraficofi_r` - Muestra el gráfico interactivo de la FI-R.\n"
            "`lgrafico141` - Muestra el gráfico interactivo del 141.\n"
            "`lgraficor_ldh` - Muestra el gráfico interactivo de la R-LDH."
        ),
        inline=False
    )

    # Sección: Rankings y promedios
    embed.add_field(
        name="🏅 **Rankings y Promedios**",
        value=(
            "`ltop <cantidad de jugadores> <categoría>` - Muestra el top 15 de jugadores según la categoría especificada:\n"
            "  `general`, `ldh`, `sae`, `fi`, `141`, `fi-r`, `r-ldh`.\n"
            "`lpromedios` - Muestra los promedios de estadísticas por clan."
        ),
        inline=False
    )

    # Pie de página
    embed.set_footer(
        text="Usa los comandos con el prefijo `l` para interactuar con el bot. ¡Diviértete!"
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
        "r-ldh": GITHUB_JSON_R_LDH
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
        await ctx.send("❌ **Comando no reconocido.** Usa `layuda` para ver la lista de comandos disponibles.")
    
    # Error cuando faltan argumentos en un comando
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❗ Faltan argumentos. Asegúrate de usar el comando correctamente. Ejemplo: `lestadisticas <jugador>`.")
        
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
