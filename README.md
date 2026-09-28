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
./scripts/render.sh           # out/semif/final.mp4 with narration + subtitles.srt (Manim, brutalist)
TTS=none ./scripts/render.sh  # silent, timing estimated from word count (fast)
./scripts/render_all.sh       # reference: both stacks + out/compare.mp4
uv run scripts/check.py       # hard gates
```

## Write a new video
Add `specs/<name>.json` (scene types: title, problem, pipeline, readout, race, branch, bars, metrics, loop, checklist, fanout, gantt, balance, flow, outro).
Each scene has `narration` (spoken sentences; captions and timing come from it) and `duration_s` (minimum length). Then:
```bash
./scripts/render.sh <name>.json
uv run scripts/check.py <name>.json
```
Both renderers read the same file: Remotion via `--props`, Manim via the `SPEC` env var.

## Ending every video the same way
Set `meta.source` once — `{"kind": "repo"|"blog"|"paper", "url": "...", "credit": "optional"}` — and end the spec
with `{"id": "source", "type": "source", "duration_s": 3.5, "narration": [], "data": {}}`. The card reads
"Check out the repo" / "Read the full post at" / "Read the full paper at" + the link. No custom outros.

## Figures (`flow` scenes)
Describe a diagram as data and the renderer lays it out and animates it — see `specs/figures.json`:
`panels`, `nodes` (`shape`: box/stack/trapezoid/pill/matrix/bars, `role` → colour slot via `roles`), `edges`
(`style: dashed`, `label`), `steps` (reveal, highlight, flow with packet `kind`/`back`, diagonal, cells, bars).
`mode: "figure"` = silent, fixed `hold` per step; otherwise steps wait on narration sentences.
Subscripts: write `S_{N}`, not Unicode subscript characters (fonts lack most of them).

## Tips
- Manim themes: `THEME=midnight|neon|brutalist|pop` (presets in `renderers/manim/theme.py`).
  Preview a few scenes fast: `SCENES=title,readout THEME=pop uv run manim -qh main.py Explainer` in `renderers/manim`.
- `cd renderers/remotion && npm run studio` for a live, scrubbable preview.
- Manim text doesn't wrap; use `fit()` in `main.py` for anything that might overflow.
- Animated text: use `on_change(key, build)` (rebuilds only when `key()` changes), never `always_redraw` — per-frame
  text rebuilds made one scene take 2 minutes.
- Subtitles own the bottom band: narrated scenes must keep content above `CAPTION_TOP`; a render fails
  if anything reaches into it. Check all specs in seconds with `--dry_run` (see NOTES pass 8).
- Iterate fast: `SCENES=how ./scripts/render.sh spec.json` re-renders one scene and reuses the rest
  (same narration only). A long scene still costs its full length.
- Pace templates with `self.beat(step, sentence_index, frac=0)` so each step lands when its sentence is spoken;
  override per scene with `"beats": {"step": index}` or `[index, fraction]` (partway through a sentence). Check pacing with ffmpeg `freezedetect`.
- Scenes render in parallel (`JOBS=` to limit). Scene lengths are frame-exact so the concatenated video stays in sync.
