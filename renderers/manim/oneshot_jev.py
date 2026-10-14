"""Bake-off: the Jev video written as one bespoke Manim scene (no templates, no spec data fields).
Same narration, voice, timing, captions, cast and wordmark as the template cut; only the visuals differ.
Usage (from renderers/manim): uv run manim -qh oneshot_jev.py OneShot   (needs out/jev/voice from the template render)
"""

import json
from pathlib import Path

import numpy as np
from manim import (
    DOWN, LEFT, RIGHT, UP, ORIGIN, Arrow, Circle, Create, Dot, FadeIn, FadeOut, GrowFromCenter, Group, ImageMobject,
    Line, MoveAlongPath, Polygon, Rectangle, RoundedRectangle, Scene, Text, Transform, ValueTracker, VGroup, Write,
    config, linear, rate_functions, Indicate, DashedLine, always_redraw, Flash,
)

import cast as C
import skins

ROOT = Path(__file__).resolve().parents[2]
VOICE = ROOT / "out" / "jev" / "voice"
TIMING = json.loads((VOICE / "timing.json").read_text())
SCN, TOTAL = TIMING["scenes"], TIMING["total"]
WORDS = json.loads((VOICE / "words.json").read_text())
SKIN = skins.SKINS["office"]
HERE = Path(__file__).parent
BRAND = json.loads((HERE / "brand" / "brand.json").read_text())

BOARD, INK, MUTED, RED = "#f7f5ee", "#1b1b1b", "#555555", "#b03a2e"
YEL, VIO, GRN, BLU, ORG = "#f9d65c", "#c9b0f7", "#86dca5", "#9cc2f7", "#f8b08a"
HAND, MONO = "Chalkboard SE", "Menlo"
config.background_color = BOARD
config.frame_rate = 30


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


def lines_of(sid):
    """Spoken lines of a scene as (who, abs start, abs end, [(word, abs s, abs e)])."""
    s0, out = SCN[sid]["start"], []
    for i, l in enumerate(SCN[sid].get("lines", [])):
        ws = WORDS.get(sid, [])[i]["words"] if i < len(WORDS.get(sid, [])) else []
        out.append((l["who"], s0 + l["start"], s0 + l["end"], [(w["w"].lower(), s0 + w["start"], s0 + w["end"]) for w in ws]))
    return out


class OneShot(Scene):
    def at(self, sid, rel):
        """Wait until `rel` seconds into scene `sid` (absolute timeline shared with the voice track)."""
        target = SCN[sid]["start"] + rel
        if target - self.time > 1 / 30:
            self.wait(target - self.time)

    def line(self, sid, i, frac=0.0):
        l = SCN[sid]["lines"][i]
        self.at(sid, l["start"] + frac * (l["end"] - l["start"]))

    def clear(self, keep=()):
        gone = [m for m in self.mobjects if m not in self.persist and m not in keep]
        if gone:
            self.play(*[FadeOut(m) for m in gone], run_time=0.3)

    def construct(self):
        clock = lambda: self.time
        self.persist = []
        # Captions (whole video), coloured by speaker like the template cut.
        for sid, sc in SCN.items():
            for c in sc["cues"]:
                col = SKIN["roles"][c.get("who", "explainer")]["caption"]
                txt = t(c["text"], 34, col)
                if txt.width > 13.4:
                    txt.scale_to_fit_width(13.4)
                bg = Rectangle(width=txt.width + 0.4, height=txt.height + 0.3, fill_color=INK, fill_opacity=1,
                               stroke_width=0).move_to(txt)
                cap = VGroup(bg, txt).to_edge(DOWN, buff=0.55).set_z_index(20).set_opacity(0)
                a, b = sc["start"] + c["start"], sc["start"] + c["end"]
                cap.add_updater(lambda m, dt, a=a, b=b: m.set_opacity(1 if a <= self.time < b else 0))
                self.add(cap)
                self.persist.append(cap)
        # The asker pops up in the bottom-right corner for his lines in board scenes (same device as the template cut).
        asker_lines = [(a, b, w) for sid in ("call", "trust") for who, a, b, w in lines_of(sid) if who == "asker"]
        px = 0.135
        up_y, down_y = -3.45, -4.0 - 16 * px - 0.3
        corner = C.Actor(SKIN["roles"]["asker"], "asker", px, [6.55, down_y, 0], -1, asker_lines, [])
        spans = [(a, b) for a, b, _ in asker_lines]

        def slide(m, dt=0):
            k = max([min(1.0, max(0.0, (self.time - a + 0.3) / 0.3), max(0.0, (b + 0.3 - self.time) / 0.3))
                     for a, b in spans] or [0.0])
            k = k * k * (3 - 2 * k)
            m.move_to([6.55, down_y + (up_y - down_y) * k, 0])
        corner.feet.add_updater(slide)
        corner_mob = corner.attach(clock).set_z_index(15)
        self.persist += [corner.feet, corner_mob]
        self.add(corner.feet, corner_mob)

        self.title()
        self.systems()
        self.call()
        self.numbers()
        self.interview()
        self.trust()
        self.source()
        if TOTAL - self.time > 1 / 30:
            self.wait(TOTAL - self.time - 0.5 / 30)

    # ---- 1. hook: not a chatbot -------------------------------------------------------------------------------
    def title(self):
        sid, z = "title", C.BOARD_ZOOM
        room, feet = C.board_set(SKIN, "office")
        room.scale(1 / z, about_point=ORIGIN)
        actors = []
        for role, (x, f) in zip(("explainer", "asker"), ((feet[0][0] / z, 1), (feet[1][0] / z, -1))):
            mine = [(a, b, w) for who, a, b, w in lines_of(sid) if who == role]
            a = C.Actor(SKIN["roles"][role], role, C.BOARD_PX / z, [x, C.FLOOR_Y / z, 0], f, mine, [])
            actors += [a.feet, a.attach(lambda: self.time)]
        mark = ImageMobject(str(HERE / "brand" / BRAND["wordmark"])).set(height=0.5).move_to([0, 2.5, 0])
        self.add(room, *actors)
        self.play(FadeIn(mark), run_time=0.3)
        # "Great, another chatbot?": a chat bubble types itself out
        bubble = box(4.2, 1.3, "#ffffff", r=0.5).move_to([0, 0.7, 0])
        tail = Polygon([-0.6, -0.6, 0], [-0.2, -0.6, 0], [-0.9, -1.1, 0], fill_color="#ffffff", fill_opacity=1,
                       stroke_color=INK, stroke_width=3).shift(bubble.get_center() + [0, -0.05, 0])
        dots = VGroup(*[Dot(radius=0.12, color=MUTED) for _ in range(3)]).arrange(RIGHT, buff=0.3).move_to(bubble)
        self.line(sid, 0)
        self.play(GrowFromCenter(VGroup(bubble, tail)), FadeIn(dots), run_time=0.4)
        for _ in range(2):
            self.play(*[d.animate(rate_func=rate_functions.there_and_back).shift(UP * 0.15) for d in dots],
                      lag_ratio=0.2, run_time=0.5)
        # "No. Jev is a System One model: it makes decisions, not conversation."
        self.line(sid, 1)
        x = cross(bubble)
        self.play(Create(x), run_time=0.35)
        name = t("Jev", 120, RED).move_to([0, 0.95, 0])
        sub = t("decisions, not conversation", 34).next_to(name, DOWN, buff=0.15)
        self.play(FadeOut(VGroup(bubble, tail, dots, x)), FadeIn(name, scale=0.6), run_time=0.45)
        self.play(FadeIn(sub, shift=UP * 0.15), run_time=0.35)
        self.line(sid, 1, 0.55)
        yes, no = chip("yes", GRN, 30), chip("no", ORG, 30)
        VGroup(yes, no).arrange(RIGHT, buff=0.4).next_to(sub, DOWN, buff=0.3)
        self.play(FadeIn(yes, shift=UP * 0.1), FadeIn(no, shift=UP * 0.1), run_time=0.3)
        self.play(Indicate(yes, color=GRN, scale_factor=1.2), run_time=0.6)
        self.at(sid, SCN[sid]["frames"] / 30 - 0.3)
        self.play(*[FadeOut(m) for m in self.mobjects if m not in self.persist], run_time=0.3)

    # ---- 2. Kahneman: fast lane vs slow lane --------------------------------------------------------------------
    def systems(self):
        sid = "systems"
        head = t("Kahneman's two modes of thinking", 46).to_edge(UP, buff=0.5)
        self.line(sid, 0)
        self.play(Write(head), run_time=0.8)
        lanes = VGroup()
        for y, name, sub, col in ((1.2, "System 1", "fast, intuitive", GRN), (-1.0, "System 2", "slow, deliberate", VIO)):
            tag = chip(name, col, 34).move_to([-4.9, y, 0])
            s = t(sub, 24, MUTED, bold=False).next_to(tag, DOWN, buff=0.12)
            track = DashedLine([-3.2, y, 0], [5.6, y, 0], color=MUTED, dash_length=0.15)
            lanes.add(VGroup(tag, s, track))
        self.line(sid, 0, 0.6)
        self.play(FadeIn(lanes[0], shift=RIGHT * 0.3), FadeIn(lanes[1], shift=RIGHT * 0.3), run_time=0.5)
        # "System one is fast and intuitive. That's Jev." — a bolt zips across, Jev lands in lane 1
        self.line(sid, 1)
        bolt = Polygon([0, 0.35, 0], [-0.18, 0.0, 0], [0.02, 0.0, 0], [-0.1, -0.35, 0], [0.2, 0.06, 0], [0.0, 0.06, 0],
                       fill_color=YEL, fill_opacity=1, stroke_color=INK, stroke_width=2).scale(1.3).move_to([-3.0, 1.2, 0])
        self.play(FadeIn(bolt), run_time=0.15)
        self.play(bolt.animate.move_to([5.3, 1.2, 0]), run_time=0.35, rate_func=rate_functions.rush_into)
        done = chip("answer", GRN, 28).move_to([5.3, 1.2, 0])
        self.play(Transform(bolt, done), Flash(done, color=GRN), run_time=0.35)
        self.line(sid, 1, 0.6)
        jev = chip("Jev", YEL, 34).next_to(lanes[0][0], RIGHT, buff=0.3)
        self.play(FadeIn(jev, shift=DOWN * 0.4), run_time=0.35)
        # "System two is slow and deliberate, like a model writing out its reasoning." — lines get written slowly
        self.line(sid, 2)
        pen = Dot([-3.0, -1.0, 0], radius=0.22, color=VIO)
        self.play(FadeIn(pen), run_time=0.2)
        notes = VGroup()
        for k in range(6):
            x0 = -3.0 + k * 1.45
            seg = Line([x0, -1.0, 0], [x0 + 1.2, -1.0, 0], color=VIO, stroke_width=16).shift(DOWN * (0.18 * (k % 2)))
            self.play(Create(seg), pen.animate.move_to(seg.get_end()), run_time=0.75, rate_func=linear)
            notes.add(seg)
        thinking = t("thinking...", 26, MUTED, bold=False).next_to(pen, DOWN, buff=0.2)
        self.play(FadeIn(thinking), run_time=0.3)
        self.at(sid, SCN[sid]["frames"] / 30 - 0.3)
        self.clear()

    # ---- 3. not a reply: a function call ------------------------------------------------------------------------
    def call(self):
        sid = "call"
        # "So I prompt it, and it writes me a reply?" — a reply bubble fills with prose
        reply = box(6.0, 2.6, "#ffffff", r=0.4).move_to([0, 0.8, 0])
        self.line(sid, 0)
        self.play(GrowFromCenter(reply), run_time=0.35)
        prose = VGroup(*[Line([-2.6, 0, 0], [2.6 - (k % 3) * 0.9, 0, 0], color=MUTED, stroke_width=7) for k in range(5)])
        prose.arrange(DOWN, buff=0.28, aligned_edge=LEFT).move_to(reply)
        self.play(*[Create(p) for p in prose], lag_ratio=0.35, run_time=1.6)
        # "No. Think of it as a function call."
        self.line(sid, 1)
        x = cross(reply)
        self.play(Create(x), run_time=0.3)
        code = t("decision = jev(state)", 50, INK, font=MONO).move_to([0, 2.9, 0])
        self.play(FadeOut(VGroup(reply, prose, x)), Write(code), run_time=0.8)
        fn = box(2.6, 1.6, VIO).move_to([0, 0.2, 0])
        fl = t("jev()", 44, INK, font=MONO).move_to(fn)
        self.play(GrowFromCenter(VGroup(fn, fl)), run_time=0.35)
        # "Unstructured state goes in: text, or your program's state." — scraps fly into the box
        self.line(sid, 2)
        scraps = [chip('"my order never arrived"', YEL, 24, MONO), chip("{ cart, user, history }", BLU, 24, MONO),
                  chip("support ticket", YEL, 24)]
        for s, pos in zip(scraps, ([-4.6, 1.3, 0], [-4.6, -0.2, 0], [-4.6, -1.5, 0])):
            s.move_to(pos)
        ex = t("example", 22, MUTED, bold=False).next_to(scraps[0], UP, buff=0.12)  # not from TypeSafe's post
        self.play(*[FadeIn(s, shift=RIGHT * 0.4) for s in scraps], FadeIn(ex), lag_ratio=0.3, run_time=0.9)
        self.line(sid, 2, 0.55)
        self.play(*[s.animate.scale(0.2).move_to(fn).set_opacity(0) for s in scraps], FadeOut(ex), lag_ratio=0.2,
                  run_time=1.0)
        self.play(Indicate(VGroup(fn, fl), color=VIO, scale_factor=1.08), run_time=0.5)
        # "A typed value comes out, with a calibrated probability." — a typed chip and a filling bar
        self.line(sid, 3)
        out = chip("Decision.REFUND", GRN, 30, MONO).move_to([4.3, 0.55, 0])
        arrow = Arrow(fn.get_right(), out.get_left(), buff=0.15, color=INK, stroke_width=5)
        ex2 = t("example", 22, MUTED, bold=False).next_to(out, UP, buff=0.12)
        self.play(Create(arrow), FadeIn(out, shift=RIGHT * 0.3), FadeIn(ex2), run_time=0.5)
        frame = box(3.2, 0.42, "#ffffff", r=0.1).next_to(out, DOWN, buff=0.45)
        p = ValueTracker(0.0)
        fill = always_redraw(lambda: Rectangle(width=max(0.01, 3.1 * p.get_value()), height=0.32, fill_color=GRN,
                                               fill_opacity=1, stroke_width=0).align_to(frame, LEFT).shift(RIGHT * 0.05)
                             .set_y(frame.get_y()))
        lab = t("probability", 24, MUTED, bold=False).next_to(frame, DOWN, buff=0.12)
        self.play(FadeIn(frame), FadeIn(lab), run_time=0.3)
        self.add(fill)
        self.play(p.animate.set_value(0.9), run_time=1.4, rate_func=rate_functions.ease_out_cubic)
        self.at(sid, SCN[sid]["frames"] / 30 - 0.3)
        self.remove(fill)
        self.clear()

    # ---- 4. TypeSafe's numbers ---------------------------------------------------------------------------------
    def numbers(self):
        sid = "numbers"
        says = chip("TypeSafe's numbers", ORG, 34).to_edge(UP, buff=0.45)  # the one on-screen attribution
        self.line(sid, 0)
        self.play(FadeIn(says, shift=DOWN * 0.2), run_time=0.35)
        # "TypeSafe says each answer takes seventy to five hundred milliseconds." — a time ruler with the band lit
        self.line(sid, 0, 0.25)
        ruler = Line([-5.5, 1.0, 0], [5.5, 1.0, 0], color=INK, stroke_width=5)
        band = Rectangle(width=11 * (500 - 70) / 600, height=0.5, fill_color=YEL, fill_opacity=1, stroke_width=0)
        band.move_to([-5.5 + 11 * (70 + 500) / 2 / 600, 1.0, 0]).set_z_index(-1)
        l70 = t("70ms", 30, RED).next_to(band.get_left(), UP, buff=0.35)
        l500 = t("500ms", 30, RED).next_to(band.get_right(), UP, buff=0.35)
        cap = t("per answer", 26, MUTED, bold=False).next_to(band, DOWN, buff=0.15)
        self.play(Create(ruler), run_time=0.4)
        self.play(GrowFromCenter(band), FadeIn(l70), FadeIn(l500), FadeIn(cap), run_time=0.5)
        ping = Dot(band.get_left(), radius=0.13, color=RED)
        self.play(MoveAlongPath(ping, Line(band.get_left(), band.get_right())), run_time=1.6,
                  rate_func=rate_functions.there_and_back)
        # "Forty to two hundred times faster than frontier models, on these queries." — a race
        self.line(sid, 1)
        self.play(FadeOut(VGroup(ruler, band, l70, l500, cap, ping)), run_time=0.3)
        y1, y2 = 0.9, -0.6
        r1 = chip("Jev", YEL, 30).move_to([-5.2, y1, 0])
        r2 = chip("frontier model", BLU, 30).move_to([-4.5, y2, 0])
        finish = DashedLine([5.6, 1.6, 0], [5.6, -1.3, 0], color=INK)
        self.play(FadeIn(r1), FadeIn(r2), Create(finish), run_time=0.4)
        self.play(r1.animate.move_to([4.9, y1, 0]), r2.animate.shift(RIGHT * 0.25), run_time=0.5,
                  rate_func=rate_functions.rush_into)
        tag = t("40x-200x faster", 44, RED).move_to([0, -1.85, 0])
        self.play(FadeIn(tag, scale=0.8), r2.animate.shift(RIGHT * 0.15), run_time=0.5)
        self.play(r2.animate.shift(RIGHT * 0.3), run_time=2.0, rate_func=linear)
        # "And about four cents per million input tokens." — a price tag swings in
        self.line(sid, 2)
        self.play(FadeOut(VGroup(r1, r2, finish, tag)), run_time=0.3)
        price = VGroup(box(5.6, 2.4, YEL, r=0.3), t("$0.042", 90, RED))
        price[1].move_to(price[0]).shift(UP * 0.25)
        per = t("per million input tokens", 28).next_to(price[1], DOWN, buff=0.12)
        hole = Circle(radius=0.14, color=INK, stroke_width=3).move_to(price[0].get_corner(UP + LEFT) + [0.4, -0.4, 0])
        tagg = VGroup(price, per, hole).move_to([0, 0.2, 0]).rotate(0.25)
        self.play(FadeIn(tagg, shift=DOWN * 0.6), run_time=0.45)
        self.play(tagg.animate.rotate(-0.25), run_time=0.8, rate_func=rate_functions.ease_out_elastic)
        self.at(sid, SCN[sid]["frames"] / 30 - 0.3)
        self.clear()

    # ---- 5. the asker, to camera -------------------------------------------------------------------------------
    def interview(self):
        sid = "interview"
        back, desk, feet = C.interview_set(SKIN, "office")
        mine = [(a, b, w) for who, a, b, w in lines_of(sid) if who == "asker"]
        a = C.Actor(SKIN["roles"]["asker"], "asker", C.INTERVIEW_PX, feet, 1, mine, [])
        m = a.attach(lambda: self.time)
        card = C.lower_third(lambda s, size, color, weight=None: t(s, size, color), SKIN["roles"]["asker"], 0.9,
                             -1.35, SKIN["set"]["accent"])
        self.add(back, a.feet, m, desk)
        self.play(FadeIn(card, shift=RIGHT * 0.3), run_time=0.4)
        for i in range(2):
            for frac in (0.1, 0.6):
                self.line(sid, i, frac)
                self.play(a.feet.animate.shift(UP * a.px), run_time=0.15)
                self.play(a.feet.animate.shift(DOWN * a.px), run_time=0.15)
        self.at(sid, SCN[sid]["frames"] / 30 - 0.3)
        self.play(*[FadeOut(x) for x in (back, m, desk, card)], run_time=0.3)
        self.remove(a.feet)

    # ---- 6. why trust the probability, then the thesis ----------------------------------------------------------
    def trust(self):
        sid = "trust"
        # "But why trust its confidence?" — a gauge with a question mark
        self.line(sid, 0)
        gauge = VGroup(*[Line(ORIGIN, [np.cos(a), np.sin(a), 0]).scale(1.6).set_stroke(MUTED, 4) for a in
                         np.linspace(0.15, np.pi - 0.15, 7)]).move_to([0, 0.9, 0])
        needle = Line([0, 0.2, 0], [0.9, 1.6, 0], color=RED, stroke_width=8)
        q = t("?", 80, RED).next_to(gauge, RIGHT, buff=0.4)
        self.play(FadeIn(gauge), Create(needle), FadeIn(q), run_time=0.5)
        self.play(needle.animate.rotate(0.6, about_point=[0, 0.2, 0]), run_time=0.6, rate_func=rate_functions.there_and_back)
        # "It's trained with reinforcement learning for calibrated decisions." — calibration chart
        self.line(sid, 1)
        self.play(FadeOut(VGroup(gauge, needle, q)), run_time=0.3)
        ax = VGroup(Line([-3, -1.6, 0], [3, -1.6, 0], color=INK, stroke_width=4),
                    Line([-3, -1.6, 0], [-3, 2.6, 0], color=INK, stroke_width=4))
        diag = DashedLine([-3, -1.6, 0], [3, 2.6, 0], color=GRN)
        xl = t("how sure it says it is", 24, MUTED, bold=False).next_to(ax[0], DOWN, buff=0.15)
        yl = t("how often it's right", 24, MUTED, bold=False).rotate(np.pi / 2).next_to(ax[1], LEFT, buff=0.15)
        trained = chip("trained to match", GRN, 26).move_to([4.6, 2.2, 0])
        self.play(Create(ax), FadeIn(xl), FadeIn(yl), run_time=0.5)
        self.play(Create(diag), FadeIn(trained), run_time=0.5)
        xs = np.linspace(-2.4, 2.4, 6)
        on = [[x, -1.6 + (x + 3) * 0.7, 0] for x in xs]
        off = [[x, p[1] + d, 0] for x, p, d in zip(xs, on, (1.3, -0.9, 1.1, -1.2, 0.8, -1.0))]
        dots = VGroup(*[Dot(o, radius=0.13, color=ORG) for o in off])
        self.play(FadeIn(dots), run_time=0.3)
        self.play(*[d.animate.move_to(p).set_color(GRN) for d, p in zip(dots, on)], run_time=2.2,
                  rate_func=rate_functions.smooth)
        # "So its probabilities are meant to be honest, and your code can branch on them." — the smart if
        self.line(sid, 2)
        self.play(FadeOut(VGroup(ax, diag, xl, yl, trained, dots)), run_time=0.3)
        p = chip("probability", YEL, 32).move_to([-4.2, 0.6, 0])
        hi = chip("confident: act", GRN, 30).move_to([3.4, 1.7, 0])
        lo = chip("unsure: ask a human", ORG, 30).move_to([3.4, -0.5, 0])
        iff = chip("if", VIO, 34, MONO).move_to([-0.8, 0.6, 0])
        a1 = Arrow(p.get_right(), iff.get_left(), buff=0.1, color=INK)
        a2 = Arrow(iff.get_right(), hi.get_left(), buff=0.1, color=INK)
        a3 = Arrow(iff.get_right(), lo.get_left(), buff=0.1, color=INK)
        self.play(FadeIn(p), run_time=0.3)
        self.play(Create(a1), FadeIn(iff), run_time=0.4)
        self.line(sid, 2, 0.5)
        self.play(Create(a2), FadeIn(hi), Create(a3), FadeIn(lo), run_time=0.5)
        pulse = Dot(p.get_right(), radius=0.12, color=RED)
        self.play(MoveAlongPath(pulse, Line(p.get_right(), iff.get_left())), run_time=0.5)
        self.play(MoveAlongPath(pulse, Line(iff.get_right(), hi.get_left())), run_time=0.5)
        # "Jev is a function call: state in, a typed decision out." — the whole idea in one strip
        self.line(sid, 3)
        self.play(FadeOut(VGroup(p, hi, lo, iff, a1, a2, a3, pulse)), run_time=0.3)
        s_in = chip("state", YEL, 40).move_to([-4.6, 0.6, 0])
        fn = chip("jev()", VIO, 44, MONO).move_to([0, 0.6, 0])
        d_out = chip("typed decision", GRN, 40).move_to([4.4, 0.6, 0])
        b1 = Arrow(s_in.get_right(), fn.get_left(), buff=0.15, color=INK, stroke_width=6)
        b2 = Arrow(fn.get_right(), d_out.get_left(), buff=0.15, color=INK, stroke_width=6)
        self.play(FadeIn(s_in, shift=RIGHT * 0.3), run_time=0.35)
        self.play(Create(b1), FadeIn(fn), run_time=0.4)
        self.line(sid, 3, 0.6)
        self.play(Create(b2), FadeIn(d_out, shift=RIGHT * 0.3), run_time=0.4)
        self.play(Indicate(d_out, color=GRN, scale_factor=1.1), run_time=0.7)
        self.at(sid, SCN[sid]["frames"] / 30 - 0.3)
        self.clear()

    # ---- 7. source card ---------------------------------------------------------------------------------------
    def source(self):
        sid = "source"
        self.at(sid, 0)
        h = t("Read the full post at", 64)
        u = t("typesafe.ai/blog/introducing-system-one-models-and-jev", 30, RED, font=MONO).next_to(h, DOWN, buff=0.4)
        mark = ImageMobject(str(HERE / "brand" / BRAND["wordmark"])).set(height=0.8).next_to(u, DOWN, buff=0.8)
        handle = t(BRAND["handle"], 30, MUTED, font=MONO).next_to(mark, DOWN, buff=0.2)
        Group(h, u, mark, handle).move_to([0, 0.6, 0])
        self.play(FadeIn(h, shift=UP * 0.2), run_time=0.35)
        self.play(FadeIn(u), run_time=0.35)
        self.play(FadeIn(mark), FadeIn(handle), run_time=0.35)
