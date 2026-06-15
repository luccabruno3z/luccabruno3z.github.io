import requests
from bs4 import BeautifulSoup
import pandas as pd
import plotly.express as px
import numpy as np
import os
from datetime import datetime
from sklearn.preprocessing import MinMaxScaler
import json
import re

os.environ["OMP_NUM_THREADS"] = "1"

# ── Site theme palette (keep in sync with scraper/charts.py) ──────────────────
THEME_BG = "#0a0a0f"
THEME_SURFACE = "#0f0f19"
THEME_CYAN = "#00FFFF"
THEME_ORANGE = "#FFA500"
THEME_GREEN = "#00FF88"
THEME_TEXT = "#ffffff"
THEME_MUTED = "#a0a0b0"
THEME_GRID = "rgba(255, 255, 255, 0.08)"
THEME_ZERO = "rgba(255, 255, 255, 0.18)"
COLOR_SEQUENCE = [THEME_CYAN, THEME_ORANGE, THEME_GREEN, "#FF4D6D", "#9D4EDD", "#FFD60A"]
PERFORMANCE_COLORSCALE = [
    [0.0, "#0b3d4d"],
    [0.45, "#0c93a8"],
    [0.7, THEME_CYAN],
    [1.0, THEME_GREEN],
]


def _apply_dark_theme(fig, title_text):
    """Apply the site's dark/cyan theme on top of the plotly_dark template."""
    fig.update_traces(marker=dict(line=dict(width=1, color="rgba(0,0,0,0.6)"), opacity=0.9))
    fig.update_layout(
        title=dict(text=title_text, font=dict(size=26, color=THEME_CYAN, family="Bebas Neue"),
                   x=0.5, xanchor="center"),
        font=dict(color=THEME_TEXT, family="Roboto"),
        paper_bgcolor=THEME_BG,
        plot_bgcolor=THEME_BG,
        colorway=COLOR_SEQUENCE,
        margin=dict(l=70, r=40, t=80, b=60),
        hoverlabel=dict(bgcolor=THEME_SURFACE, bordercolor=THEME_CYAN,
                        font=dict(color=THEME_TEXT, family="Roboto", size=13)),
        legend=dict(bgcolor="rgba(15,15,25,0.8)", bordercolor="rgba(0,255,255,0.3)",
                    borderwidth=1, font=dict(color=THEME_TEXT, family="Roboto")),
        xaxis=dict(gridcolor=THEME_GRID, zerolinecolor=THEME_ZERO,
                   linecolor="rgba(255,255,255,0.15)",
                   title_font=dict(size=16, color=THEME_CYAN, family="Roboto"),
                   tickfont=dict(size=12, color=THEME_MUTED, family="Roboto")),
        yaxis=dict(gridcolor=THEME_GRID, zerolinecolor=THEME_ZERO,
                   linecolor="rgba(255,255,255,0.15)",
                   title_font=dict(size=16, color=THEME_CYAN, family="Roboto"),
                   tickfont=dict(size=12, color=THEME_MUTED, family="Roboto")),
        coloraxis=dict(colorscale=PERFORMANCE_COLORSCALE,
                       colorbar=dict(title=dict(text="Performance Score",
                                                font=dict(size=14, color=THEME_CYAN, family="Roboto")),
                                     tickfont=dict(size=11, color=THEME_MUTED, family="Roboto"),
                                     outlinewidth=0, bgcolor="rgba(0,0,0,0)")),
    )


def _add_top_annotations(fig, df, n=3):
    """Annotate the top N players by Performance Score with on-theme labels."""
    for _, row in df.nlargest(n, "Performance Score").iterrows():
        fig.add_annotation(
            x=row["K/D Ratio"], y=row["Score per Round"], text=f"⭐ {row['Player']}",
            showarrow=True, arrowhead=2, arrowcolor=THEME_CYAN, arrowwidth=1.5,
            ax=0, ay=-32, font=dict(color="#000000", size=12, family="Roboto"),
            bgcolor=THEME_CYAN, bordercolor=THEME_CYAN, borderpad=4, opacity=0.95,
        )


# Crear carpeta 'graphs' si no existe
output_dir = "graphs"
os.makedirs(output_dir, exist_ok=True)

# Crear carpeta 'history' si no existe
history_dir = os.path.join(output_dir, "history")
os.makedirs(history_dir, exist_ok=True)

# URLs de clanes
clan_urls = {
    "LDH": "https://prstats.realitymod.org/clan/11204/ldh",
    "FI": "https://prstats.realitymod.org/clan/8067/fi",
    "SAE": "https://prstats.realitymod.org/clan/42817/sae",
    "FI-R": "https://prstats.realitymod.org/clan/30397/fi-r",
    "R-LDH": "https://prstats.realitymod.org/clan/37315/r-ldh",
    "141": "https://prstats.realitymod.org/clan/7555/141",
    "WD": "https://prstats.realitymod.org/clan/11052/wd",
    "300": "https://prstats.realitymod.org/clan/36331/300",
    "E-LAM": "https://prstats.realitymod.org/clan/29486/e-lam",
    "RIM:LA": "https://prstats.realitymod.org/clan/9406/rimla",
    "ADG": "https://prstats.realitymod.org/clan/17913/adg",
    "A-LDH": "https://prstats.realitymod.org/clan/44173/a-ldh",
    "FASO": "https://prstats.realitymod.org/clan/46393/faso",
    "PORN": "https://prstats.realitymod.org/clan/47806/porn"
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

# Función para generar nombres de archivo seguros
def safe_filename(filename):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', filename)

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
    size="Rounds",
    size_max=42,
    hover_name=df_general.apply(lambda row: f"{row['Player']} ({row['Clan']})", axis=1),
    color="Performance Score",
    title="Desempeño General · Todos los Jugadores",
    template="plotly_dark",
    labels={
        "K/D Ratio": "K/D Ratio",
        "Score per Round": "Puntuación por Ronda",
        "Performance Score": "Performance Score"
    }
)

_apply_dark_theme(fig_general, "Desempeño General · Todos los Jugadores")
_add_top_annotations(fig_general, df_general)

fig_general.write_html(os.path.join(output_dir, "all_players_interactive_chart.html"),
                       include_plotlyjs="cdn", full_html=True,
                       config={"responsive": True, "displaylogo": False})

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
        df_clan = df_clan.copy()  # Asegurarse de trabajar sobre una copia
        df_clan["Last Updated"] = timestamp
        df_clan.to_json(os.path.join(output_dir, f"{clan_name}_players.json"), orient="records", lines=False)
        
        # Gráfico interactivo individual por clan
        fig_clan = px.scatter(
            df_clan,
            x="K/D Ratio",
            y="Score per Round",
            size="Rounds",
            size_max=42,
            hover_name="Player",
            color="Performance Score",
            title=f"Clan {clan_name} · Desempeño de Jugadores",
            template="plotly_dark",
            labels={
                "K/D Ratio": "K/D Ratio",
                "Score per Round": "Puntuación por Ronda",
                "Performance Score": "Performance Score"
            }
        )

        _apply_dark_theme(fig_clan, f"Clan {clan_name} · Desempeño de Jugadores")
        _add_top_annotations(fig_clan, df_clan)

        fig_clan.write_html(os.path.join(output_dir, f"{clan_name}_interactive_chart.html"),
                            include_plotlyjs="cdn", full_html=True,
                            config={"responsive": True, "displaylogo": False})

# Full-bleed dark body styling + back button injected into the generated HTML.
HTML_HEAD_INJECT = f'''
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
<style>
  html, body {{ margin:0; padding:0; height:100%; background-color:{THEME_BG};
    color:{THEME_TEXT}; font-family:'Roboto',sans-serif; overflow:hidden; }}
  .plotly-graph-div {{ background-color:{THEME_BG}; }}
  .pr-back-btn {{ position:fixed; top:18px; left:18px; z-index:1000; display:inline-flex;
    align-items:center; justify-content:center; width:42px; height:42px; background:{THEME_CYAN};
    color:#000; text-decoration:none; border-radius:8px; font-weight:700;
    box-shadow:0 0 12px rgba(0,255,255,0.45); transition:transform .15s ease, box-shadow .15s ease; }}
  .pr-back-btn:hover {{ transform:translateY(-2px); box-shadow:0 0 18px rgba(0,255,255,0.7); }}
</style>
'''
HTML_BACK_BUTTON = '''
<a class="pr-back-btn" href="https://luccabruno3z.github.io" title="Volver"><i class="fas fa-arrow-left"></i></a>
'''


def _inject_theme(path):
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("</head>", HTML_HEAD_INJECT + "</head>", 1)
    html = html.replace("<body>", "<body>" + HTML_BACK_BUTTON, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


_inject_theme(os.path.join(output_dir, "all_players_interactive_chart.html"))
for clan_name in clan_urls.keys():
    clan_path = os.path.join(output_dir, f"{clan_name}_interactive_chart.html")
    if os.path.exists(clan_path):
        _inject_theme(clan_path)

# Guardar historial de Performance Score de cada jugador
for _, row in df_general.iterrows():
    player_name = row["Player"]
    safe_player_name = safe_filename(player_name)
    player_history_file = os.path.join(history_dir, f"{safe_player_name}_history.json")
    
    # Cargar historial existente si existe
    if os.path.exists(player_history_file):
        with open(player_history_file, "r") as f:
            player_history = json.load(f)
    else:
        player_history = []

    # Agregar nuevo registro de Performance Score
    player_history.append({
        "Date": timestamp,
        "Performance Score": row["Performance Score"]
    })

    # Guardar historial actualizado
    with open(player_history_file, "w") as f:
        json.dump(player_history, f, indent=4)

print("Actualización completada exitosamente usando Performance Score.")
