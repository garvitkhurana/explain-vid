# /// script
# requires-python = ">=3.12"
# dependencies = ["jsonschema>=4"]
# ///
"""Hard gates for one explainer. Exit 1 on any failure. Usage: uv run scripts/check.py <video> [--plan]

Spec gates (schema, structure, words, grounding) need only video-specs/<video>/; render gates need out/<video>/.
--plan: spec gates plus still screens predicted by a dry run (out/<video>/voice/plan.json), then stop. render.sh
runs it before rendering, so a long still fails in seconds instead of after a full render."""

import json
import re
import subprocess
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
args = [a for a in sys.argv[1:] if a != "--plan"]
if len(args) != 1:
    sys.exit("Usage: uv run scripts/check.py <video> [--plan]   (a folder in video-specs/)")
VIDEO, PLAN = args[0], "--plan" in sys.argv
SPEC_DIR = ROOT / "video-specs" / VIDEO
OUT = ROOT / "out" / VIDEO
spec = json.loads((SPEC_DIR / "spec.json").read_text())
facts = json.loads((SPEC_DIR / "facts.json").read_text())
scenes = spec["scenes"]
failures = []

# The arc is picked by what the content is, not where it came from (a blog can describe a tool, a repo can hold a
# result). Every scene except the closing card has a role from its arc; all of them must appear.
ARCS = {
    "tool": ["hook", "how", "why", "use"],          # something you can run: what it does → how → why → how you use it
    "concept": ["hook", "how", "why", "takeaway"],  # an idea: what it is → how it works → why it matters → the point
    "result": ["hook", "problem", "how", "proof"],  # a finding: the problem → the method → the evidence
}
# Where the spec's one-sentence point (meta.thesis) must be said: a tool says what it does up front; an idea or a
# finding lands it at the end. A video once promised "one bitter lesson" and never said what it was.
THESIS_AT = {"tool": "hook", "concept": "takeaway", "result": "proof"}
MAX_CUE = 64      # caption characters per cue (voice.py splits to this)
MAX_STILL_S = 4.5  # user flagged a ~5 s screen with only a title and voice as "nothing comes up"
REPEAT = 0.6       # share of a closing sentence's words already said in the opening that counts as a repeat


def gate(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        failures.append(msg)


def listed(items, ok="all ok"):
    return ", ".join(items) or ok


# ---- spec ------------------------------------------------------------------------------------------------------
try:
    jsonschema.validate(spec, json.loads((ROOT / "video-specs" / "scene.schema.json").read_text()))
    gate(True, "spec validates against schema")
except jsonschema.ValidationError as e:
    gate(False, f"spec schema: {e.message}")

arc = ARCS.get(spec["meta"].get("arc"), [])
body = [s for s in scenes if s["type"] != "source"]
roles = [s.get("role") for s in body]
gate(bool(arc) and all(r in arc for r in roles), f"every scene has a role from its arc {arc} ({listed(s['id'] for s in body if s.get('role') not in arc)})")
gate(set(arc) <= set(roles), f"arc covers all its parts (missing: {listed(sorted(set(arc) - set(roles)), 'none')})")
gate(scenes[0]["type"] == "title" and scenes[0].get("role") == "hook", "opens on a title scene (the hook)")
gate(scenes[-1]["type"] == "source" and len(scenes) - len(body) == 1, "ends on one source card")
# The card is the only call to action; a scene of its own that says "clone the repo" is a second ending.
url = spec["meta"]["source"]["url"].rstrip("/")
cta = [s["id"] for s in body if "clone the repo" in " ".join(s["narration"]).lower() or url in json.dumps(s["data"])]
gate(not cta, f"only the source card sends viewers to the source ({listed(cta)})")


def words(text):
    return {w for w in re.findall(r"[a-z']+", text.lower()) if len(w) > 3}


opening = words(" ".join(scenes[0]["narration"]))
repeats = [s for s in body[-1]["narration"] if words(s) and len(words(s) & opening) / len(words(s)) >= REPEAT]
gate(not repeats, f"closing scene doesn't restate the opening ({listed(repeats)})")

# The thesis is said, not just shown: one sentence in a scene of its role carries most of its words.
thesis, at = words(spec["meta"].get("thesis", "")), THESIS_AT.get(spec["meta"].get("arc"))
said_at = [x for s in body if s.get("role") == at for x in s["narration"]]
gate(bool(thesis) and any(len(words(x) & thesis) / len(thesis) >= REPEAT for x in said_at),
     f"thesis said in the {at} narration ({spec['meta'].get('thesis', 'no meta.thesis')})")
# An idea or a finding ends on its point: nothing after the scene that says it (a "habits" scene of extra numbers
# after harness_zero's result read as an afterthought). A tool says its thesis up front, so it's exempt.
if at != "hook":
    says = [s["id"] for s in body if any(thesis and len(words(x) & thesis) / len(thesis) >= REPEAT for x in s["narration"])]
    ids = [s["id"] for s in body]
    after = ids[ids.index(says[-1]) + 1:] if says else []
    gate(not after, f"ends on the thesis: no scene after the one that says it ({listed(after, 'none')})")

# ---- words -----------------------------------------------------------------------------------------------------
# Jargon: an on-screen glossary term needs its plain phrase said in the same or an earlier scene.
said, unexplained = "", []
for s in scenes:
    said += " " + " ".join(s["narration"]).lower()
    shown = json.dumps(s["data"]).lower()
    unexplained += [f"{s['id']}:{g['term']}" for g in spec["meta"].get("glossary", [])
                    if g["term"].lower() in shown and g["plain"].lower() not in said]
gate(not unexplained, f"on-screen jargon explained in narration first ({listed(unexplained)})")

# ---- grounding against facts.json ------------------------------------------------------------------------------
# Every number on screen or written as digits in narration must match a fact's value. Numeric data fields are
# geometry, not claims. Digits glued to a word or a dot (role colour c1, Qwen3, python3.12) are names.
NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")
bad = [f.get("id", "?") for f in facts if not all(f.get(k) for k in ("id", "value", "source", "kind"))
       or f["kind"] not in ("measured", "illustrative")]
gate(not bad, f"facts.json entries have id, value, source, kind ({listed(bad)})")


def strings(x):
    """On-screen text: every string in a scene's data except beats and quoted commands/code (checked verbatim)."""
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            if k not in ("beats", "cmd", "code"):
                yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)


def quoted(x):
    """Shell commands and code lines shown on screen: they must appear verbatim in a fact."""
    if isinstance(x, dict):
        if isinstance(x.get("cmd"), str):
            yield x["cmd"]
        if isinstance(x.get("code"), list):
            yield from (line.strip() for line in x["code"] if line.strip())
        for v in x.values():
            yield from quoted(v)
    elif isinstance(x, list):
        for v in x:
            yield from quoted(v)


by_num = {}
for f in facts:
    for n in NUM.findall(str(f.get("value", "")).replace(",", "")):
        by_num.setdefault(float(n), []).append(f)
ungrounded, unlabelled = [], []
for s in scenes:
    shown = list(strings(s["data"]))
    for text in shown + s["narration"]:
        for n in NUM.findall(text.replace(",", "")):
            matches = by_num.get(float(n))
            if not matches:
                ungrounded.append(f"{s['id']}:{n}")
            elif all(f["kind"] == "illustrative" for f in matches) and not any("illustrative" in t.lower() for t in shown):
                unlabelled.append(f"{s['id']}:{n}")
gate(not ungrounded, f"every number traces to facts.json ({listed(sorted(set(ungrounded)))})")
gate(not unlabelled, f"illustrative numbers labelled on screen ({listed(sorted(set(unlabelled)))})")
fact_text = "\n".join(" ".join(str(f.get(k, "")) for k in ("claim", "value", "source")) for f in facts).replace("\\n", "\n")
unquoted = [f"{s['id']}:{c}" for s in scenes for c in quoted(s["data"]) if c not in fact_text]
gate(not unquoted, f"commands and code appear verbatim in facts.json ({listed(unquoted)})")

# ---- plan (dry run, before rendering) ---------------------------------------------------------------------------
if PLAN:
    timing = json.loads((OUT / "voice" / "timing.json").read_text())["scenes"]
    long = [f"{sid} sentence {sum(t >= x for x in timing[sid]['sentences']) - 1}: {d}s from {t}s"
            for sid, t, d in json.loads((OUT / "voice" / "plan.json").read_text())["stills"] if d > MAX_STILL_S]
    gate(not long, f"predicted still screens <= {MAX_STILL_S:.1f}s ({listed(long)})")
    sys.exit(1 if failures else 0)

# ---- render ----------------------------------------------------------------------------------------------------
timing_path, final = OUT / "voice" / "timing.json", OUT / "final.mp4"
if not (timing_path.exists() and final.exists()):
    print(f"SKIP render gates: no render in {OUT.relative_to(ROOT)} (run ./scripts/render.sh {VIDEO})")
    sys.exit(1 if failures else 0)
timing = json.loads(timing_path.read_text())
gate(timing.get("video") == VIDEO and list(timing["scenes"]) == [s["id"] for s in scenes],
     "timing.json matches this spec's scenes (re-run voice.py after editing scenes)")
long_cues = [c["text"] for sc in timing["scenes"].values() for c in sc["cues"] if len(c["text"]) > MAX_CUE]
gate(not long_cues, f"caption cues <= {MAX_CUE} chars ({listed(long_cues)})")


def probe(path, entries, stream="v:0"):
    return subprocess.run(["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries", entries, "-of", "json",
                           str(path)], capture_output=True, text=True, check=True).stdout


expected, (w, h), fps = timing["total"], spec["meta"]["size"], spec["meta"]["fps"]
info = json.loads(probe(final, "stream=width,height,r_frame_rate:format=duration"))
v, dur = info["streams"][0], float(info["format"]["duration"])
gate(abs(dur - expected) <= 0.2, f"duration {dur:.2f}s vs narration timing {expected:.2f}s")
gate((v["width"], v["height"], v["r_frame_rate"]) == (w, h, f"{fps}/1"), f"format {v['width']}x{v['height']} @ {v['r_frame_rate']}")
gate(bool(json.loads(probe(final, "stream=index", "a:0"))["streams"]), "narration audio track present")

# A scene that overruns its narration shifts every later caption.
wrong = []
for sid, sc in timing["scenes"].items():
    f = OUT / "scenes" / sid / "videos" / "main" / "1080p30" / f"{sid}.mp4"
    n = int(subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries",
                            "stream=nb_read_packets", "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout or 0)
    if n != sc["frames"]:
        wrong.append(f"{sid} {n}/{sc['frames']}")
gate(not wrong, f"scene frame counts match narration timing ({listed(wrong, 'all exact')})")

# Black stretches (a scene that failed to draw) and still screens (nothing moves while the voice talks). The caption
# band is cropped out: captions change on their own.
log = subprocess.run(["ffmpeg", "-v", "info", "-i", str(final), "-vf",
                      "blackdetect=d=0.5:pix_th=0.02,crop=iw:ih*0.82:0:0,freezedetect=n=0.001:d=1",
                      "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
black = re.findall(r"black_duration:(\S+)", log)
still = max([float(x) for x in re.findall(r"freeze_duration: (\S+)", log)] or [0.0])
gate(not black, f"no black stretches over 0.5s ({len(black)} found)")
gate(still <= MAX_STILL_S, f"longest still screen {still:.1f}s <= {MAX_STILL_S:.1f}s")

sys.exit(1 if failures else 0)
