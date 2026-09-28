# explain-vid

Explainer videos for software projects, generated from a JSON scene spec.

## Setup
```bash
brew install cairo pango pkg-config ffmpeg node uv
cd renderers/remotion && npm install && cd ../..
cd renderers/manim && uv sync && cd ../..
```

## Render
```bash
./scripts/render.sh semif           # out/semif/final.mp4 with narration + subtitles.srt (Manim, brutalist)
TTS=none ./scripts/render.sh semif  # silent, timing estimated from word count (fast)
./scripts/render_all.sh semif       # reference: both stacks + out/compare.mp4
uv run scripts/check.py semif       # hard gates
```

## Write a new video
Each video is a folder: `videos/<video>/spec.json` is its script (scene types: title, problem, pipeline, readout, race, branch, bars, metrics, loop, checklist, fanout, gantt, balance, outro).
Each scene has `narration` (spoken sentences; captions and timing come from it) and `duration_s` (minimum length). Then:
```bash
./scripts/render.sh <video>
uv run scripts/check.py <video>
```
Both renderers read the same file: Remotion via `--props`, Manim via the `SPEC` env var.

## Tips
- Manim themes: `THEME=midnight|neon|brutalist|pop` (presets in `renderers/manim/theme.py`).
  Preview a few scenes fast: `SPEC=semif SCENES=title,readout THEME=pop uv run manim -qh main.py Explainer` in `renderers/manim`.
- `cd renderers/remotion && npm run studio` for a live, scrubbable preview.
- Manim text doesn't wrap; use `fit()` in `main.py` for anything that might overflow.
- Animated text: use `on_change(key, build)` (rebuilds only when `key()` changes), never `always_redraw` — per-frame
  text rebuilds made one scene take 2 minutes.
- Pace templates with `self.beat(step, sentence_index, frac=0)` so each step lands when its sentence is spoken;
  override per scene with `"beats": {"step": index}` in the spec's `data`. Check pacing with ffmpeg `freezedetect`.
- Scenes render in parallel (`JOBS=` to limit). Scene lengths are frame-exact so the concatenated video stays in sync.
