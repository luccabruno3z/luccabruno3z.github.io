import requests
from bs4 import BeautifulSoup
import pandas as pd
import plotly.express as px
import numpy as np
import os
from datetime import datetime

os.environ["OMP_NUM_THREADS"] = "1"

# URLs de clanes
clan_urls = {
    "LDH": "https://prstats.realitymod.com/clan/11204/ldh",
    "FI": "https://prstats.realitymod.com/clan/8067/fi",
    "SAE": "https://prstats.realitymod.com/clan/42817/sae"
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

# Crear DataFrame general
df_general = pd.DataFrame(datos_todos_jugadores).dropna()
df_general["K/D Ratio"] = df_general.apply(lambda row: row["Total Kills"] / row["Total Deaths"] 
                                           if row["Total Deaths"] > 0 else np.nan, axis=1)
df_general["Score per Round"] = df_general.apply(lambda row: row["Total Score"] / row["Rounds"] 
                                                 if row["Rounds"] > 0 else np.nan, axis=1)

df_general = df_general.replace([np.inf, -np.inf], np.nan).dropna()

# ✅ Calcular un puntaje combinado de desempeño
df_general["Performance Score"] = (df_general["Score per Round"] + df_general["K/D Ratio"]) / 2

# ✅ Asignar clusters basados en percentiles
df_general["Cluster"] = pd.qcut(df_general["Performance Score"], q=20, labels=False, duplicates='drop')

# ✅ Crear etiquetas jerárquicas basadas en percentiles
cluster_labels = [
    "Legendario (Top 5%)", "Excepcional", "Sobresaliente", "Elite", "Excelente",
    "Notable", "Destacado", "Alto", "Muy Bueno", "Bueno",
    "Promedio Alto", "Promedio", "Promedio Bajo", "Aceptable",
    "Bajo", "Insuficiente", "Deficiente", "Muy Deficiente",
    "Crítico", "Extremadamente Bajo (Bottom 5%)"
]

# Asignar las etiquetas de manera inversa (mejor desempeño = cluster 0)
df_general["Cluster Label"] = df_general["Cluster"].map(lambda x: cluster_labels[x])

# 🎯 Crear gráfico general interactivo con etiquetas correctas
fig_general = px.scatter(
    df_general, 
    x="K/D Ratio", 
    y="Score per Round", 
    hover_name=df_general.apply(lambda row: f"{row['Player']} ({row['Clan']})", axis=1), 
    color="Cluster Label",
    title="Desempeño General de Todos los Jugadores"
)
fig_general.write_html("all_players_interactive_chart.html")

# ✅ Guardar el archivo JSON general
df_general.to_json("all_players_clusters.json", orient="records", lines=False)

# ✅ Guardar los promedios por clan
clan_averages = df_general.groupby("Clan")[["Total Score", "Total Kills", "Total Deaths", "Rounds"]].mean().to_dict(orient="index")
with open("clan_averages.json", "w") as f:
    import json
    json.dump(clan_averages, f, indent=4)

# ✅ Guardar archivos individuales por clan
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for clan_name in clan_urls.keys():
    try:
        # Filtrar el DataFrame por clan
        df_clan = df_general[df_general["Clan"] == clan_name]
        
        if not df_clan.empty:
            # Guardar datos del clan en JSON
            df_clan.to_json(f"{clan_name}_players.json", orient="records", lines=False)
            
            # Guardar gráfico interactivo por clan
            fig_clan = px.scatter(
                df_clan, 
                x="K/D Ratio", 
                y="Score per Round", 
                hover_name="Player", 
                color="Cluster Label",
                title=f"Gráfico interactivo de {clan_name}"
            )
            fig_clan.write_html(f"{clan_name}_interactive_chart.html")

            # Agregar marca de tiempo al archivo JSON
            with open(f"{clan_name}_players.json", "a") as f:
                f.write(f"\n# Last updated: {timestamp}\n")
            
            print(f"Datos y gráfico guardados exitosamente para {clan_name}")
        else:
            print(f"No se generaron datos para el clan {clan_name}")

    except Exception as e:
        print(f"Error al procesar el clan {clan_name}: {e}")

print("\n✅ Todos los archivos han sido actualizados correctamente.")

