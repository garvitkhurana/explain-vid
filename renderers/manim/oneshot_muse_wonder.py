"""Muse Wonder (Meta, 2026-10-12), one-shot. Render: ./scripts/oneshot.sh muse_wonder"""

import numpy as np
from manim import (
    DOWN, LEFT, RIGHT, UP, Arrow, Create, CurvedArrow, DashedLine, Dot, FadeIn, FadeOut, Flash, GrowFromCenter,
    GrowFromEdge, Indicate, Line, MoveAlongPath, Polygon, Rectangle, Transform, VGroup, VMobject, Write,
    rate_functions,
)

from oneshot import BLU, GRN, INK, MONO, MUTED, ORG, RED, VIO, WHITE, YEL, OneShot, box, chip, cross, t


def bubble(text, fill=WHITE, size=26, tail=-1):
    """A chat bubble; tail -1 points down-left (them), +1 down-right (you)."""
    l = t(text, size, bold=False)
    b = box(l.width + 0.6, l.height + 0.45, fill, r=0.3)
    c = b.get_bottom() + [tail * (b.width / 2 - 0.5), 0.02, 0]
    tl = Polygon(c + [-0.15, 0, 0], c + [0.15, 0, 0], c + [tail * 0.25, -0.25, 0], fill_color=fill, fill_opacity=1,
                 stroke_color=INK, stroke_width=3)
    return VGroup(tl, b, l.move_to(b))


def flag(x, y):
    pole = Line([x, y - 0.7, 0], [x, y + 0.7, 0], color=INK, stroke_width=5)
    cloth = Polygon([x, y + 0.7, 0], [x + 0.7, y + 0.45, 0], [x, y + 0.2, 0], fill_color=RED, fill_opacity=1,
                    stroke_color=INK, stroke_width=3)
    return VGroup(pole, cloth)


class Video(OneShot):
    VIDEO = "muse_wonder"

    # ---- 1. hook --------------------------------------------------------------------------------------------
    def title(self, sid):
        self.title_room(sid)
        self.line(sid, 0)
        meta = chip("Meta: new model", BLU, 34).move_to([-0.4, 0.95, 0])
        q = t("?", 90, RED).next_to(meta, RIGHT, buff=0.35)
        self.play(FadeIn(meta, shift=DOWN * 0.3), run_time=0.4)
        self.play(FadeIn(q, scale=0.5), run_time=0.3)
        # "Muse Wonder is Meta's new model for agents: AI that does tasks for you, at work and at home."
        self.line(sid, 1)
        name = t("Muse Wonder", 92, RED).move_to([0, 1.2, 0])
        sub = t("a model for agents", 34).next_to(name, DOWN, buff=0.15)
        self.play(FadeOut(VGroup(meta, q)), FadeIn(name, scale=0.6), run_time=0.45)
        self.play(FadeIn(sub, shift=UP * 0.15), run_time=0.3)
        self.line(sid, 1, 0.6)
        work, home = chip("tasks at work", YEL, 30), chip("tasks at home", GRN, 30)
        VGroup(work, home).arrange(RIGHT, buff=0.5).next_to(sub, DOWN, buff=0.35)
        self.play(FadeIn(work, shift=UP * 0.15), FadeIn(home, shift=UP * 0.15), lag_ratio=0.3, run_time=0.5)
        self.end(sid)

    # ---- 2. Active Memory -----------------------------------------------------------------------------------
    def memory(self, sid):
        self.line(sid, 0, 0.45)
        head = chip("Active Memory", VIO, 40).to_edge(UP, buff=0.45)
        self.play(FadeIn(head, shift=DOWN * 0.2), run_time=0.4)
        # "It keeps what matters about you from past chats." — old chats drop into a memory drawer
        self.line(sid, 1)
        past = VGroup(bubble("I'm training for a 10k"), bubble("hills hurt my knee"), bubble("I run on Saturdays"))
        past.arrange(DOWN, buff=0.3, aligned_edge=LEFT).move_to([-4.0, 0.6, 0])
        when = t("past chats", 26, MUTED, bold=False).next_to(past, UP, buff=0.15)
        ex = t("example", 22, MUTED, bold=False).next_to(past, DOWN, buff=0.15)
        self.play(FadeIn(when), *[FadeIn(b, shift=RIGHT * 0.3) for b in past], FadeIn(ex), lag_ratio=0.25, run_time=0.9)
        drawer = box(2.6, 1.6, VIO, r=0.2).move_to([0.2, -0.6, 0])
        dl = t("memory", 32).move_to(drawer)
        self.play(GrowFromCenter(VGroup(drawer, dl)), run_time=0.35)
        self.line(sid, 1, 0.55)
        notes = VGroup(chip("10k training", YEL, 24), chip("knee: no hills", YEL, 24), chip("runs Saturdays", YEL, 24))
        for n, b in zip(notes, past):
            n.move_to(b)
        self.play(*[Transform(b, n) for b, n in zip(past, notes)], run_time=0.4)
        self.play(*[b.animate.scale(0.3).move_to(drawer).set_opacity(0) for b in past], lag_ratio=0.2, run_time=0.8)
        self.play(Indicate(VGroup(drawer, dl), color=VIO, scale_factor=1.06), run_time=0.4)
        # "And when a new task needs it, it pulls that detail back up on its own."
        self.line(sid, 2)
        ask = bubble("plan my Saturday run", BLU, 28, tail=1).move_to([4.2, 1.6, 0])
        self.play(FadeIn(ask, shift=LEFT * 0.3), FadeOut(when), FadeOut(ex), run_time=0.4)
        plan = box(4.0, 2.2, WHITE, r=0.2).move_to([4.2, -0.6, 0])
        pt = t("your plan", 28).move_to(plan.get_top() + DOWN * 0.35)
        self.play(GrowFromCenter(plan), FadeIn(pt), run_time=0.35)
        self.line(sid, 2, 0.5)
        got = VGroup(chip("10k training", YEL, 24), chip("knee: no hills", YEL, 24)).arrange(DOWN, buff=0.15)
        got.move_to(drawer)
        self.play(FadeIn(got, scale=0.4), run_time=0.3)
        self.play(got.animate.move_to(plan.get_center() + DOWN * 0.25), run_time=0.7, rate_func=rate_functions.ease_out_cubic)
        self.play(Indicate(got, color=GRN, scale_factor=1.06), run_time=0.5)
        self.end(sid)

    # ---- 3. Active Focus ------------------------------------------------------------------------------------
    def focus(self, sid):
        self.line(sid, 0)
        head = chip("Active Focus", ORG, 40).to_edge(UP, buff=0.45)
        self.play(FadeIn(head, shift=DOWN * 0.2), run_time=0.4)
        start, goal = np.array([-5.4, 0.2, 0]), np.array([4.6, 0.2, 0])
        me = Dot(start, radius=0.2, color=BLU)
        g = flag(goal[0], goal[1] + 0.3)
        gl = t("hard goal", 28).next_to(g, DOWN, buff=0.15)
        track = DashedLine(start, goal, color=MUTED, dash_length=0.15)
        self.play(FadeIn(me), FadeIn(g), FadeIn(gl), Create(track), run_time=0.6)
        # "When it hits a blocker, it tries another way instead of giving up." — a wall, a bounce, a detour
        self.line(sid, 1)
        wall = Rectangle(width=0.4, height=2.4, fill_color=RED, fill_opacity=1, stroke_color=INK, stroke_width=3)
        wall.move_to([-0.4, 0.2, 0])
        wl = t("blocker", 26, RED).next_to(wall, UP, buff=0.12)
        self.play(GrowFromEdge(wall, DOWN), FadeIn(wl), run_time=0.4)
        self.play(me.animate.move_to([-0.85, 0.2, 0]), run_time=0.6, rate_func=rate_functions.rush_into)
        self.play(me.animate.shift(LEFT * 0.4), run_time=0.25, rate_func=rate_functions.ease_out_back)
        self.line(sid, 1, 0.55)
        way = VMobject(stroke_color=GRN, stroke_width=6).set_points_smoothly(
            [[-1.25, 0.2, 0], [-1.0, -1.3, 0], [0.4, -1.7, 0], [1.6, -0.9, 0], [2.2, 0.2, 0]])
        self.play(Create(way), MoveAlongPath(me, way), run_time=1.3)
        # "And before an important step, it checks with you first."
        self.line(sid, 2)
        ask = VGroup(box(4.6, 1.7, WHITE, r=0.2), t("OK to place the order?", 28))
        ask[1].move_to(ask[0]).shift(UP * 0.35)
        yes = chip("yes", GRN, 26).move_to(ask[0]).shift(DOWN * 0.4 + LEFT * 0.7)
        no = chip("not yet", "#eeeeee", 26).move_to(ask[0]).shift(DOWN * 0.4 + RIGHT * 0.8)
        ask.add(yes, no)
        ask.move_to([2.9, 2.35, 0])
        pause = t("pauses", 26, MUTED, bold=False).next_to(me, DOWN, buff=0.2)
        self.play(FadeOut(head), FadeIn(ask, shift=DOWN * 0.2), FadeIn(pause), run_time=0.45)
        self.line(sid, 2, 0.65)
        self.play(Indicate(yes, color=GRN, scale_factor=1.2), run_time=0.45)
        self.play(FadeOut(pause), me.animate.move_to(goal), run_time=0.6)
        self.play(Flash(goal, color=GRN), run_time=0.4)
        self.end(sid)

    # ---- 4. new tasks, not just tests -----------------------------------------------------------------------
    def unknown(self, sid):
        # "Don't all new models top the tests?" — a test sheet with a big score
        self.line(sid, 0)
        sheet = box(2.6, 3.2, WHITE, r=0.15).move_to([-3.0, 0.6, 0])
        rows = VGroup(*[Line([0, 0, 0], [1.6, 0, 0], color=MUTED, stroke_width=5) for _ in range(5)])
        rows.arrange(DOWN, buff=0.35).move_to(sheet).shift(DOWN * 0.2 + LEFT * 0.2)
        grade = t("A+", 70, RED).move_to(sheet.get_corner(UP + RIGHT) + [-0.1, 0.0, 0]).rotate(-0.2)
        self.play(GrowFromCenter(sheet), FadeIn(rows), run_time=0.4)
        self.play(FadeIn(grade, scale=1.6), run_time=0.3)
        # "Two models can score the same on tests, and still differ on tasks they've never seen." — bars
        self.line(sid, 1, 0.25)
        self.play(FadeOut(VGroup(sheet, rows, grade)), run_time=0.3)
        base_y = -1.6
        def bar(x, h, fill):
            return Rectangle(width=0.9, height=h, fill_color=fill, fill_opacity=1, stroke_color=INK,
                             stroke_width=3).move_to([x, base_y + h / 2, 0])
        floor = Line([-5.6, base_y, 0], [4.6, base_y, 0], color=INK, stroke_width=4)
        test = VGroup(bar(-3.9, 3.0, BLU), bar(-2.8, 3.0, GRN))
        new = VGroup(bar(1.6, 1.4, BLU), bar(2.7, 2.6, GRN))
        tl = t("tests", 30).next_to(test, DOWN, buff=0.2).set_y(base_y - 0.35)
        nl = t("tasks never seen", 30).next_to(new, DOWN, buff=0.2).set_y(base_y - 0.35)
        legend = VGroup(chip("model A", BLU, 24), chip("model B", GRN, 24)).arrange(RIGHT, buff=0.3).move_to([-0.6, 2.6, 0])
        sk = t("sketch", 22, MUTED, bold=False).next_to(legend, RIGHT, buff=0.3)
        self.play(Create(floor), FadeIn(legend), FadeIn(sk), run_time=0.4)
        self.play(*[GrowFromEdge(b, DOWN) for b in test], FadeIn(tl), run_time=0.5)
        same = t("=", 50).next_to(test, UP, buff=0.15)
        self.play(FadeIn(same), run_time=0.25)
        self.line(sid, 1, 0.6)
        self.play(*[GrowFromEdge(b, DOWN) for b in new], FadeIn(nl), run_time=0.6)
        diff = t("≠", 50, RED).next_to(new, UP, buff=0.15)
        self.play(FadeIn(diff, scale=1.5), run_time=0.3)
        # "Meta plotted both: tasks it practised for, against tasks it never saw." — the axes, old model's line
        self.line(sid, 2)
        self.play(FadeOut(VGroup(floor, test, new, tl, nl, legend, same, diff)), run_time=0.3)
        o = np.array([-4.2, -1.7, 0])
        ax = VGroup(Line(o, o + [7.6, 0, 0], color=INK, stroke_width=4), Line(o, o + [0, 4.3, 0], color=INK, stroke_width=4))
        xl = t("tasks it practised for", 26, MUTED, bold=False).next_to(ax[0], DOWN, buff=0.15)
        yl = t("tasks it never saw", 26, MUTED, bold=False).rotate(np.pi / 2).next_to(ax[1], LEFT, buff=0.15)
        sk.next_to(ax[0].get_end(), UP, buff=0.15).shift(LEFT * 0.4)
        self.play(Create(ax), FadeIn(xl), FadeIn(yl), run_time=0.5)
        old_pts = [o + [x, 0.4 + 0.42 * x, 0] for x in (1.0, 2.2, 3.4, 4.6)]
        old = VGroup(*[Dot(p, radius=0.13, color=BLU) for p in old_pts])
        trend = DashedLine(o + [0.4, 0.4 + 0.42 * 0.4, 0], o + [7.2, 0.4 + 0.42 * 7.2, 0], color=BLU, dash_length=0.15)
        ol = chip("Muse Spark 1.3", BLU, 24).move_to(o + [6.0, 0.8, 0])
        self.line(sid, 2, 0.5)
        self.play(FadeIn(old, lag_ratio=0.2), FadeIn(sk), run_time=0.6)
        self.play(Create(trend), FadeIn(ol), run_time=0.5)
        # "The new model sits above the old model's line: better on new tasks than its test scores predict."
        self.line(sid, 3)
        new_pts = [o + [x, 0.4 + 0.42 * x + 1.0, 0] for x in (2.6, 3.8, 5.0, 6.2)]
        nd = VGroup(*[Dot(p, radius=0.13, color=GRN) for p in new_pts])
        nl2 = chip("Muse Wonder Full", GRN, 24).move_to(o + [2.0, 4.0, 0])
        self.play(FadeIn(nd, lag_ratio=0.2), FadeIn(nl2), run_time=0.6)
        self.line(sid, 3, 0.45)
        gap = Arrow(o + [5.0, 0.4 + 0.42 * 5.0, 0], new_pts[2], buff=0.12, color=RED, stroke_width=6)
        gl = t("better than predicted", 24, RED).next_to(nl2, DOWN, buff=0.15).align_to(nl2, LEFT)
        self.play(GrowFromEdge(gap, DOWN), FadeIn(gl), run_time=0.5)
        # "Meta says that's because it's built on a bigger, stronger base model." — same training, bigger base
        self.line(sid, 4)
        self.play(FadeOut(VGroup(ax, xl, yl, old, trend, ol, nd, nl2, gap, gl, sk)), run_time=0.3)
        def stack(x, w, fill, name):
            base = box(w, 1.2, fill, r=0.1).move_to([x, -1.0, 0])
            bl = t("base model", 26).move_to(base)
            top = box(2.2, 0.8, YEL, r=0.1).next_to(base, UP, buff=0.1)
            tl2 = t("training", 24).move_to(top)
            n = t(name, 28).next_to(top, UP, buff=0.25)
            return VGroup(base, bl, top, tl2, n)
        a = stack(-3.2, 2.8, BLU, "older")
        b = stack(2.6, 5.0, GRN, "Muse Wonder")
        self.play(FadeIn(a, shift=UP * 0.2), run_time=0.4)
        self.line(sid, 4, 0.5)
        self.play(FadeIn(b, shift=UP * 0.2), run_time=0.4)
        self.play(Indicate(b[0], color=GRN, scale_factor=1.05), run_time=0.5)
        self.end(sid)

    # ---- 6. where to get it --------------------------------------------------------------------------------------
    def access(self, sid):
        # "Developers can use it today, through Meta's Model API and Muse Code."
        self.line(sid, 0)
        dev = t("Developers, today", 34).move_to([-3.6, 2.4, 0])
        mw = chip("Muse Wonder", GRN, 34).move_to([-3.6, 1.3, 0])
        api, mc = chip("Meta Model API", WHITE, 28, MONO), chip("Muse Code", WHITE, 28, MONO)
        VGroup(api, mc).arrange(DOWN, buff=0.35).move_to([-3.6, -0.6, 0])
        a1 = Arrow(mw.get_bottom(), VGroup(api, mc).get_top(), buff=0.1, color=INK, stroke_width=4)
        self.play(FadeIn(dev), FadeIn(mw, shift=DOWN * 0.2), run_time=0.4)
        self.line(sid, 0, 0.45)
        self.play(Create(a1), FadeIn(api), FadeIn(mc), lag_ratio=0.2, run_time=0.6)
        # "A second version, called Full, is for Muse Code subscribers."
        self.line(sid, 1)
        full = chip("Muse Wonder Full", VIO, 34).move_to([2.6, 1.3, 0])
        subs = chip("Muse Code subscribers", WHITE, 28).move_to([2.6, -0.1, 0])
        a2 = Arrow(full.get_bottom(), subs.get_top(), buff=0.1, color=INK, stroke_width=4)
        self.play(FadeIn(full, shift=DOWN * 0.2), run_time=0.4)
        self.play(Create(a2), FadeIn(subs), run_time=0.4)
        # "It comes to the Muse app soon, subscribers first."
        self.line(sid, 2)
        self.play(FadeOut(VGroup(dev, mw, api, mc, a1, full, subs, a2)), run_time=0.3)
        phone = box(2.6, 4.2, WHITE, r=0.35).move_to([-1.6, 0.6, 0])
        app = t("Muse app", 30).move_to(phone).shift(UP * 1.4)
        lines = VGroup(box(1.8, 0.45, BLU, r=0.2), box(1.4, 0.45, "#eeeeee", r=0.2)).arrange(DOWN, buff=0.25).move_to(phone)
        soon = chip("soon", ORG, 36).move_to(phone.get_corner(UP + RIGHT)).rotate(-0.25)
        first = chip("subscribers first", VIO, 32).move_to([2.6, 0.6, 0])
        self.play(GrowFromCenter(phone), FadeIn(app), FadeIn(lines, lag_ratio=0.3), run_time=0.5)
        self.play(FadeIn(soon, scale=1.6), run_time=0.3)
        self.play(FadeIn(first, shift=LEFT * 0.3), run_time=0.35)
        self.end(sid)

    # ---- 7. is it safe? then the thesis ----------------------------------------------------------------------
    def trust(self, sid):
        # "An agent with my messages and calendar? Is that safe?"
        self.line(sid, 0)
        agent = chip("agent", BLU, 36).move_to([1.0, 0.6, 0])
        stuff = VGroup(chip("messages", WHITE, 28), chip("calendar", WHITE, 28), chip("documents", WHITE, 28))
        stuff.arrange(DOWN, buff=0.35).move_to([-4.0, 0.6, 0])
        arrows = VGroup(*[Arrow(s.get_right(), agent.get_left(), buff=0.15, color=MUTED, stroke_width=4) for s in stuff])
        self.play(FadeIn(agent), FadeIn(stuff, lag_ratio=0.2), run_time=0.5)
        self.play(*[Create(a) for a in arrows], run_time=0.4)
        q = t("?", 90, RED).next_to(agent, RIGHT, buff=0.4)
        self.play(FadeIn(q, scale=0.5), run_time=0.3)
        # "Meta says it's trained to resist bad instructions, and to be careful with private information."
        self.line(sid, 1)
        self.play(FadeOut(q), run_time=0.2)
        bad = chip("bad instruction", RED, 26).move_to([5.0, 2.0, 0])
        shield = Polygon([0, 0.6, 0], [0.55, 0.35, 0], [0.45, -0.35, 0], [0, -0.7, 0], [-0.45, -0.35, 0], [-0.55, 0.35, 0],
                         fill_color=GRN, fill_opacity=1, stroke_color=INK, stroke_width=3).move_to(agent.get_right() + [0.9, 0.5, 0])
        self.play(FadeIn(shield, scale=0.5), FadeIn(bad), run_time=0.4)
        self.play(bad.animate.move_to(shield.get_center() + [0.9, 0.3, 0]), run_time=0.4, rate_func=rate_functions.rush_into)
        self.play(bad.animate.move_to([5.6, 2.6, 0]).set_opacity(0.3), run_time=0.4, rate_func=rate_functions.ease_out_cubic)
        self.line(sid, 1, 0.6)
        careful = t("careful with private info", 26, GRN).next_to(stuff, DOWN, buff=0.3)
        self.play(FadeIn(careful), *[a.animate.set_color(GRN) for a in arrows], run_time=0.5)
        # "A full safety report is coming soon."
        self.line(sid, 2)
        self.play(FadeOut(VGroup(agent, stuff, arrows, shield, bad, careful)), run_time=0.3)
        doc = box(2.8, 3.4, WHITE, r=0.15).move_to([0, 0.6, 0])
        dt = t("safety report", 30).move_to(doc.get_top() + DOWN * 0.45)
        rows = VGroup(*[Line([0, 0, 0], [1.9, 0, 0], color=MUTED, stroke_width=5) for _ in range(4)]).arrange(DOWN, buff=0.35)
        rows.move_to(doc).shift(DOWN * 0.3)
        stamp = chip("coming soon", ORG, 34).move_to(doc).rotate(0.25)
        self.play(GrowFromCenter(doc), FadeIn(dt), FadeIn(rows), run_time=0.4)
        self.play(FadeIn(stamp, scale=1.6), run_time=0.3)
        # "So Muse Wonder is built to remember you, and keep going until the job is done."
        self.line(sid, 3)
        self.play(FadeOut(VGroup(doc, dt, rows, stamp)), run_time=0.3)
        rem = chip("remembers you", VIO, 40).move_to([-3.2, 0.9, 0])
        keep = chip("keeps going", ORG, 40).move_to([0.9, 0.9, 0])
        done = VGroup(flag(4.6, 0.9), t("done", 30, GRN).move_to([4.95, -0.1, 0]))
        a1 = Arrow(rem.get_right(), keep.get_left(), buff=0.1, color=INK, stroke_width=5)
        a2 = Arrow(keep.get_right(), [4.4, 0.9, 0], buff=0.1, color=INK, stroke_width=5)
        self.play(FadeIn(rem, shift=RIGHT * 0.2), run_time=0.35)
        self.line(sid, 3, 0.45)
        self.play(Create(a1), FadeIn(keep, shift=RIGHT * 0.2), run_time=0.4)
        self.line(sid, 3, 0.75)
        self.play(Create(a2), FadeIn(done), run_time=0.4)
        self.play(Indicate(done[1], color=GRN, scale_factor=1.2), run_time=0.5)
        self.end(sid)
