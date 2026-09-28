# /// script
# requires-python = ">=3.12"
# dependencies = ["jsonschema>=4"]
# ///
"""Hard gates for rendered explainers. Exit 1 on any failure. Usage: uv run scripts/check.py <video>"""

import json
import re
import subprocess
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
if len(sys.argv) != 2:
    sys.exit("Usage: uv run scripts/check.py <video>   (a folder in videos/)")
VIDEO = sys.argv[1]
spec_path = ROOT / "videos" / VIDEO / "spec.json"
spec = json.loads(spec_path.read_text())
schema = json.loads((ROOT / "videos" / "scene.schema.json").read_text())
failures = []


def gate(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        failures.append(msg)


try:
    jsonschema.validate(spec, schema)
    gate(True, "spec validates against schema")
except jsonschema.ValidationError as e:
    gate(False, f"spec schema: {e.message}")

OUT = ROOT / "out" / VIDEO
timing_path = OUT / "voice" / "timing.json"
timing = json.loads(timing_path.read_text()) if timing_path.exists() else None
gate(timing is not None and timing.get("video") == VIDEO, "timing.json exists and matches this video")
# Narration drives length; fall back to the spec minimums if timing is missing (that gate already failed).
expected = timing["total"] if timing else sum(s["duration_s"] for s in spec["scenes"])

if timing:
    long_cues = [c["text"] for sc in timing["scenes"].values() for c in sc["cues"] if len(c["text"]) > 64]
    gate(not long_cues, f"caption cues <= 64 chars ({len(long_cues)} too long)")

# Jargon rule: an on-screen glossary term needs its plain phrase in narration of the same or an earlier scene.
said = ""
unexplained = []
for sc in spec["scenes"]:
    said += " " + " ".join(sc["narration"]).lower()
    shown = json.dumps(sc["data"]).lower()
    for g in spec["meta"].get("glossary", []):
        if g["term"].lower() in shown and g["plain"].lower() not in said:
            unexplained.append(f"{sc['id']}:{g['term']}")
gate(not unexplained, f"on-screen jargon explained in narration first ({', '.join(unexplained) or 'all ok'})")
# Grounding: every number shown on screen (strings in data) or written as digits in narration must match a fact in
# videos/<video>/facts.json. Numeric data fields are chart geometry, not stated claims. Illustrative facts need the
# word "illustrative" on screen in the scene that uses them. Spelled-out narration numbers are not checked yet.
NUM = re.compile(r"\d+(?:\.\d+)?")


def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            if k != "beats":
                yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)


facts_path = spec_path.parent / "facts.json"
if facts_path.exists():
    facts = json.loads(facts_path.read_text())
    bad = [f.get("id", "?") for f in facts if not all(f.get(k) for k in ("id", "value", "source", "kind"))
           or f["kind"] not in ("measured", "illustrative")]
    gate(not bad, f"facts.json entries have id, value, source, kind ({', '.join(bad) or 'all ok'})")
    by_num = {}
    for f in facts:
        for n in NUM.findall(str(f.get("value", "")).replace(",", "")):
            by_num.setdefault(float(n), []).append(f)
    ungrounded, unlabelled = [], []
    for sc in spec["scenes"]:
        shown = list(strings(sc["data"]))
        for text in shown + [s for s in sc["narration"]]:
            for n in NUM.findall(text.replace(",", "")):
                matches = by_num.get(float(n))
                if not matches:
                    ungrounded.append(f"{sc['id']}:{n}")
                elif all(f["kind"] == "illustrative" for f in matches) and \
                        not any("illustrative" in t.lower() for t in shown):
                    unlabelled.append(f"{sc['id']}:{n}")
    gate(not ungrounded, f"every number traces to facts.json ({', '.join(sorted(set(ungrounded))) or 'all ok'})")
    gate(not unlabelled, f"illustrative numbers labelled on screen ({', '.join(sorted(set(unlabelled))) or 'all ok'})")
else:
    print(f"SKIP grounding: no {facts_path.relative_to(ROOT)}")

w, h = spec["meta"]["size"]
fps = spec["meta"]["fps"]

# final.mp4 and manim.mp4 are required; remotion.mp4 is checked only if a comparison render produced it.
for name in ["remotion", "manim", "final"]:
    f = OUT / f"{name}.mp4"
    if not f.exists():
        if name in ("manim", "final"):
            gate(False, f"{name}: {f.name} missing")
        continue
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(f)],
        capture_output=True, text=True, check=True).stdout)
    st, dur = probe["streams"][0], float(probe["format"]["duration"])
    gate(abs(dur - expected) <= 0.2, f"{name}: duration {dur:.2f}s vs spec {expected:.2f}s")
    gate((st["width"], st["height"]) == (w, h), f"{name}: size {st['width']}x{st['height']}")
    gate(st["r_frame_rate"] == f"{fps}/1", f"{name}: fps {st['r_frame_rate']}")
    # Background is near-black by design, so only flag fully black stretches (pixel threshold 0.02).
    bd = subprocess.run(["ffmpeg", "-v", "info", "-i", str(f), "-vf", "blackdetect=d=0.5:pix_th=0.02",
                         "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
    runs = re.findall(r"black_start:\S+ black_end:\S+ black_duration:(\S+)", bd)
    gate(not runs, f"{name}: no black runs >0.5s ({len(runs)} found)")

# Per-scene frame counts: a scene that overruns its narration shifts every later caption.
if timing:
    wrong = []
    for sid, sc in timing["scenes"].items():
        f = OUT / "scenes" / sid / "videos" / "main" / "1080p30" / f"{sid}.mp4"
        if f.exists():
            n = int(subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries",
                                    "stream=nb_read_packets", "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout or 0)
            if n != sc["frames"]:
                wrong.append(f"{sid} {n}/{sc['frames']}")
    gate(not wrong, f"scene frame counts match narration timing ({', '.join(wrong) or 'all exact'})")

# Still screen: the longest stretch with no visual change, caption band cropped out (captions change on their own).
# Narrated videos only: silent figure-mode specs hold each step for a fixed `hold` on purpose.
MAX_STILL_S = 6.0
manim = OUT / "manim.mp4"
narrated = any(s["narration"] for s in spec["scenes"])
if not narrated:
    print("SKIP still screen: no narration (figure mode)")
elif manim.exists():
    fd = subprocess.run(["ffmpeg", "-v", "info", "-i", str(manim), "-vf", "crop=iw:ih*0.82:0:0,freezedetect=n=0.001:d=1",
                         "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
    still = max([float(x) for x in re.findall(r"freeze_duration: (\S+)", fd)] or [0.0])
    gate(still <= MAX_STILL_S, f"manim: longest still screen {still:.1f}s <= {MAX_STILL_S:.0f}s")

final = OUT / "final.mp4"
if final.exists() and timing and timing.get("backend") != "none":
    audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "format=duration",
                            "-of", "csv=p=0", str(final)], capture_output=True, text=True).stdout.strip()
    gate(bool(audio) and abs(float(audio) - expected) <= 0.3, f"final: narration audio present, {audio or 'none'}s vs {expected:.2f}s")

sys.exit(1 if failures else 0)
