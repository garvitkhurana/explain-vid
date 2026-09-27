"""Render specs/<name>.json as one Manim scene. Usage: uv run manim -qh main.py Explainer"""

import json
import os
from pathlib import Path

from manim import (
    DOWN, LEFT, RIGHT, UP, Arrow, Create, FadeIn, FadeOut, GrowFromEdge, Line, Rectangle,
    RoundedRectangle, Scene, Text, ValueTracker, VGroup, always_redraw, config, linear, rate_functions,
)

import theme as T

ROOT = Path(__file__).resolve().parents[2]
SPEC = json.loads((ROOT / "specs" / os.environ.get("SPEC", "semif.json")).read_text())

config.background_color = T.BG
config.frame_rate = SPEC["meta"]["fps"]
config.pixel_width, config.pixel_height = SPEC["meta"]["size"]

PX = 1080 / 8  # pixels per Manim unit at 1080p


def txt(s, size=36, color=T.FG, font=T.FONT, weight="NORMAL"):
    # font_size is in pt-ish units; ×0.75 keeps sizes close to the Remotion px values.
    return Text(s, font=font, font_size=size * 0.75, color=color, weight=weight)


def fit(m, max_w):
    # Manim has no text layout engine: shrink anything wider than its container.
    return m.scale_to_fit_width(max_w) if m.width > max_w else m


def box(label, highlight=False, w=300, h=100):
    r = RoundedRectangle(corner_radius=16 / PX, width=w / PX, height=h / PX,
                         stroke_color=T.ACCENT if highlight else T.MUTED, stroke_width=4,
                         fill_color=T.PANEL, fill_opacity=1)
    return VGroup(r, fit(txt(label, 32, weight="BOLD"), r.width - 0.3).move_to(r))


class Explainer(Scene):
    def construct(self):
        for s in SPEC["scenes"]:
            start = self.time
            cap = self.caption(s["caption"])
            getattr(self, f"scene_{s['type']}")(s["data"], cap)
            # Pad so each scene lasts exactly duration_s, leaving 0.25 s for the fade-out.
            self.wait(max(0.01, s["duration_s"] - 0.25 - (self.time - start)))
            self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.25)

    def caption(self, text):
        t = fit(txt(text, 34), 13.4)
        bg = Rectangle(width=t.width + 0.4, height=t.height + 0.3, fill_color="#000000",
                       fill_opacity=0.55, stroke_width=0).move_to(t)
        return VGroup(bg, t).to_edge(DOWN, buff=0.55)

    def scene_title(self, d, cap):
        title = txt(d["title"], 160, T.ACCENT, weight="BOLD").shift(UP * 1.2)
        sub = txt(d["subtitle"], 56).next_to(title, DOWN, buff=0.4)
        kick = txt(d["kicker"], 36, T.MUTED).next_to(sub, DOWN, buff=0.6)
        self.play(FadeIn(title, shift=UP * 0.2), run_time=0.4)
        self.play(FadeIn(sub, shift=UP * 0.2), FadeIn(cap), run_time=0.35)
        self.play(FadeIn(kick), run_time=0.35)

    def scene_pipeline(self, d, cap):
        head = txt("How it works", 48, weight="BOLD").to_edge(UP, buff=0.8)
        inputs = VGroup(*[box(l) for l in d["inputs"]]).arrange(DOWN, buff=0.6).shift(LEFT * 4.8)
        model = box(d["model"], highlight=True)
        logits = box(d["stages"][0]).move_to(RIGHT * 4.8 + UP * 0.8)
        probs = box(d["stages"][1], highlight=True).move_to(RIGHT * 4.8 + DOWN * 1.4)
        self.play(FadeIn(head), FadeIn(cap), run_time=0.3)
        for b in inputs:
            self.play(FadeIn(b, shift=UP * 0.2), run_time=0.2)
        self.play(FadeIn(model), run_time=0.3)
        arrows = [Arrow(b.get_right(), model.get_left(), color=T.MUTED, buff=0.1) for b in inputs]
        self.play(*[Create(a) for a in arrows], run_time=0.5)
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
            return RoundedRectangle(corner_radius=0.15, width=820 / PX, height=560 / PX, fill_color=T.PANEL,
                                    fill_opacity=1, stroke_width=0).move_to([x, 0.6, 0])

        ll, rl = lane(-3.3), lane(3.3)
        top = txt(f"21 decisions, {d['note']}", 40, T.MUTED).to_edge(UP, buff=0.4)
        lt = txt(L["label"], 38, T.WARN, weight="BOLD").move_to(ll.get_corner(UP + LEFT), aligned_edge=UP + LEFT).shift(RIGHT * 0.27 + DOWN * 0.27)
        rt = txt(R["label"], 38, T.ACCENT, weight="BOLD").move_to(rl.get_corner(UP + LEFT), aligned_edge=UP + LEFT).shift(RIGHT * 0.27 + DOWN * 0.27)

        def clock_text(limit, anchor):
            v = min(clock.get_value(), limit)
            done = clock.get_value() >= limit
            return txt(f"{v:.3f} s", 64, T.ACCENT if done else T.FG, font=T.MONO).next_to(anchor, DOWN, aligned_edge=LEFT, buff=0.15)

        lc = always_redraw(lambda: clock_text(L["seconds"], lt))
        rc = always_redraw(lambda: clock_text(R["seconds"], rt))

        def stream():
            frac = min(1, clock.get_value() / L["seconds"])
            s = js[: round(frac * len(js))] or " "
            lines = [s[i:i + 26] for i in range(0, len(s), 26)]
            return txt("\n".join(lines), 30, font=T.MONO).next_to(lt, DOWN, aligned_edge=LEFT, buff=1.2)

        def tokens():
            frac = min(1, clock.get_value() / L["seconds"])
            return txt(f"{round(frac * L['tokens'])} / {L['tokens']} tokens", 30, T.MUTED).move_to(
                ll.get_corner(DOWN + LEFT), aligned_edge=DOWN + LEFT).shift(RIGHT * 0.27 + UP * 0.22)

        def grid():
            done = clock.get_value() >= R["seconds"]
            cells = VGroup()
            for a in answers:
                fill = (T.ACCENT if a == "yes" else T.MUTED) if done else "#2a2e37"
                r = RoundedRectangle(corner_radius=0.07, width=0.75, height=0.44, fill_color=fill, fill_opacity=1, stroke_width=0)
                cells.add(VGroup(r, txt(a if done else "", 26, T.BG, weight="BOLD").move_to(r)) if done else r)
            return cells.arrange_in_grid(rows=3, cols=7, buff=0.1).next_to(rt, DOWN, aligned_edge=LEFT, buff=1.2)

        rfoot = txt(f"{R['tokens']} output tokens · {n} probability pairs", 30, T.MUTED).move_to(
            rl.get_corner(DOWN + LEFT), aligned_edge=DOWN + LEFT).shift(RIGHT * 0.27 + UP * 0.22)

        self.play(FadeIn(VGroup(ll, rl, top, lt, rt, rfoot)), FadeIn(cap), run_time=0.4)
        self.add(lc, rc, always_redraw(stream), always_redraw(tokens), always_redraw(grid))
        self.wait(0.1)
        self.play(clock.animate.set_value(L["seconds"]), run_time=L["seconds"] * scale, rate_func=linear)
        big = txt(f"{d['speedup']} faster", 90, T.ACCENT, weight="BOLD").move_to(DOWN * 2.2)
        self.play(FadeIn(big, scale=0.8), run_time=0.4)

    def scene_bars(self, d, cap):
        rows = [txt("STATE", 30, T.MUTED), fit(txt(d["state"], 40), 11.5), txt("QUESTION", 30, T.MUTED), fit(txt(d["question"], 40), 11.5)]
        head = VGroup(*rows).arrange(DOWN, aligned_edge=LEFT, buff=0.15).to_corner(UP + LEFT, buff=1.2)
        rows[2].shift(DOWN * 0.2); rows[3].shift(DOWN * 0.2)
        self.play(FadeIn(head[:2]), FadeIn(cap), run_time=0.35)
        self.play(FadeIn(head[2:]), run_time=0.35)
        anims = []
        for i, o in enumerate(d["options"]):
            y = -0.4 - i * 0.65
            label = txt(o["id"], 32, font=T.MONO).move_to([-3.2, y, 0], aligned_edge=RIGHT)
            bar = Rectangle(width=max(0.03, 900 * o["p"] / PX), height=50 / PX, stroke_width=0,
                            fill_color=T.ACCENT if i == 0 else T.MUTED, fill_opacity=1).move_to([-2.9, y, 0], aligned_edge=LEFT)
            val = txt(f"{o['p']:.2f}", 32, font=T.MONO).next_to(bar, RIGHT, buff=0.25)
            self.add(label)
            anims += [GrowFromEdge(bar, LEFT), FadeIn(val)]
        self.play(*anims, run_time=0.9)

    def scene_readout(self, d, cap):
        q = txt(f"Q: {d['question']}", 36, T.MUTED).to_edge(UP, buff=0.45)
        head = txt("Next-token scores (whole vocabulary)", 30, weight="BOLD").move_to([-7.1 + 160 / PX, 2.55, 0], aligned_edge=LEFT)
        rows = []
        for i, v in enumerate(d["vocab"]):
            y = 1.95 - i * 70 / PX
            tok = txt(v["tok"], 34, font=T.MONO).move_to([-7.1 + 310 / PX, y, 0], aligned_edge=RIGHT)
            bar = Rectangle(width=(v["logit"] - 15) * 50 / PX, height=40 / PX, stroke_width=0, fill_color=T.MUTED,
                            fill_opacity=1).move_to([-7.1 + 335 / PX, y, 0], aligned_edge=LEFT)
            val = txt(f"{v['logit']:.1f}", 28, T.MUTED, font=T.MONO).next_to(bar, RIGHT, buff=0.15)
            rows.append((v, VGroup(tok, bar, val)))
        rest = txt("… every other token in the vocabulary", 28, T.MUTED).move_to(
            [-7.1 + 160 / PX, 1.95 - len(rows) * 70 / PX, 0], aligned_edge=LEFT)
        self.play(FadeIn(q), FadeIn(head), FadeIn(cap), run_time=0.3)
        self.play(*[FadeIn(r, shift=RIGHT * 0.2) for _, r in rows], FadeIn(rest), run_time=0.8)
        self.wait(0.6)
        dims = [r.animate.set_opacity(0.15) for v, r in rows if not v.get("slot")] + [rest.animate.set_opacity(0.15)]
        hl = [r[0].animate.set_color(T.ACCENT) for v, r in rows if v.get("slot")] + \
             [r[1].animate.set_fill(T.ACCENT) for v, r in rows if v.get("slot")]
        self.play(*dims, *hl, run_time=0.6)
        arrow = txt("→", 64, T.ACCENT).move_to([0.3, 0.9, 0])
        sm = txt("softmax over A, B, C", 30, weight="BOLD").move_to([1.1, 1.95, 0], aligned_edge=LEFT)
        self.play(FadeIn(arrow), FadeIn(sm), run_time=0.4)
        anims = []
        for i, s in enumerate(d["slots"]):
            y = 1.35 - i * 90 / PX
            lab = txt(f"{s['letter']} → {s['option']}", 28, T.MUTED, font=T.MONO).move_to([1.1, y, 0], aligned_edge=LEFT)
            bar = Rectangle(width=max(0.03, 560 * s["p"] / PX), height=36 / PX, stroke_width=0,
                            fill_color=T.ACCENT if i == 0 else T.MUTED, fill_opacity=1).move_to([1.1, y - 0.33, 0], aligned_edge=LEFT)
            val = txt(f"{s['p']:.2f}", 30, font=T.MONO).next_to(bar, RIGHT, buff=0.15)
            self.add(lab)
            anims += [GrowFromEdge(bar, LEFT), FadeIn(val)]
        self.play(*anims, run_time=0.9)
        note = txt(d["note"], 30, T.WARN).move_to([1.1, -1.4, 0], aligned_edge=LEFT)
        self.play(FadeIn(note), run_time=0.3)

    def scene_branch(self, d, cap):
        n = d["branches"]
        left = -7.1 + 160 / PX
        label = txt(d["prefix_label"], 30, weight="BOLD").move_to([left, 1.55, 0], aligned_edge=LEFT)
        track = Rectangle(width=600 / PX, height=80 / PX, stroke_width=0, fill_color="#2a2e37", fill_opacity=1).move_to(
            [left, 1.0, 0], aligned_edge=LEFT)
        prefill = Rectangle(width=600 / PX, height=80 / PX, stroke_width=0, fill_color=T.MUTED, fill_opacity=1).move_to(track)
        once = txt("prefilled once", 26, T.MUTED).next_to(track, DOWN, aligned_edge=LEFT, buff=0.12)
        self.play(FadeIn(label), FadeIn(track), FadeIn(cap), run_time=0.3)
        self.play(GrowFromEdge(prefill, LEFT), FadeIn(once), run_time=1.2)
        cache = box(d["cache_label"], highlight=True, w=240, h=120).move_to([0.5, 1.0, 0])
        self.play(Create(Arrow(track.get_right(), cache.get_left(), color=T.MUTED, buff=0.05, tip_length=0.15)), FadeIn(cache), run_time=0.5)
        strips = VGroup(*[
            RoundedRectangle(corner_radius=0.03, width=460 / PX, height=12 / PX, stroke_width=0, fill_color="#2a2e37", fill_opacity=1)
            for _ in range(n)]).arrange(DOWN, buff=6 / PX).move_to([4.5, 1.15, 0])
        blabel = txt(d["branch_label"], 30, weight="BOLD").next_to(strips, UP, aligned_edge=LEFT, buff=0.2)
        lines = VGroup(*[Line(cache.get_right(), s.get_left(), color=T.MUTED, stroke_width=2, stroke_opacity=0.7) for s in strips])
        self.play(Create(lines), FadeIn(strips), FadeIn(blabel), run_time=1.0)
        self.play(strips.animate.set_fill(T.ACCENT), lines.animate.set_color(T.ACCENT), run_time=0.3)
        unit = txt(f"{d['unit']} · {d['workload']}", 30, T.MUTED).move_to([left, -0.85, 0], aligned_edge=LEFT)
        self.play(FadeIn(unit), run_time=0.3)
        vmax = max(r["v"] for r in d["rates"])
        anims = []
        for i, r in enumerate(d["rates"]):
            y = -1.35 - i * 0.55
            best = r["v"] == vmax
            lab = txt(r["label"], 30).move_to([left + 360 / PX, y, 0], aligned_edge=RIGHT)
            bar = Rectangle(width=1000 * r["v"] / vmax / PX, height=38 / PX, stroke_width=0,
                            fill_color=T.ACCENT if best else T.MUTED, fill_opacity=1).move_to([left + 384 / PX, y, 0], aligned_edge=LEFT)
            val = txt(f"{r['v']:.2f}", 32, T.ACCENT if best else T.FG, font=T.MONO).next_to(bar, RIGHT, buff=0.18)
            self.add(lab)
            anims += [GrowFromEdge(bar, LEFT), FadeIn(val)]
        self.play(*anims, run_time=1.0)

    def scene_metrics(self, d, cap):
        cards = VGroup()
        for c in d["cards"]:
            r = RoundedRectangle(corner_radius=0.18, width=500 / PX, height=380 / PX, fill_color=T.PANEL, fill_opacity=1, stroke_width=0)
            lab = fit(txt(c["label"], 30, T.MUTED), r.width - 0.4).move_to(r.get_top(), aligned_edge=UP).shift(DOWN * 0.35)
            val = fit(txt(c["value"], 70, T.ACCENT, weight="BOLD"), r.width - 0.5).move_to(r)
            cmp = txt(c["compare"], 30).move_to(r.get_bottom(), aligned_edge=DOWN).shift(UP * 0.35)
            cards.add(VGroup(r, lab, val, cmp))
        cards.arrange(RIGHT, buff=50 / PX).shift(UP * 0.3)
        self.play(FadeIn(cap), run_time=0.3)
        for c in cards:
            self.play(FadeIn(c, shift=UP * 0.2), run_time=0.35)

    def scene_outro(self, d, cap):
        h = txt(d["headline"], 96, weight="BOLD").shift(UP * 0.6)
        u = txt(d["url"], 44, T.ACCENT, font=T.MONO).next_to(h, DOWN, buff=0.5)
        self.play(FadeIn(h, shift=UP * 0.2), FadeIn(cap), run_time=0.35)
        self.play(FadeIn(u), run_time=0.35)
