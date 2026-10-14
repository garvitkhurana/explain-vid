"""Channel thumbnails: black, a cyan name, a white hook, and the scene told left to right, with the asker reacting.
Pure Pillow (Impact type, the cast sprite drawn pixel by pixel). An optional logo goes next to the name if
brand/logos/<key>.png exists (supplied by the owner; never fetched or redrawn here).
Make one: uv run python thumbs.py <Gemini|Muse> <out.png>   (from renderers/manim)
"""

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import cast as C
import skins

HERE = Path(__file__).parent
W, H = 1280, 720
IMPACT = "/System/Library/Fonts/Supplemental/Impact.ttf"
CYAN, WHITE, RED, ORG, GRN, INK = "#00e5ff", "#ffffff", "#e0473a", "#f8b08a", "#86dca5", "#1b1b1b"


def words(img, lines, x=60, y=70, maxw=560, logo=None):
    """Stacked lines top-left; the first line can carry a logo after it."""
    d = ImageDraw.Draw(img)
    for i, (text, col, size) in enumerate(lines):
        f = ImageFont.truetype(IMPACT, size)
        while d.textlength(text, font=f) > maxw:
            size -= 4
            f = ImageFont.truetype(IMPACT, size)
        _, top, _, bot = f.getbbox(text)
        d.text((x, y - top), text, font=f, fill=col)
        path = HERE / "brand" / "logos" / f"{logo}.png"
        if i == 0 and logo and path.exists():
            m = Image.open(path).convert("RGBA")
            h = int((bot - top) * 0.6)
            m = m.resize((int(m.width * h / m.height), h))
            img.paste(m, (int(x + d.textlength(text, font=f) + 24), int(y + (bot - top - h) / 2)), m)
        y += bot - top + 28


def wordmark(img, right, y, h=44):
    m = Image.open(HERE / "brand" / "wordmark_transparent.png").convert("RGBA")
    m = m.resize((int(m.width * h / m.height), h))
    img.paste(m, (right - m.width, y), m)


def asker(img, left, bottom, px, gaze=0):
    """The asker, shocked: mouth open, arms up."""
    a = C.Actor(skins.SKINS["office"]["roles"]["asker"], "asker", 1, [0, 0, 0], -1, [], [])
    pix = a.pixels("shrug", "open", True, gaze, 0)
    rows = max(r for _, r in pix) + 1
    d = ImageDraw.Draw(img)
    for (c, r), col in pix.items():
        x0, y0 = left + (c + 1) * px, bottom - (rows - r) * px
        d.rectangle([x0, y0, x0 + px - 1, y0 + px - 1], fill=str(col))


def shout(img, x, y, size=110):
    ImageDraw.Draw(img).text((x, y), "!", font=ImageFont.truetype(IMPACT, size), fill=CYAN)


def robot(img, x, y, s, bdx=1.5):
    """A blocky robot (torso centre x, y; s px per unit) that has just landed a bean bag on the board: 7/7."""
    d = ImageDraw.Draw(img)

    def rbox(cx, cy, w, h, fill):
        d.rounded_rectangle([cx - w * s / 2, cy - h * s / 2, cx + w * s / 2, cy + h * s / 2], radius=int(0.06 * s),
                            fill=fill, outline=INK, width=max(2, int(0.025 * s)))
    rbox(x - 0.2 * s, y + 0.75 * s, 0.22, 0.6, "#9e9e9e")
    rbox(x + 0.2 * s, y + 0.75 * s, 0.22, 0.6, "#9e9e9e")
    rbox(x, y, 0.8, 0.9, "#bfbfbf")
    rbox(x, y - 0.75 * s, 0.55, 0.45, "#d9d9d9")
    d.rounded_rectangle([x - 0.16 * s, y - 0.79 * s, x + 0.16 * s, y - 0.71 * s], radius=int(0.04 * s), fill=CYAN)
    ax0, ay0, ang, L, t = x + 0.3 * s, y - 0.15 * s, -0.4, 0.62 * s, 0.17 * s
    dx, dy, nx, ny = math.cos(ang), math.sin(ang), -math.sin(ang), math.cos(ang)
    d.polygon([(ax0 - nx * t / 2, ay0 - ny * t / 2), (ax0 + dx * L - nx * t / 2, ay0 + dy * L - ny * t / 2),
               (ax0 + dx * L + nx * t / 2, ay0 + dy * L + ny * t / 2), (ax0 + nx * t / 2, ay0 + ny * t / 2)],
              fill="#8e8e8e", outline=INK)
    hand = (ax0 + dx * L, ay0 + dy * L)
    bx, by = x + bdx * s, y + 0.95 * s
    d.polygon([(bx - 0.7 * s, by + 0.25 * s), (bx + 0.7 * s, by + 0.25 * s), (bx + 0.45 * s, by - 0.2 * s),
               (bx - 0.45 * s, by - 0.2 * s)], fill=ORG)
    hole = (bx, by - 0.02 * s)
    for i in range(0, 30, 2):  # dashed arc from hand to hole
        q = [(hand[0] + (hole[0] - hand[0]) * p, hand[1] + (hole[1] - hand[1]) * p - math.sin(math.pi * p) * 0.9 * s)
             for p in (i / 30, (i + 1) / 30)]
        d.line(q, fill="#bbbbbb", width=max(2, int(0.02 * s)))
    b = 0.09 * s
    d.rectangle([hole[0] - b, hole[1] - b, hole[0] + b, hole[1] + b], fill=RED, outline=INK)
    f = ImageFont.truetype(IMPACT, int(0.38 * s))
    d.text((bx - d.textlength("7/7", font=f) / 2, by + 0.35 * s), "7/7", font=f, fill=GRN)


def detour(img):
    """A path that meets a wall, goes around under it, and reaches the flag."""
    d = ImageDraw.Draw(img)
    pts = [(650, 260), (740, 260), (770, 330), (790, 450), (850, 520), (910, 450), (930, 330), (960, 260), (1020, 260)]
    smooth = []
    for i in range(len(pts) - 1):  # Catmull-Rom through the points
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, len(pts) - 1)]
        for k in range(12):
            u = k / 12
            smooth.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * u + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * u * u
                                       + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * u ** 3) for j in (0, 1)))
    smooth.append(pts[-1])
    d.line(smooth, fill=GRN, width=12, joint="curve")
    d.rectangle([828, 140, 872, 420], fill=RED)
    d.ellipse([638, 248, 662, 272], fill=WHITE)
    d.ellipse([996, 236, 1044, 284], fill=CYAN)
    d.line([(1070, 170), (1070, 340)], fill=WHITE, width=8)
    d.polygon([(1070, 170), (1150, 200), (1070, 230)], fill=CYAN)


def Gemini():
    img = Image.new("RGB", (W, H), "#000000")
    words(img, [("GEMINI", CYAN, 190), ("7 SHOTS", WHITE, 170), ("IN A ROW", WHITE, 170)], logo="gemini")
    robot(img, 710, 365, 125)
    asker(img, 1005, 722, 19, gaze=-1)
    shout(img, 985, 330)
    wordmark(img, 1240, 30)
    return img


def Muse():
    img = Image.new("RGB", (W, H), "#000000")
    words(img, [("META'S AI", CYAN, 190), ("WON'T", WHITE, 170), ("QUIT", WHITE, 170)], logo="meta")
    detour(img)
    asker(img, 1005, 722, 19, gaze=-1)
    shout(img, 975, 400)
    wordmark(img, 1240, 30)
    return img


if __name__ == "__main__":
    {"Gemini": Gemini, "Muse": Muse}[sys.argv[1]]().save(sys.argv[2])
