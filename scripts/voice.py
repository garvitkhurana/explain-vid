# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Narration → audio, caption cues and scene timing. The spec's `narration` is the single source for all three.

Usage: uv run scripts/voice.py [spec.json]
Env:   TTS=say|none   (none = estimate timing from word count, no audio; for fast silent previews)

Writes out/<spec>/voice/timing.json (read by the Manim renderer), out/<spec>/voice/narration.wav, out/<spec>/subtitles.srt.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RATE = 48000
LEAD_S = 0.4      # silence before a scene's first sentence (lets the visuals land first)
GAP_S = 0.3       # silence between sentences
TAIL_S = 0.6      # silence after the last sentence before the cut
MAX_CUE = 64      # characters per on-screen caption cue


def tts_say(text: str, path: Path, voice: dict) -> None:
    aiff = path.with_suffix(".aiff")
    subprocess.run(["say", "-v", voice.get("voice", "Samantha"), "-r", str(voice.get("rate_wpm", 175)),
                    "-o", str(aiff), text], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(aiff), "-ar", str(RATE), "-ac", "1", str(path)], check=True)
    aiff.unlink()


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def split_cues(sentence: str) -> list[str]:
    """One cue per sentence; long sentences split at the comma/colon nearest the middle, else at a space."""
    if len(sentence) <= MAX_CUE:
        return [sentence]
    mid = len(sentence) // 2
    cuts = [m.end() for m in re.finditer(r"[,:;]\s", sentence)] or [m.end() for m in re.finditer(r"\s", sentence)]
    cut = min(cuts, key=lambda c: abs(c - mid))
    return split_cues(sentence[:cut].strip()) + split_cues(sentence[cut:].strip())


def srt_time(t: float) -> str:
    ms = round(t * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def main() -> None:
    spec_name = sys.argv[1] if len(sys.argv) > 1 else "semif.json"
    spec = json.loads((ROOT / "specs" / spec_name).read_text())
    OUT = ROOT / "out" / Path(spec_name).stem / "voice"  # one output dir per spec so videos don't overwrite each other
    voice = spec["meta"].get("voice", {})
    backend = os.environ.get("TTS", voice.get("backend", "say"))
    if backend not in ("say", "none"):
        raise SystemExit(f"Unknown TTS backend {backend!r} (say|none)")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    wpm = voice.get("rate_wpm", 175)
    fps = spec["meta"]["fps"]

    scenes, clips, t0 = {}, [], 0.0  # clips: (absolute start, wav path)
    for s in spec["scenes"]:
        t = LEAD_S
        cues, sentences = [], []
        for i, sentence in enumerate(s["narration"]):
            sentences.append(round(t, 3))  # scene-relative start; scene templates pace their steps on these
            if backend == "say":
                wav = OUT / f"{s['id']}_{i:02}.wav"
                tts_say(sentence, wav, voice)
                d = duration(wav)
                clips.append((t0 + t, wav))
            else:
                d = len(sentence.split()) / wpm * 60
            # Split the sentence's time across its cues by character count.
            parts = split_cues(sentence)
            total = sum(len(p) for p in parts)
            ct = t
            for p in parts:
                cd = d * len(p) / total
                cues.append({"text": p, "start": round(ct, 3), "end": round(ct + cd, 3)})
                ct += cd
            t += d + GAP_S
        spoken = t - GAP_S + TAIL_S
        # Snap scene boundaries to whole frames so scenes rendered separately concatenate without drift.
        start_f = round(t0 * fps)
        frames = round((t0 + max(s["duration_s"], spoken)) * fps) - start_f
        scenes[s["id"]] = {"start": start_f / fps, "frames": frames, "duration": frames / fps,
                           "spoken": round(spoken, 3), "sentences": sentences, "cues": cues}
        t0 = (start_f + frames) / fps

    timing = {"spec": spec_name, "backend": backend, "fps": fps, "total": t0, "scenes": scenes}
    (OUT / "timing.json").write_text(json.dumps(timing, indent=2) + "\n")

    # Subtitles use the same cues, shifted to absolute time.
    lines, n = [], 0
    for sid, sc in scenes.items():
        for c in sc["cues"]:
            n += 1
            lines += [str(n), f"{srt_time(sc['start'] + c['start'])} --> {srt_time(sc['start'] + c['end'])}", c["text"], ""]
    (OUT.parent / "subtitles.srt").write_text("\n".join(lines))

    if backend == "say":
        # One track: every clip delayed to its absolute start, mixed over silence of the full length.
        inputs, filters = [], []
        for k, (start, wav) in enumerate(clips):
            inputs += ["-i", str(wav)]
            ms = round(start * 1000)
            filters.append(f"[{k}]adelay={ms}|{ms}[a{k}]")
        mix = "".join(f"[a{k}]" for k in range(len(clips)))
        filters.append(f"{mix}amix=inputs={len(clips)}:normalize=0,apad=whole_dur={t0}[out]")
        subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filters),
                        "-map", "[out]", "-ar", str(RATE), "-ac", "1", str(OUT / "narration.wav")], check=True)

    over = [sid for sid, sc in scenes.items() if sc["spoken"] > spec_min(spec, sid)]
    print(f"{backend}: {n} cues, {t0:.1f}s total; audio extended: {', '.join(over) or 'none'}")


def spec_min(spec: dict, sid: str) -> float:
    return next(s["duration_s"] for s in spec["scenes"] if s["id"] == sid)


if __name__ == "__main__":
    main()
