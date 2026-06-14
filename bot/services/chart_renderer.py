"""Matplotlib chart helpers with guaranteed plt.close() and dark theme."""

from contextlib import contextmanager
import io

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend; must be set before importing pyplot
import matplotlib.pyplot as plt
import numpy as np


@contextmanager
def _chart_context(figsize=(10, 6)):
    """Context manager that yields (fig, ax) and always closes the figure."""
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=figsize)
    try:
        yield fig, ax
    finally:
        buf = None  # caller handles buf outside
        plt.close(fig)


def _save_to_buffer(fig) -> io.BytesIO:
    """Save figure to a BytesIO buffer and close it."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf


# ── Public renderers ──────────────────────────────────────────────────────────

def render_bar_chart(
    labels: list[str],
    values: list[float],
    title: str,
    xlabel: str,
    ylabel: str,
) -> io.BytesIO:
    """Generic bar chart with dark theme, gradient coloring, value labels, and
    average line. Returns BytesIO ready for discord.File."""
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor("#121212")
    ax.set_facecolor("#121212")

    index = range(len(labels))

    # Gradient coloring: higher values get more cyan, lower get more gray
    max_val = max(values) if values else 1
    colors = []
    for v in values:
        ratio = v / max_val if max_val != 0 else 0
        # Interpolate from gray (0.4, 0.4, 0.4) to cyan (0, 1, 1)
        r = 0.4 * (1 - ratio)
        g = 0.4 + 0.6 * ratio
        b = 0.4 + 0.6 * ratio
        colors.append((r, g, b))

    bars = ax.bar(index, values, 0.5, color=colors, edgecolor="white", linewidth=0.5)

    # Value labels on top of each bar
    for bar, v in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max_val * 0.01,
            f"{v:.1f}",
            ha="center",
            va="bottom",
            color="white",
            fontsize=9,
        )

    # Horizontal average line
    if values:
        avg = sum(values) / len(values)
        ax.axhline(y=avg, color="red", linestyle="--", linewidth=1.2, label=f"Promedio: {avg:.1f}")
        ax.legend(loc="upper right", fontsize=9)

    ax.set_xlabel(xlabel, color="white")
    ax.set_ylabel(ylabel, color="white")
    ax.set_title(title, color="white")
    ax.set_xticks(index)
    ax.set_xticklabels(labels, rotation=45, ha="right", color="white")
    ax.tick_params(axis="y", colors="white")

    return _save_to_buffer(fig)


def render_kd_chart(
    player_names: list[str],
    kd_ratios: list[float],
    title: str,
) -> io.BytesIO:
    """Bar chart of K/D ratios with tier-based coloring and break-even line."""
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor("#121212")
    ax.set_facecolor("#121212")

    index = range(len(player_names))

    # Color each bar by K/D tier
    colors = []
    for kd in kd_ratios:
        if kd >= 2.0:
            colors.append("#FFD700")  # gold
        elif kd >= 1.5:
            colors.append("#00FF00")  # green
        elif kd >= 1.0:
            colors.append("#00FFFF")  # cyan
        else:
            colors.append("#FF4444")  # red

    bars = ax.bar(index, kd_ratios, 0.5, color=colors, edgecolor="white", linewidth=0.5)

    ax.set_xlabel("Jugadores", color="white")
    ax.set_ylabel("K/D Ratio", color="white")
    ax.set_title(title, color="white")
    ax.set_xticks(index)
    ax.set_xticklabels(player_names, rotation=45, ha="right", color="white")
    ax.tick_params(axis="y", colors="white")
    ax.grid(axis="y", linestyle="--", color="gray", alpha=0.3)

    # Break-even line at K/D = 1.0
    ax.axhline(y=1.0, color="white", linestyle="--", linewidth=1.2, label="Break-even (1.0)")
    ax.legend(loc="upper right", fontsize=9)

    # Value labels on bars
    for bar, kd in zip(bars, kd_ratios):
        yval = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            yval + 0.01,
            f"{yval:.2f}",
            ha="center",
            color="white",
            fontsize=9,
        )

    return _save_to_buffer(fig)


def render_comparison_chart(
    team1_name: str,
    team1_data: list[dict],
    team2_name: str,
    team2_data: list[dict],
) -> io.BytesIO:
    """Grouped bar chart comparing K/D ratios of two teams side by side."""
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor("#121212")
    ax.set_facecolor("#121212")

    # Build aligned player lists by position index
    max_players = max(len(team1_data), len(team2_data))
    t1_names = [p["Player"] for p in team1_data]
    t1_kds = [p["K/D Ratio"] for p in team1_data]
    t2_names = [p["Player"] for p in team2_data]
    t2_kds = [p["K/D Ratio"] for p in team2_data]

    # Pad shorter team with zeros/empty
    while len(t1_names) < max_players:
        t1_names.append("")
        t1_kds.append(0)
    while len(t2_names) < max_players:
        t2_names.append("")
        t2_kds.append(0)

    x = np.arange(max_players)
    bar_width = 0.35

    bars1 = ax.bar(x - bar_width / 2, t1_kds, bar_width, label=team1_name, color="#00FFFF", edgecolor="white", linewidth=0.5)
    bars2 = ax.bar(x + bar_width / 2, t2_kds, bar_width, label=team2_name, color="orange", edgecolor="white", linewidth=0.5)

    # Value labels on each bar
    for bars in [bars1, bars2]:
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    h + 0.01,
                    f"{h:.2f}",
                    ha="center",
                    va="bottom",
                    color="white",
                    fontsize=8,
                )

    # X-axis labels: show both player names per position
    combined_labels = []
    for i in range(max_players):
        parts = []
        if t1_names[i]:
            parts.append(t1_names[i])
        if t2_names[i]:
            parts.append(t2_names[i])
        combined_labels.append(" vs ".join(parts) if len(parts) == 2 else (parts[0] if parts else ""))

    ax.set_xlabel("Jugadores", color="white")
    ax.set_ylabel("K/D Ratio", color="white")
    ax.set_title(f"Comparación K/D: {team1_name} vs {team2_name}", color="white", fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(combined_labels, rotation=45, ha="right", color="white", fontsize=9)
    ax.tick_params(axis="y", colors="white")
    ax.legend(loc="upper right", fontsize=10)
    ax.grid(axis="y", linestyle="--", color="gray", alpha=0.3)

    fig.tight_layout()
    return _save_to_buffer(fig)


def render_radar_chart(
    player_values: dict,
    clan_avg_values: dict,
    player_name: str,
    clan_name: str,
) -> io.BytesIO:
    """Radar/spider chart comparing player stats vs clan average. Returns BytesIO."""
    categories = list(player_values.keys())
    n = len(categories)

    # Compute angles for each axis
    angles = [i / n * 2 * np.pi for i in range(n)]
    angles += angles[:1]  # close the polygon

    player_vals = [player_values[c] for c in categories] + [player_values[categories[0]]]
    clan_vals = [clan_avg_values.get(c, 0) for c in categories] + [clan_avg_values.get(categories[0], 0)]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor("#121212")
    ax.set_facecolor("#121212")

    # Draw player polygon
    ax.plot(angles, player_vals, color="#00FFFF", linewidth=2, label=player_name)
    ax.fill(angles, player_vals, color="#00FFFF", alpha=0.25)

    # Draw second dataset polygon (clan average or second player)
    ax.plot(angles, clan_vals, color="orange", linewidth=2, linestyle="--", label=clan_name)

    # Labels at each vertex with category name and numeric value
    ax.set_xticks(angles[:-1])
    label_texts = [f"{cat}\n({player_values[cat]:.2f})" for cat in categories]
    ax.set_xticklabels(label_texts, color="white", fontsize=10)

    # Style grid and ticks
    ax.set_ylim(0, 1.0)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], color="gray", fontsize=8)
    ax.spines["polar"].set_color("gray")
    ax.tick_params(colors="gray")
    ax.grid(color="gray", linestyle="--", linewidth=0.5)

    ax.set_title(f"Perfil de {player_name}", color="white", fontsize=14, pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=10)

    return _save_to_buffer(fig)


def render_history_chart(
    player_name: str,
    dates: list[str],
    scores: list[float],
) -> io.BytesIO:
    """Line chart of historical performance with trend line and formatted dates."""
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor("#121212")
    ax.set_facecolor("#121212")

    # Format dates as dd/mm
    from datetime import datetime

    formatted_dates = []
    for d in dates:
        try:
            dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
            formatted_dates.append(dt.strftime("%d/%m"))
        except (ValueError, AttributeError):
            # Fallback: try to extract dd/mm from common formats
            formatted_dates.append(str(d)[:5] if len(str(d)) >= 5 else str(d))

    x_numeric = np.arange(len(scores))

    # Linear trend line
    if len(scores) >= 2:
        coeffs = np.polyfit(x_numeric, scores, 1)
        trend_line = np.polyval(coeffs, x_numeric)
        improving = coeffs[0] >= 0

        # Area fill colored by trend direction
        fill_color = "#00FF00" if improving else "#FF4444"
        ax.fill_between(x_numeric, scores, alpha=0.15, color=fill_color)

        # Trend line
        trend_label = "Tendencia (mejorando)" if improving else "Tendencia (bajando)"
        ax.plot(x_numeric, trend_line, linestyle="--", color="orange", linewidth=1.5, label=trend_label)
    else:
        ax.fill_between(x_numeric, scores, alpha=0.15, color="#00FF00")

    # Adaptive marker size: smaller if many points
    n_pts = len(scores)
    marker_size = 6 if n_pts <= 30 else (3 if n_pts <= 60 else 1)
    marker_style = "o" if n_pts <= 60 else ""

    ax.plot(x_numeric, scores, marker=marker_style, color="#00FFFF", linewidth=2, markersize=marker_size)

    ax.set_title(f"Performance Score Historico de {player_name}", color="white", fontsize=13)
    ax.set_xlabel("Fecha", color="white")
    ax.set_ylabel("Performance Score", color="white")

    # Smart X-axis: limit to ~15 evenly spaced ticks max
    max_ticks = min(n_pts, 15)
    if n_pts > max_ticks:
        step = max(1, n_pts // max_ticks)
        tick_indices = list(range(0, n_pts, step))
        if tick_indices[-1] != n_pts - 1:
            tick_indices.append(n_pts - 1)  # always show last date
        ax.set_xticks([x_numeric[i] for i in tick_indices])
        ax.set_xticklabels([formatted_dates[i] for i in tick_indices], rotation=45, ha="right", color="white")
    else:
        ax.set_xticks(x_numeric)
        ax.set_xticklabels(formatted_dates, rotation=45, ha="right", color="white")

    ax.tick_params(axis="y", colors="white")
    ax.grid(True, linestyle="--", color="gray", alpha=0.2)
    if len(scores) >= 2:
        ax.legend(loc="upper left", fontsize=9)

    return _save_to_buffer(fig)


def render_distribution_chart(
    all_values: list[float],
    player_value: float,
    metric_name: str,
    player_name: str,
) -> io.BytesIO:
    """Histogram showing distribution of a metric across all players, with
    the given player's position highlighted. Returns BytesIO."""
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor("#121212")
    ax.set_facecolor("#121212")

    # Histogram
    n_bins = min(20, max(5, len(all_values) // 3))
    ax.hist(all_values, bins=n_bins, color="#00FFFF", alpha=0.6, edgecolor="white", linewidth=0.5)

    # Player position line
    ax.axvline(x=player_value, color="#FF4444", linestyle="--", linewidth=2, label=player_name)

    # Calculate percentile (top X%)
    count_below = sum(1 for v in all_values if v <= player_value)
    percentile = (count_below / len(all_values)) * 100 if all_values else 0
    top_pct = 100 - percentile

    # Label showing position
    y_max = ax.get_ylim()[1]
    ax.text(
        player_value,
        y_max * 0.92,
        f"  Tu posición: top {top_pct:.0f}%",
        color="#FF4444",
        fontsize=11,
        fontweight="bold",
        va="top",
    )

    ax.set_title(f"Distribución de {metric_name}", color="white", fontsize=14)
    ax.set_xlabel(metric_name, color="white")
    ax.set_ylabel("Cantidad de jugadores", color="white")
    ax.tick_params(axis="x", colors="white")
    ax.tick_params(axis="y", colors="white")
    ax.grid(axis="y", linestyle="--", color="gray", alpha=0.2)
    ax.legend(loc="upper right", fontsize=10)

    return _save_to_buffer(fig)


def render_multi_comparison(
    name1: str,
    values1: list[float],
    name2: str,
    values2: list[float],
    labels: list[str],
    title: str = "",
) -> io.BytesIO:
    """Grouped bar chart comparing two entities across multiple metrics.

    Normalizes each metric independently (max of both = 1.0) so different
    scales (K/D ~2 vs Total Kills ~5000) are visually comparable.
    Real values are shown as labels on each bar.
    Returns BytesIO ready for discord.File.
    """
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor("#121212")
    ax.set_facecolor("#121212")

    # Normalize per-metric for bar heights, keep raw for labels
    norm1, norm2 = [], []
    for v1, v2 in zip(values1, values2):
        mx = max(abs(v1), abs(v2), 0.001)
        norm1.append(v1 / mx)
        norm2.append(v2 / mx)

    x = np.arange(len(labels))
    bar_width = 0.35

    bars1 = ax.bar(
        x - bar_width / 2, norm1, bar_width,
        label=name1, color="#00FFFF", edgecolor="white", linewidth=0.5,
    )
    bars2 = ax.bar(
        x + bar_width / 2, norm2, bar_width,
        label=name2, color="orange", edgecolor="white", linewidth=0.5,
    )

    # Show REAL values as labels (not normalized)
    for bars, raw_vals in [(bars1, values1), (bars2, values2)]:
        for bar, raw in zip(bars, raw_vals):
            h = bar.get_height()
            label = f"{raw:,.0f}" if abs(raw) >= 100 else f"{raw:.2f}"
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + 0.02,
                label,
                ha="center",
                va="bottom",
                color="white",
                fontsize=8,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", color="white")
    ax.set_ylim(0, 1.25)  # normalized scale with room for labels
    ax.set_yticks([])  # hide y-axis (values are on bars)
    if title:
        ax.set_title(title, color="white", fontsize=14)
    ax.legend(loc="upper right", fontsize=10)
    ax.grid(axis="y", linestyle="--", color="gray", alpha=0.3)

    fig.tight_layout()
    return _save_to_buffer(fig)


def render_ranking_change_chart(
    names: list[str],
    changes: list[float],
    title: str = "",
) -> io.BytesIO:
    """Horizontal bar chart showing ranking changes per player.
    Positive = green (right), negative = red (left). Sorted by magnitude.
    Returns BytesIO ready for discord.File."""
    plt.style.use("dark_background")

    # Sort by magnitude (biggest change on top)
    paired = sorted(zip(names, changes), key=lambda p: abs(p[1]))
    sorted_names = [p[0] for p in paired]
    sorted_changes = [p[1] for p in paired]

    fig, ax = plt.subplots(figsize=(10, max(4, len(sorted_names) * 0.45)))
    fig.patch.set_facecolor("#121212")
    ax.set_facecolor("#121212")

    colors = ["#00FF00" if c >= 0 else "#FF4444" for c in sorted_changes]
    y = np.arange(len(sorted_names))

    bars = ax.barh(y, sorted_changes, color=colors, edgecolor="white", linewidth=0.5)

    # Change value labels on bars
    for bar, val in zip(bars, sorted_changes):
        label = f"+{val:.0f}" if val >= 0 else f"{val:.0f}"
        x_pos = bar.get_width()
        ha = "left" if val >= 0 else "right"
        offset = abs(max(sorted_changes, key=abs)) * 0.02 if sorted_changes else 0.1
        x_pos = x_pos + offset if val >= 0 else x_pos - offset
        ax.text(
            x_pos,
            bar.get_y() + bar.get_height() / 2,
            label,
            ha=ha,
            va="center",
            color="white",
            fontsize=10,
            fontweight="bold",
        )

    ax.set_yticks(y)
    ax.set_yticklabels(sorted_names, color="white", fontsize=10)
    ax.tick_params(axis="x", colors="white")
    ax.axvline(x=0, color="white", linewidth=0.8)
    ax.set_xlabel("Cambio en ranking", color="white")
    if title:
        ax.set_title(title, color="white", fontsize=14)
    ax.grid(axis="x", linestyle="--", color="gray", alpha=0.3)

    fig.tight_layout()
    return _save_to_buffer(fig)


def render_horizontal_bars(
    items: list[tuple[str, float, str]],
    title: str = "",
    max_value: float | None = None,
    value_suffix: str = "",
    show_values: bool = True,
    bar_height: float = 0.6,
) -> io.BytesIO:
    """Horizontal bar chart. Returns BytesIO PNG.

    items: list of (label, value, color) tuples.
    """
    plt.style.use("dark_background")
    fig_h = max(2, len(items) * 0.55 + 0.8)
    fig, ax = plt.subplots(figsize=(6, fig_h))
    fig.patch.set_facecolor("#121212")
    ax.set_facecolor("#121212")

    labels = [it[0] for it in items]
    values = [it[1] for it in items]
    colors = [it[2] for it in items]

    y = np.arange(len(items))
    bars = ax.barh(y, values, height=bar_height, color=colors, edgecolor="none")

    if max_value is not None:
        ax.set_xlim(0, max_value * 1.15)

    if show_values:
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_width() + (max(values) if values else 1) * 0.02,
                bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}{value_suffix}",
                ha="left",
                va="center",
                color="white",
                fontsize=9,
            )

    ax.set_yticks(y)
    ax.set_yticklabels(labels, color="white", fontsize=10)
    ax.tick_params(axis="x", colors="white")
    ax.grid(False)
    if title:
        ax.set_title(title, color="white", fontsize=13)

    fig.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf


def render_comparison_bars(
    metrics: list[tuple[str, float, float]],
    name1: str = "Jugador 1",
    name2: str = "Jugador 2",
    title: str = "",
) -> io.BytesIO:
    """Side-by-side horizontal bars comparing two entities. Returns BytesIO PNG."""
    plt.style.use("dark_background")
    fig_h = max(2.5, len(metrics) * 0.7 + 1.2)
    fig, ax = plt.subplots(figsize=(7, fig_h))
    fig.patch.set_facecolor("#121212")
    ax.set_facecolor("#121212")

    labels = [m[0] for m in metrics]
    vals1 = [m[1] for m in metrics]
    vals2 = [m[2] for m in metrics]

    y = np.arange(len(metrics))
    bar_h = 0.35

    bars1 = ax.barh(y - bar_h / 2, vals1, height=bar_h, color="#00FFFF", label=name1)
    bars2 = ax.barh(y + bar_h / 2, vals2, height=bar_h, color="orange", label=name2)

    all_vals = vals1 + vals2
    max_val = max(all_vals) if all_vals else 1

    for bars, vals in [(bars1, vals1), (bars2, vals2)]:
        for bar, val in zip(bars, vals):
            label = f"{val:,.0f}" if abs(val) >= 100 else f"{val:.2f}"
            ax.text(
                bar.get_width() + max_val * 0.02,
                bar.get_y() + bar.get_height() / 2,
                label,
                ha="left",
                va="center",
                color="white",
                fontsize=8,
            )

    ax.set_yticks(y)
    ax.set_yticklabels(labels, color="white", fontsize=10)
    ax.tick_params(axis="x", colors="white")
    ax.grid(False)
    ax.legend(loc="upper right", fontsize=9)
    if title:
        ax.set_title(title, color="white", fontsize=13)

    fig.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf


def render_probability_bar(
    prob_a: float,
    prob_b: float,
    label_a: str = "Equipo A",
    label_b: str = "Equipo B",
) -> io.BytesIO:
    """Stacked horizontal bar showing win probability. Returns BytesIO PNG."""
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(7, 1.5))
    fig.patch.set_facecolor("#121212")
    ax.set_facecolor("#121212")

    ax.barh(0, prob_a, height=0.5, color="#00FFFF", edgecolor="none")
    ax.barh(0, prob_b, height=0.5, left=prob_a, color="orange", edgecolor="none")

    # Percentage labels centered in each segment
    if prob_a > 0.05:
        ax.text(
            prob_a / 2, 0,
            f"{label_a}\n{prob_a * 100:.0f}%",
            ha="center", va="center",
            color="black", fontsize=10, fontweight="bold",
        )
    if prob_b > 0.05:
        ax.text(
            prob_a + prob_b / 2, 0,
            f"{label_b}\n{prob_b * 100:.0f}%",
            ha="center", va="center",
            color="black", fontsize=10, fontweight="bold",
        )

    ax.set_xlim(0, prob_a + prob_b)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.grid(False)

    fig.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf
