# explain-vid
Turn software projects into short explainer videos from a JSON scene spec; automate repo → spec → video later.

## Run
- Both stacks + side-by-side: `./scripts/render_all.sh` → `out/{remotion,manim,compare}.mp4`
- Gates: `uv run scripts/check.py [spec.json]`
- Remotion live preview: `cd renderers/remotion && npm run studio`
- Needs: node, ffmpeg, uv, brew `cairo pango pkg-config` (for Manim)

## Constraints
- Goal: one shared spec (`specs/*.json`, schema in `specs/scene.schema.json`) rendered by fixed scene templates; LLMs fill specs, never write animation code.
- Hard gates are code (`scripts/check.py`), never model judgment. Every number in a spec must trace to the source repo.
- Non-goals now: narration/TTS (deferred, `caption` field reserved for it), Blender, publishing, LLM spec generation.
- Python via uv only (pinned 3.12 in renderers/manim).

## Key decisions
- 2026-09-27 — Scene spec JSON + fixed template set (title, pipeline, race, bars, metrics, outro). Keeps renders deterministic and LLM output checkable.
- 2026-09-27 — Bake-off Remotion vs Manim on the same spec before picking one stack. Compare look, authoring effort, render time.
- 2026-09-27 — Added readout + branch templates for architecture (mechanism) scenes. Explainers must show why, not just inputs/outputs.

## Session
See STATUS.md. Hand-spec judgment calls are logged in specs/NOTES.md (future LLM prompt).
