# Visual presets. Pick with THEME=<name> (default: brutalist, chosen 2026-09-27).
import os

PRESETS = {
    # Dark, minimal, one mint accent. The original look.
    "midnight": dict(
        BG="#0f1115", PANEL="#1a1d24", FG="#e8eaed", MUTED="#8b93a1", ACCENT="#6ee7b7", WARN="#f59e0b",
        EMPTY="#2a2e37", ON_ACCENT="#0f1115", FONT="Helvetica Neue", MONO="Menlo", WEIGHT="NORMAL",
        BORDER=None, BORDER_W=0, RADIUS=1.0, SHADOW=None,
        CAPTION_BG="#000000", CAPTION_OPACITY=0.55, CAPTION_FG="#e8eaed",
    ),
    # Synthwave: deep purple, hot pink + cyan.
    "neon": dict(
        BG="#0d0221", PANEL="#1b0b44", FG="#fdfdff", MUTED="#9d8ec7", ACCENT="#ff2e88", WARN="#00e5ff",
        EMPTY="#2b1a5c", ON_ACCENT="#0d0221", FONT="Avenir Next", MONO="Menlo", WEIGHT="NORMAL",
        BORDER="#ff2e88", BORDER_W=3, RADIUS=1.0, SHADOW=None,
        CAPTION_BG="#ff2e88", CAPTION_OPACITY=1.0, CAPTION_FG="#0d0221",
    ),
    # Text colors in the light themes are picked for >= 4.4:1 contrast on both BG and PANEL.
    # Neo-brutalist: cream paper, thick black outlines, hard offset shadows, square corners.
    "brutalist": dict(
        BG="#f3ede2", PANEL="#ffffff", FG="#111111", MUTED="#555555", ACCENT="#c93a00", WARN="#1f3fd6",
        EMPTY="#e2dccf", ON_ACCENT="#ffffff", FONT="Helvetica Neue", MONO="Menlo", WEIGHT="MEDIUM", MONO_WEIGHT="BOLD",
        BORDER="#111111", BORDER_W=5, RADIUS=0.0, SHADOW=(0.12, -0.12),
        CAPTION_BG="#111111", CAPTION_OPACITY=1.0, CAPTION_FG="#f3ede2",
    ),
    # Loud pop / sticker style: yellow, hot pink, chunky rounded outlines, playful font.
    "pop": dict(
        BG="#ffd60a", PANEL="#ffffff", FG="#1d1d1d", MUTED="#4b2bd6", ACCENT="#c2004f", WARN="#006b4f",
        EMPTY="#fff3b0", ON_ACCENT="#ffffff", FONT="Arial Rounded MT Bold", MONO="Menlo", WEIGHT="NORMAL", MONO_WEIGHT="BOLD",
        BORDER="#1d1d1d", BORDER_W=6, RADIUS=1.6, SHADOW=(0.14, -0.14),
        CAPTION_BG="#1d1d1d", CAPTION_OPACITY=1.0, CAPTION_FG="#ffd60a",
    ),
}

NAME = os.environ.get("THEME", "brutalist")
if NAME not in PRESETS:
    raise SystemExit(f"Unknown THEME={NAME!r}; choose from {', '.join(PRESETS)}")
globals().update({"MONO_WEIGHT": "NORMAL", **PRESETS[NAME]})


# ---- Flow figures: colour = concept ------------------------------------------------------------------------------
# Figures map their own role names (e.g. "action", "state") to these slots in the spec (`data.roles`), so the same
# concept keeps the same colour across a figure. Each slot: fill, stroke, text. Light and dark variants are picked
# from the theme's background; text colours are chosen for >= 4.4:1 contrast on their fill.
_ROLES_LIGHT = {
    "neutral": ("#ffffff", "#111111", "#111111"),
    "c1": ("#fbe7a1", "#8a6500", "#111111"),   # yellow
    "c2": ("#ece0fb", "#6b3fd6", "#111111"),   # violet
    "c3": ("#d3ecdf", "#1e7a4f", "#111111"),   # green
    "c4": ("#d9e6f8", "#1f3fd6", "#111111"),   # blue
    "c5": ("#fde2d2", "#c93a00", "#111111"),   # orange
}
_ROLES_DARK = {
    "neutral": ("#1a1d24", "#8b93a1", "#e8eaed"),
    "c1": ("#3a3218", "#f2c94c", "#f5f5f5"),
    "c2": ("#2c2342", "#b99cf7", "#f5f5f5"),
    "c3": ("#18342a", "#6ee7b7", "#f5f5f5"),
    "c4": ("#1b2a44", "#7aa7ff", "#f5f5f5"),
    "c5": ("#3d2418", "#ff9a62", "#f5f5f5"),
}
# Packet kinds moving along rails.
PACKETS = {"request": "c4", "response": "c3", "change": "c2"}
GHOST = 0.15  # opacity of not-yet-revealed parts of a figure


def _is_dark(hex_color: str) -> bool:
    r, g, b = (int(hex_color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 < 0.5


ROLES = _ROLES_DARK if _is_dark(BG) else _ROLES_LIGHT  # noqa: F821 (BG comes from the preset above)
