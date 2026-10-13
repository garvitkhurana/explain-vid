"""Cast kit: pixel characters, their poses and mouths, and the sets they stand in. Data lives in skins.py.

A character's look at any moment is a small state (pose, mouth, eyes, gaze, head bob), so an Actor redraws only when
that state changes. Pixels of one colour are merged into runs and drawn as one shape, which keeps a frame cheap.
Board shots zoom the camera out by BOARD_ZOOM so the scene template lands on the set's board with the cast either side.
"""

import math
import re
import zlib
from functools import lru_cache

import numpy as np

from manim import DOWN, LEFT, RIGHT, UP, Dot, Rectangle, VGroup, VMobject

BOARD_ZOOM = 1.7
BOARD = dict(x=0.0, y=0.55, w=14.7, h=7.3)  # the board, in the template's own frame coordinates
FLOOR_Y = -4.5                               # board-shot feet: just above the caption band once zoomed out
BOARD_PX = 0.30                              # one sprite pixel in board shots
INTERVIEW_PX = 0.42
DARK_MOUTH, LIP, TONGUE, EYE = "#4a1414", "#9a5a48", "#c0504d", "#1a1a1a"

MOUTHS = {
    "closed": {(4, 5): LIP, (5, 5): LIP, (6, 5): LIP, (7, 5): LIP},  # a lip line, not a dark gap: reads as shut
    "mid": {(4, 5): DARK_MOUTH, (5, 5): DARK_MOUTH, (6, 5): DARK_MOUTH, (7, 5): DARK_MOUTH, (5, 6): DARK_MOUTH,
            (6, 6): DARK_MOUTH},
    "open": {(4, 5): DARK_MOUTH, (5, 5): DARK_MOUTH, (6, 5): DARK_MOUTH, (7, 5): DARK_MOUTH, (4, 6): DARK_MOUTH,
             (5, 6): TONGUE, (6, 6): TONGUE, (7, 6): DARK_MOUTH},
    "oo": {(5, 5): DARK_MOUTH, (6, 5): DARK_MOUTH, (5, 6): DARK_MOUTH, (6, 6): DARK_MOUTH},
}
ACTS = {"point": 1.6, "shrug": 1.4, "facepalm": 1.8, "look_camera": 1.8, "nod": 0.8, "level_up": 2.2}


def blocks(pix, px, x0, y0):
    """Pixels {(col, row): colour} as one filled shape per colour; (x0, y0) is the top-left of pixel (0, 0)."""
    out = VGroup()
    by_colour = {}
    for (c, r), col in pix.items():
        by_colour.setdefault(col, {}).setdefault(r, []).append(c)
    for col, rows in by_colour.items():
        vm = VMobject(fill_color=col, fill_opacity=1, stroke_color=col, stroke_width=1)
        for r, cs in rows.items():
            cs.sort()
            start = prev = cs[0]
            for c in cs[1:] + [None]:
                if c is not None and c == prev + 1:
                    prev = c
                    continue
                left, right, top = x0 + start * px, x0 + (prev + 1) * px, y0 - r * px
                vm.start_new_path(np.array([left, top, 0.0]))
                for p in ([right, top, 0], [right, top - px, 0], [left, top - px, 0], [left, top, 0]):
                    vm.add_line_to(np.array(p, dtype=float))
                if c is not None:
                    start = prev = c
        out.add(vm)
    return out


def words_of(text):
    return re.findall(r"[a-z0-9']+", text.lower())


class Actor:
    """One cast member in one scene. `facing` +1 looks right, -1 left; `lines` [(start, end, [(word, s, e)])] are the
    sentences this character speaks (scene-relative seconds); `acts` [(start, do)]."""

    def __init__(self, char, role, px, feet, facing, lines, acts):
        self.char, self.role, self.px, self.facing = char, role, px, facing
        self.feet = Dot(feet, radius=0.001).set_opacity(0)  # animate this to move the actor (a bob, a hop)
        self.lines, self.acts = lines, sorted(acts)
        self.skin = char["pal"].get("s", "#f2c6a5")
        self.arm = char["pal"].get(char["rows"][8][0], self.skin)
        seed = zlib.crc32(role.encode())
        self.blink_every, self.blink_at = 3.1 + (seed % 9) * 0.17, (seed % 13) * 0.21
        self.state = None
        self.mob = self.draw(*self.state_at(0.0))

    # ---- what the character looks like at time t -------------------------------------------------------------
    def mouth_at(self, t):
        for s, e, words in self.lines:
            if not s <= t < e:
                continue
            for w, ws, we in words:
                if ws <= t < we:
                    groups = re.findall(r"[aeiouy]+", w) or ["a"]
                    phase = (t - ws) / max(we - ws, 1e-3) * len(groups)
                    k = min(int(phase), len(groups) - 1)
                    f = phase - int(phase)
                    o = math.sin(math.pi * f)
                    if o > 0.55:
                        return "oo" if re.search(r"[ouw]", groups[k]) and "a" not in groups[k] else "open"
                    return "mid" if o > 0.2 else "closed"
            return "closed"
        return None  # not speaking

    def state_at(self, t):
        mouth = self.mouth_at(t)
        speaking = mouth is not None
        mouth = mouth or "closed"
        eyes = (t + self.blink_at) % self.blink_every >= 0.13
        gaze = 0 if speaking else self.facing
        pose, dy = "idle", 0
        for start, do in self.acts:
            if start <= t < start + ACTS[do]:
                if do in ("point", "shrug", "facepalm"):
                    pose = do
                elif do == "look_camera":
                    gaze = 0
                elif do == "nod":
                    dy = 1 if int((t - start) / 0.2) % 2 == 0 else 0
        return pose, mouth, eyes, gaze, dy

    # ---- drawing --------------------------------------------------------------------------------------------
    def pixels(self, pose, mouth, eyes, gaze, dy):
        pal, pix = self.char["pal"], {}
        for r, row in enumerate(self.char["rows"]):
            for c, ch in enumerate(row):
                if ch == ".":
                    continue
                col = self.skin if ch in "em" else pal[ch]
                pix[(c, r + dy if r <= 6 else r)] = col
        for c, r in [(c, r) for r, row in enumerate(self.char["rows"]) for c, ch in enumerate(row) if ch == "e"]:
            if eyes:
                pix[(c + gaze, r + dy)] = EYE
        for (c, r), col in MOUTHS[mouth].items():
            pix[(c, r + dy)] = col
        side = 11 if self.facing > 0 else 0
        f = self.facing
        if pose == "point":
            pix.pop((side, 10), None)
            for i in (1, 2, 3):
                pix[(side + f * i, 8)] = self.arm
            pix[(side + f * 4, 8)] = self.skin
        elif pose == "shrug":
            for s in (0, 11):
                pix.pop((s, 10), None)
            for s, o in ((0, -1), (11, 12)):
                pix[(o, 8)], pix[(o, 7)] = self.arm, self.skin
        elif pose == "facepalm":
            pix.pop((side, 10), None)
            for c, r in ((side, 8), (side, 7), (side - f, 6)):
                pix[(c, r)] = self.arm
            for c in range(4, 9):
                for r in (3, 4):
                    pix[(c if f > 0 else 11 - c, r + dy)] = self.skin
        return pix

    @lru_cache(maxsize=256)
    def draw(self, pose, mouth, eyes, gaze, dy):
        return blocks(self.pixels(pose, mouth, eyes, gaze, dy), self.px, -6 * self.px, 16 * self.px)

    def head_top(self):
        return self.feet.get_center()[1] + 16 * self.px

    def attach(self, clock):
        """Redraw from `clock()` (scene-relative seconds) whenever the look changes; follow the feet marker."""
        m = self.mob.copy().shift(self.feet.get_center())
        m.last = (self.state_at(0.0), tuple(self.feet.get_center()))

        def update(mob, dt):
            key = (self.state_at(clock()), tuple(self.feet.get_center()))
            if key != mob.last:
                mob.become(self.draw(*key[0]).copy().shift(self.feet.get_center()))
                mob.last = key
        m.add_updater(update)
        return m


def name_tag(text_fn, label, x, y, size=22):
    t = text_fn(label, size, "#412402")
    bg = Rectangle(width=t.width + 0.36, height=t.height + 0.26, fill_color="#fac775", fill_opacity=1,
                   stroke_color="#412402", stroke_width=2).move_to([x, y, 0])
    return VGroup(bg, t.move_to(bg))


def level_up(text_fn, x, y):
    t = text_fn("LEVEL UP!", 30, "#fac775", "BOLD")
    back = Rectangle(width=t.width + 0.3, height=t.height + 0.2, fill_color="#26215c", fill_opacity=1,
                     stroke_width=0)
    g = VGroup(back, t)
    g.move_to([x, y, 0])
    for dx, dy in ((-1.1, 0.4), (1.2, 0.3), (-0.9, -0.4), (1.0, -0.5)):
        g.add(Rectangle(width=0.14, height=0.14, fill_color="#fac775", fill_opacity=1, stroke_width=0)
              .move_to([x + dx * (t.width / 2 + 0.3) / 1.1, y + dy, 0]))
    return g


def lower_third(text_fn, char, x, y, accent, label=None):
    """Name card for an interview: the character's name, and under it what they stand for in this video, if given."""
    name = text_fn(char["name"], 40, "#111111", "BOLD")
    title = text_fn(label, 26, "#444441") if label else VGroup()
    w = max(name.width, title.width) + 0.8
    card = Rectangle(width=w, height=name.height + (title.height + 0.14 if label else 0) + 0.46, fill_color="#f7f5ee",
                     fill_opacity=1, stroke_color="#111111", stroke_width=4)
    bar = Rectangle(width=0.22, height=card.height, fill_color=accent, fill_opacity=1, stroke_width=0)
    g = VGroup(card, bar)
    g.move_to([x + w / 2, y, 0])
    bar.align_to(card, LEFT)
    name.next_to(card.get_corner(UP + LEFT), DOWN + RIGHT, buff=0).shift(RIGHT * 0.45 + DOWN * 0.22)
    if label:
        title.next_to(name, DOWN, buff=0.14, aligned_edge=LEFT)
    return VGroup(g, name, title)


def rect(x0, y0, x1, y1, col):
    return Rectangle(width=x1 - x0, height=y1 - y0, fill_color=col, fill_opacity=1, stroke_width=0).move_to(
        [(x0 + x1) / 2, (y0 + y1) / 2, 0])


def board_set(skin, name):
    """Background for a board shot, in world coordinates with the camera zoomed out by BOARD_ZOOM around the origin.
    Returns (backdrop, [left feet, right feet])."""
    s, W, H = skin["set"], 7.12 * BOARD_ZOOM + 0.1, 4.0 * BOARD_ZOOM + 0.1
    b = BOARD
    g = VGroup(rect(-W, -H, W, H, s["wall"]))
    if name == "rpg":
        mortar = VMobject(fill_color=s["mortar"], fill_opacity=1, stroke_width=0)
        y, k = -H, 0
        while y < H:
            mortar.start_new_path(np.array([-W, y, 0.0]))
            for p in ([W, y, 0], [W, y + 0.06, 0], [-W, y + 0.06, 0], [-W, y, 0]):
                mortar.add_line_to(np.array(p, dtype=float))
            x = -W + (k % 2) * 0.55
            while x < W:
                mortar.start_new_path(np.array([x, y, 0.0]))
                for p in ([x + 0.06, y, 0], [x + 0.06, y + 0.55, 0], [x, y + 0.55, 0], [x, y, 0]):
                    mortar.add_line_to(np.array(p, dtype=float))
                x += 1.1
            y, k = y + 0.55, k + 1
        g.add(mortar, rect(-W, -H, W, FLOOR_Y + 0.1, s["floor"]))
        for x in (-10.4, 10.4):  # torches, above the cast's heads
            g.add(rect(x - 0.1, 2.2, x + 0.1, 2.9, "#6b4423"), rect(x - 0.22, 2.9, x + 0.22, 3.35, s["flame"]),
                  rect(x - 0.1, 3.0, x + 0.1, 3.5, s["flame_core"]))
        frame_w = 0.35
    else:
        g.add(rect(-W, -H, W, -2.6, s["wainscot"]), rect(-W, -2.66, W, -2.56, s["accent"]),
              rect(-W, -H, W, FLOOR_Y + 0.1, s["floor"]))
        for x in (-7.0, 0.0, 7.0):  # ceiling lights
            g.add(rect(x - 1.4, 6.35, x + 1.4, 6.6, "#fbfaf6"))
        g.add(rect(-11.7, 1.4, -8.6, 5.6, s["frame"]), rect(-11.55, 1.55, -8.75, 5.45, s["window"]))
        for y in [1.75 + 0.3 * i for i in range(13)]:
            g.add(rect(-11.55, y, -8.75, y + 0.12, s["blind"]))
        g.add(rect(8.9, 2.0, 11.1, 4.6, "#444441"), rect(9.05, 2.15, 10.95, 4.45, "#b5d4f4"),
              rect(9.05, 2.15, 10.95, 2.9, "#3b6d11"), rect(9.7, 2.9, 10.3, 3.6, "#888780"))
        frame_w = 0.2
    g.add(rect(b["x"] - b["w"] / 2 - frame_w, b["y"] - b["h"] / 2 - frame_w, b["x"] + b["w"] / 2 + frame_w,
               b["y"] + b["h"] / 2 + frame_w, s["frame"]),
          rect(b["x"] - b["w"] / 2, b["y"] - b["h"] / 2, b["x"] + b["w"] / 2, b["y"] + b["h"] / 2, s["board"]))
    if name == "rpg":
        for cx, cy in ((-1, 1), (1, 1), (-1, -1), (1, -1)):  # quest-board pins
            px, py = b["x"] + cx * (b["w"] / 2 - 0.25), b["y"] + cy * (b["h"] / 2 - 0.25)
            g.add(rect(px - 0.1, py - 0.1, px + 0.1, py + 0.1, "#a32d2d"))
    else:
        g.add(rect(-2.0, b["y"] - b["h"] / 2 - 0.34, 2.0, b["y"] - b["h"] / 2 - 0.2, s["frame"]))  # marker tray
    edge = b["w"] / 2 + 0.25 + 6 * BOARD_PX
    return g, [[-edge - 0.2, FLOOR_Y, 0], [edge + 0.2, FLOOR_Y, 0]]


def interview_set(skin, name):
    """Backdrop and desk for a talking-head shot (camera not zoomed). Returns (backdrop, desk, feet)."""
    s = skin["set"]
    g = VGroup(rect(-7.2, -4.1, 7.2, 4.1, s["wall"]))
    if name == "rpg":
        for y in [-4.0 + 0.55 * i for i in range(16)]:
            g.add(rect(-7.2, y, 7.2, y + 0.06, s["mortar"]))
        g.add(rect(1.4, 0.6, 5.6, 3.6, s["frame"]), rect(1.6, 0.8, 5.4, 3.4, s["window"]))
        for x, y in ((2.2, 2.9), (3.1, 1.6), (4.6, 2.5), (5.0, 1.2)):
            g.add(rect(x, y, x + 0.1, y + 0.1, "#fac775"))
    else:
        g.add(rect(-7.2, -4.1, 7.2, -1.0, s["wainscot"]), rect(-7.2, -1.06, 7.2, -0.96, s["accent"]),
              rect(1.4, 0.4, 5.8, 3.6, s["frame"]), rect(1.6, 0.6, 5.6, 3.4, s["window"]))
        for y in [0.8 + 0.28 * i for i in range(10)]:
            g.add(rect(1.6, y, 5.6, y + 0.1, s["blind"]))
    desk = VGroup(rect(-7.2, -4.1, 7.2, -2.3, s["desk"]), rect(-7.2, -2.45, 7.2, -2.2, s["desk_top"]))
    if name == "rpg":
        desk.add(rect(6.2, -2.2, 6.5, -1.5, "#efe3c4"), rect(6.28, -1.5, 6.42, -1.2, s["flame"]))
    else:
        desk.add(rect(5.9, -2.2, 6.6, -1.5, "#f1efe8"), rect(6.6, -2.05, 6.75, -1.7, "#f1efe8"))  # a mug
    return g, desk, [-3.0, -2.3 - 4 * INTERVIEW_PX, 0]
