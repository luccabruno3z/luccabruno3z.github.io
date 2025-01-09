import requests
from bs4 import BeautifulSoup
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import plotly.express as px
import numpy as np
import os
from datetime import datetime

# Evitar errores con hilos en KMeans
os.environ["OMP_NUM_THREADS"] = "1"

# URLs de clanes
clan_urls = {
    "LDH": "https://prstats.realitymod.com/clan/11204/ldh",
    "FI": "https://prstats.realitymod.com/clan/8067/fi",
    "SAE": "https://prstats.realitymod.com/clan/42817/sae"
}

# Lista para almacenar todos los jugadores de todos los clanes
datos_todos_jugadores = []

def convertir_valor(valor):
    """Convierte valores con 'M' y 'k' a enteros."""
    try:
        if 'M' in valor:
            return int(float(valor.replace('M', '')) * 1_000_000)
        elif 'k' in valor:
            return int(float(valor.replace('k', '')) * 1_000)
        else:
            return int(valor.replace(',', '').strip())
    except (ValueError, AttributeError):
        return None

# Recopilar datos de los clanes
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

# Crear DataFrame general y eliminar valores problemáticos
df_general = pd.DataFrame(datos_todos_jugadores).dropna()

# Evitar división por cero y valores infinitos
df_general["K/D Ratio"] = df_general.apply(
    lambda row: row["Total Kills"] / row["Total Deaths"] if row["Total Deaths"] > 0 else np.nan, axis=1)
df_general["Score per Round"] = df_general.apply(
    lambda row: row["Total Score"] / row["Rounds"] if row["Rounds"] > 0 else np.nan, axis=1)
df_general["Kills per Round"] = df_general.apply(
    lambda row: row["Total Kills"] / row["Rounds"] if row["Rounds"] > 0 else np.nan, axis=1)

# Eliminar valores infinitos y nulos
df_general = df_general.replace([np.inf, -np.inf], np.nan).dropna()

# Normalizar los datos y aplicar K-means
scaler = StandardScaler()
data_scaled = scaler.fit_transform(df_general[['K/D Ratio', 'Score per Round']])

# K-means con 20 clusters
kmeans = KMeans(n_clusters=20, random_state=42, n_init=10)
df_general["Cluster"] = kmeans.fit_predict(data_scaled)

# Definir etiquetas para los clusters
cluster_labels = {
    0: "Legendario", 1: "Excepcional", 2: "Sobresaliente", 3: "Elite", 4: "Excelente",
    5: "Notable", 6: "Destacado", 7: "Alto", 8: "Muy Bueno", 9: "Bueno",
    10: "Promedio Alto", 11: "Promedio", 12: "Promedio Bajo", 13: "Aceptable",
    14: "Bajo", 15: "Insuficiente", 16: "Deficiente", 17: "Muy Deficiente",
    18: "Crítico", 19: "Extremadamente Bajo"
}
df_general["Cluster Label"] = df_general["Cluster"].map(cluster_labels)

# Crear gráfico general
fig_general = px.scatter(
    df_general, 
    x="K/D Ratio", 
    y="Score per Round", 
    hover_name=df_general.apply(lambda row: f"{row['Player']} ({row['Clan']})", axis=1), 
    color="Cluster Label"
)
fig_general.write_html("grafico_general_todos_clanes.html")

# Guardar el archivo JSON general con timestamp
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
df_general.to_json("todos_los_jugadores.json", orient="records", indent=4)
with open("todos_los_jugadores.json", "a") as f:
    f.write(f"\n# Last updated: {timestamp}\n")

print("\n✅ Gráfico general y archivo JSON creados exitosamente.")

# Guardar gráficos y archivos JSON individuales por clan
for clan_name in clan_urls.keys():
    try:
        df_clan = df_general[df_general["Clan"] == clan_name]
        
        if not df_clan.empty:
            # Guardar archivo JSON corregido
            df_clan.to_json(f"{clan_name}_players.json", orient="records", indent=4)
            
            # Agregar marca de tiempo
            with open(f"{clan_name}_players.json", "a") as f:
                f.write(f"\n# Last updated: {timestamp}\n")
            
            # Crear gráfico para el clan
            fig_clan = px.scatter(
                df_clan, 
                x="K/D Ratio", 
                y="Score per Round", 
                hover_name="Player", 
                color="Cluster Label"
            )
            fig_clan.write_html(f"{clan_name}_grafico_interactivo.html")

            print(f"✅ Datos y gráficos generados correctamente para {clan_name}")

        else:
            print(f"⚠️ No se encontraron datos para el clan {clan_name}")

    except Exception as e:
        print(f"❌ Error al procesar el clan {clan_name}: {e}")

print("\n✅ Proceso completado.")
