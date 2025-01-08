import requests
from bs4 import BeautifulSoup
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import plotly.express as px
import numpy as np
import os

os.environ["OMP_NUM_THREADS"] = "1"

# URLs de clanes
clan_urls = {
    "LDH": "https://prstats.realitymod.com/clan/11204/ldh",
    "FI": "https://prstats.realitymod.com/clan/8067/fi",
    "SAE": "https://prstats.realitymod.com/clan/42817/sae"
}

# Listas para almacenar datos combinados y promedios de clanes
all_players_data = []
clan_averages = []

# Etiquetas para los clusters
cluster_labels = {
    0: "Leyenda máxima", 1: "Élite profesional", 2: "Maestro veterano", 3: "Experto competitivo",
    4: "Jugador destacado", 5: "Rendimiento alto", 6: "Rendimiento sólido", 7: "Rendimiento bueno",
    8: "Por encima del promedio", 9: "Promedio alto", 10: "Promedio estándar", 11: "Promedio bajo",
    12: "Por debajo del promedio", 13: "Rendimiento bajo", 14: "Rendimiento insuficiente",
    15: "Novato prometedor", 16: "Principiante", 17: "Bajo rendimiento", 18: "Rendimiento crítico",
    19: "Nivel extremadamente bajo"
}

# Función para convertir valores con 'k' y 'M'
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

# Procesamiento de cada clan individualmente
for clan_name, url in clan_urls.items():
    print(f"\nProcesando datos para el clan: {clan_name}")

    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    tabla = soup.find('table')
    filas = tabla.find_all('tr')[1:]

    datos_clan = []

    for fila in filas:
        columnas = fila.find_all('td')
        try:
            player = columnas[1].text.strip()
            total_score = convertir_valor(columnas[2].text.strip())
            total_kills = convertir_valor(columnas[3].text.strip())
            total_deaths = convertir_valor(columnas[4].text.strip())
            rounds = convertir_valor(columnas[5].text.strip())

            if rounds and rounds > 0:
                datos_clan.append({
                    "Player": player,
                    "Clan": clan_name,
                    "Total Score": total_score,
                    "Total Kills": total_kills,
                    "Total Deaths": total_deaths,
                    "Rounds": rounds
                })
        except IndexError:
            print(f"Error al procesar fila: {fila}")

    # Convertir a DataFrame y calcular estadísticas
    df = pd.DataFrame(datos_clan).dropna()
    df["K/D Ratio"] = df.apply(lambda row: row["Total Kills"] / row["Total Deaths"] 
                               if row["Total Deaths"] > 0 else np.nan, axis=1)
    df["Score per Round"] = df.apply(lambda row: row["Total Score"] / row["Rounds"] 
                                     if row["Rounds"] > 0 else np.nan, axis=1)
    df["Kills per Round"] = df.apply(lambda row: row["Total Kills"] / row["Rounds"] 
                                     if row["Rounds"] > 0 else np.nan, axis=1)
    df = df.replace([np.inf, -np.inf], np.nan).dropna()

    # Calcular promedios del clan
    clan_avg_kd = df["K/D Ratio"].mean()
    clan_avg_score = df["Score per Round"].mean()
    clan_avg_kills = df["Kills per Round"].mean()
    clan_averages.append({
        "Clan": clan_name,
        "K/D Ratio": clan_avg_kd,
        "Score per Round": clan_avg_score,
        "Kills per Round": clan_avg_kills
    })

    # Normalizar y aplicar K-means
    scaler = StandardScaler()
    data_scaled = scaler.fit_transform(df[['K/D Ratio', 'Score per Round']])
    kmeans = KMeans(n_clusters=20, random_state=42)
    df["Cluster"] = kmeans.fit_predict(data_scaled)

    # Ordenar los clusters del clan y asignar etiquetas
    cluster_order = df.groupby("Cluster")[['K/D Ratio', 'Score per Round']].mean().sort_values(
        by=['K/D Ratio', 'Score per Round'], ascending=[False, False]).index.tolist()
    cluster_reorder_map = {cluster: i for i, cluster in enumerate(cluster_order)}
    df["Cluster"] = df["Cluster"].map(cluster_reorder_map)
    df["Cluster Label"] = df["Cluster"].map(cluster_labels)

    # Guardar datos del clan individual
    df.to_json(f"{clan_name}_players.json", orient="records", lines=False)
    fig = px.scatter(df, x="K/D Ratio", y="Score per Round", hover_name="Player", 
                     color="Cluster Label", title=f"Clasificación de jugadores del clan {clan_name}")
    fig.write_html(f"{clan_name}_grafico_interactivo.html")

    # Añadir al conjunto general
    all_players_data.extend(df.to_dict(orient='records'))

# Procesamiento global de todos los jugadores
df_all = pd.DataFrame(all_players_data)
scaler = StandardScaler()
data_scaled_all = scaler.fit_transform(df_all[['K/D Ratio', 'Score per Round']])
kmeans_all = KMeans(n_clusters=20, random_state=42)
df_all["Cluster"] = kmeans_all.fit_predict(data_scaled_all)

# Ordenar y etiquetar clusters globales
cluster_order_global = df_all.groupby("Cluster")[['K/D Ratio', 'Score per Round']].mean().sort_values(
    by=['K/D Ratio', 'Score per Round'], ascending=[False, False]).index.tolist()
cluster_reorder_map_global = {cluster: i for i, cluster in enumerate(cluster_order_global)}
df_all["Cluster"] = df_all["Cluster"].map(cluster_reorder_map_global)
df_all["Cluster Label"] = df_all["Cluster"].map(cluster_labels)

# Guardar resultados globales
df_all.to_json("all_players_clusters.json", orient="records", lines=False)
fig_all = px.scatter(df_all, x="K/D Ratio", y="Score per Round", hover_name="Player", 
                     color="Cluster Label", title="Clasificación global de jugadores")
fig_all.write_html("all_players_interactive_chart.html")

# Guardar promedios de clanes
df_clan_avg = pd.DataFrame(clan_averages)
df_clan_avg.to_json("clan_averages.json", orient="records", lines=False)

print("\n✅ Análisis completado con éxito.")
