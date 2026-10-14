"""Channel kit for one-shot videos: each video is one bespoke Manim file (oneshot_<video>.py) on top of this.
Here: the house look (board, palette, hand font), timing from the narration, captions, the corner asker, the title
room, the interview cut and the end card. Everything a video shows in between is drawn fresh in its own file.

A video file defines `class Video(OneShot)` with `VIDEO = "<video>"` and one method per scene id (same ids as its
spec). Render with ./scripts/oneshot.sh <video>; ONE=<scene id> renders that scene alone (frame-exact, so scenes
render in parallel and concatenate).
"""

import json
import os
from pathlib import Path

from manim import (
    DOWN, LEFT, ORIGIN, RIGHT, UP, FadeIn, FadeOut, Group, ImageMobject, Line, Rectangle, RoundedRectangle, Scene,
    Text, VGroup, config,
)

import cast as C
import skins

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
SKIN = skins.SKINS["office"]
BRAND = json.loads((HERE / "brand" / "brand.json").read_text())

BOARD, INK, MUTED, RED = "#f7f5ee", "#1b1b1b", "#555555", "#b03a2e"
YEL, VIO, GRN, BLU, ORG = "#f9d65c", "#c9b0f7", "#86dca5", "#9cc2f7", "#f8b08a"
WHITE = "#ffffff"
HAND, MONO = "Chalkboard SE", "Menlo"
FPS = 30
config.background_color = BOARD
config.frame_rate = FPS


def t(s, size=40, color=INK, font=HAND, bold=True):
    k = 1 if font == MONO else 8  # lay out big and scale down: small proportional text spaces evenly
    w = config.pixel_width
    config.pixel_width = w * k
    try:
        m = Text(s, font=font, font_size=size * 0.75 * k, color=color, weight="BOLD" if bold else "NORMAL")
    finally:
        config.pixel_width = w
    return m.scale(1 / k)


def box(w, h, fill, stroke=INK, r=0.18, sw=3):
    return RoundedRectangle(corner_radius=r, width=w, height=h, fill_color=fill, fill_opacity=1, stroke_color=stroke,
                            stroke_width=sw)


def chip(label, fill, size=32, font=HAND, pad=0.3):
    l = t(label, size, font=font)
    b = box(l.width + 2 * pad, l.height + 0.45, fill)
    return VGroup(b, l.move_to(b))


def cross(m, color=RED):
    c = m.get_center()
    w, h = m.width / 2 + 0.15, m.height / 2 + 0.15
    return VGroup(Line(c + [-w, -h, 0], c + [w, h, 0], color=color, stroke_width=12),
                  Line(c + [-w, h, 0], c + [w, -h, 0], color=color, stroke_width=12))


def wordmark(height):
    return ImageMobject(str(HERE / "brand" / BRAND["wordmark"])).set(height=height)


class OneShot(Scene):
    VIDEO = ""
    ROOMS = ("title", "interview")  # scenes with their own set; the asker talks from the corner everywhere else

    # ---- timeline ---------------------------------------------------------------------------------------------
    def setup(self):
        voice = ROOT / "out" / self.VIDEO / "voice"
        timing = json.loads((voice / "timing.json").read_text())
        self.SCN, self.TOTAL = timing["scenes"], timing["total"]
        self.WORDS = json.loads((voice / "words.json").read_text())
        self.only = os.environ.get("ONE")
        self.t0 = self.SCN[self.only]["start"] if self.only else 0.0

    def now(self):
        """Seconds on the video's timeline (a scene rendered alone starts at its own start)."""
        return self.t0 + self.time

    def at(self, sid, rel):
        """Wait until `rel` seconds into scene `sid`."""
        target = self.SCN[sid]["start"] + rel
        if target - self.now() > 1 / FPS:
            self.wait(target - self.now())

    def line(self, sid, i, frac=0.0):
        """Wait until `frac` of the way through sentence `i` of scene `sid`."""
        l = self.SCN[sid]["lines"][i]
        self.at(sid, l["start"] + frac * (l["end"] - l["start"]))

    def end(self, sid):
        """Hold until 0.3 s before the cut, then fade the board (keeps captions and the corner asker)."""
        self.at(sid, self.SCN[sid]["frames"] / FPS - 0.3)
        gone = [m for m in self.mobjects if m not in self.persist]
        if gone:
            self.play(*[FadeOut(m) for m in gone], run_time=0.3)
        for m in gone:
            self.remove(m)

    def lines_of(self, sid):
        """Spoken lines of a scene as (who, abs start, abs end, [(word, abs s, abs e)])."""
        s0, out = self.SCN[sid]["start"], []
        rows = self.WORDS.get(sid, [])
        for i, l in enumerate(self.SCN[sid].get("lines", [])):
            ws = rows[i]["words"] if i < len(rows) else []
            out.append((l["who"], s0 + l["start"], s0 + l["end"],
                        [(w["w"].lower(), s0 + w["start"], s0 + w["end"]) for w in ws]))
        return out

    # ---- run --------------------------------------------------------------------------------------------------
    def construct(self):
        self.persist = []
        ids = [self.only] if self.only else list(self.SCN)
        self.captions(ids)
        self.corner_asker(ids)
        for sid in ids:
            self.at(sid, 0)
            getattr(self, sid)(sid)
        last = ids[-1]
        stop = self.SCN[last]["start"] + self.SCN[last]["frames"] / FPS
        if stop - self.now() > 0.5 / FPS:
            self.wait(stop - self.now() - 0.5 / FPS)

    def captions(self, ids):
        """Every caption cue, coloured by speaker, shown only while its words are spoken."""
        for sid in ids:
            sc = self.SCN[sid]
            for c in sc["cues"]:
                col = SKIN["roles"][c.get("who", "explainer")]["caption"]
                txt = t(c["text"], 34, col)
                if txt.width > 13.4:
                    txt.scale_to_fit_width(13.4)
                bg = Rectangle(width=txt.width + 0.4, height=txt.height + 0.3, fill_color=INK, fill_opacity=1,
                               stroke_width=0).move_to(txt)
                cap = VGroup(bg, txt).to_edge(DOWN, buff=0.55).set_z_index(20).set_opacity(0)
                a, b = sc["start"] + c["start"], sc["start"] + c["end"]
                cap.add_updater(lambda m, dt, a=a, b=b: m.set_opacity(1 if a <= self.now() < b else 0))
                self.add(cap)
                self.persist.append(cap)

    def corner_asker(self, ids):
        """The asker slides up in the bottom-right corner for their lines in board scenes."""
        lines = [(a, b, w) for sid in ids if sid not in self.ROOMS
                 for who, a, b, w in self.lines_of(sid) if who == "asker"]
        if not lines:
            return
        px = C.CORNER_PX
        up_y, down_y = -3.45, -4.0 - 16 * px - 0.3
        corner = C.Actor(SKIN["roles"]["asker"], "asker", px, [6.55, down_y, 0], -1, lines, [])
        spans = [(a, b) for a, b, _ in lines]

        def slide(m, dt=0):
            now = self.now()
            k = max([min(1.0, max(0.0, (now - a + 0.3) / 0.3), max(0.0, (b + 0.3 - now) / 0.3)) for a, b in spans])
            k = k * k * (3 - 2 * k)
            m.move_to([6.55, down_y + (up_y - down_y) * k, 0])
        corner.feet.add_updater(slide)
        mob = corner.attach(self.now).set_z_index(15)
        self.persist += [corner.feet, mob]
        self.add(corner.feet, mob)

    # ---- house sets -------------------------------------------------------------------------------------------
    def title_room(self, sid):
        """The wide office shot with both cast members and the wordmark; returns the room (draw on its board)."""
        z = C.BOARD_ZOOM
        room, feet = C.board_set(SKIN, "office")
        room.scale(1 / z, about_point=ORIGIN)
        actors = []
        for role, (x, f) in zip(("explainer", "asker"), ((feet[0][0] / z, 1), (feet[1][0] / z, -1))):
            mine = [(a, b, w) for who, a, b, w in self.lines_of(sid) if who == role]
            a = C.Actor(SKIN["roles"][role], role, C.BOARD_PX / z, [x, C.FLOOR_Y / z, 0], f, mine, [])
            actors += [a.feet, a.attach(self.now)]
        mark = wordmark(0.5).move_to([0, 2.5, 0])
        self.add(room, *actors)
        self.play(FadeIn(mark), run_time=0.3)
        return room

    def interview(self, sid):
        """The asker to camera with a lower third, a little hop on each line."""
        back, desk, feet = C.interview_set(SKIN, "office")
        mine = [(a, b, w) for who, a, b, w in self.lines_of(sid) if who == "asker"]
        a = C.Actor(SKIN["roles"]["asker"], "asker", C.INTERVIEW_PX, feet, 1, mine, [])
        m = a.attach(self.now)
        card = C.lower_third(lambda s, size, color, weight=None: t(s, size, color), SKIN["roles"]["asker"], 0.9,
                             -1.35, SKIN["set"]["accent"])
        self.add(back, a.feet, m, desk)
        self.play(FadeIn(card, shift=RIGHT * 0.3), run_time=0.4)
        for i in range(len(mine)):
            self.line(sid, i, 0.1)
            self.play(a.feet.animate.shift(UP * a.px), run_time=0.15)
            self.play(a.feet.animate.shift(DOWN * a.px), run_time=0.15)
        self.end(sid)

    def source(self, sid):
        """End card: where to read the original, then the channel."""
        url = json.loads((ROOT / "video-specs" / self.VIDEO / "spec.json").read_text())["meta"]["source"]["url"]
        url = url.split("://", 1)[-1].removeprefix("www.").rstrip("/")
        h = t("Read the full post at", 64)
        u = t(url, 30, RED, font=MONO)
        if u.width > 13:
            u.scale_to_fit_width(13)
        u.next_to(h, DOWN, buff=0.4)
        mark = wordmark(0.8).next_to(u, DOWN, buff=0.8)
        handle = t(BRAND["handle"], 30, MUTED, font=MONO).next_to(mark, DOWN, buff=0.2)
        Group(h, u, mark, handle).move_to([0, 0.6, 0])
        self.play(FadeIn(h, shift=UP * 0.2), run_time=0.35)
        self.play(FadeIn(u), run_time=0.35)
        self.play(FadeIn(mark), FadeIn(handle), run_time=0.35)
