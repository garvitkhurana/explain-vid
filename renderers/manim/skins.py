"""Cast kit data: skins map teaching roles to pixel characters. Pure data (no Manim), so voice.py and check.py read it too.

Specs name roles (`meta.cast.roles`), never characters; the skin (`meta.cast.skin`, or SKIN=<name> at render time)
decides who plays them, so one script renders in any setting.

Roles:  explainer — walks through the mechanism (plain-string narration is theirs)
        asker     — voices the wrong guess or the viewer's plain question
        reactor   — optional, wordless payoff (look to camera)
Sprites are 12 x 16 pixel maps: rows 0-6 head (eyes 'e' on row 3, mouth 'm' on row 5), 7-11 body, 12-15 legs.
Each letter is a colour in the character's `pal`; '.' is transparent. Characters are original designs.
"""

LEGS = ["..pppppppp..", "..ppp..ppp..", "..ppp..ppp..", ".kkkk..kkkk."]
ROBE = ["..tttttttt..", ".tttttttttt.", ".tttttttttt.", ".kkkk..kkkk."]

SKINS = {
    "office": {
        "set": {"wall": "#d8d0bb", "wainscot": "#b9ae94", "floor": "#7d725d", "board": "#f7f5ee", "frame": "#8a8f98",
                "accent": "#3c5a8a", "desk": "#6b4423", "desk_top": "#8b5a2b", "window": "#bfd9ee", "blind": "#e9e4d6",
                "plant": "#3b6d11", "pot": "#b04a2e"},
        "roles": {
            "explainer": {
                "name": "Wendell Crumb", "voice": "am_michael",
                "caption": "#f3ede2",
                "rows": ["..hhhhhhhh..", ".hhhhhhhhhh.", ".hgggssgggh.", "..gegssgeg..", "..ssssssss..",
                         "..ssmmmmss..", "...ssssss...", ".qquqqqquqq.", "qqquqqqquqqq", "qqquqqqquqqq",
                         "sqquqqqquqqs", ".qquqqqquqq.", *LEGS],
                "pal": {"h": "#1f1f1f", "g": "#7a7f88", "s": "#f2c6a5", "q": "#4f8a3c", "u": "#3a2a1a",
                        "p": "#3a3d44", "k": "#111111"},
            },
            "asker": {
                "name": "Gary Pruitt", "voice": "am_puck",
                "caption": "#fac775",
                "rows": ["...ssssss...", "..ssssssss..", ".hssssssssh.", ".hsessssesh.", "..ssssssss..",
                         "..ssmmmmss..", "...ssssss...", ".bbrrrrrrbb.", "bbrrrrrrrrbb", "bbrrrrrrrrbb",
                         "sbrrrrrrrrbs", ".rrrrrrrrrr.", *LEGS],
                "pal": {"s": "#e8b894", "h": "#8a8a8a", "r": "#b03a2e", "b": "#7aa7d9", "p": "#4a4a4a",
                        "k": "#111111"},
            },
            "reactor": {
                "name": "Sam Okafor", "voice": "am_echo",
                "caption": "#a9c8e8",
                "rows": ["..h.hhh.hh..", ".hhhhhhhhhh.", "..hhssssss..", "..sesssses..", "..ssssssss..",
                         "..ssmmmmss..", "...ssssss...", ".bbbbtbbbbb.", "bbbbbtbbbbbb", "bbbbbbtbbbbb",
                         "sbbbbbtbbbbs", ".bbbbbbbbbb.", *LEGS],
                "pal": {"s": "#8d5a3b", "h": "#2b1d14", "b": "#a9c8e8", "t": "#7a2a2a", "p": "#3a3d44",
                        "k": "#111111"},
            },
        },
    },
    "rpg": {
        "set": {"wall": "#4a4a5a", "mortar": "#3a3a48", "floor": "#2e2e38", "board": "#efe3c4", "frame": "#6b4423",
                "accent": "#c9a227", "desk": "#5a3a1e", "desk_top": "#7a4a22", "window": "#2c2f5a", "flame": "#ef9f27",
                "flame_core": "#fac775"},
        "roles": {
            "explainer": {
                "name": "Brother Tomas", "voice": "bm_george",
                "caption": "#f3ede2",
                "rows": ["...ssssss...", "..ssssssss..", ".hssssssssh.", ".hsessssesh.", "..ssssssss..",
                         "..ssmmmmss..", "...ssssss...", ".wwwwyywwww.", "wwwwwyywwwww", "wwwwwyywwwww",
                         "swwwwyywwwws", ".wwwwyywwww.", "..wwwwwwww..", ".wwwwwwwwww.", ".wwwwwwwwww.",
                         ".kkkk..kkkk."],
                "pal": {"s": "#e8b894", "h": "#fac775", "w": "#e8e8f0", "y": "#c9a227", "k": "#5a3a1e"},
            },
            "asker": {
                "name": "Pip", "voice": "af_bella",
                "caption": "#fac775",
                "rows": ["..hhhhhhhh..", ".hhhhhhhhhh.", ".hssssssssh.", "..sesssses..", "..ssssssss..",
                         "..ssmmmmss..", "...ssssss...", ".gggggggggg.", "gggggggggggg", "gggggggggggg",
                         "suuuuuuuuuus", ".gggggggggg.", *LEGS],
                "pal": {"h": "#6b4423", "g": "#3b6d11", "u": "#7a4a1a", "p": "#6b4423", "k": "#3a2a1a",
                        "s": "#f2c6a5"},
            },
            "reactor": {
                "name": "Mirelda", "voice": "bf_emma",
                "caption": "#cecbf6",
                "rows": [".....cc.....", "...cccccc...", ".cccccccccc.", ".hsessssesh.", ".hssssssssh.",
                         ".hssmmmmssh.", ".hhsssssshh.", ".tttttttttt.", "tttttttttttt", "tttttttttttt",
                         "stttttttttts", ".tttttttttt.", *ROBE],
                "pal": {"c": "#3c3489", "h": "#d3d1c7", "t": "#534ab7", "k": "#2a2a2a", "s": "#f2c6a5"},
            },
        },
    },
}

ROLES = ("explainer", "asker", "reactor")
SPEAKING = ("explainer", "asker")


def skin_name(spec, env=None):
    """The skin in use: SKIN=<name> overrides the spec's meta.cast.skin."""
    import os
    return (env if env is not None else os.environ.get("SKIN")) or spec["meta"].get("cast", {}).get("skin", "office")


def line(item):
    """A narration item as (who, text, kind): plain strings belong to the explainer."""
    if isinstance(item, str):
        return "explainer", item, None
    return item["who"], item["say"], item.get("kind")


def texts(narration):
    """Just the spoken text of a scene's narration, whatever form its items take."""
    return [line(x)[1] for x in narration]
