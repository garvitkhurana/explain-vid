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
./scripts/render_all.sh       # out/remotion.mp4, out/manim.mp4, out/compare.mp4
uv run scripts/check.py       # hard gates
```

## Write a new video
Add `specs/<name>.json` (scene types: title, pipeline, race, bars, metrics, outro), then:
```bash
./scripts/render_all.sh <name>.json
uv run scripts/check.py <name>.json
```
Both renderers read the same file: Remotion via `--props`, Manim via the `SPEC` env var.

## Tips
- `cd renderers/remotion && npm run studio` for a live, scrubbable preview.
- Manim text doesn't wrap; use `fit()` in `main.py` for anything that might overflow.
