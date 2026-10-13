# /// script
# requires-python = ">=3.12"
# dependencies = ["mlx-whisper>=0.4"]
# ///
"""The exposure sheet: when every spoken word starts and ends. Runs Whisper (local, MLX) on each narration clip.

Usage: uv run scripts/words.py <video>   (after voice.py; SKIN= picks the same output folder as voice.py)
Writes out/<video>/voice/words.json: {scene id: [{who, said, words: [{w, start, end}]} per sentence]}, times relative
to the scene. The renderer times mouths and phrase-anchored acts on these; check.py compares `said` to the script
(a clip that slurs or skips words fails there, before any frame is drawn).
"""

import json
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import mlx_whisper  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MODEL = "mlx-community/whisper-large-v3-turbo"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: uv run scripts/words.py <video>")
    video = sys.argv[1]
    out = ROOT / "out" / (video + (f"-{os.environ['SKIN']}" if os.environ.get("SKIN") else "")) / "voice"
    timing = json.loads((out / "timing.json").read_text())["scenes"]
    sheet = {}
    for sid, sc in timing.items():
        rows = []
        for i, span in enumerate(sc.get("lines", [])):
            r = mlx_whisper.transcribe(str(out / f"{sid}_{i:02}.wav"), path_or_hf_repo=MODEL, word_timestamps=True,
                                       language="en")
            words = [{"w": w["word"].strip(), "start": round(span["start"] + w["start"], 3),
                      "end": round(span["start"] + w["end"], 3)}
                     for seg in r["segments"] for w in seg.get("words", [])]
            rows.append({"who": span["who"], "said": r["text"].strip(), "words": words})
        sheet[sid] = rows
    (out / "words.json").write_text(json.dumps(sheet, indent=1) + "\n")
    print(f"words: {sum(len(x['words']) for rows in sheet.values() for x in rows)} words timed")


if __name__ == "__main__":
    main()
