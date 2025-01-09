import requests
from bs4 import BeautifulSoup
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
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

# Extracción de datos
for clan_name, url in clan_urls.items():
    print(f"\nProcesando datos para el clan: {clan_name}")

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

# Creación del DataFrame general
df_general = pd.DataFrame(datos_todos_jugadores).dropna()
df_general["K/D Ratio"] = df_general.apply(lambda row: row["Total Kills"] / row["Total Deaths"] 
                                           if row["Total Deaths"] > 0 else np.nan, axis=1)
df_general["Score per Round"] = df_general.apply(lambda row: row["Total Score"] / row["Rounds"] 
                                                 if row["Rounds"] > 0 else np.nan, axis=1)
df_general["Kills per Round"] = df_general.apply(lambda row: row["Total Kills"] / row["Rounds"] 
                                                 if row["Rounds"] > 0 else np.nan, axis=1)

df_general = df_general.replace([np.inf, -np.inf], np.nan).dropna()

# Normalizar y aplicar K-means con 20 clusters
scaler = StandardScaler()
data_scaled = scaler.fit_transform(df_general[['K/D Ratio', 'Score per Round']])
kmeans = KMeans(n_clusters=20, random_state=42)
df_general["Cluster"] = kmeans.fit_predict(data_scaled)

# Definir etiquetas para clusters
cluster_labels = {
    0: "Legendario", 1: "Excepcional", 2: "Sobresaliente", 3: "Elite", 4: "Excelente",
    5: "Notable", 6: "Destacado", 7: "Alto", 8: "Muy Bueno", 9: "Bueno",
    10: "Promedio Alto", 11: "Promedio", 12: "Promedio Bajo", 13: "Aceptable",
    14: "Bajo", 15: "Insuficiente", 16: "Deficiente", 17: "Muy Deficiente",
    18: "Crítico", 19: "Extremadamente Bajo"
}
df_general["Cluster Label"] = df_general["Cluster"].map(cluster_labels)

# 🎯 Gráfico general con información del clan
fig_general = px.scatter(
    df_general, 
    x="K/D Ratio", 
    y="Score per Round", 
    hover_name=df_general.apply(lambda row: f"{row['Player']} ({row['Clan']})", axis=1), 
    color="Cluster Label"
)
fig_general.write_html("all_players_interactive_chart.html")

# ✅ Guardar JSON de todos los jugadores con clusters
df_general.to_json("all_players_clusters.json", orient="records", lines=False)

# ✅ Guardar JSON con promedios por clan
clan_averages = df_general.groupby("Clan")[["Total Score", "Total Kills", "Total Deaths", "Rounds"]].mean().to_dict(orient="index")
with open("clan_averages.json", "w") as f:
    import json
    json.dump(clan_averages, f, indent=4)

# ✅ Guardar JSON de cada clan y agregar timestamp
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for clan_name in clan_urls.keys():
    try:
        df_clan = df_general[df_general["Clan"] == clan_name]
        if not df_clan.empty:
            df_clan.to_json(f"{clan_name}_players.json", orient="records", lines=False)
            with open(f"{clan_name}_players.json", "a") as f:
                f.write(f"\n# Last updated: {timestamp}\n")
            print(f"Datos guardados exitosamente para {clan_name}")
        else:
            print(f"No se generaron datos para el clan {clan_name}")
    except Exception as e:
        print(f"Error al procesar el clan {clan_name}: {e}")

print("\n✅ Todos los archivos han sido actualizados correctamente.")

