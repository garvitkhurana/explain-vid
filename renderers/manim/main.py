"""Render videos/<video>/spec.json as one Manim scene. Usage: SPEC=<video> uv run manim -qh main.py Explainer

Env: SPEC=<video folder name in videos/> (required), THEME=<preset in theme.py>, SCENES=<comma-separated scene ids to render only those>.
Needs out/<video>/voice/timing.json from scripts/voice.py (scene lengths + caption cues come from the narration).
"""

import json
import math
import os
import re
import zlib
from functools import lru_cache
from pathlib import Path

from manim import (
    DOWN, LEFT, RIGHT, UP, Arrow, Create, FadeIn, FadeOut, GrowFromEdge, Line, Rectangle, Transform,
    LaggedStart, RoundedRectangle, Scene, Square, Text, ValueTracker, VGroup, VMobject, config, linear, rate_functions,
    DashedVMobject, Dot, MoveAlongPath, Polygon, Succession, AnimationGroup, Intersection, ManimColor,
    interpolate_color,
)

from manim.animation.animation import prepare_animation

import theme as T
from layout import layout as layout_graph

ROOT = Path(__file__).resolve().parents[2]
VIDEO = os.environ.get("SPEC", "")
if not VIDEO:
    raise SystemExit("Set SPEC=<video> (a folder in videos/).")
SPEC = json.loads((ROOT / "videos" / VIDEO / "spec.json").read_text())
ONLY = {x for x in os.environ.get("SCENES", "").split(",") if x}
TIMING_PATH = ROOT / "out" / VIDEO / "voice" / "timing.json"
if not TIMING_PATH.exists():
    raise SystemExit(f"Missing {TIMING_PATH}: run `uv run scripts/voice.py {VIDEO}` first (TTS=none for silent timing).")
TIMING = json.loads(TIMING_PATH.read_text())["scenes"]

config.background_color = T.BG
config.frame_rate = SPEC["meta"]["fps"]
config.pixel_width, config.pixel_height = SPEC["meta"]["size"]

PX = 1080 / 8  # pixels per Manim unit at 1080p
LAYOUT_SCALE = 8
CAPTION_TOP = -2.72  # captions live below this line; narrated content must stay above it


def txt(s, size=36, color=T.FG, font=T.FONT, weight=None):
    # font_size is in pt-ish units, scaled ×0.75.
    # Cached: animated text (race clocks, JSON stream) asks for the same strings many times, and each fresh
    # Text is a full Pango layout + SVG parse. Callers get a copy so they can move/recolor it freely.
    return _text(s, size, color, font, weight or (T.MONO_WEIGHT if font == T.MONO else T.WEIGHT)).copy()


@lru_cache(maxsize=4096)
def _text(s, size, color, font, weight):
    # Proportional fonts: lay out at 8x and scale down. At small sizes Pango snaps glyphs to whole pixels, giving
    # uneven letter spacing ("cl osed", "scal ing"). Monospace glyphs have fixed advances, so they skip this.
    scale = 1 if font == T.MONO else LAYOUT_SCALE
    width = config.pixel_width
    config.pixel_width = width * scale  # Pango's layout box is pixel_width wide; widen it or big text wraps.
    try:
        t = Text(s, font=font, font_size=size * 0.75 * scale, color=color, weight=weight)
    finally:
        config.pixel_width = width
    return t.scale(1 / scale)


def on_change(key, build):
    """Like but rebuilds only when key() changes. Rebuilding text every frame dominated render time."""
    m = build(key())
    m.last_key = key()

    def update(mob):
        k = key()
        if k != mob.last_key:
            mob.become(build(k))
            mob.last_key = k

    return m.add_updater(update)


def fit(m, max_w):
    # Manim has no text layout engine: shrink anything wider than its container.
    return m.scale_to_fit_width(max_w) if m.width > max_w else m


def on_baseline(t, y):
    """Move a one-line Text so its baseline sits at y. Centring by bounding box makes "y" sit lower than "b";
    the median glyph bottom is the baseline (only a few glyphs have descenders)."""
    bottoms = sorted(g.get_bottom()[1] for g in t.family_members_with_points())
    return t.shift(UP * (y - bottoms[len(bottoms) // 2])) if bottoms else t


def panel(w, h, radius, stroke=None, stroke_w=None, fill=None):
    """Card surface in the current theme: optional outline and hard offset shadow. Last element is the card."""
    stroke = stroke or T.BORDER
    width = (stroke_w or T.BORDER_W) if stroke else 0
    r = radius * T.RADIUS
    kw = dict(width=w, height=h, fill_color=fill or T.PANEL, fill_opacity=1, stroke_color=stroke or T.PANEL, stroke_width=width)
    card = RoundedRectangle(corner_radius=r, **kw) if r > 0 else Rectangle(**kw)
    if not T.SHADOW:
        return VGroup(card)
    shadow = card.copy().set_fill(T.BORDER or T.FG, 1).set_stroke(width=0).shift(RIGHT * T.SHADOW[0] + UP * T.SHADOW[1])
    return VGroup(shadow, card)


def bar(w, h, color):
    return Rectangle(width=max(0.03, w), height=h, fill_color=color, fill_opacity=1,
                     stroke_color=T.BORDER or color, stroke_width=3 if T.BORDER else 0)


def box(label, highlight=False, w=300, h=100):
    p = panel(w / PX, h / PX, 16 / PX, stroke=T.ACCENT if highlight else (T.BORDER or T.MUTED), stroke_w=max(4, T.BORDER_W))
    return VGroup(p, fit(txt(label, 32, weight="BOLD"), p[-1].width - 0.3).move_to(p[-1]))


class Explainer(Scene):
    def wait(self, duration=1.0, **kw):
        # Manim writes a *static* wait as int(duration * fps) frames (rounds down) but an animated one as
        # ceil(duration * fps). Always take the animated path so silent scenes stay frame-exact too.
        kw.setdefault("frozen_frame", False)
        return super().wait(duration, **kw)

    def construct(self):
        for s in SPEC["scenes"]:
            if ONLY and s["id"] not in ONLY:
                continue
            start = self.time
            timing = TIMING[s["id"]]
            self.scene_start, self.sentences, self.beats = start, timing["sentences"], s["data"].get("beats", {})
            self.scene_end = start + timing["frames"] / config.frame_rate
            cue_objs = self.cues(timing["cues"], start)
            self.add(*cue_objs)
            # Scene templates still accept a caption to fade in; captions now come from the narration cues.
            getattr(self, f"scene_{s['type']}")(s["data"], VGroup())
            if timing["cues"]:
                self.check_caption_band(s["id"], set(cue_objs))
            # End on exactly timing["frames"] frames. Manim turns a duration into ceil(duration * fps) frames, and
            # float noise can tip an exact value up by one, so ask for n - 0.5 frames to get exactly n.
            fps = config.frame_rate
            fade = round(0.25 * fps)
            rest = round(start * fps) + timing["frames"] - fade - round(self.time * fps)
            if rest > 0:
                self.wait((rest - 0.5) / fps)
            self.play(*[FadeOut(m) for m in self.mobjects], run_time=(fade - 0.5) / fps)

    def cues(self, cues, scene_start):
        """One caption per narration cue, visible only during its spoken time window."""
        out = []
        for c in cues:
            cap = self.caption(c["text"]).set_opacity(0)
            # dt in the signature makes this a time-based updater, so Manim keeps updating during waits.
            cap.add_updater(lambda m, dt, c=c: m.set_opacity(
                1 if c["start"] <= self.time - scene_start < c["end"] else 0))
            out.append(cap)
        return out

    def check_caption_band(self, sid, captions):
        """Fail the render if anything on screen reaches into the caption band (subtitles would cover it)."""
        low = [(m.get_bottom()[1], type(m).__name__) for m in self.mobjects
               if m not in captions and m.get_bottom()[1] < CAPTION_TOP and m.get_top()[1] > -config.frame_height / 2]
        if low:
            y, kind = min(low)
            raise ValueError(f"scene {sid!r}: {kind} reaches y={y:.2f}, into the caption band (keep content above {CAPTION_TOP})")

    def beat(self, step, default, frac=0.0):
        """Hold until the narration sentence this step belongs to starts (spec data.beats overrides the default);
        frac > 0 lands partway through that sentence. Steps are paced by the voice, so visuals change as things
        are said instead of all up front."""
        if not self.sentences:  # silent scene: nothing to wait for
            return
        b = self.beats.get(step, default)
        if isinstance(b, list):  # [sentence, fraction]: land partway through that sentence
            b, frac = b
        i = min(b, len(self.sentences) - 1)
        target = self.scene_start + self.sentences[i] + frac * self.span(step, default)
        if target - self.time > 1 / config.frame_rate:
            self.wait(target - self.time)

    def span(self, step, default):
        """Seconds from this step's sentence start to the next sentence (or 2 s for the last one)."""
        b = self.beats.get(step, default)
        i = min(b[0] if isinstance(b, list) else b, len(self.sentences) - 1)
        nxt = self.sentences[i + 1] if i + 1 < len(self.sentences) else self.sentences[i] + 2
        return nxt - self.sentences[i]

    def caption(self, text):
        t = fit(txt(text, 34, T.CAPTION_FG), 13.4)
        bg = Rectangle(width=t.width + 0.4, height=t.height + 0.3, fill_color=T.CAPTION_BG,
                       fill_opacity=T.CAPTION_OPACITY, stroke_width=0).move_to(t)
        return VGroup(bg, t).to_edge(DOWN, buff=0.55)

    def scene_title(self, d, cap):
        title = fit(txt(d["title"], 160, T.ACCENT, weight="BOLD"), 13).shift(UP * 1.2)  # long titles shrink to fit
        sub = fit(txt(d["subtitle"], 56), 13).next_to(title, DOWN, buff=0.4)
        kick = fit(txt(d["kicker"], 36, T.MUTED), 13).next_to(sub, DOWN, buff=0.6)
        self.beat("title", 0)
        self.play(FadeIn(title, shift=UP * 0.2), run_time=0.4)
        self.play(FadeIn(sub, shift=UP * 0.2), FadeIn(cap), run_time=0.35)
        self.play(FadeIn(kick), run_time=0.35)

    def scene_problem(self, d, cap):
        """The usual way: ticket → model writes prose → parser → if. Then cross out the writing and parsing."""
        tp = panel(4.1, 1.75, 0.15).move_to([-4.85, 1.3, 0])
        tl = txt(d["ticket_label"], 28, T.MUTED, weight="BOLD").move_to(tp[-1].get_corner(UP + LEFT), aligned_edge=UP + LEFT).shift(RIGHT * 0.25 + DOWN * 0.22)
        # Fit the lines as one group so they share a size (fitting each line separately made them differ).
        tb = fit(VGroup(*[txt(line, 30) for line in d["ticket"]]).arrange(DOWN, aligned_edge=LEFT, buff=0.12), 3.6).next_to(tl, DOWN, aligned_edge=LEFT, buff=0.3)
        q = fit(txt(d["question"], 32, T.ACCENT, weight="BOLD"), 4.1).next_to(tp, DOWN, buff=0.35)
        model = box(d["model"], highlight=True, w=200, h=100).move_to([-1.2, 1.3, 0])
        ap = panel(4.9, 1.9, 0.15).move_to([3.95, 2.0, 0])
        parser = box(d["parser"], w=260, h=90).move_to([3.95, 0.0, 0])
        cp = panel(4.9, 0.95, 0.15).move_to([3.95, -1.55, 0])
        code = fit(txt(d["code"], 30, font=T.MONO), 4.5).move_to(cp[-1])
        prose = " ".join(d["answer"])
        chars = ValueTracker(0)

        def lines_of(text):
            return VGroup(*[txt(l or " ", 28) for l in text]).arrange(DOWN, aligned_edge=LEFT, buff=0.1)

        # Size the streamed answer from its full text once, so partial text never overflows or changes size.
        answer_scale = min(1, (ap[-1].width - 0.5) / lines_of(d["answer"]).width)

        def answer(n):
            words, lines, k = prose[:n], [], 0
            for line in d["answer"]:  # keep the authored line breaks while streaming
                lines.append(words[k:k + len(line)]); k += len(line) + 1
            return lines_of(lines).scale(answer_scale).move_to(
                ap[-1].get_corner(UP + LEFT), aligned_edge=UP + LEFT).shift(RIGHT * 0.25 + DOWN * 0.25)

        def arrow(a, b):
            return Arrow(a, b, color=T.MUTED, buff=0.1, tip_length=0.22, max_tip_length_to_length_ratio=0.45, stroke_width=5)

        self.beat("ticket", 0)
        self.play(FadeIn(VGroup(tp, tl, tb), shift=UP * 0.2), run_time=0.4)
        self.beat("question", 0, frac=0.45)
        self.play(FadeIn(q, shift=UP * 0.15), run_time=0.3)
        self.beat("write", 1)
        self.play(FadeIn(model), Create(arrow(tp.get_right(), model.get_left())), run_time=0.4)
        self.play(FadeIn(ap), Create(arrow(model.get_right(), ap.get_left())), run_time=0.3)
        self.add(on_change(lambda: int(chars.get_value()), answer))
        # The prose streams in over part of the sentence, so parse and code still land while it's being said.
        self.play(chars.animate.set_value(len(prose)), run_time=max(1.0, self.span("write", 1) * 0.45), rate_func=linear)
        self.play(FadeIn(parser), Create(arrow(ap.get_bottom(), parser.get_top())), run_time=0.35)
        self.play(FadeIn(VGroup(cp, code)), Create(arrow(parser.get_bottom(), cp.get_top())), run_time=0.35)
        self.beat("cross", 2)
        area = VGroup(ap, parser)
        x = VGroup(Line(area.get_corner(UP + LEFT), area.get_corner(DOWN + RIGHT)),
                   Line(area.get_corner(DOWN + LEFT), area.get_corner(UP + RIGHT))).set_stroke(T.ACCENT, 14)
        self.play(Create(x), run_time=0.5)

    def scene_pipeline(self, d, cap):
        head = txt(d.get("head", "How it works"), 48, weight="BOLD").to_edge(UP, buff=0.8)
        inputs = VGroup(*[box(l) for l in d["inputs"]]).arrange(DOWN, buff=0.6).shift(LEFT * 4.8)
        model = box(d["model"], highlight=True)
        logits = box(d["stages"][0]).move_to(RIGHT * 4.8 + UP * 0.8)
        probs = box(d["stages"][1], highlight=True).move_to(RIGHT * 4.8 + DOWN * 1.4)
        self.beat("head", 0)
        self.play(FadeIn(head), FadeIn(cap), run_time=0.3)
        self.beat("inputs", 1)
        for b in inputs:
            self.play(FadeIn(b, shift=UP * 0.2), run_time=0.35)
        self.play(FadeIn(model), run_time=0.3)
        arrows = [Arrow(b.get_right(), model.get_left(), color=T.MUTED, buff=0.1) for b in inputs]
        self.play(*[Create(a) for a in arrows], run_time=0.5)
        self.beat("outputs", 2)
        self.play(model[0].animate.scale(1.08), rate_func=rate_functions.there_and_back, run_time=0.7)
        self.play(Create(Arrow(model.get_right(), logits.get_left(), color=T.MUTED, buff=0.1)), FadeIn(logits), run_time=0.5)
        self.wait(0.4)
        self.play(Create(Arrow(logits.get_bottom(), probs.get_top(), color=T.MUTED, buff=0.1)), FadeIn(probs), run_time=0.5)

    def scene_race(self, d, cap):
        """Two lanes racing a clock: left streams generated JSON token by token, right fills a grid of answers at once.
        data: {left: {label, seconds, tokens, counter}, right: {label, seconds, decisions, tokens, passes, footer},
               answers: [str] (one per decision; streamed as a JSON array and shown in the grid), highlight? (the answer
               drawn in the accent colour; default the first), note, speedup, time_scale?}
        note/counter/footer are format strings over the lane's numbers: note and right.footer get right's fields
        ({decisions}, {tokens}, {passes}); left.counter gets {done} (tokens so far) and left's fields.
        steps: lanes (0), start (1), one_pass (3), speedup (4)."""
        L, R = d["left"], d["right"]
        n = R["decisions"]
        answers = d["answers"]
        if len(answers) != n:
            raise ValueError(f"race: {len(answers)} answers for {n} decisions")
        hot = d.get("highlight", answers[0])
        js = "[" + ",".join(f'"{a}"' for a in answers) + "]"
        clock = ValueTracker(0)  # measured seconds
        scale = d.get("time_scale", 1)  # video seconds per measured second

        def lane(x):
            return panel(820 / PX, 560 / PX, 0.15).move_to([x, 0.6, 0])

        ll, rl = lane(-3.3), lane(3.3)
        top = fit(txt(d["note"].format(**R), 40, T.MUTED), 13).to_edge(UP, buff=0.4)
        lt = txt(L["label"], 38, T.WARN, weight="BOLD").move_to(ll.get_corner(UP + LEFT), aligned_edge=UP + LEFT).shift(RIGHT * 0.27 + DOWN * 0.27)
        rt = txt(R["label"], 38, T.ACCENT, weight="BOLD").move_to(rl.get_corner(UP + LEFT), aligned_edge=UP + LEFT).shift(RIGHT * 0.27 + DOWN * 0.27)

        # Each animated element is rebuilt only when what it shows changes (key), not every frame.
        def clock_key(limit):
            return lambda: (f"{min(clock.get_value(), limit):.3f}", clock.get_value() >= limit)

        def clock_text(key, anchor):
            v, done = key
            return txt(f"{v} s", 64, T.ACCENT if done else T.FG, font=T.MONO).next_to(anchor, DOWN, aligned_edge=LEFT, buff=0.15)

        lc = on_change(clock_key(L["seconds"]), lambda k: clock_text(k, lt))
        rc = on_change(clock_key(R["seconds"]), lambda k: clock_text(k, rt))

        def progress():
            return min(1, clock.get_value() / L["seconds"])

        def stream(chars):
            s = js[:chars] or " "
            lines = [s[i:i + 26] for i in range(0, len(s), 26)]
            return txt("\n".join(lines), 30, font=T.MONO).next_to(lt, DOWN, aligned_edge=LEFT, buff=1.2)

        def tokens(done):
            return txt(L["counter"].format(**L, done=done), 30, T.MUTED).move_to(
                ll.get_corner(DOWN + LEFT), aligned_edge=DOWN + LEFT).shift(RIGHT * 0.27 + UP * 0.22)

        def grid(done):
            cells = VGroup()
            for a in answers:
                fill = (T.ACCENT if a == hot else T.MUTED) if done else T.EMPTY
                r = RoundedRectangle(corner_radius=0.07 * max(T.RADIUS, 0.01), width=0.68, height=0.44, fill_color=fill, fill_opacity=1,
                                     stroke_color=T.BORDER or fill, stroke_width=3 if T.BORDER else 0)
                cells.add(VGroup(r, txt(a if done else "", 26, T.ON_ACCENT, weight="BOLD").move_to(r)) if done else r)
            return cells.arrange_in_grid(rows=3, cols=7, buff=0.1).next_to(rt, DOWN, aligned_edge=LEFT, buff=1.2)

        rfoot = fit(txt(R["footer"].format(**R), 30, T.MUTED), 820 / PX - 0.6).move_to(
            rl.get_corner(DOWN + LEFT), aligned_edge=DOWN + LEFT).shift(RIGHT * 0.27 + UP * 0.22)

        self.beat("lanes", 0)
        self.play(FadeIn(VGroup(ll, rl, top, lt, rt, rfoot)), FadeIn(cap), run_time=0.4)
        self.beat("start", 1)
        self.add(lc, rc,
                 on_change(lambda: round(progress() * len(js)), stream),
                 on_change(lambda: round(progress() * L["tokens"]), tokens),
                 on_change(lambda: clock.get_value() >= R["seconds"], grid))
        self.wait(0.1)
        self.play(clock.animate.set_value(L["seconds"]), run_time=L["seconds"] * scale, rate_func=linear)
        self.beat("one_pass", 3)
        self.play(rl.animate.scale(1.04), rate_func=rate_functions.there_and_back, run_time=0.6)
        self.beat("speedup", 4)
        big = fit(txt(d["speedup"], 90, T.ACCENT, weight="BOLD"), 13).move_to(DOWN * 2.2)
        self.play(FadeIn(big, scale=0.8), run_time=0.4)

    def scene_bars(self, d, cap):
        rows = [txt("STATE", 30, T.MUTED), fit(txt(d["state"], 40), 11.5), txt("QUESTION", 30, T.MUTED), fit(txt(d["question"], 40), 11.5)]
        head = VGroup(*rows).arrange(DOWN, aligned_edge=LEFT, buff=0.15).to_corner(UP + LEFT, buff=1.2)
        rows[2].shift(DOWN * 0.2); rows[3].shift(DOWN * 0.2)
        self.beat("rows", 0)
        self.play(FadeIn(head[:2]), FadeIn(cap), run_time=0.35)
        self.play(FadeIn(head[2:]), run_time=0.35)
        self.beat("bars", 1)
        anims = []
        for i, o in enumerate(d["options"]):
            y = -0.4 - i * 0.65
            label = txt(o["id"], 32, font=T.MONO).move_to([-3.2, y, 0], aligned_edge=RIGHT)
            b = bar(900 * o["p"] / PX, 50 / PX, T.ACCENT if i == 0 else T.MUTED).move_to([-2.9, y, 0], aligned_edge=LEFT)
            val = txt(f"{o['p']:.2f}", 32, font=T.MONO).next_to(b, RIGHT, buff=0.25)
            self.add(label)
            anims += [GrowFromEdge(b, LEFT), FadeIn(val)]
        self.play(*anims, run_time=0.9)

    def scene_readout(self, d, cap):
        """Left: the model's raw scores for a few tokens; the slot tokens are kept, the rest dimmed; right: softmax
        over the slots as probability bars.
        data: {question, scores_label, rest_label, vocab: [{tok, logit, slot?, ignored?}], softmax_label,
               slots: [{letter, option, p}], note, ignored_label} — the vocab row marked `ignored` gets the label.
        steps: question (0), scores (1), answer (2), keep (3), ignored (4)."""
        q = fit(txt(d["question"], 36, T.MUTED), 13).to_edge(UP, buff=0.45)
        head = txt(d["scores_label"], 30, weight="BOLD").move_to([-7.1 + 160 / PX, 2.55, 0], aligned_edge=LEFT)
        rows = []
        for i, v in enumerate(d["vocab"]):
            y = 1.95 - i * 70 / PX
            tok = txt(v["tok"], 34, font=T.MONO).move_to([-7.1 + 310 / PX, y, 0], aligned_edge=RIGHT)
            b = bar((v["logit"] - 15) * 50 / PX, 40 / PX, T.MUTED).move_to([-7.1 + 335 / PX, y, 0], aligned_edge=LEFT)
            val = txt(f"{v['logit']:.1f}", 28, T.MUTED, font=T.MONO).next_to(b, RIGHT, buff=0.15)
            rows.append((v, VGroup(tok, b, val)))
        rest = txt(d["rest_label"], 28, T.MUTED).move_to(
            [-7.1 + 160 / PX, 1.95 - len(rows) * 70 / PX, 0], aligned_edge=LEFT)
        self.beat("question", 0)
        self.play(FadeIn(q), FadeIn(head), FadeIn(cap), run_time=0.3)
        self.beat("scores", 1)
        self.play(*[FadeIn(r, shift=RIGHT * 0.2) for _, r in rows], FadeIn(rest), run_time=0.8)
        self.beat("answer", 2)  # "Those scores are its answer."
        self.play(*[r[1].animate(rate_func=rate_functions.there_and_back).stretch(1.12, 0, about_edge=LEFT) for _, r in rows], run_time=0.7)
        self.beat("keep", 3)
        # Ignored tokens stay readable: recolor to MUTED text + EMPTY bars (no opacity, which turns muddy on light BGs).
        dims = [a for v, r in rows if not v.get("slot") for a in (
            r[0].animate.set_color(T.MUTED), r[1].animate.set_fill(T.EMPTY), r[2].animate.set_color(T.MUTED))]
        marked = next(r for v, r in rows if v.get("ignored"))  # the dimmed row the narration points at
        ignored = txt(d["ignored_label"], 26, T.MUTED, weight="BOLD").next_to(marked, RIGHT, buff=0.25)
        hl = [r[0].animate.set_color(T.ACCENT) for v, r in rows if v.get("slot")] + \
             [r[1].animate.set_fill(T.ACCENT) for v, r in rows if v.get("slot")]
        self.play(*dims, *hl, run_time=0.6)
        arrow = txt("→", 64, T.ACCENT).move_to([0.3, 0.9, 0])
        sm = txt(d["softmax_label"], 30, weight="BOLD").move_to([1.1, 1.95, 0], aligned_edge=LEFT)
        self.play(FadeIn(arrow), FadeIn(sm), run_time=0.4)
        anims = []
        for i, s in enumerate(d["slots"]):
            y = 1.4 - i * 115 / PX
            lab = txt(f"{s['letter']} → {s['option']}", 28, T.MUTED, font=T.MONO).move_to([1.1, y, 0], aligned_edge=LEFT)
            b = bar(560 * s["p"] / PX, 36 / PX, T.ACCENT if i == 0 else T.MUTED).move_to([1.1, y - 0.33, 0], aligned_edge=LEFT)
            val = txt(f"{s['p']:.2f}", 30, font=T.MONO).next_to(b, RIGHT, buff=0.15)
            self.add(lab)
            anims += [GrowFromEdge(b, LEFT), FadeIn(val)]
        self.play(*anims, run_time=0.9)
        note = txt(d["note"], 30, T.WARN).move_to([1.1, -1.75, 0], aligned_edge=LEFT)
        self.play(FadeIn(note), run_time=0.3)
        self.beat("ignored", 4)
        self.play(FadeIn(ignored, shift=LEFT * 0.2), marked.animate(rate_func=rate_functions.there_and_back).scale(1.06), run_time=0.6)

    def scene_branch(self, d, cap):
        """A shared prefix read once into a cache, then many short branches off it; rates compared as bars.
        data: {prefix_label, prefix_note, cache_label, branches, branch_label, unit, workload, rates: [{label, v}]}
        steps: document (0), read_once (1), questions (2), rates (3)."""
        n = d["branches"]
        left = -7.1 + 160 / PX
        label = txt(d["prefix_label"], 30, weight="BOLD").move_to([left, 1.55, 0], aligned_edge=LEFT)
        track = bar(600 / PX, 80 / PX, T.EMPTY).move_to([left, 1.0, 0], aligned_edge=LEFT)
        prefill = bar(600 / PX, 80 / PX, T.MUTED).move_to(track)
        once = txt(d["prefix_note"], 26, T.MUTED).next_to(track, DOWN, aligned_edge=LEFT, buff=0.12)
        self.beat("document", 0)
        self.play(FadeIn(label), FadeIn(track), FadeIn(cap), run_time=0.3)
        self.beat("read_once", 1)
        self.play(GrowFromEdge(prefill, LEFT), FadeIn(once), run_time=1.2)
        cache = box(d["cache_label"], highlight=True, w=240, h=120).move_to([0.5, 1.0, 0])
        self.play(Create(Arrow(track.get_right(), cache.get_left(), color=T.MUTED, buff=0.05, tip_length=0.15)), FadeIn(cache), run_time=0.5)
        strips = VGroup(*[
            Rectangle(width=460 / PX, height=12 / PX, stroke_width=0, fill_color=T.EMPTY, fill_opacity=1)
            for _ in range(n)]).arrange(DOWN, buff=6 / PX).move_to([4.5, 1.15, 0])
        blabel = txt(d["branch_label"], 30, weight="BOLD").next_to(strips, UP, aligned_edge=LEFT, buff=0.2)
        lines = VGroup(*[Line(cache.get_right(), s.get_left(), color=T.MUTED, stroke_width=2, stroke_opacity=0.7) for s in strips])
        self.beat("questions", 2)
        self.play(Create(lines), FadeIn(strips), FadeIn(blabel), run_time=1.0)
        self.play(strips.animate.set_fill(T.ACCENT), lines.animate.set_color(T.ACCENT), run_time=0.3)
        unit = txt(f"{d['unit']} · {d['workload']}", 30, T.MUTED).move_to([left, -0.85, 0], aligned_edge=LEFT)
        self.beat("rates", 3)
        self.play(FadeIn(unit), run_time=0.3)
        vmax = max(r["v"] for r in d["rates"])
        anims = []
        for i, r in enumerate(d["rates"]):
            y = -1.35 - i * 0.55
            best = r["v"] == vmax
            lab = txt(r["label"], 30).move_to([left + 360 / PX, y, 0], aligned_edge=RIGHT)
            b = bar(1000 * r["v"] / vmax / PX, 38 / PX, T.ACCENT if best else T.MUTED).move_to([left + 384 / PX, y, 0], aligned_edge=LEFT)
            val = txt(f"{r['v']:.2f}", 32, T.ACCENT if best else T.FG, font=T.MONO).next_to(b, RIGHT, buff=0.18)
            self.add(lab)
            anims += [GrowFromEdge(b, LEFT), FadeIn(val)]
        self.play(*anims, run_time=1.0)

    def scene_metrics(self, d, cap):
        """Big-number cards, one per sentence, with an optional headline on top and a closing footnote under them.
        data: {title?, subtitle?, cards: [{label, value, compare}], footnote?}
        steps: title (sentence 0, when there is one), card{i} (i, or i+1 after a title), footnote (after the cards).
        A footnote is a closing line: narrating it before every card is an error — a headline said first is `title`."""
        head = self.headline(d)
        n = len(d["cards"])
        first = 1 if head else 0  # a title takes sentence 0; cards follow
        w = min(500, (1780 - 50 * (n - 1)) / n)  # up to 3 cards at full width; more cards share the frame
        foot = fit(txt(d["footnote"], 32, weight="BOLD"), 13) if d.get("footnote") else None
        card_h = 380 / PX
        if head:
            # Cards (+ footnote) centred in the space between the headline and the caption band; shorter if needed.
            top = head.get_bottom()[1] - 0.45
            bottom = CAPTION_TOP + 0.12 + (foot.height + 0.55 if foot else 0)
            card_h = min(card_h, top - bottom)
            cy = (top + bottom) / 2
        else:
            cy = 0.5
        cards = VGroup()
        for c in d["cards"]:
            p = panel(w / PX, card_h, 0.18)
            r = p[-1]
            lab = fit(txt(c["label"], 30, T.MUTED), r.width - 0.4).move_to(r.get_top(), aligned_edge=UP).shift(DOWN * 0.35)
            val = fit(txt(c["value"], 70, T.ACCENT, weight="BOLD"), r.width - 0.5).move_to(r)
            cmp = fit(txt(c["compare"], 30), r.width - 0.4).move_to(r.get_bottom(), aligned_edge=DOWN).shift(UP * 0.35)
            cards.add(VGroup(p, lab, val, cmp))
        cards.arrange(RIGHT, buff=50 / PX).move_to([0, cy, 0])
        if foot:
            foot.next_to(cards, DOWN, buff=0.55)
        steps = ([("title", 0, head)] if head else []) + [(f"card{i}", i + first, c) for i, c in enumerate(cards)] + \
                ([("footnote", n + first, foot)] if foot else [])
        last = len(self.sentences) - 1

        def sentence(name, default):
            b = self.beats.get(name, default)
            return min(b[0] if isinstance(b, list) else b, last)

        if foot and self.sentences and sentence("footnote", n + first) < min(sentence(f"card{i}", i + first) for i in range(n)):
            raise ValueError("metrics: footnote narrated before the cards — use `title` for a headline said first "
                             "(the footnote is a closing line under the cards)")
        # Play in the order the narration reaches them (beats can put the footnote before some cards).
        for name, default, m in sorted(steps, key=lambda st: (sentence(st[0], st[1]), st[1])):
            self.beat(name, default)
            self.play(FadeIn(m, shift=UP * 0.2), run_time=self.step_time(name, default, 0.35 if m is not head else 0.4))

    # ---- templates added for agent-unwrapped + Habitat ------------------------------------------------------

    def scene_loop(self, d, cap):
        """Agent loop: a cycle diagram on the left, the message list growing on the right as the loop runs."""
        N = d["nodes"]
        node = {k: box(N[k], w=260, h=90) for k in N}
        node["chat"].move_to([-5.15, 1.2, 0]); node["decide"].move_to([-2.05, 1.2, 0])
        node["run"].move_to([-2.05, -1.1, 0]); node["append"].move_to([-5.15, -1.1, 0])
        node["final"].move_to([-2.05, 3.05, 0])

        def arrow(a, b, label=None):
            ar = Arrow(a, b, color=T.MUTED, buff=0.08, tip_length=0.2, max_tip_length_to_length_ratio=0.35, stroke_width=5)
            return VGroup(ar, txt(label, 24, T.MUTED, weight="BOLD").next_to(ar, RIGHT, buff=0.1)) if label else ar

        wires = VGroup(arrow(node["chat"].get_right(), node["decide"].get_left()),
                       arrow(node["decide"].get_bottom(), node["run"].get_top(), "yes"),
                       arrow(node["run"].get_left(), node["append"].get_right()),
                       arrow(node["append"].get_top(), node["chat"].get_bottom()),
                       arrow(node["decide"].get_top(), node["final"].get_bottom(), "no"))

        def focus(key):
            """Accent the active node's outline, return every other node to normal."""
            anims = []
            for k, b in node.items():
                card = b[0][-1]
                on = k == key
                anims.append(card.animate.set_stroke(T.ACCENT if on else (T.BORDER or T.MUTED), width=9 if on else max(4, T.BORDER_W)))
            return anims

        tp = panel(6.3, 5.9, 0.15).move_to([3.7, 0.55, 0])
        head = txt("messages", 30, T.MUTED, weight="BOLD").move_to(tp[-1].get_corner(UP + LEFT), aligned_edge=UP + LEFT).shift(RIGHT * 0.3 + DOWN * 0.25)
        colors = {"system": T.MUTED, "user": T.FG, "assistant": T.ACCENT, "tool": T.WARN}
        bubbles, y = [], head.get_bottom()[1] - 0.3
        for m in d["messages"]:
            role = txt(m["role"], 24, colors.get(m["role"], T.FG), font=T.MONO, weight="BOLD")
            body = fit(txt(m["text"], 26, font=T.MONO if m.get("code") else T.FONT), 5.4)
            content = VGroup(role, body).arrange(DOWN, aligned_edge=LEFT, buff=0.08)
            rail = Rectangle(width=0.07, height=content.height + 0.1, stroke_width=0, fill_color=colors.get(m["role"], T.FG), fill_opacity=1)
            b = VGroup(rail, content).arrange(RIGHT, buff=0.18, aligned_edge=UP)
            b.move_to([tp[-1].get_left()[0] + 0.3, y, 0], aligned_edge=UP + LEFT)
            y -= b.height + 0.28
            bubbles.append(b)

        def say(i):
            return FadeIn(bubbles[i], shift=UP * 0.15)

        self.beat("setup", 0)
        self.play(FadeIn(tp), FadeIn(head), *[FadeIn(b) for b in node.values()], Create(wires), run_time=0.8)
        self.play(say(0), run_time=0.3)
        self.play(say(1), run_time=0.3)
        self.beat("chat", 1)
        self.play(*focus("chat"), run_time=0.4)
        self.beat("call", 2)
        self.play(*focus("decide"), run_time=0.4)
        self.play(say(2), run_time=0.4)
        self.beat("run", 3)
        self.play(*focus("run"), run_time=0.4)
        self.beat("append", 3, frac=0.5)
        self.play(*focus("append"), say(3), run_time=0.5)
        self.beat("loop", 4)
        self.play(*focus("chat"), run_time=0.4)
        self.play(*focus("decide"), run_time=0.4)
        self.beat("final", 4, frac=0.55)
        self.play(*focus("final"), say(4), run_time=0.5)
        if d.get("footnote"):
            self.beat("summary", 5)
            foot = fit(txt(d["footnote"], 28, T.MUTED, font=T.MONO), 6.2).move_to([-3.6, -2.45, 0])
            self.play(FadeIn(foot, shift=UP * 0.15), *[b.animate(rate_func=rate_functions.there_and_back).scale(1.05) for b in node.values()], run_time=0.7)

    def scene_checklist(self, d, cap):
        """Rows of checks that tick as the narration reaches them."""
        title = txt(d["title"], 56, weight="BOLD").to_edge(UP, buff=0.9)
        rows = []
        for i, r in enumerate(d["rows"]):
            # Rows share the space between the title and the caption band (plus room for a footer).
            step_y = min(1.3, (1.55 - (CAPTION_TOP + (1.0 if d.get("footer") else 0.6))) / max(1, len(d["rows"]) - 1))
            p = panel(11.6, 0.95, 0.12).move_to([0, 1.55 - i * step_y, 0])
            boxy = Square(0.5, color=T.BORDER or T.MUTED, stroke_width=5).move_to(p[-1].get_left() + RIGHT * 0.6)
            label = fit(txt(r["label"], 36, weight="BOLD"), 6.6).next_to(boxy, RIGHT, buff=0.4)
            tag = fit(txt(r["tag"], 26, T.MUTED), 3.6).move_to(p[-1].get_right() + LEFT * 0.3, aligned_edge=RIGHT)
            # Drawn, not a glyph: Helvetica has no ✓ and the fallback font renders a √-like mark.
            tick = VMobject(stroke_color=T.ACCENT, stroke_width=10).set_points_as_corners(
                [boxy.get_center() + v for v in (LEFT * 0.17, DOWN * 0.15 + LEFT * 0.03, UP * 0.2 + RIGHT * 0.2)])
            rows.append((VGroup(p, boxy, label, tag), tick))
        self.beat("title", 0)
        self.play(FadeIn(title, shift=UP * 0.2), run_time=0.4)
        for i, (row, tick) in enumerate(rows):
            self.beat(f"row{i}", min(i + 1, len(self.sentences) - 1))
            self.play(FadeIn(row, shift=UP * 0.15), run_time=0.35)
            self.play(Create(tick), row[1].animate.set_stroke(T.ACCENT), run_time=0.35)
        if d.get("footer"):
            self.beat("footer", len(rows) + 1)
            foot = fit(txt(d["footer"], 30, T.MUTED, font=T.MONO), 12).next_to(rows[-1][0], DOWN, buff=0.35)
            if foot.get_bottom()[1] < CAPTION_TOP + 0.1:
                foot.shift(UP * (CAPTION_TOP + 0.1 - foot.get_bottom()[1]))
            self.play(FadeIn(foot, shift=UP * 0.15), run_time=0.35)

    def scene_fanout(self, d, cap):
        """A library copied into many services (slow rollouts, rollbacks) → one central service."""
        xs, ys = [-5.4, -1.8, 1.8, 5.4], [2.35, 0.35]
        svcs, chips = [], []
        for i, name in enumerate(d["services"]):
            b = box(name, w=380, h=90).move_to([xs[i % 4], ys[i // 4], 0])
            chip = self.chip(f"{d['lib']} {d['old']}", T.EMPTY, T.FG).next_to(b, DOWN, buff=0.12)
            svcs.append(b); chips.append(chip)
        status = txt(d["rollout_label"], 30, T.WARN, weight="BOLD").move_to([0, -1.45, 0])
        self.beat("services", 0)
        self.play(LaggedStart(*[FadeIn(VGroup(b, c), shift=UP * 0.15) for b, c in zip(svcs, chips)], lag_ratio=0.12), run_time=1.2)
        self.beat("rollout", 1)
        self.play(FadeIn(status), run_time=0.3)
        per = max(0.25, self.span("rollout", 1) * 0.7 / len(chips))  # deliberately slow: one service at a time
        for c in chips:
            self.play(Transform(c, self.chip(f"{d['lib']} {d['new']}", T.WARN, T.ON_ACCENT).move_to(c)), run_time=per)
        self.beat("rollback", 2)
        k = d["rollback"]
        bad = self.chip(f"{d['lib']} {d['old']}", T.ACCENT, T.ON_ACCENT).move_to(chips[k])
        self.play(Transform(chips[k], bad), svcs[k][0][-1].animate.set_stroke(T.ACCENT, width=9),
                  Transform(status, txt(d["outage_label"], 30, T.ACCENT, weight="BOLD").move_to(status)), run_time=0.5)
        self.beat("service", 3)
        central = box(d["service"], highlight=True, w=520, h=110).move_to([0, -1.75, 0])
        # Behind the boxes: wires from the top row pass under the second row instead of across it.
        # Land each wire on the central box's top edge in proportion to its service's x, so the tips don't pile up.
        span = central[0][-1].width * 0.8 / 2
        xmax = max(abs(b.get_center()[0]) for b in svcs)
        wires = VGroup(*[Arrow(b.get_bottom(), central.get_top() + RIGHT * span * b.get_center()[0] / xmax + UP * 0.02,
                               color=T.MUTED, buff=0.1, stroke_width=4, tip_length=0.18) for b in svcs]).set_z_index(-1)
        self.play(*[FadeOut(c) for c in chips], FadeOut(status), svcs[k][0][-1].animate.set_stroke(T.BORDER or T.MUTED, width=max(4, T.BORDER_W)), run_time=0.4)
        self.play(FadeIn(central, scale=0.9), Create(wires), run_time=0.8)

    def chip(self, text, fill, color):
        t = txt(text, 22, color, weight="BOLD")
        r = Rectangle(width=t.width + 0.3, height=0.42, fill_color=fill, fill_opacity=1,
                      stroke_color=T.BORDER or fill, stroke_width=3 if T.BORDER else 0)
        return VGroup(r, t.move_to(r))

    def scene_gantt(self, d, cap):
        """Timelines of segments per row (e.g. CPU vs waiting), one panel per scenario, shared time axis."""
        style = {"cpu": (T.FG, None), "io": (T.EMPTY, T.BORDER or T.MUTED), "stall": (T.ACCENT, None)}
        end = max(seg[1] + seg[2] for pnl in d["panels"] for row in pnl["rows"] for seg in row)
        x0, width = -4.6, 11.2
        unit = width / end
        title = fit(txt(d["title"], 40, weight="BOLD"), 13).to_edge(UP, buff=0.35)
        legend = VGroup()
        for kind, label in d["legend"].items():
            fill, stroke = style[kind]
            sw = Rectangle(width=0.4, height=0.26, fill_color=fill, fill_opacity=1, stroke_color=stroke or fill, stroke_width=3)
            legend.add(VGroup(sw, txt(label, 24, T.MUTED)).arrange(RIGHT, buff=0.15))
        legend.arrange(RIGHT, buff=0.6).next_to(title, DOWN, buff=0.25)
        unit_note = txt(d["unit"], 22, T.MUTED).to_corner(UP + RIGHT, buff=0.35).shift(DOWN * 0.95)
        panels = []
        for pi, pnl in enumerate(d["panels"]):
            top = 1.85 - pi * 2.2
            label = txt(pnl["label"], 30, weight="BOLD").move_to([x0 - 2.2, top, 0], aligned_edge=LEFT)
            segs, stalls = [], []
            for ri, row in enumerate(pnl["rows"]):
                y = top - 0.55 - ri * 0.52
                name = txt(f"req {ri + 1}", 24, T.MUTED, font=T.MONO).move_to([x0 - 0.25, y, 0], aligned_edge=RIGHT)
                segs.append(name)
                for kind, start, length in row:
                    fill, stroke = style[kind]
                    r = Rectangle(width=length * unit, height=0.36, fill_color=fill, fill_opacity=1,
                                  stroke_color=stroke or fill, stroke_width=3).move_to([x0 + start * unit, y, 0], aligned_edge=LEFT)
                    segs.append(r)
                    if kind == "stall":
                        stalls.append(r)
            panels.append((label, segs, stalls))
        self.beat("title", 0)
        self.play(FadeIn(title), FadeIn(legend), FadeIn(unit_note), run_time=0.5)
        for pi, (label, segs, stalls) in enumerate(panels):
            self.beat(f"panel{pi}", pi + 1)
            self.play(FadeIn(label), run_time=0.3)
            bars = [m for m in segs if isinstance(m, Rectangle)]
            bars.sort(key=lambda m: m.get_left()[0])  # draw left to right, like time passing
            self.play(*[FadeIn(m) for m in segs if not isinstance(m, Rectangle)],
                      LaggedStart(*[GrowFromEdge(b, LEFT) for b in bars], lag_ratio=0.15), run_time=1.6)
            if stalls:
                self.beat(f"stall{pi}", pi + 1, frac=0.5)
                self.play(*[st.animate(rate_func=rate_functions.there_and_back).stretch(1.4, 1) for st in stalls], run_time=0.6)
        if d.get("footer"):
            self.beat("footer", len(panels) + 1)
            lowest = min(m.get_bottom()[1] for _, segs, _ in panels for m in segs)
            foot = fit(txt(d["footer"], 32, T.ACCENT, weight="BOLD"), 12).move_to([0, lowest - 0.35, 0])  # above the captions
            self.play(FadeIn(foot, shift=UP * 0.15), run_time=0.35)

    def scene_balance(self, d, cap):
        """Per-server load bars evolving over steps, one panel per strategy (e.g. LIFO vs FIFO)."""
        vmax = max(v for pnl in d["panels"] for series in pnl["series"] for v in series)
        H = 3.0  # bar height at vmax
        note = txt(d["note"], 24, T.MUTED).to_edge(UP, buff=0.35)
        lanes = []
        for pi, pnl in enumerate(d["panels"]):
            cx = -3.45 + pi * 6.9
            p = panel(6.4, 5.4, 0.15).move_to([cx, 0.2, 0])
            label = fit(txt(pnl["label"], 30, weight="BOLD"), 5.8).move_to(p[-1].get_top() + DOWN * 0.45)
            base = p[-1].get_bottom()[1] + 0.95
            bars, names = [], []
            for si, name in enumerate(d["servers"]):
                x = cx - 1.8 + si * 1.8
                v0 = pnl["series"][si][0]
                slow = si == len(d["servers"]) - 1
                b = Rectangle(width=1.0, height=max(0.05, H * v0 / vmax), fill_color=T.ACCENT if slow else T.MUTED, fill_opacity=1,
                              stroke_color=T.BORDER or T.MUTED, stroke_width=3 if T.BORDER else 0).move_to([x, base, 0], aligned_edge=DOWN)
                bars.append(b)
                names.append(txt(name, 26, font=T.MONO, weight="BOLD").move_to([x, base - 0.35, 0]))
            lanes.append((VGroup(p, label, *names), bars, pnl["series"], base))
        self.play(FadeIn(note), *[FadeIn(fr) for fr, _, _, _ in lanes], run_time=0.5)

        def run(li, step_name, default):
            frame, bars, series, base = lanes[li]
            self.beat(step_name, default)
            self.play(*[FadeIn(b) for b in bars], run_time=0.3)
            per = max(0.35, self.span(step_name, default) * 0.75 / (len(series[0]) - 1))
            for t in range(1, len(series[0])):
                self.play(*[b.animate.stretch_to_fit_height(max(0.05, H * series[si][t] / vmax)).move_to([b.get_center()[0], base, 0], aligned_edge=DOWN)
                            for si, b in enumerate(bars)], run_time=per)

        run(0, "first", 0)
        slow_bar = lanes[0][1][-1]
        self.beat("why", 1)
        self.play(slow_bar.animate(rate_func=rate_functions.there_and_back).scale(1.08), run_time=0.6)
        self.beat("feedback", 2)
        self.play(slow_bar.animate(rate_func=rate_functions.there_and_back).scale(1.08), run_time=0.6)
        run(1, "second", 3)

    # ---- compare + commands: side-by-side tradeoffs, and terminal usage ----------------------------------------

    @staticmethod
    def mark(kind, center, r, color, width=9):
        """Drawn tick or cross (paths, not glyphs: fonts lack ✓/✗ — NOTES #26). r = half-size of the mark."""
        c = center
        if kind == "tick":
            return VMobject(stroke_color=color, stroke_width=width).set_points_as_corners(
                [c + v * r for v in (LEFT * 0.85 + UP * 0.05, DOWN * 0.7 + LEFT * 0.15, UP * 0.8 + RIGHT * 0.9)])
        return VGroup(Line(c + (LEFT + UP) * r * 0.7, c + (RIGHT + DOWN) * r * 0.7),
                      Line(c + (LEFT + DOWN) * r * 0.7, c + (RIGHT + UP) * r * 0.7)).set_stroke(color, width)

    def role_style(self, role):
        """(fill, stroke, text) for a role slot (neutral, c1..c5); unknown/missing → neutral."""
        return T.ROLES[role if role in T.ROLES else "neutral"]

    def scene_compare(self, d, cap):
        """Two-column comparison: header labels, then one row per sentence; the winning cell gets a drawn tick,
        the other a cross and muted text.
        data: {title, subtitle?, left: {label, role?}, right: {label, role?}, rows: [{left, right, winner?}],
               winner?: "left"|"right"|"both"|"none" (default left; a row's own `winner` overrides), footer?}
        role: a theme role slot (neutral, c1..c5) colouring the column header. 2-5 rows.
        steps: title (sentence 0), row{i} (i+1), footer (len(rows)+1)."""
        title = fit(txt(d["title"], 52, weight="BOLD"), 13).to_edge(UP, buff=0.45)
        top = VGroup(title)
        if d.get("subtitle"):
            top.add(fit(txt(d["subtitle"], 30, T.MUTED), 13).next_to(title, DOWN, buff=0.18))
        col_w, gap = 6.3, 0.3
        xs = {"left": -(col_w + gap) / 2, "right": (col_w + gap) / 2}
        heads = VGroup()
        for side in ("left", "right"):
            fill, stroke, text = self.role_style(d[side].get("role"))
            h = RoundedRectangle(corner_radius=0.12 * T.RADIUS + 0.001, width=col_w, height=0.8, fill_color=fill,
                                 fill_opacity=1, stroke_color=stroke, stroke_width=max(3, T.BORDER_W))
            lab = fit(txt(d[side]["label"], 34, text, weight="BOLD"), col_w - 0.5).move_to(h)
            heads.add(VGroup(h, lab).move_to([xs[side], 0, 0]))
        heads.next_to(top, DOWN, buff=0.4)
        foot = fit(txt(d["footer"], 30, T.MUTED, weight="BOLD"), 13) if d.get("footer") else None
        # Rows share the space between the headers and the caption band (less the footer's line).
        n = len(d["rows"])
        y_top = heads.get_bottom()[1] - 0.2
        y_bot = CAPTION_TOP + 0.12 + (foot.height + 0.3 if foot else 0)
        pitch = min(1.1, (y_top - y_bot) / max(1, n))
        row_h = min(0.9, pitch - 0.14)
        rows = []
        for i, r in enumerate(d["rows"]):
            y = y_top - pitch * (i + 0.5)
            win = r.get("winner", d.get("winner", "left"))
            cells, marks, losers = VGroup(), [], []
            for side in ("left", "right"):
                p = panel(col_w, row_h, 0.1).move_to([xs[side], y, 0])
                c = p[-1]
                icon_c = c.get_left() + RIGHT * 0.45
                t = txt(r[side], 30)
                w0 = t.width
                if t.height > row_h * 0.55:
                    t.scale_to_fit_height(row_h * 0.55)
                t = fit(t, col_w - 1.1).move_to(icon_c + RIGHT * 0.4, aligned_edge=LEFT)
                cap_h = txt("H", 30).height * t.width / w0  # cap height at this text's final size
                on_baseline(t, y - cap_h / 2)
                if win != "none":  # "none": a plain row, no marks
                    won = win in (side, "both")
                    marks.append(self.mark("tick" if won else "cross", icon_c, min(0.2, row_h * 0.28),
                                           T.ACCENT if won else T.MUTED, 9 if won else 7))
                    if not won:
                        losers.append(t)
                cells.add(VGroup(p, t))
            rows.append((cells, marks, losers))
        self.beat("title", 0)
        self.play(FadeIn(top, shift=UP * 0.2), run_time=0.4)
        self.play(LaggedStart(*[FadeIn(h, shift=UP * 0.15) for h in heads], lag_ratio=0.3), run_time=0.5)
        for i, (cells, marks, losers) in enumerate(rows):
            self.beat(f"row{i}", i + 1)
            show = FadeIn(cells, shift=UP * 0.15, run_time=0.35)
            if marks:
                show = Succession(show, AnimationGroup(*[Create(m) for m in marks],
                                                       *[t.animate.set_color(T.MUTED) for t in losers], run_time=0.4))
            self.play(show, run_time=self.step_time(f"row{i}", i + 1, show.run_time))
        if foot:
            self.beat("footer", n + 1)
            foot.move_to([0, y_top - pitch * n - 0.15 - foot.height / 2, 0])
            self.play(FadeIn(foot, shift=UP * 0.15), run_time=self.fit_time(0.35, 1))

    def scene_commands(self, d, cap):
        """Terminal panel: each command types in after a `$` prompt over ~40% of its sentence; its note fades in
        beneath in muted text.
        data: {title, lines: [{cmd, note?}], footer?}
        steps: title (sentence 0), line{i} (i+1), footer (len(lines)+1)."""
        title = fit(txt(d["title"], 52, weight="BOLD"), 13).to_edge(UP, buff=0.45)
        foot = fit(txt(d["footer"], 30, T.MUTED, weight="BOLD"), 13) if d.get("footer") else None
        W, pad, bar_h = 12.4, 0.45, 0.5
        text_w = W - 2 * pad
        prompt0 = txt("$", 34, T.ACCENT, font=T.MONO)
        cmd_w = text_w - prompt0.width - 0.25
        # One shared size for every command so the terminal reads as one font; only a very long command shrinks
        # further on its own (never below what fits the width).
        need = [min(1.0, cmd_w / txt(ln["cmd"], 34, font=T.MONO).width) for ln in d["lines"]]
        shared = max(min(need), 0.7)
        scales = [min(shared, s) for s in need]
        notes = [fit(txt(ln["note"], 24, T.MUTED), cmd_w) if ln.get("note") else None for ln in d["lines"]]
        line_h = prompt0.height
        ref = txt("$H", 34, font=T.MONO)
        dollar_dy, cap_h = ref[0].get_bottom()[1] - ref[1].get_bottom()[1], ref[1].height
        heights = [line_h + (nt.height + 0.14 if nt else 0) for nt in notes]
        gap = 0.32
        content_h = sum(heights) + gap * (len(heights) - 1)
        avail = (title.get_bottom()[1] - 0.35) - (CAPTION_TOP + 0.15 + (foot.height + 0.3 if foot else 0))
        k = min(1.0, (avail - bar_h - 2 * pad) / content_h)  # too many/tall lines → shrink the whole body
        H = content_h * k + bar_h + 2 * pad
        p = panel(W, H, 0.14).move_to([0, title.get_bottom()[1] - 0.35 - H / 2, 0])
        body = p[-1]
        # Title bar = the card's top band, cut from the card itself so it follows the theme's corner radius.
        band = Rectangle(width=body.width + 0.2, height=bar_h).move_to(body.get_top(), aligned_edge=UP)
        strip = Intersection(body.copy(), band, fill_color=T.EMPTY, fill_opacity=1,
                             stroke_color=T.BORDER or T.EMPTY, stroke_width=T.BORDER_W if T.BORDER else 0)
        dots = VGroup(*[Dot(radius=0.08, color=T.MUTED) for _ in range(3)]).arrange(RIGHT, buff=0.14).move_to(
            strip.get_left() + RIGHT * 0.45, aligned_edge=LEFT)
        frame = VGroup(p, strip, dots)
        x0 = body.get_left()[0] + pad
        y = strip.get_bottom()[1] - pad
        items = []
        for i, ln in enumerate(d["lines"]):
            # Prompt and command share a baseline (the "$" glyph hangs below it, so place it by the offset measured
            # against "H" in the same font, not by its box).
            base = y - line_h * k * 0.8
            prompt = prompt0.copy().scale(k).move_to([x0, 0, 0], aligned_edge=LEFT).set_y(base + dollar_dy * k, direction=DOWN)
            s = scales[i] * k
            anchor = prompt.get_right() + RIGHT * 0.25 * k
            cmd = ln["cmd"]
            # Typed text = the first glyphs of the full, already-placed command (Text drops spaces from its glyphs),
            # so the baseline never jumps as descenders appear and nothing is re-laid out per frame.
            full = txt(cmd, 34, font=T.MONO).scale(s).move_to(anchor, aligned_edge=LEFT)
            on_baseline(full, base)
            glyphs = [sum(1 for ch in cmd[:n] if not ch.isspace()) for n in range(len(cmd) + 1)]
            cw = full.width / max(1, len(cmd))  # monospace advance: where the cursor sits after n chars

            def typed(n, full=full, glyphs=glyphs, cw=cw, anchor=anchor, base=base, cmd=cmd):
                shown = full[:glyphs[n]].copy()
                if n >= len(cmd):
                    return VGroup(shown)
                cursor = Rectangle(width=cw * 0.8, height=line_h * k * 0.95, fill_color=T.ACCENT, fill_opacity=1,
                                   stroke_width=0).move_to([anchor[0] + n * cw, base + cap_h * k / 2, 0], aligned_edge=LEFT)
                return VGroup(shown, cursor)

            nt = notes[i]
            if nt:
                nt = nt.copy().scale(k).move_to([anchor[0], prompt.get_bottom()[1] - 0.14 * k, 0], aligned_edge=UP + LEFT)
            items.append((prompt, typed, cmd, nt))
            y -= (heights[i] + gap) * k
        self.beat("title", 0)
        self.play(FadeIn(title, shift=UP * 0.2), run_time=0.4)
        self.play(FadeIn(frame, shift=UP * 0.15), run_time=0.4)
        for i, (prompt, typed, cmd, nt) in enumerate(items):
            step = f"line{i}"
            self.beat(step, i + 1)
            chars = ValueTracker(0)
            self.add(prompt, on_change(lambda chars=chars: int(chars.get_value()), typed))  # prompts appear instantly, like a shell
            t_type = max(0.6, self.span(step, i + 1) * 0.4) if self.sentences else 1.0  # ~40% of the sentence
            show = chars.animate(rate_func=linear, run_time=t_type).set_value(len(cmd))
            if nt:
                show = Succession(show, FadeIn(nt, shift=UP * 0.1, run_time=0.3))
            self.play(show, run_time=self.step_time(step, i + 1, t_type + (0.3 if nt else 0)))
        if foot:
            self.beat("footer", len(items) + 1)
            foot.next_to(p, DOWN, buff=0.3)
            self.play(FadeIn(foot, shift=UP * 0.15), run_time=self.fit_time(0.35, 1))

    # ---- alternatives: two ways to do the same thing, as two app windows side by side ------------------------------

    def scene_alternatives(self, d, cap):
        """Two windows side by side, each one alternative way to do the same thing (e.g. command line vs browser).
        Both windows appear empty with the title; each then fills in on its own sentence (terminal lines type in;
        browser fields, slider, button press, then log lines) and its one-line caption lands under it.
        data: {title, subtitle?, panels: [left, right], footer?}
          panel: {label (title-bar text), kind: "terminal"|"browser", role? (theme slot tinting the title bar),
                  caption? (one plain line under the window),
                  terminal: lines: [{cmd} | {out} | {comment}],
                  browser: url?, fields?: [{label, value}], slider?: {label, value (0-1: knob position, not shown)},
                           button?: str, log?: [str]}
          Keep each window to ~6 rows; anything taller is scaled down to fit, long lines shrink to the width.
        steps: title (sentence 0), left (1), right (2), footer (3)."""
        head = self.headline(d)
        W, gap, bar_h, pad = 6.55, 0.5, 0.5, 0.32
        xs = [-(W + gap) / 2, (W + gap) / 2]
        caps = [fit(txt(p["caption"], 28, T.MUTED), W) if p.get("caption") else None for p in d["panels"]]
        foot = fit(txt(d["footer"], 30, T.FG, weight="BOLD"), 13) if d.get("footer") else None
        cap_h = max([c.height for c in caps if c] + [0])
        below = (cap_h + 0.22 if cap_h else 0)  # caption line under the windows
        top = head.get_bottom()[1] - 0.4
        bottom = CAPTION_TOP + 0.12 + below + (foot.height + 0.3 if foot else 0)
        iw = W - 2 * pad
        built = [{"terminal": self.alt_terminal, "browser": self.alt_browser}[p["kind"]](p, iw) for p in d["panels"]]
        # Windows are sized to their fullest contents (both the same height), within what the frame leaves.
        body_extra = 0.25 + pad  # gap under the title bar + bottom padding
        H = min(top - bottom, max(2.8, bar_h + body_extra + max(c.height for c, _, _ in built)))
        windows, blocks, builds, live = [], [], [], []
        for i, p in enumerate(d["panels"]):
            chrome, inner = self.alt_window(p, W, H, bar_h, pad)
            chrome.move_to([xs[i], top - H / 2, 0])
            inner.move_to([xs[i], chrome[0][-1].get_bottom()[1] + inner.height / 2, 0])
            windows.append(chrome)
            content, anims, rows_live = built[i]
            # Built at natural size, then scaled down (never up) to the window body. Every animation is created
            # only after this (they're factories): `.animate`/Grow targets snapshot positions when constructed.
            avail_h = inner.height - body_extra
            if content.height > avail_h:
                content.scale(avail_h / content.height)
            content.move_to([inner.get_left()[0] + pad, inner.get_top()[1] - 0.25, 0], aligned_edge=UP + LEFT)
            blocks.append(content)
            if caps[i]:
                # Shared baseline: captions with and without descenders ("rows" vs "fields") line up.
                on_baseline(caps[i].set_x(xs[i]), chrome[0][-1].get_bottom()[1] - 0.22 - txt("H", 28).height)
                anims.append((lambda c=caps[i]: FadeIn(c, shift=UP * 0.1), 0.6))
            builds.append(anims)
            live += rows_live
        if foot:
            foot.set_y(windows[0][0][-1].get_bottom()[1] - below - 0.3 - foot.height / 2)
        # Centre windows + captions + footer between the headline and the caption band. The blocks hold the typed
        # rows' reference text, so they move too.
        group = VGroup(*windows, *[c for c in caps if c], *([foot] if foot else []))
        dy = (top + CAPTION_TOP + 0.12) / 2 - group.get_center()[1]
        for m in [*windows, *blocks, *[c for c in caps if c], *([foot] if foot else [])]:
            m.shift(UP * dy)
        # Typed rows draw nothing until their command starts. On top: added now, they'd sit under the window cards
        # that fade in later (draw order = add order).
        self.add(*[r.set_z_index(1) for r in live])

        steps = [("title", 0), ("left", 1), ("right", 2)] + ([("footer", 3)] if foot else [])
        last = max(0, len(self.sentences) - 1)

        def sentence(step, default):
            b = self.beats.get(step, default)
            return min(b[0] if isinstance(b, list) else b, last)

        # Play in the order the narration reaches them (beats may put the right window first).
        for name, default in sorted(steps, key=lambda s: (sentence(*s), s[1])):
            self.beat(name, default)
            if name == "title":
                self.play(FadeIn(head, shift=UP * 0.2), run_time=self.step_time(name, default, 0.4))
                self.play(LaggedStart(*[FadeIn(w, shift=UP * 0.15) for w in windows], lag_ratio=0.3),
                          run_time=self.step_time(name, default, 0.6))
            elif name == "footer":
                self.play(FadeIn(foot, shift=UP * 0.15), run_time=self.step_time(name, default, 0.35))
            else:
                anims = builds[default - 1]
                if not anims:
                    continue
                # Share the step's time by weight: typing a long command takes longer than a log line appearing.
                want = max(1.2, self.span(name, default) * 0.75) if self.sentences else 2.5
                run = self.step_time(name, default, want)
                total = sum(w for _, w in anims)
                self.play(Succession(*[prepare_animation(make()).set_run_time(run * w / total) for make, w in anims]),
                          run_time=run)
                # play() put a Group of the Succession's mobjects in the scene, typing trackers included. Fading a
                # tracker at scene end moves its value, the typed row rebuilds mid-fade and Manim fails ("zip()
                # argument 2 is longer than argument 1"). The trackers are done; take them out.
                self.remove(*[r.tracker for r in live])

    def alt_window(self, p, W, H, bar_h, pad):
        """Window chrome: card, title bar (three dots + label, tinted by role), URL pill for browsers.
        Returns (chrome, inner) — inner is the empty body rectangle (not drawn) the contents go in."""
        if p.get("kind") not in ("terminal", "browser"):
            raise ValueError(f"alternatives panel kind must be terminal or browser, got {p.get('kind')!r}")
        fill, _, text = self.role_style(p["role"]) if p.get("role") else (T.EMPTY, None, T.FG)
        card = panel(W, H, 0.14)
        body = card[-1]
        # Title bar = the card's top band, cut from the card itself so it follows the theme's corner radius.
        band = Rectangle(width=W + 0.2, height=bar_h).move_to(body.get_top(), aligned_edge=UP)
        strip = Intersection(body.copy(), band, fill_color=fill, fill_opacity=1,
                             stroke_color=T.BORDER or fill, stroke_width=T.BORDER_W if T.BORDER else 0)
        dots = VGroup(*[Dot(radius=0.075, color=T.MUTED) for _ in range(3)]).arrange(RIGHT, buff=0.13).move_to(
            strip.get_left() + RIGHT * 0.4, aligned_edge=LEFT)
        label = txt(p["label"], 26, text, weight="BOLD")
        parts = [card, strip, dots, label]
        if p["kind"] == "browser" and p.get("url"):
            # Browser bar: label on the left like a tab, the URL pill fills the rest of the bar.
            fit(label, W * 0.3).next_to(dots, RIGHT, buff=0.3)
            left = label.get_right()[0] + 0.3
            pill = RoundedRectangle(corner_radius=0.17, width=body.get_right()[0] - 0.2 - left, height=0.34, fill_color=T.BG,
                                    fill_opacity=1, stroke_color=T.BORDER or T.MUTED, stroke_width=2)
            pill.move_to([left, strip.get_center()[1], 0], aligned_edge=LEFT)
            url = fit(txt(p["url"], 20, T.MUTED, font=T.MONO), pill.width - 0.36).move_to(
                pill.get_left() + RIGHT * 0.18, aligned_edge=LEFT)
            parts += [pill, url]
        else:
            fit(label, W - 2 * (dots.width + 0.6)).move_to(strip)
        inner = Rectangle(width=W, height=strip.get_bottom()[1] - body.get_bottom()[1], stroke_width=0)
        return VGroup(*parts), inner

    def alt_terminal(self, p, iw):
        """Terminal rows: `$ cmd` types in (prompt, text and cursor rebuilt from reference text that moves with the
        block), `out` output and `# comment` lines fade in. Returns (block, [(factory, weight)], live rows)."""
        dim = interpolate_color(ManimColor(T.PANEL), ManimColor(T.MUTED), 0.7)  # comments: quieter than output
        block, anims, live = VGroup(), [], []
        # One shared size so the terminal reads as one font (floor 0.7x); only a still-too-long line shrinks further.
        shown = [ln["cmd"] if "cmd" in ln else ln.get("out", f"# {ln.get('comment', '')}") for ln in p.get("lines", [])]
        x_cmd0 = txt("$", 26, font=T.MONO).width + 0.2 + 0.15  # "$ " + right margin, as placed below (at full size)
        room = [iw - (x_cmd0 if "cmd" in ln else 0) for ln in p.get("lines", [])]
        need = [min(1.0, r / txt(t, 26, font=T.MONO).width) for t, r in zip(shown, room)] or [1.0]
        size = 26 * max(0.7, min(need))
        pitch = 0.52 * size / 26
        ref = txt("$H", size, font=T.MONO)
        dollar_dy, cap_h = ref[0].get_bottom()[1] - ref[1].get_bottom()[1], ref[1].height
        for i, ln in enumerate(p.get("lines", [])):
            base = -i * pitch
            if "cmd" in ln:
                cmd = ln["cmd"]
                prompt = txt("$", size, T.ACCENT, font=T.MONO).move_to([0, 0, 0], aligned_edge=LEFT)
                prompt.set_y(base + dollar_dy, direction=DOWN)
                x_cmd = prompt.get_right()[0] + 0.2
                full = fit(txt(cmd, size, font=T.MONO), iw - x_cmd - 0.15).move_to([x_cmd, 0, 0], aligned_edge=LEFT)
                s = full.height / txt(cmd, size, font=T.MONO).height
                on_baseline(full, base)
                cur = Rectangle(width=full.width / max(1, len(cmd)) * 0.8, height=cap_h * s * 1.35, fill_color=T.ACCENT,
                                fill_opacity=1, stroke_width=0).move_to([x_cmd, base + cap_h * s / 2, 0], aligned_edge=LEFT)
                row = VGroup(prompt, full, cur)  # reference only (never added); scaled/moved with the block
                block.add(row)
                glyphs = [sum(1 for ch in cmd[:n] if not ch.isspace()) for n in range(len(cmd) + 1)]
                chars = ValueTracker(-1)

                def typed(n, row=row, glyphs=glyphs, cmd=cmd):
                    if n < 0:  # not reached yet
                        return VGroup()
                    prompt, full, cur = row
                    shown = VGroup(prompt.copy(), full[:glyphs[n]].copy())
                    if n < len(cmd):  # monospace: the cursor sits n advances right of the command's left edge
                        shown.add(cur.copy().shift(RIGHT * n * full.width / len(cmd)))
                    return shown

                row_live = on_change(lambda chars=chars: math.floor(chars.get_value()), typed)
                row_live.tracker = chars
                live.append(row_live)
                anims.append((lambda chars=chars, n=len(cmd): chars.animate(rate_func=linear).set_value(n), 0.4 + len(cmd) / 18))
            else:
                is_out = "out" in ln
                t = txt(ln["out"] if is_out else f"# {ln['comment']}", size, T.MUTED if is_out else dim, font=T.MONO)
                t = fit(t, iw).move_to([0, 0, 0], aligned_edge=LEFT)
                on_baseline(t, base)
                block.add(t)
                anims.append((lambda t=t: FadeIn(t, shift=UP * 0.08), 0.5))
        return block, anims, live

    def alt_browser(self, p, iw):
        """Browser page: a form (labelled fields, a slider, a button that gets pressed) and, beside it, a progress log
        whose lines appear after the press. Returns (block, [(factory, weight)], [])."""
        block, anims = VGroup(), []
        has_form = bool(p.get("fields") or p.get("slider") or p.get("button"))
        fw = iw * 0.5 if has_form and p.get("log") else iw  # form column width; the log takes the rest
        labels = [f["label"] for f in p.get("fields", [])] + ([p["slider"]["label"]] if p.get("slider") else [])
        lab_w = min(fw * 0.36, max([txt(s, 22, T.MUTED).width for s in labels] + [0]) + 0.05)
        col = lab_w + 0.2 if labels else 0  # the input column starts here
        in_w = fw - col
        pitch, box_h = 0.56, 0.42
        y = 0.0
        for f in p.get("fields", []):
            lab = fit(txt(f["label"], 22, T.MUTED), lab_w).move_to([0, y, 0], aligned_edge=LEFT)
            box_ = Rectangle(width=in_w, height=box_h, fill_color=T.BG, fill_opacity=1,
                             stroke_color=T.BORDER or T.MUTED, stroke_width=2).move_to([col, y, 0], aligned_edge=LEFT)
            val = fit(txt(f["value"], 22), in_w - 0.26).move_to(box_.get_left() + RIGHT * 0.13, aligned_edge=LEFT)
            row = VGroup(lab, box_, val)
            block.add(row)
            anims.append((lambda row=row: FadeIn(row, shift=UP * 0.1), 0.5))
            y -= pitch
        if p.get("slider"):
            sl = p["slider"]
            v = min(1.0, max(0.0, float(sl.get("value", 0.5))))
            lab = fit(txt(sl["label"], 22, T.MUTED), lab_w).move_to([0, y, 0], aligned_edge=LEFT)
            track = Rectangle(width=in_w - 0.26, height=0.08, fill_color=T.EMPTY, fill_opacity=1, stroke_width=0).move_to(
                [col + 0.13, y, 0], aligned_edge=LEFT)
            filled = Rectangle(width=max(0.02, track.width * v), height=0.08, fill_color=T.ACCENT, fill_opacity=1,
                               stroke_width=0).move_to(track, aligned_edge=LEFT)
            knob = Dot(radius=0.12, color=T.ACCENT).set_stroke(T.BORDER or T.PANEL, 3).move_to(track.get_left())
            knob.set_z_index(1)  # the growing fill is added later; keep the knob on top of it
            row = VGroup(lab, track, knob)
            block.add(VGroup(row, filled))
            anims.append((lambda row=row: FadeIn(row, shift=UP * 0.1), 0.4))
            anims.append((lambda: AnimationGroup(GrowFromEdge(filled, LEFT), knob.animate.move_to(filled.get_right())), 0.6))
            y -= pitch
        if p.get("button"):
            t = fit(txt(p["button"], 24, T.ON_ACCENT, weight="BOLD"), in_w - 0.3)
            r = RoundedRectangle(corner_radius=0.1 * T.RADIUS + 0.001, width=in_w, height=0.48, fill_color=T.ACCENT,
                                 fill_opacity=1, stroke_color=T.BORDER or T.ACCENT, stroke_width=T.BORDER_W if T.BORDER else 0)
            btn = VGroup(r, t.move_to(r)).move_to([col, y - 0.04, 0], aligned_edge=LEFT)
            block.add(btn)
            anims.append((lambda: FadeIn(btn, shift=UP * 0.1), 0.35))
            anims.append((lambda: btn.animate(rate_func=rate_functions.there_and_back).scale(0.92), 0.4))  # the press
        if p.get("log"):
            x0 = fw + 0.25 if has_form else 0
            lines = VGroup(*[txt(s, 20, T.MUTED, font=T.MONO) for s in p["log"]]).arrange(DOWN, aligned_edge=LEFT, buff=0.14)
            fit(lines, iw - x0 - 0.36)
            form_h = (block.get_top()[1] - block.get_bottom()[1]) if has_form else 0
            top = block.get_top()[1] if has_form else 0.0
            logbox = Rectangle(width=iw - x0, height=max(form_h, lines.height + 0.36), fill_color=T.BG, fill_opacity=1,
                               stroke_color=T.BORDER or T.MUTED, stroke_width=2).move_to([x0, top, 0], aligned_edge=UP + LEFT)
            lines.move_to(logbox.get_corner(UP + LEFT) + RIGHT * 0.18 + DOWN * 0.18, aligned_edge=UP + LEFT)
            block.add(VGroup(logbox, lines))
            anims.append((lambda: FadeIn(logbox), 0.25))
            anims += [(lambda ln=ln: FadeIn(ln, shift=UP * 0.06), 0.4) for ln in lines]
        return block, anims, []

    # ---- flow: any figure described as data (panels, nodes with shape + role, edges, steps) --------------------

    def headline(self, d, size=52):
        """Optional title (+ muted subtitle) at the top of the frame, fitted to its width; None without a title."""
        if not d.get("title"):
            return None
        title = fit(txt(d["title"], size, weight="BOLD"), 13).to_edge(UP, buff=0.45)
        head = VGroup(title)
        if d.get("subtitle"):
            head.add(fit(txt(d["subtitle"], 30, T.MUTED), 13).next_to(title, DOWN, buff=0.18))
        return head

    def scene_flow(self, d, cap):
        """Generic animated figure. Layout comes from layout.py; nothing here is specific to one figure.
        All parts start ghosted and are revealed/animated by `steps` (figure mode: fixed holds; narrated: beats).
        data: {title?, subtitle?, mode?, roles?, panels?, nodes: [{id, label, sub?, role?, shape?, art?: "wave"|"lines",
               panel?, ...}], edges, steps}. A title sits at the top and the figure is laid out (and vertically
        centred) in the space left between it and the caption band. Step names are the steps' own `id`s."""
        roles = d.get("roles", {})

        def style(role):
            slot = roles.get(role, role if role in T.ROLES else "neutral")
            if slot not in T.ROLES:
                raise ValueError(f"unknown role slot {slot!r} (role {role!r})")
            return T.ROLES[slot]

        figure = d.get("mode") == "figure"
        head = self.headline(d)
        # The figure's box: below the headline (or the frame's top margin), above the captions (narrated) or the
        # frame's bottom margin (silent figure mode, no captions).
        top = head.get_bottom()[1] - 0.35 if head else 3.65
        bottom = -3.45 if figure else CAPTION_TOP + 0.12
        built = {n["id"]: self.flow_node(n, style) for n in d["nodes"]}
        sizes = {k: (m.width, m.height) for k, m in built.items()}
        label_w = {(e["from"], e["to"]): txt(e["label"], 20, T.MUTED).width for e in d.get("edges", []) if e.get("label")}
        geo = layout_graph(d, sizes, area=(13.6, top - bottom), center=(0, (top + bottom) / 2), label_w=label_w)
        k = geo["scale"]
        for nid, m in built.items():
            m.scale(k).move_to([*geo["nodes"][nid]["center"], 0])

        frames = VGroup()
        for pnl in d.get("panels", []):
            x0, y0, x1, y1 = geo["panels"][pnl["id"]]["rect"]
            fill, stroke, text = style(pnl.get("role", "neutral"))
            frame = RoundedRectangle(corner_radius=0.18 * max(T.RADIUS, 0.3), width=x1 - x0, height=y1 - y0,
                                     fill_color=fill, fill_opacity=0.35, stroke_color=stroke, stroke_width=3).move_to([(x0 + x1) / 2, (y0 + y1) / 2, 0])
            tag = self.flow_pill(pnl["label"], style(pnl.get("role", "neutral")), 26).scale(k)
            tag.move_to(frame.get_corner(UP + LEFT), aligned_edge=UP + LEFT).shift(RIGHT * 0.25 * k + DOWN * 0.2 * k)
            parts = [frame, tag]
            if pnl.get("sub"):
                parts.append(txt(pnl["sub"], 22, T.MUTED).scale(k).next_to(tag, RIGHT, buff=0.25 * k))
            frames.add(VGroup(*parts))

        rails = {}
        for r in geo["rails"]:
            line = VMobject(stroke_color=T.MUTED, stroke_width=3).set_points_as_corners([[x, y, 0] for x, y in r["points"]])
            shown = DashedVMobject(line, num_dashes=max(6, int(line.get_arc_length() / 0.14))) if r["dashed"] else line.copy()
            tip = Polygon([0, 0, 0], [-0.16, 0.07, 0], [-0.16, -0.07, 0], fill_color=T.MUTED, fill_opacity=1, stroke_width=0)
            (x1, y1), (x2, y2) = r["points"][-2], r["points"][-1]
            tip.rotate(__import__("math").atan2(y2 - y1, x2 - x1), about_point=[0, 0, 0]).shift([x2, y2, 0])
            parts = [shown, tip]
            if r.get("label"):
                mid = line.point_from_proportion(0.5)
                parts.append(txt(r["label"], 20, T.MUTED).scale(k).next_to(mid, UP, buff=0.08))  # same scale the gap was reserved at
            g = VGroup(*parts).set_z_index(-1)  # rails pass behind boxes
            g.shown, g.tip = shown, tip
            rails[(r["from"], r["to"])] = (g, line)

        # Centre what is actually drawn (stack offsets, rail labels, loop-back floors) in the figure's box; the
        # layout only centres its own node/panel rectangles. Packet paths (`line`) move with their rails.
        drawn = VGroup(frames, *built.values(), *[g for g, _ in rails.values()])
        dy = (top + bottom) / 2 - drawn.get_center()[1]
        for m in [*frames, *built.values(), *[x for pair in rails.values() for x in pair]]:
            m.shift(UP * dy)

        # A wave first reached by a flow starts flat (silence) and rises when the packets land.
        first = {}
        for st in d["steps"]:
            ids = st.get("targets") or st.get("path") or [st.get("target")]
            for i in ids:
                first.setdefault(i, st)
        for nid, m in built.items():
            st = first.get(nid)
            if getattr(m, "wave", None) and st and st["do"] == "flow" and st["path"][-1] == nid:
                m.wave_h = [b.height for b in m.wave]  # final (scaled) heights, restored by the rise
                for b in m.wave:
                    b.stretch_to_fit_height(0.03 * k)  # a linear stretch, so stretching back restores the bar exactly

        def rail_opacity(g, a):
            # Stroke/tip only: set_opacity on a polyline would also turn on its fill (filled wedges behind rails).
            g.shown.set_stroke(opacity=a)
            g.tip.set_fill(opacity=a)
            for extra in g[2:]:
                extra.set_opacity(a)
            return g

        revealed = set()
        for m in built.values():
            m.set_opacity(T.GHOST)
        for g, _ in rails.values():
            rail_opacity(g, T.GHOST)
        self.play(*([FadeIn(head, shift=UP * 0.2)] if head else []), FadeIn(frames), *[FadeIn(m) for m in built.values()],
                  *[FadeIn(g) for g, _ in rails.values()], run_time=0.6)

        def unghost(ids):
            anims = []
            for i in ids:
                if i not in built:
                    raise ValueError(f"step references unknown node {i!r}")
                if i not in revealed:
                    revealed.add(i)
                    anims.append(built[i].animate.set_opacity(1))
            for (a, b), (g, _) in rails.items():
                if a in revealed and b in revealed and (a, b) not in revealed:
                    revealed.add((a, b))
                    # Tip and label first: .animate snapshots g now, so anything set after would be undone.
                    g.tip.set_fill(opacity=1)
                    for extra in g[2:]:
                        extra.set_opacity(1)
                    anims.append(g.animate(rate_func=rate_functions.smooth).set_stroke(opacity=1))
            return anims

        def reveal_first(ids):
            anims = unghost(ids)
            if anims:  # already visible (e.g. revealed by an earlier flow) → nothing to animate
                self.play(*anims, run_time=0.3)

        def packets(path_ids, kind, share=1):
            pts = []
            for a, b in zip(path_ids, path_ids[1:]):
                if (a, b) not in rails:
                    raise ValueError(f"flow step uses {a!r} → {b!r}, which is not an edge")
                seg = list(rails[(a, b)][1].get_anchors())
                pts += seg if not pts else seg[1:]
            path = VMobject().set_points_as_corners(pts)
            fill = T.ROLES[T.PACKETS.get(kind, "c4")][1]
            shape = {"request": lambda: Square(0.2), "response": lambda: Dot(radius=0.11),
                     "change": lambda: Square(0.18).rotate(__import__("math").pi / 4)}[kind]
            dots = [shape().set_fill(fill, 1).set_stroke(T.BG, 2).move_to(pts[0]) for _ in range(3)]
            run = self.fit_time(min(2.2, 0.55 + path.get_arc_length() * 0.12), share)
            self.play(LaggedStart(*[MoveAlongPath(dot, path, rate_func=rate_functions.ease_in_out_sine) for dot in dots], lag_ratio=0.25), run_time=run)
            self.remove(*dots)

        figure = d.get("mode") == "figure"
        for i, st in enumerate(d["steps"]):
            if not figure:
                self.beat(st.get("id", f"step{i}"), i)
            do = st["do"]
            if do in ("reveal", "highlight"):
                ghosted = [t for t in st["targets"] if t not in revealed]
                anims = unghost(st["targets"])
                if do == "highlight":
                    # `.animate` stores its target on the mobject (generate_target), so a second .animate on the same
                    # node overwrites the first one's target: reveal + pulse together left a ghosted node ghosted.
                    # Reveal first, and build the pulse only after that has played.
                    def pulse():
                        return [built[t].animate(rate_func=rate_functions.there_and_back).scale(1.06) for t in st["targets"]]
                    if ghosted:
                        self.play(*anims, run_time=self.fit_time(0.3, 2))
                        self.play(*pulse(), run_time=self.fit_time(0.45, 1))
                    else:
                        self.play(*anims, *pulse(), run_time=self.fit_time(0.5, 1))
                elif anims:
                    self.play(*anims, run_time=0.5)
            elif do == "flow":
                anims = unghost(st["path"])
                if anims:
                    self.play(*anims, run_time=0.4)
                packets(st["path"], st.get("kind", "request"), share=2 if st.get("back") else 1)
                # Pulse the node the packets reach, so every flow visibly lands (small packets alone read as still).
                # A flat wave rises instead (never both: a node pulse and bar animations would fight over the bars).
                end = built[st["path"][-1]]
                if getattr(end, "wave_h", None):
                    rise = [b.animate(rate_func=rate_functions.ease_out_back).stretch_to_fit_height(h)
                            for b, h in zip(end.wave, end.wave_h)]
                    end.wave_h = None
                    self.play(LaggedStart(*rise, lag_ratio=0.06), run_time=self.fit_time(0.7, 1))
                else:
                    self.play(end.animate(rate_func=rate_functions.there_and_back).scale(1.07), run_time=self.fit_time(0.45, 1))
                if st.get("back"):
                    self.flow_return(st["path"], st["back"], rails)
            elif do == "diagonal":
                m = built[st["target"]]
                reveal_first([st["target"]])
                fill, stroke, _ = style(st.get("role", d["nodes"][[n["id"] for n in d["nodes"]].index(st["target"])].get("role", "neutral")))
                cells = [c for c in m.cells if c.diag]
                self.play(LaggedStart(*[c[0].animate.set_fill(fill, 1).set_stroke(stroke, 4) for c in cells], lag_ratio=0.35), run_time=0.4 + 0.25 * len(cells))
                self.bring_to_front(*[c[1] for c in cells])  # animated rects are drawn last; put labels back on top
            elif do == "cells":
                m = built[st["target"]]
                reveal_first([st["target"]])
                fill, stroke, _ = style(st.get("role", "c4"))
                pick = [c for c in m.cells if [c.r, c.c] in st["at"]]
                self.play(*[c[0].animate.set_fill(fill, 1).set_stroke(stroke, 4) for c in pick], run_time=0.4)
                self.bring_to_front(*[c[1] for c in pick])
            elif do == "bars":
                m = built[st["target"]]
                reveal_first([st["target"]])
                self.play(*[f.animate.stretch_to_fit_width(max(0.03, t.width * pv), about_edge=LEFT)
                            for f, t, pv in m.fills], run_time=0.8)
            else:
                raise ValueError(f"unknown step {do!r}")
            if figure:
                self.wait(st.get("hold", 0.8))

    def step_time(self, step, default, want):
        """Run time for one step's animation: at most ~90% of its sentence (so short sentences don't push later
        steps late and the scene past its narration) and never past the scene's fade-out."""
        return self.fit_time(min(want, max(0.3, self.span(step, default) * 0.9)), 1) if self.sentences else want

    def fit_time(self, want, share):
        """Shrink an animation so it (and `share - 1` more like it) ends before the scene's fade-out; a step that
        starts on the last sentence would otherwise push the scene past its narration and break the concat sync."""
        left = self.scene_end - 0.4 - self.time
        return max(0.3, min(want, left / share))

    def flow_return(self, path, kind, rails):
        """Response packets travel back along the same rails (reversed geometry, same edges)."""
        pts = []
        for a, b in zip(path, path[1:]):
            seg = list(rails[(a, b)][1].get_anchors())
            pts += seg if not pts else seg[1:]
        path_obj = VMobject().set_points_as_corners(list(reversed(pts)))
        fill = T.ROLES[T.PACKETS.get(kind, "c3")][1]
        dots = [Dot(radius=0.11).set_fill(fill, 1).set_stroke(T.BG, 2).move_to(path_obj.get_start()) for _ in range(3)]
        run = self.fit_time(min(2.2, 0.55 + path_obj.get_arc_length() * 0.12), 1)
        self.play(LaggedStart(*[MoveAlongPath(dot, path_obj, rate_func=rate_functions.ease_in_out_sine) for dot in dots], lag_ratio=0.25), run_time=run)
        self.remove(*dots)

    def rich(self, label, size, color, weight="BOLD"):
        """Text with `_{...}` subscripts drawn as smaller, lowered text — fonts lack most Unicode subscripts
        (e.g. ₙ), so never rely on those glyphs. Plain labels go straight through txt()."""
        if "_{" not in label:
            return txt(label, size, color, weight=weight)
        parts = VGroup()
        for chunk in re.split(r"(_\{[^}]*\})", label):
            if not chunk:
                continue
            gap = 0.02 + (len(chunk) - len(chunk.lstrip(" "))) * size * 0.006  # keep authored spaces as gaps
            if chunk.startswith("_{"):
                sub = txt(chunk[2:-1], size * 0.62, color, weight=weight)
                sub.next_to(parts, RIGHT, buff=0.02).align_to(parts, DOWN).shift(DOWN * sub.height * 0.35)
                parts.add(sub)
            else:
                t = txt(chunk.strip(" ") or " ", size, color, weight=weight)
                if len(parts):
                    t.next_to(parts, RIGHT, buff=gap).align_to(parts[0], DOWN)
                parts.add(t)
        return parts

    def flow_pill(self, label, st, size):
        fill, stroke, text = st
        t = self.rich(label, size, text)
        r = RoundedRectangle(corner_radius=(t.height + 0.3) / 2, width=t.width + 0.5, height=t.height + 0.3,
                             fill_color=fill, fill_opacity=1, stroke_color=stroke, stroke_width=3)
        return VGroup(r, t.move_to(r))

    def flow_node(self, n, style):
        """Build one node, centred at the origin, from its shape + role. Sizes are measured by the layout.
        A wave node keeps its bars as `.wave` so a flow can make them rise."""
        art = {}
        m = self.flow_shape(n, style, art)
        if "wave" in art:
            m.wave = art["wave"]
        return m

    def flow_art(self, kind, nid, width, fill, stroke):
        """Decoration under a node's label, drawn (not glyphs). "wave": a row of bars in the role colour, heights
        from the node id (crc32, not hash(): Python salts str hashes per process, so frames would differ per render);
        "lines": three grey rounded text-line bars (a document)."""
        if kind == "wave":
            n_bars = max(9, int(width / 0.13))
            pitch = width / n_bars
            bars = VGroup()
            for i in range(n_bars):
                r = (zlib.crc32(f"{nid}:{i}".encode()) % 1000) / 999
                env = 0.45 + 0.55 * math.sin(math.pi * (i + 0.5) / n_bars)  # louder in the middle, like speech
                h = 0.07 + 0.36 * r * env
                bars.add(Rectangle(width=pitch * 0.55, height=h, fill_color=stroke, fill_opacity=1, stroke_width=0)
                         .move_to([i * pitch, 0, 0]))
            return bars
        if kind == "lines":
            grey = interpolate_color(ManimColor(fill), ManimColor(T.MUTED), 0.55)
            return VGroup(*[RoundedRectangle(corner_radius=0.045, width=width * f, height=0.09, fill_color=grey,
                                             fill_opacity=1, stroke_width=0) for f in (1.0, 0.86, 0.6)]
                          ).arrange(DOWN, buff=0.1, aligned_edge=LEFT)
        raise ValueError(f"unknown node art {kind!r} (node {nid!r}); use wave or lines")

    def flow_shape(self, n, style, art):
        fill, stroke, text = style(n.get("role", "neutral"))
        shape = n.get("shape", "box")

        def label_block(size=26):
            parts = [self.rich(n["label"], size, text)] if n.get("label") else []
            if n.get("sub"):
                parts.append(txt(n["sub"], 20, T.MUTED))
            block = VGroup(*parts).arrange(DOWN, buff=0.08)
            if not n.get("art"):
                return block
            a = self.flow_art(n["art"], n["id"], max(block.width, 1.6), fill, stroke)
            if n["art"] == "wave":
                art["wave"] = a
            # Centre the art under the label; the node grows to hold it, and the layout measures the node as built.
            return VGroup(block, a.next_to(block, DOWN, buff=0.18)) if len(block) else a

        def card(content, pad=0.3, min_w=1.3):
            r = RoundedRectangle(corner_radius=0.12 * max(T.RADIUS, 0.3), width=max(content.width + 2 * pad, min_w),
                                 height=content.height + 2 * pad * 0.7, fill_color=fill, fill_opacity=1,
                                 stroke_color=stroke, stroke_width=3)
            return VGroup(r, content.move_to(r))

        if shape == "pill":
            return self.flow_pill(n["label"], (fill, stroke, text), 24)
        if shape == "trapezoid":
            lb = label_block(24)
            w, h = max(1.5, lb.width + 0.5), max(1.3, lb.height + 0.8)
            poly = Polygon([-w / 2, h / 2, 0], [w / 2, h * 0.3, 0], [w / 2, -h * 0.3, 0], [-w / 2, -h / 2, 0],
                           fill_color=fill, fill_opacity=1, stroke_color=stroke, stroke_width=3)
            return VGroup(poly, lb.move_to(poly))
        if shape == "matrix":
            rows, cols = n["rows"], n["cols"]
            cw, ch = 0.95, 0.5
            row_st, col_st = style(n.get("row_role", "neutral")), style(n.get("col_role", "neutral"))
            g = VGroup()
            cells = []
            for j, c in enumerate(cols):  # column headers above
                g.add(self.flow_chip(c, col_st, cw, ch).move_to([(j + 1) * (cw + 0.08), 0, 0]))
            for i, r in enumerate(rows):
                y = -(i + 1) * (ch + 0.08)
                g.add(self.flow_chip(r, row_st, cw * 0.7, ch).move_to([0.1, y, 0]))
                for j, c in enumerate(cols):
                    plain = any(sym in (r + c) for sym in ("…", "⋮"))
                    label = "…" if plain else f"{r}·{c}"
                    cell = self.flow_chip(label, style("neutral"), cw, ch, size=18)
                    cell.move_to([(j + 1) * (cw + 0.08), y, 0])
                    cell.r, cell.c, cell.diag = i, j, (i == j and n.get("diagonal", False))
                    cells.append(cell); g.add(cell)
            g.move_to([0, 0, 0])
            g.cells = cells
            return g
        if shape == "bars":
            label_w = max(txt(name, 22, T.FG, weight="BOLD").width for name, _ in n["bars"])
            rows, fills = VGroup(), []
            for name, pv in n["bars"]:
                lab = txt(name, 22, T.FG, weight="BOLD")
                track = Rectangle(width=2.2, height=0.2, fill_color=T.EMPTY, fill_opacity=1, stroke_width=0)
                pct = txt(f"{round(pv * 100)}%", 22, T.FG, font=T.MONO)
                lab.move_to([0, 0, 0], aligned_edge=LEFT)
                track.next_to([label_w, 0, 0], RIGHT, buff=0.2)
                pct.next_to(track, RIGHT, buff=0.2)
                # Starts collapsed at the left edge; the `bars` step grows it to its share of the track.
                bar_fill = Rectangle(width=0.03, height=0.2, fill_color=stroke, fill_opacity=1, stroke_width=0).move_to(track, aligned_edge=LEFT)
                fills.append((bar_fill, track, pv))
                rows.add(VGroup(lab, track, bar_fill, pct))
            rows.arrange(DOWN, aligned_edge=LEFT, buff=0.18)
            c = card(rows, pad=0.25)
            c.fills = fills
            return c
        content = label_block()
        if n.get("items"):
            chips = VGroup(*[self.flow_chip(it, style("neutral"), None, 0.42, size=20) for it in n["items"]])
            chips.arrange_in_grid(cols=min(3, len(chips)), buff=0.12, cell_alignment=LEFT)
            content = VGroup(content, chips).arrange(DOWN, buff=0.25)
        c = card(content)
        if shape == "stack":  # a batch: two offset outlines behind the card
            back = [c[0].copy().set_fill(fill, 1).shift(RIGHT * 0.1 * k + DOWN * 0.1 * k).set_z_index(-0.5) for k in (2, 1)]
            return VGroup(*back, c)
        return c

    def flow_chip(self, label, st, w, h, size=22):
        fill, stroke, text = st
        t = self.rich(label, size, text)
        width = w if w else t.width + 0.35
        if t.width > width - 0.12:
            t.scale_to_fit_width(width - 0.12)
        r = RoundedRectangle(corner_radius=0.08, width=width, height=h, fill_color=fill, fill_opacity=1,
                             stroke_color=stroke, stroke_width=2)
        return VGroup(r, t.move_to(r))

    def scene_source(self, d, cap):
        """Standard closing card built from the spec's meta.source {kind, url, credit?} — same for every video."""
        src = SPEC["meta"]["source"]
        head = {"repo": "Check out the repo", "blog": "Read the full post at", "paper": "Read the full paper at"}[src["kind"]]
        url = src["url"].removeprefix("https://").removeprefix("http://").rstrip("/")
        h = fit(txt(head, 72, weight="BOLD"), 13).shift(UP * 0.7)
        u = fit(txt(url, 40, T.ACCENT, font=T.MONO), 13).next_to(h, DOWN, buff=0.45)
        parts = [h, u]
        if src.get("credit"):
            parts.append(fit(txt(src["credit"], 30, T.MUTED), 13).next_to(u, DOWN, buff=0.4))
        self.play(FadeIn(h, shift=UP * 0.2), run_time=0.35)
        self.play(*[FadeIn(m, shift=UP * 0.1) for m in parts[1:]], run_time=0.35)

    def scene_outro(self, d, cap):
        h = fit(txt(d["headline"], 96, weight="BOLD"), 13).shift(UP * 0.6)
        u = fit(txt(d["url"], 44, T.ACCENT, font=T.MONO), 13).next_to(h, DOWN, buff=0.5)  # long URLs shrink to fit
        self.beat("headline", 0)
        self.play(FadeIn(h, shift=UP * 0.2), FadeIn(cap), run_time=0.35)
        self.beat("url", 1)  # same sentence when the outro has only one
        self.play(FadeIn(u, shift=UP * 0.15), run_time=0.35)
