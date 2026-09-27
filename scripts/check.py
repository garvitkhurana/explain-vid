# /// script
# requires-python = ">=3.12"
# dependencies = ["jsonschema>=4"]
# ///
"""Hard gates for rendered explainers. Exit 1 on any failure. Usage: uv run scripts/check.py [spec.json]"""

import json
import re
import subprocess
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
spec_path = ROOT / "specs" / (sys.argv[1] if len(sys.argv) > 1 else "semif.json")
spec = json.loads(spec_path.read_text())
schema = json.loads((ROOT / "specs" / "scene.schema.json").read_text())
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

OUT = ROOT / "out" / spec_path.stem
timing_path = OUT / "voice" / "timing.json"
timing = json.loads(timing_path.read_text()) if timing_path.exists() else None
gate(timing is not None and timing.get("spec") == spec_path.name, "timing.json exists and matches this spec")
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

final = OUT / "final.mp4"
if final.exists() and timing and timing.get("backend") != "none":
    audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "format=duration",
                            "-of", "csv=p=0", str(final)], capture_output=True, text=True).stdout.strip()
    gate(bool(audio) and abs(float(audio) - expected) <= 0.3, f"final: narration audio present, {audio or 'none'}s vs {expected:.2f}s")

sys.exit(1 if failures else 0)
