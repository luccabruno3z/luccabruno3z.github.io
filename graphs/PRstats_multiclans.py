import requests
from bs4 import BeautifulSoup
import pandas as pd
import plotly.express as px
import numpy as np
import os
from datetime import datetime
from sklearn.preprocessing import MinMaxScaler

os.environ["OMP_NUM_THREADS"] = "1"

# Crear carpeta 'graphs' si no existe
output_dir = "graphs"
os.makedirs(output_dir, exist_ok=True)

# URLs de clanes
clan_urls = {
    "LDH": "https://prstats.realitymod.com/clan/11204/ldh",
    "FI": "https://prstats.realitymod.com/clan/8067/fi",
    "SAE": "https://prstats.realitymod.com/clan/42817/sae",
    "FI-R": "https://prstats.realitymod.com/clan/30397/fi-r",
    "R-LDH": "https://prstats.realitymod.com/clan/37315/r-ldh",
    "141": "https://prstats.realitymod.com/clan/7555/141",
    "WD": "https://prstats.realitymod.com/clan/11052/wd",
    "300": "https://prstats.realitymod.com/clan/36331/300",
    "E-LAM": "https://prstats.realitymod.com/clan/29486/e-lam",
    "RIM:LA": "https://prstats.realitymod.com/clan/9406/rimla"
}

datos_todos_jugadores = []

def convertir_valor(valor):
    try:
        if 'M' in valor:
            return int(float(valor.replace('M', '')) * 1_000_000)
        elif 'k' in valor:
            return int(float(valor.replace('k', '')) * 1_000)
        else:
            return int(valor.replace(',', '').strip())
    except (ValueError, AttributeError):
        return None

# Extraer datos de PRStats
for clan_name, url in clan_urls.items():
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    tabla = soup.find('table')
    filas = tabla.find_all('tr')[1:]

    for fila in filas:
        columnas = fila.find_all('td')
        try:
            player = columnas[1].text.strip()
            total_score = convertir_valor(columnas[2].text.strip())
            total_kills = convertir_valor(columnas[3].text.strip())
            total_deaths = convertir_valor(columnas[4].text.strip())
            rounds = convertir_valor(columnas[5].text.strip())

            if rounds and rounds > 0:
                datos_todos_jugadores.append({
                    "Player": player,
                    "Clan": clan_name,
                    "Total Score": total_score,
                    "Total Kills": total_kills,
                    "Total Deaths": total_deaths,
                    "Rounds": rounds
                })
        except IndexError:
            print(f"Error al procesar fila: {fila}")

# Crear DataFrame general y calcular métricas
df_general = pd.DataFrame(datos_todos_jugadores).dropna()
df_general["K/D Ratio"] = df_general["Total Kills"] / df_general["Total Deaths"]
df_general["Score per Round"] = df_general["Total Score"] / df_general["Rounds"]
df_general["Kills per Round"] = df_general["Total Kills"] / df_general["Rounds"]

# Reemplazar infinitos y valores erróneos
df_general = df_general.replace([np.inf, -np.inf], np.nan).dropna()

# Normalizar métricas relevantes para calcular Performance Score
scaler = MinMaxScaler()
df_general[["Normalized_KD", "Normalized_Score", "Normalized_Kills_Per_Round", "Normalized_Rounds"]] = scaler.fit_transform(
    df_general[["K/D Ratio", "Score per Round", "Kills per Round", "Rounds"]]
)

# Calcular Performance Score con penalización para pocas rondas jugadas
df_general["Performance Score"] = (
    1 * df_general["Normalized_KD"] +
    0.4 * df_general["Normalized_Score"] +
    0.4 * df_general["Normalized_Kills_Per_Round"] +
    0.2 * df_general["Normalized_Rounds"]
)

# Penalización proporcional por pocas rondas jugadas
df_general["Performance Score"] *= df_general["Rounds"].apply(lambda x: 0.2 if x < 10 else (x / 50 + 0.2) if x < 50 else 1)

# Crear gráfico general interactivo basado en el Performance Score
fig_general = px.scatter(
    df_general, 
    x="K/D Ratio", 
    y="Score per Round", 
    size="Kills per Round", 
    hover_name=df_general.apply(lambda row: f"{row['Player']} ({row['Clan']})", axis=1), 
    color="Performance Score",
    title="Desempeño General de Todos los Jugadores (Basado en Performance Score)",
    template="plotly_dark"  # Plantilla oscura
)

# Personalización de colores y estilo
fig_general.update_layout(
    title_font=dict(size=24, color="#00FFFF", family="Bebas Neue"),
    font=dict(color="#00FFFF", family="Roboto"),
    paper_bgcolor="#121212",
    plot_bgcolor="#121212",
    xaxis=dict(gridcolor="rgba(255, 255, 255, 0.1)"),
    yaxis=dict(gridcolor="rgba(255, 255, 255, 0.1)"),
    coloraxis_colorbar=dict(
        title="Performance Score",
        title_font=dict(size=16, color="#00FFFF", family="Roboto"),
        tickfont=dict(size=12, color="#FFFFFF", family="Roboto"),
        bgcolor="#121212"
    )
)
fig_general.write_html(os.path.join(output_dir, "all_players_interactive_chart.html"))

# Guardar archivos JSON y gráficos individuales
df_general.to_json(os.path.join(output_dir, "all_players_clusters.json"), orient="records", lines=False)

# Calcular y guardar promedios por clan
clan_averages = df_general.groupby("Clan")[[
    "Total Score", 
    "Total Kills", 
    "Total Deaths", 
    "Rounds", 
    "Kills per Round", 
    "Score per Round", 
    "Performance Score",
    "K/D Ratio"
]].mean().reset_index()

clan_averages.to_json(os.path.join(output_dir, "clan_averages.json"), orient="records", lines=False)

# Guardar datos individuales de cada clan
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for clan_name in clan_urls.keys():
    df_clan = df_general[df_general["Clan"] == clan_name]
    if not df_clan.empty:
        df_clan["Last Updated"] = timestamp
        df_clan.to_json(os.path.join(output_dir, f"{clan_name}_players.json"), orient="records", lines=False)
        
        # Gráfico interactivo individual por clan
        fig_clan = px.scatter(
            df_clan, 
            x="K/D Ratio", 
            y="Score per Round", 
            size="Kills per Round", 
            hover_name="Player", 
            color="Performance Score",
            title=f"Gráfico Interactivo del Clan {clan_name}",
            template="plotly_dark"  # Plantilla oscura
        )
        
        # Personalización de colores y estilo
        fig_clan.update_layout(
            title_font=dict(size=24, color="#00FFFF", family="Bebas Neue"),
            font=dict(color="#00FFFF", family="Roboto"),
            paper_bgcolor="#121212",
            plot_bgcolor="#121212",
            xaxis=dict(gridcolor="rgba(255, 255, 255, 0.1)"),
            yaxis=dict(gridcolor="rgba(255, 255, 255, 0.1)"),
            coloraxis_colorbar=dict(
                title="Performance Score",
                title_font=dict(size=16, color="#00FFFF", family="Roboto"),
                tickfont=dict(size=12, color="#FFFFFF", family="Roboto"),
                bgcolor="#121212"
            )
        )
        fig_clan.write_html(os.path.join(output_dir, f"{clan_name}_interactive_chart.html"))

# Agregar botón de "regresar"
html_button = '''
<div style="position: absolute; top: 20px; left: 20px;">
    <a href="https://luccabruno3z.github.io" style="padding: 10px 20px; background-color: #00FFFF; color: #000; text-decoration: none; border-radius: 5px; font-weight: bold;">Regresar</a>
</div>
'''

with open(os.path.join(output_dir, "all_players_interactive_chart.html"), "a") as file:
    file.write(html_button)

for clan_name in clan_urls.keys():
    with open(os.path.join(output_dir, f"{clan_name}_interactive_chart.html"), "a") as file:
        file.write(html_button)

print("Actualización completada exitosamente usando Performance Score.")
