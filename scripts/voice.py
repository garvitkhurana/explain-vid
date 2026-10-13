# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Narration → audio, caption cues and scene timing. The spec's `narration` is the single source for all three.

Usage: uv run scripts/voice.py <video>   (reads video-specs/<video>/spec.json)
Voice: local Kokoro-82M via scripts/tts_kokoro.py, with the spec's meta.voice {voice, speed}. A spec with a cast
(meta.cast) speaks each line in the voice of its role's character in the skin (renderers/manim/skins.py; SKIN= overrides).

Writes out/<video>/voice/timing.json (read by the Manim renderer), out/<video>/voice/narration.wav, out/<video>/subtitles.srt.
With SKIN=<name> set, the output folder is out/<video>-<name>, so each skin keeps its own voices and render.
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RATE = 48000
LEAD_S = 0.25     # silence before a scene's first sentence (lets the visuals land first)
GAP_S = 0.2       # silence between sentences
TAIL_S = 0.4      # silence after the last sentence before the cut
MAX_CUE = 64      # characters per on-screen caption cue


def load_skins():
    spec = importlib.util.spec_from_file_location("skins", ROOT / "renderers" / "manim" / "skins.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SKINS = load_skins()


def out_dir(video: str) -> Path:
    """out/<video>, or out/<video>-<skin> when SKIN is set (renderer and gates use the same rule)."""
    return ROOT / "out" / (video + (f"-{os.environ['SKIN']}" if os.environ.get("SKIN") else ""))


def tts_kokoro(items: list[tuple[str, Path, str]], voice: dict) -> None:
    """All sentences in one call so the model loads once; each clip is then resampled to RATE for mixing.
    items: (text, wav path, Kokoro voice id)."""
    jobs = {"voice": voice.get("voice", "af_heart"), "speed": voice.get("speed", 1.0),
            "items": [(text, str(path), v) for text, path, v in items]}
    subprocess.run(["uv", "run", "--quiet", str(ROOT / "scripts" / "tts_kokoro.py")], input=json.dumps(jobs),
                   text=True, check=True)
    for _, path, _ in items:
        tmp = path.with_suffix(".24k.wav")
        path.rename(tmp)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-ar", str(RATE), "-ac", "1", str(path)], check=True)
        tmp.unlink()


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
    if len(sys.argv) != 2:
        raise SystemExit("Usage: uv run scripts/voice.py <video>   (a folder in video-specs/)")
    video = sys.argv[1]
    spec = json.loads((ROOT / "video-specs" / video / "spec.json").read_text())
    OUT = out_dir(video) / "voice"  # one output dir per spec (and skin) so videos don't overwrite each other
    voice = spec["meta"].get("voice", {})
    cast = SKINS.SKINS[SKINS.skin_name(spec)]["roles"] if spec["meta"].get("cast") else None

    def speaker(who):  # voice id for a line; without a cast every line is the spec's one voice
        return cast[who]["voice"] if cast else voice.get("voice", "af_heart")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    fps = spec["meta"]["fps"]
    lines = {s["id"]: [SKINS.line(x) for x in s["narration"]] for s in spec["scenes"]}
    tts_kokoro([(text, OUT / f"{sid}_{i:02}.wav", speaker(who))
                for sid, ls in lines.items() for i, (who, text, _) in enumerate(ls)], voice)

    scenes, clips, t0 = {}, [], 0.0  # clips: (absolute start, wav path)
    for s in spec["scenes"]:
        t = LEAD_S
        cues, sentences, spans = [], [], []
        for i, (who, sentence, _) in enumerate(lines[s["id"]]):
            sentences.append(round(t, 3))  # scene-relative start; scene templates pace their steps on these
            wav = OUT / f"{s['id']}_{i:02}.wav"
            d = duration(wav)
            clips.append((t0 + t, wav))
            spans.append({"who": who, "start": round(t, 3), "end": round(t + d, 3)})
            # Split the sentence's time across its cues by character count.
            parts = split_cues(sentence)
            total = sum(len(p) for p in parts)
            ct = t
            for p in parts:
                cd = d * len(p) / total
                cues.append({"text": p, "start": round(ct, 3), "end": round(ct + cd, 3), "who": who})
                ct += cd
            t += d + GAP_S
        spoken = (t - GAP_S + TAIL_S) if s["narration"] else 0.0  # a silent card: length = duration_s
        # Snap scene boundaries to whole frames so scenes rendered separately concatenate without drift.
        start_f = round(t0 * fps)
        frames = round((t0 + max(s["duration_s"], spoken)) * fps) - start_f
        scenes[s["id"]] = {"start": start_f / fps, "frames": frames, "duration": frames / fps,
                           "spoken": round(spoken, 3), "sentences": sentences, "lines": spans, "cues": cues}
        t0 = (start_f + frames) / fps

    timing = {"video": video, "skin": SKINS.skin_name(spec) if cast else None, "fps": fps, "total": t0, "scenes": scenes}
    (OUT / "timing.json").write_text(json.dumps(timing, indent=2) + "\n")

    # Subtitles use the same cues, shifted to absolute time.
    srt, n = [], 0
    for sid, sc in scenes.items():
        for c in sc["cues"]:
            n += 1
            text = f"{cast[c['who']]['name'].split()[0].upper()}: {c['text']}" if cast else c["text"]
            srt += [str(n), f"{srt_time(sc['start'] + c['start'])} --> {srt_time(sc['start'] + c['end'])}", text, ""]
    (OUT.parent / "subtitles.srt").write_text("\n".join(srt))

    if clips:
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

    print(f"voice: {n} cues, {t0:.1f}s total")


if __name__ == "__main__":
    main()
