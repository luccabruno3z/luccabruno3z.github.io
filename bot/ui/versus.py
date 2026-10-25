"""Bloques "versus" para comparar dos jugadores/clanes en Components V2.

Cada métrica ocupa dos renglones:

    **K/D** · ▲ =FAUST= +85%
    `1,91` 🟦🟦🟦🟦🟦🟦🟧🟧🟧🟧 `1,03`

La barra se reparte según la proporción de cada lado (el mejor queda con más
segmentos, también en métricas donde menos es mejor). Usa cuadrados unicode y no
Application Emojis a propósito: ocupan 1-2 caracteres en lugar de ~36, así una
comparación de 17 métricas entra holgada en el límite de texto de V2.
"""

from __future__ import annotations

LEFT, RIGHT, EVEN = "🟦", "🟧", "⬜"
SEGMENTS = 10


def num(v) -> str:
    """1.91 → '1,91'; 2349 → '2.349'; 750.0 → '750'."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if abs(f - round(f)) < 1e-9 and abs(f) >= 10:
        return f"{int(round(f)):,}".replace(",", ".")
    if abs(f) >= 100:
        return f"{f:,.0f}".replace(",", ".")
    return f"{f:.2f}".replace(".", ",")


def _adv(win: float, lose: float) -> str:
    if not lose:
        return ""
    pct = (win - lose) / abs(lose) * 100
    return f"{'+' if pct >= 0 else ''}{pct:.0f}%"


def split_bar(v1: float, v2: float, higher_is_better: bool = True) -> str:
    a, b = (v1 or 0), (v2 or 0)
    if not higher_is_better:
        a, b = b, a  # el que tiene MENOS se lleva la parte más grande
    total = a + b
    n1 = SEGMENTS // 2 if total <= 0 else round(SEGMENTS * a / total)
    n1 = max(0, min(SEGMENTS, n1))
    return LEFT * n1 + RIGHT * (SEGMENTS - n1)


def versus_lines(name1: str, name2: str, metrics: list[tuple]) -> tuple[str, int, int, int]:
    """metrics: [(label, v1, v2, higher_is_better)] → (markdown, wins1, wins2, ties)."""
    out = []
    w1 = w2 = ties = 0
    for label, v1, v2, hib in metrics:
        a, b = v1 or 0, v2 or 0
        win1 = a > b if hib else a < b
        win2 = b > a if hib else b < a
        if win1:
            w1 += 1
            head = f"**{label}** · ▲ {name1} {_adv(a, b) if hib else ''}".rstrip()
        elif win2:
            w2 += 1
            head = f"**{label}** · ▲ {name2} {_adv(b, a) if hib else ''}".rstrip()
        else:
            ties += 1
            head = f"**{label}** · empate"
        out.append(head)
        out.append(f"`{num(a)}` {split_bar(a, b, hib)} `{num(b)}`")
    return "\n".join(out), w1, w2, ties


def verdict(name1: str, name2: str, w1: int, w2: int, total: int) -> str:
    if w1 > w2:
        return f"### 🏆 {name1} gana {w1} de {total}"
    if w2 > w1:
        return f"### 🏆 {name2} gana {w2} de {total}"
    return f"### 🤝 Empate · {w1} categorías cada uno"


def legend(name1: str, name2: str) -> str:
    return f"{LEFT} **{name1}**  vs  {RIGHT} **{name2}**"
