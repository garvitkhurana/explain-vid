"""Render video-specs/<video>/spec.json as one Manim scene. Usage: SPEC=<video> uv run manim -qh main.py Explainer

Env: SPEC=<video folder name in video-specs/> (required), THEME=<preset in theme.py>, SCENES=<comma-separated scene ids to render only those>.
Needs out/<video>/voice/timing.json from scripts/voice.py (scene lengths + caption cues come from the narration).
"""

import itertools
import json
import math
import os
import zlib
from functools import lru_cache
from pathlib import Path

from manim import (
    DOWN, LEFT, RIGHT, UP, Arrow, Create, FadeIn, FadeOut, GrowFromEdge, Line, Rectangle, Transform,
    LaggedStart, RoundedRectangle, Scene, Square, Text, ValueTracker, VGroup, VMobject, config, linear, rate_functions,
    DashedVMobject, Dot, Arc, Circle, MoveAlongPath, Polygon, Succession, AnimationGroup, Intersection, ManimColor,
    interpolate_color, Wait,
)

from manim.animation.animation import prepare_animation

import theme as T
from layout import layout as layout_graph

ROOT = Path(__file__).resolve().parents[2]
VIDEO = os.environ.get("SPEC", "")
if not VIDEO:
    raise SystemExit("Set SPEC=<video> (a folder in video-specs/).")
SPEC = json.loads((ROOT / "video-specs" / VIDEO / "spec.json").read_text())
ONLY = {x for x in os.environ.get("SCENES", "").split(",") if x}
TIMING_PATH = ROOT / "out" / VIDEO / "voice" / "timing.json"
if not TIMING_PATH.exists():
    raise SystemExit(f"Missing {TIMING_PATH}: run `uv run scripts/voice.py {VIDEO}` first.")
TIMING = json.loads(TIMING_PATH.read_text())["scenes"]

config.background_color = T.BG
config.frame_rate = SPEC["meta"]["fps"]
config.pixel_width, config.pixel_height = SPEC["meta"]["size"]

PX = 1080 / 8  # pixels per Manim unit at 1080p
LAYOUT_SCALE = 8
CAPTION_TOP = -2.72  # captions live below this line; narrated content must stay above it


def txt(s, size=36, color=T.FG, font=T.FONT, weight=None):
    # font_size is in pt-ish units, scaled ×0.75.
    # Cached: animated text (typed commands, counters) asks for the same strings many times, and each fresh
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


class Explainer(Scene):
    def wait(self, duration=1.0, **kw):
        # Manim writes a *static* wait as int(duration * fps) frames (rounds down) but an animated one as
        # ceil(duration * fps). Always take the animated path so silent scenes stay frame-exact too.
        kw.setdefault("frozen_frame", False)
        return super().wait(duration, **kw)

    def play(self, *args, **kw):
        # Log every stretch where nothing animates (captions change on their own, so they don't count). A PLAN=1
        # dry run writes these to plan.json, so check.py can flag long still screens before any frame is rendered.
        def moves(a):  # small packet dots alone read as still, to viewers and to the render's freeze gate alike
            if isinstance(a, AnimationGroup):
                return any(moves(x) for x in a.animations)
            return not isinstance(a, (Wait, MoveAlongPath))

        if not any(moves(a) for a in args):  # self.wait() plays a Wait: time passes, nothing moves
            return super().play(*args, **kw)
        if self.time - self.moved_at > 1:
            self.stills.append([self.sid, round(self.moved_at - self.scene_start, 2), round(self.time - self.moved_at, 2)])
        super().play(*args, **kw)
        self.moved_at = self.time

    def construct(self):
        self.stills, self.moved_at = [], 0.0
        if os.environ.get("PLAN"):  # jump each animation to its end: timing only, no frames (seconds, not minutes)
            self.renderer._original_skipping_status = True
        for s in SPEC["scenes"]:
            if ONLY and s["id"] not in ONLY:
                continue
            start, self.sid = self.time, s["id"]
            timing = TIMING[s["id"]]
            self.scene_start, self.sentences, self.beats = start, timing["sentences"], s["data"].get("beats", {})
            self.scene_end = start + timing["frames"] / config.frame_rate
            cue_objs = self.cues(timing["cues"], start)
            self.add(*cue_objs)
            getattr(self, f"scene_{s['type']}")(s["data"])
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
        if os.environ.get("PLAN"):
            (TIMING_PATH.parent / "plan.json").write_text(json.dumps({"stills": self.stills}, indent=1) + "\n")

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

    def scene_title(self, d):
        title = fit(txt(d["title"], 160, T.ACCENT, weight="BOLD"), 13).shift(UP * 1.2)  # long titles shrink to fit
        sub = fit(txt(d["subtitle"], 56), 13).next_to(title, DOWN, buff=0.4)
        kick = fit(txt(d["kicker"], 36, T.MUTED), 13).next_to(sub, DOWN, buff=0.6)
        self.beat("title", 0)
        self.play(FadeIn(title, shift=UP * 0.2), run_time=0.4)
        self.play(FadeIn(sub, shift=UP * 0.2), run_time=0.35)
        self.play(FadeIn(kick), run_time=0.35)

    def scene_metrics(self, d):
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
        inner = panel(w / PX, card_h, 0.18)[-1].width
        rows = {"label": ([txt(c["label"], 30, T.MUTED) for c in d["cards"]], inner - 0.4),
                "value": ([txt(c["value"], 70, T.ACCENT, weight="BOLD") for c in d["cards"]], inner - 0.5),
                "compare": ([txt(c["compare"], 30) for c in d["cards"]], inner - 0.4)}
        scale = {}
        for name, (ms, max_w) in rows.items():  # one size per row: the longest text sets it, so the cards match
            scale[name] = min(1.0, *(max_w / m.width for m in ms))
            for m in ms:
                m.scale(scale[name])
        k_val = scale["value"]
        for i in range(n):
            p = panel(w / PX, card_h, 0.18)
            r = p[-1]
            lab = rows["label"][0][i].move_to(r.get_top(), aligned_edge=UP).shift(DOWN * 0.35)
            cap_h = txt("H", 70, weight="BOLD").height * k_val  # shared baseline, so a "j" or "g" doesn't lift a value
            val = on_baseline(rows["value"][0][i].set_x(r.get_x()), r.get_y() - cap_h / 2)
            desc = (txt("Hg", 30).height - txt("H", 30).height) * scale["compare"]  # room for descenders below it
            cmp = on_baseline(rows["compare"][0][i].set_x(r.get_x()), r.get_bottom()[1] + 0.35 + desc)
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
        # Cards shown so far stay centred: each new card slides the row over as it fades in. Offsets are relative
        # to the final layout (all cards centred), so the row ends exactly there.
        shown, off = [], 0.0
        base = {id(c): c.get_center()[0] for c in cards}

        def slide(m):
            nonlocal off
            if m not in cards:
                return []
            shown.append(m)
            lo = min(base[id(c)] - c.width / 2 for c in shown)
            hi = max(base[id(c)] + c.width / 2 for c in shown)
            want = -(lo + hi) / 2
            moves = [c.animate.shift(RIGHT * (want - off)) for c in shown[:-1]]
            m.shift(RIGHT * want)
            off = want
            return moves

        # Play in the order the narration reaches them (beats can put the footnote before some cards).
        for name, default, m in sorted(steps, key=lambda st: (sentence(st[0], st[1]), st[1])):
            self.beat(name, default)
            moves = slide(m)
            self.play(*moves, FadeIn(m, shift=UP * 0.2), run_time=self.step_time(name, default, 0.35 if m is not head else 0.4))

    def scene_cycle(self, d):
        """A loop drawn as a ring: 3–6 nodes clockwise from the top, a marker that goes round as the narration reaches
        each step, optional nodes leading in (enter) and out (exit), and an optional side panel of lines that grows as
        the loop runs (e.g. a message list, or the knobs that control each step).
        data: {title?, subtitle?, nodes: [{id, label, sub?, edge?}], enter?: {label, sub?, to?, side?},
               exit?: {label, sub?, from, edge?, side?}, panel?: {title, lines: [{role?, text, code?}], note?},
               steps: [{id, at?, show?, lap?}]}
        `edge` labels the arrow leaving a node; side is left|right|above|below. Step i lands on sentence i (beats
        override); the first step draws the figure. `at` is a node id, "enter" or "exit": the marker travels there
        round the ring (`lap: true` on the node it is already on = one full lap). `show` = panel lines visible after that step."""
        nodes, n = d["nodes"], len(d["nodes"])
        if not 3 <= n <= 6:
            raise ValueError(f"cycle: {n} nodes; a ring takes 3–6")
        idx = {nd["id"]: i for i, nd in enumerate(nodes)}
        enter, ext, pd = d.get("enter"), d.get("exit"), d.get("panel")
        head = self.headline(d)
        top = head.get_bottom()[1] - 0.35 if head else 3.75
        bottom = CAPTION_TOP + 0.15
        left, right = (-6.9, -0.3) if pd else (-6.9, 6.9)
        stroke_off, stroke_w = T.BORDER or T.MUTED, max(4, T.BORDER_W)

        def content(label, sub):
            parts = [txt(label, 32, weight="BOLD")]
            if sub:
                parts.append(VGroup(*[txt(s, 22, T.MUTED) for s in sub.split("\n")]).arrange(DOWN, buff=0.06))
            return VGroup(*parts).arrange(DOWN, buff=0.14)

        def card(c, w, h):
            p = panel(w, h, 0.15, stroke=stroke_off, stroke_w=stroke_w)
            return VGroup(p, fit(c, w - 0.3).move_to(p[-1]))

        inner = [content(nd["label"], nd.get("sub")) for nd in nodes]
        cw, ch = max(2.3, max(c.width for c in inner) + 0.5), max(0.9, max(c.height for c in inner) + 0.4)
        theta = [math.pi / 2 - 2 * math.pi * i / n for i in range(n)]

        # Enter/exit nodes sit beside the ring node they attach to. Unless the spec fixes a side, try each side and
        # keep the layout that gives the biggest ring.
        outer = {}  # "enter"/"exit" -> (spec, node index, content, gap: arrow length, long enough for its edge label)
        if enter:
            outer["enter"] = (enter, idx[enter.get("to", nodes[0]["id"])], content(enter["label"], enter.get("sub")), 1.0)
        if ext:
            gap = max(1.0, txt(ext["edge"], 24, weight="BOLD").width + 0.4) if ext.get("edge") else 1.0
            outer["exit"] = (ext, idx[ext["from"]], content(ext["label"], ext.get("sub")), gap)
        DIRS = {"left": LEFT, "right": RIGHT, "above": UP, "below": DOWN}

        def rects(R, sides):
            rs = [(R * math.cos(t), R * math.sin(t), cw, ch) for t in theta]
            for key, (_, i, c, gap) in outer.items():
                x, y, _, _ = rs[i]
                ow, oh = max(2.0, c.width + 0.5), max(0.9, c.height + 0.4)
                dx, dy = DIRS[sides[key]][:2]
                g = gap if dx else 1.0
                rs.append((x + dx * (cw / 2 + g + ow / 2), y + dy * (ch / 2 + g + oh / 2), ow, oh))
            return rs

        def separated(rs):
            return all(abs(a[0] - b[0]) >= (a[2] + b[2]) / 2 + 0.6 or abs(a[1] - b[1]) >= (a[3] + b[3]) / 2 + 0.6
                       for k, a in enumerate(rs) for b in rs[k + 1:])

        def extent(rs):
            rs = rs + [(0, 0, 2 * rs[0][1] + 0.1, 2 * rs[0][1] + 0.1)]  # the ring's arcs bulge past the cards
            return (max(x + w / 2 for x, _, w, _ in rs) - min(x - w / 2 for x, _, w, _ in rs),
                    max(y + h / 2 for _, y, _, h in rs) - min(y - h / 2 for _, y, _, h in rs))

        W, H = right - left, top - bottom

        def solve(sides):
            """(scale, R) for these sides: the biggest ring that fits at full text size, else the smallest shrunk."""
            radii = [r for r in (1.0 + 0.05 * k for k in range(49)) if separated(rects(r, sides))] or [3.4]
            fits = [r for r in radii if r <= 3.0 and all(e <= m for e, m in zip(extent(rects(r, sides)), (W, H)))]
            if fits:
                return 1.0, fits[-1]
            w, h = extent(rects(radii[0], sides))
            return min(W / w, H / h), radii[0]

        options = [[o[0]["side"]] if o[0].get("side") else list(DIRS) for o in outer.values()]
        best = None
        for combo in itertools.product(*options):
            sides = dict(zip(outer, combo))
            rs = rects(3.0, sides)
            if len(outer) == 2 and not separated(rs[n:]):
                continue
            score = solve(sides)
            if best is None or score > best[0]:
                best = (score, sides)
        (scale, R), sides = best or (solve({}), {})
        rs = rects(R, sides)
        ring = [card(c, cw, ch).move_to([x, y, 0]) for c, (x, y, _, _) in zip(inner, rs)]
        outs = {key: card(o[2], rs[n + k][2], rs[n + k][3]).move_to([rs[n + k][0], rs[n + k][1], 0])
                for k, (key, o) in enumerate(outer.items())}

        def inside(m, pt, pad):
            r = m[0][-1]
            return abs(pt[0] - r.get_center()[0]) < r.width / 2 + pad and abs(pt[1] - r.get_center()[1]) < r.height / 2 + pad

        def on_ring(t):
            return [R * math.cos(t), R * math.sin(t), 0]

        arcs, paths, labels = VGroup(), [], VGroup()
        for i in range(n):
            j = (i + 1) % n
            t0, t1 = theta[i], theta[i] - 2 * math.pi / n
            while inside(ring[i], on_ring(t0), 0.12) and t0 > t1:
                t0 -= 0.005
            while inside(ring[j], on_ring(t1), 0.2) and t1 < t0:
                t1 += 0.005
            path = Arc(radius=R, start_angle=t0, angle=t1 - t0)
            paths.append(path.copy())
            arc = path.set_stroke(T.MUTED, 5)
            arc.add_tip(tip_length=0.22, tip_width=0.22)
            arcs.add(arc)
            if nodes[i].get("edge"):
                m = (t0 + t1) / 2
                lab = txt(nodes[i]["edge"], 24, T.MUTED, weight="BOLD")
                off = 0.2 + 0.5 * abs(math.cos(m)) * lab.width + 0.5 * abs(math.sin(m)) * lab.height
                labels.add(lab.move_to([(R + off) * math.cos(m), (R + off) * math.sin(m), 0]))
        links = {}  # outer key -> (arrow, path)
        for key, (spec, i, _, _) in outer.items():
            side = sides[key]
            a, b = ring[i][0][-1], outs[key][0][-1]
            v = DIRS[side]
            p_ring, p_out = a.get_center() + v * a.height / 2 if side in ("above", "below") else a.get_center() + v * a.width / 2, \
                b.get_center() - v * (b.height / 2 if side in ("above", "below") else b.width / 2)
            s, e = (p_out, p_ring) if key == "enter" else (p_ring, p_out)
            ar = Arrow(s, e, color=T.MUTED, buff=0.1, tip_length=0.22, max_tip_length_to_length_ratio=0.4, stroke_width=5)
            links[key] = (ar, Line(s, e))
            if spec.get("edge"):
                lab = txt(spec["edge"], 24, T.MUTED, weight="BOLD")
                labels.add(lab.next_to(ar, UP if side in ("left", "right") else RIGHT, buff=0.12))
        fig = VGroup(*ring, *outs.values(), arcs, labels, *[a for a, _ in links.values()], *paths, *[p for _, p in links.values()])
        if scale < 1:  # the ring can't fit at full text size: shrink the whole figure
            fig.scale(scale)
        fig.move_to([(left + right) / 2, (top + bottom) / 2, 0])
        for c in [*ring, *outs.values()]:
            c.set_z_index(2)

        lines, frame = [], None
        if pd:
            colors = {"system": T.MUTED, "user": T.FG, "assistant": T.ACCENT, "tool": T.WARN}
            ph = txt(pd["title"], 30, T.MUTED, weight="BOLD")
            rows = VGroup()
            for ln in pd["lines"]:
                col = colors.get(ln.get("role"), T.ACCENT)
                body = txt(ln["text"], 30, font=T.MONO if ln.get("code") else T.FONT)
                inner_ = VGroup(txt(ln["role"], 26, col, font=T.MONO, weight="BOLD"), body).arrange(DOWN, aligned_edge=LEFT, buff=0.08) if ln.get("role") else VGroup(body)
                rail = Rectangle(width=0.07, height=inner_.height + 0.1, stroke_width=0, fill_color=col, fill_opacity=1)
                rows.add(VGroup(rail, inner_).arrange(RIGHT, buff=0.18, aligned_edge=UP))
            rows.arrange(DOWN, aligned_edge=LEFT, buff=0.28)
            note = txt(pd["note"], 22, T.MUTED, font=T.MONO) if pd.get("note") else None
            pw, room = 6.6, H - 0.55 - ph.height - 0.3 - (note.height + 0.3 if note else 0)
            rows.scale(min(1, (pw - 0.6) / rows.width, room / rows.height))
            if note:
                fit(note, pw - 0.6)
            ph_h = 0.55 + ph.height + 0.3 + rows.height + (note.height + 0.3 if note else 0) + 0.1
            frame = panel(pw, ph_h, 0.15).move_to([0.3 + pw / 2, (top + bottom) / 2, 0])
            ph.move_to(frame[-1].get_corner(UP + LEFT), aligned_edge=UP + LEFT).shift(RIGHT * 0.3 + DOWN * 0.25)
            rows.next_to(ph, DOWN, buff=0.3, aligned_edge=LEFT)
            if note:
                note.move_to(frame[-1].get_corner(DOWN + LEFT), aligned_edge=DOWN + LEFT).shift(RIGHT * 0.3 + UP * 0.2)
                frame = VGroup(frame, note)
            frame = VGroup(frame, ph)
            lines = list(rows)

        cards = {**{nd["id"]: ring[i] for i, nd in enumerate(nodes)}, **outs}

        def focus(key):
            return [c[0][-1].animate.set_stroke(T.ACCENT if k == key else stroke_off, width=9 if k == key else stroke_w)
                    for k, c in cards.items()]

        def route(frm, to, lap):
            """Hops from where the marker is (None, a ring index, "enter", "exit") to step target `to`: a list of
            (path, key of the node that hop reaches)."""
            if to == "enter" or frm in (None, "exit"):
                return []
            out, k = [], frm
            if frm == "enter":
                k = outer["enter"][1]
                out.append((links["enter"][1], nodes[k]["id"]))
            goal = outer["exit"][1] if to == "exit" else idx[to]
            lap = lap and frm == goal and to != "exit"
            while k != goal or lap:
                out.append((paths[k], nodes[(k + 1) % n]["id"]))
                k, lap = (k + 1) % n, False
            return out + ([(links["exit"][1], "exit")] if to == "exit" else [])

        here, shown = None, 0
        for s_i, st in enumerate(d["steps"]):
            self.beat(st["id"], s_i)
            if s_i == 0:
                self.play(*[FadeIn(m) for m in ([head] if head else []) + ([frame] if frame else [])],
                          FadeIn(VGroup(*ring, *outs.values()), shift=UP * 0.15), Create(arcs),
                          *[Create(a) for a, _ in links.values()], FadeIn(labels), run_time=self.step_time(st["id"], s_i, 0.7))
            reveal = [FadeIn(m, shift=UP * 0.15) for m in lines[shown:st.get("show", shown)]]
            shown = max(shown, st.get("show", shown))
            to = st.get("at")
            if to is None:
                if reveal:
                    self.play(*reveal, run_time=self.step_time(st["id"], s_i, 0.4))
                continue
            hops = route(here, to, st.get("lap"))
            if hops:
                # One hop at a time, lighting each node as the marker reaches it (a lone small dot reads as still).
                per = self.step_time(st["id"], s_i, min(2.4, 0.3 + 0.5 * len(hops))) / len(hops)
                dot = Dot(radius=0.14).set_fill(T.ACCENT, 1).set_stroke(T.BG, 3).move_to(hops[0][0].get_start()).set_z_index(1)
                self.add(dot)
                for k, (path, reached) in enumerate(hops):
                    last = k == len(hops) - 1
                    self.play(MoveAlongPath(dot, path, rate_func=rate_functions.ease_in_out_sine), run_time=self.fit_time(per * 0.7, 2))
                    self.play(*focus(reached), *(reveal if last else []), *([FadeOut(dot, scale=0.5)] if last else []),
                              run_time=self.fit_time(per * 0.3 if not last else 0.35, 1))
            else:
                self.play(*focus(to), *reveal, run_time=self.step_time(st["id"], s_i, 0.4))
            here = "exit" if to == "exit" else "enter" if to == "enter" else idx[to]

    def scene_steps(self, d):
        """A numbered walkthrough: steps build up in a list on the left, the current one outlined; an optional code
        window on the right shows that step's real code, typed in line by line, with optional wave art under it.
        data: {title, subtitle?, items: [{label, sub?, code?: [lines], art?: "wave"}]}
        steps: title (sentence 0), item{i} (sentence i + 1). Code lines are quoted source: check.py requires each
        one verbatim in facts.json, like commands."""
        head = self.headline(d)
        items = d["items"]
        n = len(items)
        top, bottom = (head.get_bottom()[1] - 0.45) if head else 3.6, CAPTION_TOP + 0.15
        has_code = any(it.get("code") for it in items)
        list_w = 6.9 if has_code else 11.0
        x0 = -6.9 if has_code else -list_w / 2
        gap = 0.3  # clears the cards' offset shadows
        row_h = min(1.1, (top - bottom - gap * (n - 1)) / n)
        off, on = T.BORDER or T.MUTED, T.ACCENT
        rows = []
        for i, it in enumerate(items):
            p = panel(list_w, row_h, 0.12, stroke=off, stroke_w=max(3, T.BORDER_W))
            ring = VGroup(Circle(radius=0.24, stroke_color=T.MUTED, stroke_width=4),
                          txt(str(i + 1), 24, weight="BOLD"))
            ring[1].move_to(ring[0])
            label = txt(it["label"], 36, weight="BOLD")
            text = VGroup(label, txt(it["sub"], 26, T.MUTED)).arrange(DOWN, aligned_edge=LEFT, buff=0.07) if it.get("sub") else VGroup(label)
            fit(text, list_w - 1.4)
            if text.height > row_h - 0.16:
                text.scale_to_fit_height(row_h - 0.16)
            ring.move_to(p[-1].get_left() + RIGHT * 0.55)
            text.next_to(ring, RIGHT, buff=0.3)
            row = VGroup(p, ring, text)
            row.shift([x0 + list_w / 2 - p[-1].get_center()[0], top - row_h / 2 - i * (row_h + gap) - p[-1].get_center()[1], 0])
            rows.append(row)

        win = None
        blocks, arts = {}, {}
        if has_code:
            W = 13.8 - list_w - 0.4
            # Every step's code at one shared size (the widest line sets it), so the text doesn't jump between steps.
            for i, it in enumerate(items):
                if it.get("code"):
                    blocks[i] = VGroup(*[txt(l or " ", 26, font=T.MONO) for l in it["code"]]).arrange(DOWN, aligned_edge=LEFT, buff=0.16)
            k = min([1.0] + [(W - 0.6) / b.width for b in blocks.values()])
            for b in blocks.values():
                b.scale(k)
            for i, it in enumerate(items):
                if it.get("art") == "wave":
                    fill, stroke, _ = self.role_style("c3")
                    arts[i] = self.flow_art("wave", f"steps:{i}", W - 0.8, fill, stroke)
            # The window fits the tallest step (code + wave), not the whole column, and aligns with the list's top.
            need = max((blocks[i].height if i in blocks else 0) + (arts[i].height + 0.5 if i in arts else 0) for i in range(n))
            bar_h = 0.5
            H = min(top - bottom, bar_h + need + 0.7)
            chrome, inner = self.alt_window({"kind": "terminal", "label": "step 1"}, W, H, bar_h, 0.3)
            win = VGroup(chrome, inner).move_to([6.9 - W / 2, top - H / 2, 0])
            inner_box = inner

        def code_for(i):
            lines, art = blocks.get(i), arts.get(i)
            if lines is not None:
                lines.move_to(inner_box.get_corner(UP + LEFT) + RIGHT * 0.3 + DOWN * 0.35, aligned_edge=UP + LEFT)
            if art is not None:
                art.next_to(lines, DOWN, buff=0.5).set_x(inner_box.get_center()[0])
            return lines, art

        first = 1 if head else 0
        if head:
            self.beat("title", 0)
            self.play(FadeIn(head, shift=UP * 0.2), *([FadeIn(win[0])] if win else []), run_time=0.45)
        shown_code = []
        for i, row in enumerate(rows):
            self.beat(f"item{i}", i + first)
            anims = [FadeIn(row, shift=UP * 0.12), row[0][-1].animate.set_stroke(on, width=6)]
            if i:
                anims.append(rows[i - 1][0][-1].animate.set_stroke(off, width=max(3, T.BORDER_W)))
            if win and not head and i == 0:
                anims.append(FadeIn(win[0]))
            if win:
                label = win[0][3]
                anims.append(Transform(label, fit(txt(f"step {i + 1}", 26, label.get_color(), weight="BOLD"), label.width * 3).move_to(label)))
                anims += [FadeOut(m) for m in shown_code]
            self.play(*anims, run_time=self.step_time(f"item{i}", i + first, 0.4))
            shown_code = []
            if win:
                lines, art = code_for(i)
                if lines is not None:
                    self.play(LaggedStart(*[FadeIn(l, shift=RIGHT * 0.1) for l in lines], lag_ratio=0.35),
                              run_time=self.step_time(f"item{i}", i + first, min(1.6, 0.25 * len(lines) + 0.4)))
                    shown_code = [lines]
                if art is not None:
                    for b in art:
                        b.save_state()
                        b.stretch_to_fit_height(0.02)
                    self.play(LaggedStart(*[b.animate(rate_func=rate_functions.ease_out_back).restore() for b in art], lag_ratio=0.04),
                              run_time=self.fit_time(0.9, 1))
                    shown_code.append(art)

    def scene_chunks(self, d):
        """Split, one pass each, join: a document whose chunks light up in colour; each chunk goes through the engine
        in its own pass and comes out as a waveform in its colour; then the waveforms join end to end into one file.
        data: {title, doc: str, chunks: [lines per chunk], engine: {label, sub?}, output: str, footnote?}
        steps: doc (sentence 0), split (1), pass (2), join (3), footnote (4)."""
        head = self.headline(d)
        top, bottom = (head.get_bottom()[1] - 0.4) if head else 3.6, CAPTION_TOP + 0.15
        colors = [self.role_style(c) for c in ("c3", "c2", "c1", "c4", "c5")]
        foot = fit(txt(d["footnote"], 26, T.MUTED), 13) if d.get("footnote") else None
        if foot:
            bottom += foot.height + 0.3
        # Document: grey text lines grouped into chunks (line widths vary deterministically, last line shorter).
        doc_w, line_h, line_gap, pad = 4.8, 0.14, 0.12, 0.2
        tag_w = txt("chunk 9", 22, font=T.MONO, weight="BOLD").width
        groups, boxes, tags = VGroup(), VGroup(), VGroup()
        grey = interpolate_color(ManimColor(T.PANEL), ManimColor(T.MUTED), 0.55)
        y = 0.0
        for c, k in enumerate(d["chunks"]):
            g = VGroup()
            for j in range(k):
                r = (zlib.crc32(f"chunks:{c}:{j}".encode()) % 1000) / 999
                w = (doc_w - 0.3 - 2 * pad - tag_w - 0.25) * ((0.5 + 0.2 * r) if j == k - 1 else (0.8 + 0.2 * r))
                g.add(RoundedRectangle(corner_radius=0.05, width=w, height=line_h, fill_color=grey, fill_opacity=1, stroke_width=0))
            g.arrange(DOWN, buff=line_gap, aligned_edge=LEFT).move_to([0, y, 0], aligned_edge=UP)
            box = RoundedRectangle(corner_radius=0.08, width=doc_w - 0.3, height=g.height + 2 * pad, stroke_color=colors[c % 5][1],
                                   stroke_width=4, fill_opacity=0).move_to(g).shift(RIGHT * 0.0)
            g.align_to(box, LEFT).shift(RIGHT * pad)
            tag = txt(f"chunk {c + 1}", 22, colors[c % 5][1], font=T.MONO, weight="BOLD").move_to(
                box.get_corner(UP + RIGHT) + LEFT * 0.15 + DOWN * 0.12, aligned_edge=UP + RIGHT)
            groups.add(g); boxes.add(box); tags.add(tag)
            y -= box.height + 0.22
        body = VGroup(groups, boxes)
        doc_head = txt(d["doc"], 26, T.MUTED, font=T.MONO)
        dp = panel(doc_w, body.height + doc_head.height + 0.75, 0.12)
        doc_head.move_to(dp[-1].get_corner(UP + LEFT) + RIGHT * 0.2 + DOWN * 0.18, aligned_edge=UP + LEFT)
        VGroup(body, tags).next_to(doc_head, DOWN, buff=0.22, aligned_edge=LEFT).shift(RIGHT * 0.0)
        VGroup(body, tags).set_x(dp[-1].get_center()[0])
        doc = VGroup(dp, doc_head, body, tags)
        if doc.height > top - bottom:
            doc.scale_to_fit_height(top - bottom)
        doc.move_to([-6.9 + doc.width / 2, (top + bottom) / 2, 0])
        # Engine in the middle, one wave per chunk on the right.
        eng_label = txt(d["engine"]["label"], 34, weight="BOLD")
        eng_txt = VGroup(eng_label, txt(d["engine"]["sub"], 24, T.MUTED)).arrange(DOWN, buff=0.08) if d["engine"].get("sub") else VGroup(eng_label)
        ep = panel(max(2.4, eng_txt.width + 0.5), eng_txt.height + 0.45, 0.14, stroke=T.ACCENT, stroke_w=max(4, T.BORDER_W))
        engine = VGroup(ep, eng_txt.move_to(ep[-1])).move_to([doc.get_right()[0] + 1.2 + ep.width / 2, (top + bottom) / 2, 0])
        n = len(d["chunks"])
        wave_w = 6.9 - 1.4 - (engine.get_right()[0])
        waves = VGroup()
        for c in range(n):
            wv = self.flow_art("wave", f"chunks:{c}", wave_w, colors[c % 5][0], colors[c % 5][1])
            waves.add(wv)
        waves.arrange(DOWN, buff=0.7).move_to([engine.get_right()[0] + 0.9 + wave_w / 2, engine.get_center()[1], 0])
        ins = VGroup(*[Arrow(b.get_right(), engine.get_left(), color=T.MUTED, buff=0.12, stroke_width=4, tip_length=0.18,
                             max_tip_length_to_length_ratio=0.2) for b in boxes])
        outs = VGroup(*[Arrow(engine.get_right(), w.get_left(), color=T.MUTED, buff=0.12, stroke_width=4, tip_length=0.18,
                              max_tip_length_to_length_ratio=0.2) for w in waves])
        # Joined: the waves end to end in one row, in the wave column at the engine's height, labelled.
        seg = (wave_w - 0.1 * (n - 1)) / n
        row_y = engine.get_center()[1]
        joined_x0 = waves.get_left()[0]
        out_label = txt(d["output"], 28, T.MUTED, font=T.MONO)

        self.beat("doc", 0)
        self.play(*([FadeIn(head, shift=UP * 0.2)] if head else []), FadeIn(VGroup(dp, doc_head, groups), shift=UP * 0.15),
                  run_time=self.step_time("doc", 0, 0.5))
        self.beat("split", 1)
        self.play(LaggedStart(*[AnimationGroup(Create(b), FadeIn(t), g.animate.set_fill(colors[c % 5][1], 1))
                                for c, (b, t, g) in enumerate(zip(boxes, tags, groups))], lag_ratio=0.5),
                  run_time=self.step_time("split", 1, min(2.0, 0.6 * n)))
        self.beat("pass", 2)
        self.play(FadeIn(engine, scale=0.9), run_time=self.fit_time(0.35, n + 1))
        per = max(0.5, self.span("pass", 2) * 0.8 / n)
        for c in range(n):
            dot = Dot(radius=0.12).set_fill(colors[c % 5][1], 1).set_stroke(T.BG, 2).move_to(ins[c].get_start())
            self.play(Create(ins[c]), MoveAlongPath(dot, Line(ins[c].get_start(), ins[c].get_end())), run_time=self.fit_time(per * 0.4, 2))
            self.remove(dot)
            for b in waves[c]:
                b.save_state()
                b.stretch_to_fit_height(0.02)
            self.add(waves[c])
            self.play(Create(outs[c]), engine.animate(rate_func=rate_functions.there_and_back).scale(1.05),
                      LaggedStart(*[b.animate.restore() for b in waves[c]], lag_ratio=0.03), run_time=self.fit_time(per * 0.6, 1))
        self.beat("join", 3)
        moves = []
        for c, wv in enumerate(waves):
            target = wv.copy().stretch_to_fit_width(seg).move_to([joined_x0 + seg / 2 + c * (seg + 0.1), row_y, 0])
            moves.append(Transform(wv, target))
        out_label.next_to(VGroup(*[m.target_mobject for m in moves]), DOWN, buff=0.15)
        self.play(*moves, FadeOut(outs), FadeOut(ins), run_time=self.step_time("join", 3, 0.9))
        self.play(FadeIn(out_label, shift=UP * 0.1), run_time=self.fit_time(0.3, 1))
        if foot:
            self.beat("footnote", 4)
            self.play(FadeIn(foot.next_to(out_label, DOWN, buff=0.25), shift=UP * 0.1), run_time=self.fit_time(0.4, 1))

    def scene_checklist(self, d):
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

    def scene_compare(self, d):
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

    def scene_commands(self, d):
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

    def scene_alternatives(self, d):
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

    def scene_flow(self, d):
        """Generic animated figure. Layout comes from layout.py; nothing here is specific to one figure.
        All parts start ghosted and are revealed/animated by `steps`, each on its narration sentence (or `beats`).
        data: {title?, subtitle?, roles?, panels?, nodes: [{id, label, sub?, role?, shape?, art?: "wave"|"lines",
               panel?, ...}], edges, steps}. A title sits at the top and the figure is laid out (and vertically
        centred) in the space left between it and the caption band. Step names are the steps' own `id`s."""
        roles = d.get("roles", {})

        def style(role):
            slot = roles.get(role, role if role in T.ROLES else "neutral")
            if slot not in T.ROLES:
                raise ValueError(f"unknown role slot {slot!r} (role {role!r})")
            return T.ROLES[slot]

        head = self.headline(d)
        # The figure's box: below the headline (or the frame's top margin), above the caption band.
        top = head.get_bottom()[1] - 0.35 if head else 3.65
        bottom = CAPTION_TOP + 0.12
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

        for i, st in enumerate(d["steps"]):
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
                # Budget the whole step (unghost, packets, landing pulse, return) against the scene's end.
                rest = 3 if st.get("back") else 2
                if anims:
                    self.play(*anims, run_time=self.fit_time(0.4, rest + 1))
                packets(st["path"], st.get("kind", "request"), share=rest)
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
            else:
                raise ValueError(f"unknown step {do!r}")

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

    def flow_pill(self, label, st, size):
        fill, stroke, text = st
        t = txt(label, size, text, weight="BOLD")
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
            parts = [txt(n["label"], size, text, weight="BOLD")] if n.get("label") else []
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

        if shape == "trapezoid":
            lb = label_block(24)
            w, h = max(1.5, lb.width + 0.5), max(1.3, lb.height + 0.8)
            poly = Polygon([-w / 2, h / 2, 0], [w / 2, h * 0.3, 0], [w / 2, -h * 0.3, 0], [-w / 2, -h / 2, 0],
                           fill_color=fill, fill_opacity=1, stroke_color=stroke, stroke_width=3)
            return VGroup(poly, lb.move_to(poly))
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
        t = txt(label, size, text, weight="BOLD")
        width = w if w else t.width + 0.35
        if t.width > width - 0.12:
            t.scale_to_fit_width(width - 0.12)
        r = RoundedRectangle(corner_radius=0.08, width=width, height=h, fill_color=fill, fill_opacity=1,
                             stroke_color=stroke, stroke_width=2)
        return VGroup(r, t.move_to(r))

    def scene_source(self, d):
        """Standard closing card built from the spec's meta.source {kind, url, credit?} — same for every video."""
        src = SPEC["meta"]["source"]
        head = {"repo": "Clone the repo to get started", "blog": "Read the full post at",
                "paper": "Read the full paper at"}[src["kind"]]
        url = src["url"].removeprefix("https://").removeprefix("http://").rstrip("/")
        h = fit(txt(head, 72, weight="BOLD"), 13).shift(UP * 0.7)
        u = fit(txt(url, 40, T.ACCENT, font=T.MONO), 13).next_to(h, DOWN, buff=0.45)
        parts = [h, u]
        if src.get("credit"):
            parts.append(fit(txt(src["credit"], 30, T.MUTED), 13).next_to(u, DOWN, buff=0.4))
        self.play(FadeIn(h, shift=UP * 0.2), run_time=0.35)
        self.play(*[FadeIn(m, shift=UP * 0.1) for m in parts[1:]], run_time=0.35)
