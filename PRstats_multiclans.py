import requests
from bs4 import BeautifulSoup
import pandas as pd
import plotly.express as px
import numpy as np
import os
from datetime import datetime
from sklearn.preprocessing import MinMaxScaler

os.environ["OMP_NUM_THREADS"] = "1"

# URLs de clanes
clan_urls = {
    "LDH": "https://prstats.realitymod.com/clan/11204/ldh",
    "FI": "https://prstats.realitymod.com/clan/8067/fi",
    "SAE": "https://prstats.realitymod.com/clan/42817/sae",
    "FI-R": "https://prstats.realitymod.com/clan/30397/fi-r",
    "R-LDH": "https://prstats.realitymod.com/clan/37315/r-ldh",
    "141": "https://prstats.realitymod.com/clan/7555/141"
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
df_general["Kill Efficiency"] = df_general["Total Kills"] / df_general["Total Score"]
df_general["Survivability Rate"] = df_general["Total Deaths"] / df_general["Rounds"]

# Reemplazar infinitos y valores erróneos
df_general = df_general.replace([np.inf, -np.inf], np.nan).dropna()

# Normalizar métricas relevantes
scaler = MinMaxScaler()
df_general[["Normalized_KD", "Normalized_Score", "Normalized_Kills_Per_Round"]] = scaler.fit_transform(
    df_general[["K/D Ratio", "Score per Round", "Kills per Round"]]
)

# Calcular Performance Score con prioridad para KD y Score
df_general["Performance Score"] = (
    0.5 * df_general["Normalized_KD"] +
    0.3 * df_general["Normalized_Score"] +
    0.2 * df_general["Normalized_Kills_Per_Round"]
)

# Asignar clusters con nombres de materiales
def asignar_cluster(score):
    materiales = [
    "Carbón 1", "Carbón 2", "Hierro 1", "Hierro 2", "Cobre 1",
    "Cobre 2", "Bronce 1", "Bronce 2", "Plata 1", "Plata 2",
    "Oro 1", "Oro 2", "Platino 1", "Platino 2", "Diamante 1",
    "Diamante 2"
    ]
    percentiles = np.linspace(0, 1, len(materiales) + 1)
    for i in range(len(materiales)):
        if percentiles[i] <= score < percentiles[i + 1]:
            return materiales[i]
    return materiales[-1]  # Por defecto, el peor material

# Aplicar clasificación
df_general["Cluster Label"] = df_general["Performance Score"].apply(asignar_cluster)

# Crear gráfico general interactivo
fig_general = px.scatter(
    df_general, 
    x="K/D Ratio", 
    y="Score per Round", 
    size="Kills per Round", 
    hover_name=df_general.apply(lambda row: f"{row['Player']} ({row['Clan']})", axis=1), 
    color="Cluster Label",
    title="Desempeño General de Todos los Jugadores (Clasificación por Materiales)"
)
fig_general.write_html("all_players_interactive_chart.html")

# Guardar archivos JSON y gráficos
df_general.to_json("all_players_clusters.json", orient="records", lines=False)

clan_averages = (
    df_general.groupby("Clan")[["Total Score", "Total Kills", "Total Deaths", "Rounds", "Kills per Round", "Score per Round", "Performance Score"]]
    .mean()
    .reset_index()
)


# Guardar promedios por clan
clan_averages.to_json("clan_averages.json", orient="records", lines=False)

# Guardar archivos por clan y gráficos interactivos
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for clan_name in clan_urls.keys():
    df_clan = df_general[df_general["Clan"] == clan_name]
    if not df_clan.empty:
        df_clan["Last Updated"] = timestamp
        df_clan.to_json(f"{clan_name}_players.json", orient="records", lines=False)
        
        fig_clan = px.scatter(
            df_clan, 
            x="K/D Ratio", 
            y="Score per Round", 
            size="Kills per Round", 
            hover_name="Player", 
            color="Cluster Label",
            title=f"Gráfico Interactivo del Clan {clan_name}"
        )
        fig_clan.write_html(f"{clan_name}_interactive_chart.html")

print("Actualización completada exitosamente con el sistema de clasificación por materiales.")

