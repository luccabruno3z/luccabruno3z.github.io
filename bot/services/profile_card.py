"""Tarjeta de perfil como imagen (encabezado de -perfil).

Se dibuja con Pillow (viene con matplotlib) y fuentes DejaVu (vienen con
matplotlib), así anda igual en Windows y en Railway sin instalar nada.
No hace pedidos de red: recibe los datos y los bytes del logo ya bajados.

Diseño: 1100×440, el doble de lo que Discord muestra en el chat (~550 px), para
que se vea nítida y legible en el celular.
"""

from __future__ import annotations

import io
import os
from datetime import datetime

import matplotlib
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H = 1100, 440
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_FONTS = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
_RANKS = os.path.join(_ROOT, "bot", "assets", "ranks")
_KITS = os.path.join(_ROOT, "bot", "assets", "kits")
_MAPS = os.path.join(_ROOT, "web", "img", "maps")

# Colores del sitio (web/css/styles.css)
BG = (10, 10, 15)
TEXT = (255, 255, 255)
MUTED = (160, 160, 176)
DIM = (122, 122, 138)
ACCENT = (0, 255, 255)
TIER_COLORS = {
    "Elite": (255, 215, 0), "Veterano": (0, 255, 136), "Experimentado": (0, 187, 255),
    "Soldado": (255, 165, 0), "Recluta": (255, 68, 102),
}
# Rol de demos → ícono de kit
ROLE_ICON = {
    "fusilero": "kit_Rifle.png", "medico": "kit_Medic.png", "at": "kit_AT.png", "ar": "kit_MG.png",
    "ametrallador": "kit_MG.png", "breacher": "kit_Engineer.png", "granadero": "kit_Grenadier.png",
    "tirador": "kit_Marksman.png", "oficial": "kit_Officer.png", "tripulante": "kit_Crewman.png",
    "ingeniero": "kit_Engineer.png", "piloto": "kit_Pilot.png", "aa": "kit_AA.png",
    "observador": "kit_Spotter.png",
}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(os.path.join(_FONTS, name), size)


def fmt_num(v, dec: int = 0) -> str:
    """Formato rioplatense: 2.591 · 0,827."""
    s = f"{v:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def _fit(draw, text, font_size, max_w, bold=True):
    """Achica la fuente hasta que el texto entra en max_w (nombres largos)."""
    size = font_size
    while size > 14:
        f = _font(size, bold)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return _font(size, bold)


def _background(map_key: str | None) -> Image.Image:
    """Mapa más jugado, recortado, desenfocado y oscurecido; si no hay, fondo liso."""
    base = Image.new("RGB", (W, H), BG)
    path = os.path.join(_MAPS, f"{map_key}.jpg") if map_key else None
    if path and os.path.exists(path):
        m = Image.open(path).convert("RGB")
        side = int(min(m.size) * 0.55)
        cx, cy = m.size[0] // 2, m.size[1] // 2
        m = m.crop((cx - side // 2, cy - side * H // W // 2, cx + side // 2, cy + side * H // W // 2))
        m = m.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(3))
        base = Image.blend(base, m, 0.6)
    # Velo oscuro de izquierda a derecha para que el texto se lea.
    veil = Image.new("L", (W, 1))
    for x in range(W):
        veil.putpixel((x, 0), int(225 - 150 * (x / W)))
    veil = veil.resize((W, H))
    dark = Image.new("RGB", (W, H), BG)
    return Image.composite(dark, base, veil)


def _rounded(img: Image.Image, r: int) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *img.size), r, fill=255)
    out = Image.new("RGBA", img.size)
    out.paste(img, (0, 0), mask)
    return out


def _circle_logo(data: bytes | None, size: int, tag: str | None = None) -> Image.Image | None:
    """Logo del clan en un disco; sin logo, el tag del clan escrito en el disco."""
    logo = None
    if data:
        try:
            logo = Image.open(io.BytesIO(data)).convert("RGBA")
        except Exception:
            logo = None
    if logo is None and not tag:
        return None
    disc = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(disc)
    d.ellipse((0, 0, size - 1, size - 1), fill=(15, 15, 25, 235), outline=ACCENT + (120,), width=3)
    if logo is not None:
        logo = ImageOps.contain(logo, (size - 16, size - 16), Image.LANCZOS)
        disc.alpha_composite(logo, ((size - logo.width) // 2, (size - logo.height) // 2))
    else:
        f = _fit(d, tag, 40, size - 24)
        tw = d.textlength(tag, font=f)
        bb = d.textbbox((0, 0), tag, font=f)
        d.text(((size - tw) / 2, (size - (bb[3] - bb[1])) / 2 - bb[1]), tag, font=f, fill=ACCENT)
    return disc


def short_role(label: str) -> str:
    """"Anti-tanque (LAT/HAT)" → "Anti-tanque"; "Fusilero automático" → "Fus. automático"."""
    label = label.split(" (")[0]
    return {"Fusilero automático": "Fus. automático", "Ingeniero de combate": "Ingeniero"}.get(label, label)


_TIER_LEVEL = {"Recluta": 1, "Soldado": 2, "Experimentado": 3, "Veterano": 4, "Elite": 5}


def draw_insignia(tier: str, color: tuple, size: int) -> Image.Image:
    """Insignia militar del tier: escudo del color del tier con galones.

    Recluta 1 galón · Soldado 2 · Experimentado 3 · Veterano 3 y una barra ·
    Elite 3, barra y estrella. Se dibuja a 4× y se achica para que los bordes
    queden suaves.
    """
    s = size * 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lvl = _TIER_LEVEL.get(tier, 1)
    def shield(inset):
        m, b = s * (0.05 + inset), s * (0.95 - inset)
        return [(m, m), (b, m), (b, s * 0.58), (s / 2, b), (m, s * 0.58)]

    # Borde = escudo del color con otro escudo oscuro adentro (sin juntas raras).
    d.polygon(shield(0), fill=color + (255,))
    d.polygon(shield(0.045), fill=(15, 15, 25, 245))

    cx = s / 2
    w = s * 0.24          # medio ancho del galón
    hgt = s * 0.10        # alto del galón
    th = s * 0.06         # grosor
    step = s * 0.11
    n = min(lvl, 3)
    # Con barra o estrella arriba, los galones bajan; si no, quedan centrados.
    top = s * 0.32 if lvl >= 4 else s * 0.42 - (n - 1) * step / 2 - hgt / 2
    for i in range(n):
        y = top + i * step
        # Galón apuntando hacia arriba (^), como polígono con grosor.
        d.polygon([(cx - w, y + hgt), (cx, y), (cx + w, y + hgt),
                   (cx + w, y + hgt + th), (cx, y + th), (cx - w, y + hgt + th)], fill=color + (255,))
    if lvl == 4:  # Veterano: barra arriba de los galones
        y = s * 0.19
        d.rounded_rectangle((cx - w, y, cx + w, y + th), radius=int(th / 2), fill=color + (255,))
    if lvl >= 5:  # Elite: estrella arriba
        import math
        r1, r2, sy = s * 0.095, s * 0.04, s * 0.205
        pts = []
        for k in range(10):
            a = -math.pi / 2 + k * math.pi / 5
            r = r1 if k % 2 == 0 else r2
            pts.append((cx + r * math.cos(a), sy + r * math.sin(a)))
        d.polygon(pts, fill=color + (255,))
    return im.resize((size, size), Image.LANCZOS)


def _icon(path: str, size: int) -> Image.Image | None:
    if not os.path.exists(path):
        return None
    return Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)


def render_profile_card(
    *,
    name: str,
    clan: str | None,
    logo_bytes: bytes | None,
    tier: str,
    ps: float,
    tier_floor: float,
    next_tier: tuple[str, float] | None,
    rank: int | None,
    total: int,
    kd: float,
    kpr: float,
    spr: float,
    rounds: int,
    winrate: float | None,
    winrate_games: int = 0,
    best_role: tuple[str, str] | None = None,
    map_key: str | None = None,
    updated: datetime | None = None,
) -> io.BytesIO:
    """Devuelve un PNG en memoria. `best_role` = (clave, etiqueta) del rol de demos."""
    img = _background(map_key).convert("RGBA")
    d = ImageDraw.Draw(img)
    tc = TIER_COLORS.get(tier, ACCENT)

    # Marco
    d.rounded_rectangle((6, 6, W - 7, H - 7), 26, outline=ACCENT + (90,), width=2)
    d.rectangle((6, 34, 12, H - 34), fill=tc)  # filete del color del tier

    # ── Encabezado: logo, nombre, clan y puesto ──────────────────────────────
    x0 = 44
    logo = _circle_logo(logo_bytes, 112, clan)
    if logo:
        img.alpha_composite(logo, (x0, 36))
        tx = x0 + 132
    else:
        tx = x0
    d.text((tx, 40), name, font=_fit(d, name, 50, 1060 - tx - 360), fill=TEXT)
    sub = []
    if clan:
        sub.append(clan)
    if rank:
        sub.append(f"#{fmt_num(rank)} de {fmt_num(total)} por Performance"
                   + (" (provisorio)" if rounds < 50 else ""))
    d.text((tx, 104), "  ·  ".join(sub), font=_font(24), fill=MUTED)

    # ── Bloque del tier y Performance (izquierda) ────────────────────────────
    py = 184
    d.rounded_rectangle((36, py, 500, H - 40), 20, fill=(15, 15, 25, 200), outline=tc + (110,), width=2)
    img.alpha_composite(draw_insignia(tier, tc, 104), (58, py + 26))
    d.text((180, py + 22), "PERFORMANCE", font=_font(20, True), fill=DIM)
    d.text((178, py + 46), fmt_num(ps, 3), font=_font(64, True), fill=TEXT)
    d.text((182, py + 128), tier.upper(), font=_font(26, True), fill=tc)

    # Barra: progreso dentro del tier hacia el siguiente.
    bx0, bx1, by = 58, 478, H - 86
    d.rounded_rectangle((bx0, by, bx1, by + 12), 6, fill=(255, 255, 255, 30))
    if next_tier:
        span = max(next_tier[1] - tier_floor, 1e-6)
        frac = max(0.0, min(1.0, (ps - tier_floor) / span))
        label = f"Próximo: {next_tier[0]} desde {fmt_num(next_tier[1], 3)}"
    else:
        frac, label = 1.0, "Tier más alto"
    d.rounded_rectangle((bx0, by, bx0 + max(12, int((bx1 - bx0) * frac)), by + 12), 6, fill=tc)
    d.text((bx0, by + 18), label, font=_font(18), fill=MUTED)

    # ── Estadísticas (derecha, 3×2) ──────────────────────────────────────────
    tiles = [
        ("K/D", fmt_num(kd, 2), None),
        ("KILLS / RONDA", fmt_num(kpr, 2), None),
        ("SCORE / RONDA", fmt_num(spr), None),
        ("RONDAS", fmt_num(rounds), None),
        ("WINRATE", f"{fmt_num(winrate * 100)} %" if winrate is not None else "—",
         f"{fmt_num(winrate_games)} partidas" if winrate is not None else "sin demos"),
        ("MEJOR ROL", short_role(best_role[1]) if best_role else "—", None),
    ]
    gx0, gy0, tw, th, gap = 528, 184, 172, 98, 14
    for i, (lbl, val, foot) in enumerate(tiles):
        cx = gx0 + (i % 3) * (tw + gap)
        cy = gy0 + (i // 3) * (th + gap)
        d.rounded_rectangle((cx, cy, cx + tw, cy + th), 16, fill=(15, 15, 25, 205),
                            outline=ACCENT + (45,), width=1)
        d.text((cx + 16, cy + 12), lbl, font=_font(15, True), fill=DIM)
        if lbl == "MEJOR ROL" and best_role:
            ic = _icon(os.path.join(_KITS, ROLE_ICON.get(best_role[0], "kit_Rifle.png")), 34)
            if ic:
                img.alpha_composite(ic, (cx + tw - 46, cy + 8))
            d.text((cx + 16, cy + 46), val, font=_fit(d, val, 28, tw - 28), fill=TEXT)
        else:
            d.text((cx + 16, cy + 34), val, font=_fit(d, val, 38, tw - 30), fill=TEXT)
            if foot:
                d.text((cx + 16, cy + 76), foot, font=_font(14), fill=MUTED)

    # Pie
    when = (updated or datetime.now()).strftime("%d/%m/%Y")
    foot = f"LDH Stats  ·  {when}"
    f = _font(17)
    d.text((W - 40 - d.textlength(foot, font=f), H - 38), foot, font=f, fill=DIM)

    out = io.BytesIO()
    _rounded(img.convert("RGB"), 26).save(out, "PNG", optimize=True)
    out.seek(0)
    return out
