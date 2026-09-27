"""Render specs/<name>.json as one Manim scene. Usage: uv run manim -qh main.py Explainer

Env: SPEC=<file in specs/>, THEME=<preset in theme.py>, SCENES=<comma-separated scene ids to render only those>.
Needs out/voice/timing.json from scripts/voice.py (scene lengths + caption cues come from the narration).
"""

import json
import os
from functools import lru_cache
from pathlib import Path

from manim import (
    DOWN, LEFT, RIGHT, UP, Arrow, Create, FadeIn, FadeOut, GrowFromEdge, Line, Rectangle,
    RoundedRectangle, Scene, Text, ValueTracker, VGroup, config, linear, rate_functions,
)

import theme as T

ROOT = Path(__file__).resolve().parents[2]
SPEC = json.loads((ROOT / "specs" / os.environ.get("SPEC", "semif.json")).read_text())
ONLY = {x for x in os.environ.get("SCENES", "").split(",") if x}
TIMING_PATH = ROOT / "out" / "voice" / "timing.json"
if not TIMING_PATH.exists():
    raise SystemExit("Missing out/voice/timing.json: run `uv run scripts/voice.py` first (TTS=none for silent timing).")
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
        head = txt("How it works", 48, weight="BOLD").to_edge(UP, buff=0.8)
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
        cards = VGroup()
        for c in d["cards"]:
            p = panel(500 / PX, 380 / PX, 0.18)
            r = p[-1]
            lab = fit(txt(c["label"], 30, T.MUTED), r.width - 0.4).move_to(r.get_top(), aligned_edge=UP).shift(DOWN * 0.35)
            val = fit(txt(c["value"], 70, T.ACCENT, weight="BOLD"), r.width - 0.5).move_to(r)
            cmp = fit(txt(c["compare"], 30), r.width - 0.4).move_to(r.get_bottom(), aligned_edge=DOWN).shift(UP * 0.35)
            cards.add(VGroup(p, lab, val, cmp))
        cards.arrange(RIGHT, buff=50 / PX).shift(UP * 0.3)
        for i, c in enumerate(cards):
            self.beat(f"card{i}", i)
            self.play(FadeIn(c, shift=UP * 0.2), run_time=0.35)

    def scene_outro(self, d, cap):
        h = txt(d["headline"], 96, weight="BOLD").shift(UP * 0.6)
        u = txt(d["url"], 44, T.ACCENT, font=T.MONO).next_to(h, DOWN, buff=0.5)
        self.beat("headline", 0)
        self.play(FadeIn(h, shift=UP * 0.2), FadeIn(cap), run_time=0.35)
        self.play(FadeIn(u), run_time=0.35)
