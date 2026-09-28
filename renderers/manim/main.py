"""Render videos/<video>/spec.json as one Manim scene. Usage: SPEC=<video> uv run manim -qh main.py Explainer

Env: SPEC=<video folder name in videos/> (required), THEME=<preset in theme.py>, SCENES=<comma-separated scene ids to render only those>.
Needs out/<video>/voice/timing.json from scripts/voice.py (scene lengths + caption cues come from the narration).
"""

import json
import os
from functools import lru_cache
from pathlib import Path

from manim import (
    DOWN, LEFT, RIGHT, UP, Arrow, Create, FadeIn, FadeOut, GrowFromEdge, Line, Rectangle, Transform,
    LaggedStart, RoundedRectangle, Scene, Square, Text, ValueTracker, VGroup, VMobject, config, linear, rate_functions,
)

import theme as T

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


def txt(s, size=36, color=T.FG, font=T.FONT, weight=None):
    # font_size is in pt-ish units; ×0.75 keeps sizes close to the Remotion px values.
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
    def construct(self):
        for s in SPEC["scenes"]:
            if ONLY and s["id"] not in ONLY:
                continue
            start = self.time
            timing = TIMING[s["id"]]
            self.scene_start, self.sentences, self.beats = start, timing["sentences"], s["data"].get("beats", {})
            self.add(*self.cues(timing["cues"], start))
            # Scene templates still accept a caption to fade in; captions now come from the narration cues.
            getattr(self, f"scene_{s['type']}")(s["data"], VGroup())
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

    def beat(self, step, default, frac=0.0):
        """Hold until the narration sentence this step belongs to starts (spec data.beats overrides the default);
        frac > 0 lands partway through that sentence. Steps are paced by the voice, so visuals change as things
        are said instead of all up front."""
        i = min(self.beats.get(step, default), len(self.sentences) - 1)
        target = self.scene_start + self.sentences[i] + frac * self.span(step, default)
        if target - self.time > 1 / config.frame_rate:
            self.wait(target - self.time)

    def span(self, step, default):
        """Seconds from this step's sentence start to the next sentence (or 2 s for the last one)."""
        i = min(self.beats.get(step, default), len(self.sentences) - 1)
        nxt = self.sentences[i + 1] if i + 1 < len(self.sentences) else self.sentences[i] + 2
        return nxt - self.sentences[i]

    def caption(self, text):
        t = fit(txt(text, 34, T.CAPTION_FG), 13.4)
        bg = Rectangle(width=t.width + 0.4, height=t.height + 0.3, fill_color=T.CAPTION_BG,
                       fill_opacity=T.CAPTION_OPACITY, stroke_width=0).move_to(t)
        return VGroup(bg, t).to_edge(DOWN, buff=0.55)

    def scene_title(self, d, cap):
        title = txt(d["title"], 160, T.ACCENT, weight="BOLD").shift(UP * 1.2)
        sub = txt(d["subtitle"], 56).next_to(title, DOWN, buff=0.4)
        kick = txt(d["kicker"], 36, T.MUTED).next_to(sub, DOWN, buff=0.6)
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
        L, R = d["left"], d["right"]
        n = R["decisions"]
        answers = ["yes" if (i * 7) % 5 < 3 else "no" for i in range(n)]
        js = "[" + ",".join(f'"{a}"' for a in answers) + "]"
        clock = ValueTracker(0)  # measured seconds
        scale = d.get("time_scale", 1)  # video seconds per measured second

        def lane(x):
            return panel(820 / PX, 560 / PX, 0.15).move_to([x, 0.6, 0])

        ll, rl = lane(-3.3), lane(3.3)
        top = txt(f"21 decisions, {d['note']}", 40, T.MUTED).to_edge(UP, buff=0.4)
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
            return txt(f"{done} / {L['tokens']} tokens · {done} passes", 30, T.MUTED).move_to(
                ll.get_corner(DOWN + LEFT), aligned_edge=DOWN + LEFT).shift(RIGHT * 0.27 + UP * 0.22)

        def grid(done):
            cells = VGroup()
            for a in answers:
                fill = (T.ACCENT if a == "yes" else T.MUTED) if done else T.EMPTY
                r = RoundedRectangle(corner_radius=0.07 * max(T.RADIUS, 0.01), width=0.68, height=0.44, fill_color=fill, fill_opacity=1,
                                     stroke_color=T.BORDER or fill, stroke_width=3 if T.BORDER else 0)
                cells.add(VGroup(r, txt(a if done else "", 26, T.ON_ACCENT, weight="BOLD").move_to(r)) if done else r)
            return cells.arrange_in_grid(rows=3, cols=7, buff=0.1).next_to(rt, DOWN, aligned_edge=LEFT, buff=1.2)

        rfoot = fit(txt(f"{R['tokens']} output tokens · {R.get('passes', 1)} pass · {n} answers", 30, T.MUTED), 820 / PX - 0.6).move_to(
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
        big = txt(f"{d['speedup']} faster", 90, T.ACCENT, weight="BOLD").move_to(DOWN * 2.2)
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
        q = txt(f"Q: {d['question']}", 36, T.MUTED).to_edge(UP, buff=0.45)
        head = txt("Next-token scores (whole vocabulary)", 30, weight="BOLD").move_to([-7.1 + 160 / PX, 2.55, 0], aligned_edge=LEFT)
        rows = []
        for i, v in enumerate(d["vocab"]):
            y = 1.95 - i * 70 / PX
            tok = txt(v["tok"], 34, font=T.MONO).move_to([-7.1 + 310 / PX, y, 0], aligned_edge=RIGHT)
            b = bar((v["logit"] - 15) * 50 / PX, 40 / PX, T.MUTED).move_to([-7.1 + 335 / PX, y, 0], aligned_edge=LEFT)
            val = txt(f"{v['logit']:.1f}", 28, T.MUTED, font=T.MONO).next_to(b, RIGHT, buff=0.15)
            rows.append((v, VGroup(tok, b, val)))
        rest = txt("… every other token in the vocabulary", 28, T.MUTED).move_to(
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
        ignored = txt("ignored", 26, T.MUTED, weight="BOLD").next_to(
            next(r for v, r in rows if v["tok"] == "Account"), RIGHT, buff=0.25)
        hl = [r[0].animate.set_color(T.ACCENT) for v, r in rows if v.get("slot")] + \
             [r[1].animate.set_fill(T.ACCENT) for v, r in rows if v.get("slot")]
        self.play(*dims, *hl, run_time=0.6)
        arrow = txt("→", 64, T.ACCENT).move_to([0.3, 0.9, 0])
        sm = txt("softmax over A, B, C", 30, weight="BOLD").move_to([1.1, 1.95, 0], aligned_edge=LEFT)
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
        acct = next(r for v, r in rows if v["tok"] == "Account")
        self.play(FadeIn(ignored, shift=LEFT * 0.2), acct.animate(rate_func=rate_functions.there_and_back).scale(1.06), run_time=0.6)

    def scene_branch(self, d, cap):
        n = d["branches"]
        left = -7.1 + 160 / PX
        label = txt(d["prefix_label"], 30, weight="BOLD").move_to([left, 1.55, 0], aligned_edge=LEFT)
        track = bar(600 / PX, 80 / PX, T.EMPTY).move_to([left, 1.0, 0], aligned_edge=LEFT)
        prefill = bar(600 / PX, 80 / PX, T.MUTED).move_to(track)
        once = txt("prefilled once", 26, T.MUTED).next_to(track, DOWN, aligned_edge=LEFT, buff=0.12)
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
        n = len(d["cards"])
        w = min(500, (1780 - 50 * (n - 1)) / n)  # up to 3 cards at full width; more cards share the frame
        cards = VGroup()
        for c in d["cards"]:
            p = panel(w / PX, 380 / PX, 0.18)
            r = p[-1]
            lab = fit(txt(c["label"], 30, T.MUTED), r.width - 0.4).move_to(r.get_top(), aligned_edge=UP).shift(DOWN * 0.35)
            val = fit(txt(c["value"], 70, T.ACCENT, weight="BOLD"), r.width - 0.5).move_to(r)
            cmp = fit(txt(c["compare"], 30), r.width - 0.4).move_to(r.get_bottom(), aligned_edge=DOWN).shift(UP * 0.35)
            cards.add(VGroup(p, lab, val, cmp))
        cards.arrange(RIGHT, buff=50 / PX).shift(UP * 0.5)
        foot = fit(txt(d["footnote"], 32, weight="BOLD"), 13).next_to(cards, DOWN, buff=0.55) if d.get("footnote") else None
        steps = [(f"card{i}", i, c) for i, c in enumerate(cards)] + ([("footnote", n, foot)] if foot else [])
        # Play in the order the narration reaches them (beats can put the footnote before some cards).
        order = sorted(steps, key=lambda st: (min(self.beats.get(st[0], st[1]), len(self.sentences) - 1), st[1]))
        for name, default, m in order:
            self.beat(name, default)
            self.play(FadeIn(m, shift=UP * 0.2), run_time=0.35)

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
            p = panel(11.6, 0.95, 0.12).move_to([0, 1.55 - i * 1.3, 0])
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
            foot = txt(d["footer"], 30, T.MUTED, font=T.MONO).next_to(rows[-1][0], DOWN, buff=0.5)
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
            top = 1.55 - pi * 2.35
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
            foot = fit(txt(d["footer"], 32, T.ACCENT, weight="BOLD"), 12).move_to([0, -2.85, 0])
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

    def scene_outro(self, d, cap):
        h = txt(d["headline"], 96, weight="BOLD").shift(UP * 0.6)
        u = txt(d["url"], 44, T.ACCENT, font=T.MONO).next_to(h, DOWN, buff=0.5)
        self.beat("headline", 0)
        self.play(FadeIn(h, shift=UP * 0.2), FadeIn(cap), run_time=0.35)
        self.play(FadeIn(u), run_time=0.35)
