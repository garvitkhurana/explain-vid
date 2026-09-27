# Visual presets. Pick with THEME=<name> (default: brutalist, chosen 2026-09-27).
# midnight mirrors renderers/remotion/src/theme.ts; render_all.sh uses it for the stack comparison.
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
