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

expected = sum(s["duration_s"] for s in spec["scenes"])
w, h = spec["meta"]["size"]
fps = spec["meta"]["fps"]

for name in ["remotion", "manim"]:
    f = ROOT / "out" / f"{name}.mp4"
    if not f.exists():
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

sys.exit(1 if failures else 0)
