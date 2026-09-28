"""Deterministic layout for flow figures: graph data + node sizes → positions, panel frames, rail polylines.

Pure Python (+ networkx), no Manim, so it can be tested on its own. The renderer measures each node's mobject and
passes sizes in; nothing here knows what a figure is about.
"""

from __future__ import annotations

import networkx as nx

GAP_X = 0.8        # between layers (rails run in this gap)
GAP_Y = 0.35       # between nodes in a layer
PANEL_PAD = 0.4    # inside a panel frame
HEADER_H = 0.75    # panel pill header + subtitle
PANEL_GAP = 0.35   # between panels
SWEEPS = 4         # barycenter crossing-reduction passes (fixed → deterministic)
MAX_SCALE = 1.5    # small figures grow to use the frame (never shrink-only)


def _back_edges(g: nx.DiGraph, order: list[str]) -> set[tuple[str, str]]:
    """Loop-back edges, which get routed around the panel instead of layered.

    Rule: inside a cycle, an edge pointing to a node listed *earlier* in the spec is the loop-back — specs list
    nodes in reading order. If a cycle has no such edge (unusual), fall back to DFS back edges in spec order.
    """
    back = set()
    for comp in nx.strongly_connected_components(g):
        if len(comp) > 1:
            back |= {(a, b) for a, b in g.subgraph(comp).edges if order.index(b) < order.index(a)}
    rest = g.copy()
    rest.remove_edges_from(back)
    seen, stack = set(), set()

    def visit(u):
        seen.add(u); stack.add(u)
        for v in sorted(rest.successors(u), key=order.index):
            if v in stack:
                back.add((u, v))
            elif v not in seen:
                visit(v)
        stack.discard(u)

    for n in order:
        if n in rest and n not in seen:  # order spans every panel; only walk this panel's nodes
            visit(n)
    return back


def _layout_panel(ids, edges, sizes, order, label_w):
    """Layered left→right layout of one panel's nodes. Returns node rects (unscaled) and layer column bounds."""
    g = nx.DiGraph()
    g.add_nodes_from(ids)
    g.add_edges_from((a, b) for a, b in edges if a in g and b in g)
    back = _back_edges(g, order)
    dag = g.copy()
    dag.remove_edges_from(back)
    layer = {n: i for i, gen in enumerate(nx.topological_generations(dag)) for n in gen}
    layers = [sorted([n for n in ids if layer[n] == k], key=order.index) for k in range(max(layer.values()) + 1)]

    def rank(k):
        return {n: i / max(1, len(layers[k]) - 1) for i, n in enumerate(layers[k])}

    for sweep in range(SWEEPS):  # alternate down/up sweeps; ties broken by spec order
        forward = sweep % 2 == 0
        ks = range(1, len(layers)) if forward else range(len(layers) - 2, -1, -1)
        for k in ks:
            pos = {n: r for kk in range(len(layers)) for n, r in rank(kk).items()}
            nbrs = (lambda n: dag.predecessors(n)) if forward else (lambda n: dag.successors(n))

            def key(n):
                ps = [pos[p] for p in nbrs(n)]
                return (sum(ps) / len(ps) if ps else pos[n], order.index(n))

            layers[k] = sorted(layers[k], key=key)

    rects, cols, x = {}, [], 0.0
    for k, col in enumerate(layers):
        w = max(sizes[n][0] for n in col)
        total_h = sum(sizes[n][1] for n in col) + GAP_Y * (len(col) - 1)
        y = total_h / 2
        for n in col:
            nw, nh = sizes[n]
            rects[n] = [x + w / 2, y - nh / 2, nw, nh]  # cx, cy, w, h
            y -= nh + GAP_Y
        cols.append((x, x + w))
        # Widen the gap after this layer when an edge leaving it carries a label, so the label isn't cut off.
        widest = max([label_w.get((a, b), 0) for a, b in edges if a in col and layer.get(b, -1) > k] + [0])
        x += w + max(GAP_X, widest + 0.5)
    return rects, cols, layer, back


def layout(graph: dict, sizes: dict[str, tuple[float, float]], area=(13.6, 6.9), center=(0.0, 0.25),
           label_w: dict[tuple[str, str], float] | None = None) -> dict:
    """Place panels side by side or stacked (whichever fits larger), route rails, scale to fit `area`."""
    nodes = graph["nodes"]
    order = [n["id"] for n in nodes]
    known = set(order)
    for e in graph.get("edges", []):
        for end in (e["from"], e["to"]):
            if end not in known:
                raise ValueError(f"edge references unknown node {end!r}")
    panel_ids = [p["id"] for p in graph.get("panels", [])] or ["_"]
    members = {p: [n["id"] for n in nodes if n.get("panel", panel_ids[0]) == p] for p in panel_ids}
    for n in nodes:
        if n.get("panel", panel_ids[0]) not in members:
            raise ValueError(f"node {n['id']!r} is in unknown panel {n.get('panel')!r}")
    edges = [(e["from"], e["to"]) for e in graph.get("edges", [])]

    panels = {}
    for p, ids in members.items():
        rects, cols, layer, back = _layout_panel(ids, edges, sizes, order, label_w or {})
        ys = [r[1] + r[3] / 2 for r in rects.values()] + [r[1] - r[3] / 2 for r in rects.values()]
        has_back = bool(back)
        w = cols[-1][1] + 2 * PANEL_PAD
        header = HEADER_H if graph.get("panels") else 0.0  # no panels → no header band to reserve
        h = max(ys) - min(ys) + 2 * PANEL_PAD + header + (0.45 if has_back else 0)
        panels[p] = dict(rects=rects, cols=cols, layer=layer, back=back, w=w, h=h, top=max(ys), header=header)

    def arrange(horizontal):
        W = (sum(p["w"] for p in panels.values()) + PANEL_GAP * (len(panels) - 1)) if horizontal else max(p["w"] for p in panels.values())
        H = max(p["h"] for p in panels.values()) if horizontal else sum(p["h"] for p in panels.values()) + PANEL_GAP * (len(panels) - 1)
        return min(area[0] / W, area[1] / H, MAX_SCALE), W, H

    s_row, W_row, H_row = arrange(True)
    s_col, W_col, H_col = arrange(False)
    horizontal = s_row >= s_col
    scale, W, H = (s_row, W_row, H_row) if horizontal else (s_col, W_col, H_col)

    # Place panels in unscaled figure coordinates (origin = figure centre), then scale everything at the end.
    out_nodes, out_panels, offset = {}, {}, {}
    cursor = -W / 2 if horizontal else H / 2
    for pid, p in panels.items():
        if horizontal:
            x0, y1 = cursor, H / 2
            cursor += p["w"] + PANEL_GAP
            frame_h = H
        else:
            x0, y1 = -W / 2, cursor
            cursor -= p["h"] + PANEL_GAP
            frame_h = p["h"]
        frame_w = p["w"] if horizontal else W
        dx = x0 + (frame_w - (p["w"] - 2 * PANEL_PAD)) / 2  # centre content in its frame (frames can be wider)
        dy = y1 - p["header"] - PANEL_PAD - p["top"]
        offset[pid] = (dx, dy)
        out_panels[pid] = (x0, y1 - frame_h, x0 + frame_w, y1)
        for n, (cx, cy, w, h) in p["rects"].items():
            out_nodes[n] = (cx + dx, cy + dy, w, h)

    def side(n, which):
        cx, cy, w, h = out_nodes[n]
        return {"right": (cx + w / 2, cy), "left": (cx - w / 2, cy), "bottom": (cx, cy - h / 2)}[which]

    node_panel = {n: p for p, ids in members.items() for n in ids}
    rails = []
    for e in graph.get("edges", []):
        a, b = e["from"], e["to"]
        pa, pb = node_panel[a], node_panel[b]
        P = panels[pa]
        if pa == pb and (a, b) in P["back"]:
            # Cycle-closing edge: down from a, along the bottom of the panel, up into b.
            floor = out_panels[pa][1] + 0.3
            (ax, ay), (bx, by) = side(a, "bottom"), side(b, "bottom")
            pts = [(ax, ay), (ax, floor), (bx, floor), (bx, by)]
        else:
            (ax, ay), (bx, by) = side(a, "right"), side(b, "left")
            if pa == pb:
                la = P["layer"][a]
                bus = P["cols"][la][1] + offset[pa][0] + GAP_X / 2  # the gap right after a's layer
            else:
                bus = (ax + bx) / 2
            pts = [(ax, ay), (bx, by)] if abs(ay - by) < 1e-6 else [(ax, ay), (bus, ay), (bus, by), (bx, by)]
        rails.append({"from": a, "to": b, "points": pts, "dashed": e.get("style") == "dashed", "label": e.get("label")})

    def tf(x, y):
        return (round(center[0] + x * scale, 4), round(center[1] + y * scale, 4))

    return {
        "scale": round(scale, 4),
        "horizontal": horizontal,
        "nodes": {n: {"center": tf(cx, cy), "w": round(w * scale, 4), "h": round(h * scale, 4)} for n, (cx, cy, w, h) in out_nodes.items()},
        "panels": {p: {"rect": (*tf(x0, y0), *tf(x1, y1))} for p, (x0, y0, x1, y1) in out_panels.items()},
        "rails": [dict(r, points=[tf(*pt) for pt in r["points"]]) for r in rails],
    }
