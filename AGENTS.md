# explain-vid
Turn software projects into short explainer videos from a JSON scene spec; automate repo → spec → video later.

## Run
- Render: `./scripts/render.sh [spec.json]` → `out/final.mp4` + `out/subtitles.srt` (voice → Manim, one process per scene in parallel → concat → mux; `THEME=`, `TTS=say|none`, `JOBS=`)
- Fast preview: `SCENES=id,id THEME=... uv run manim -qh main.py Explainer` in `renderers/manim`
- Reference comparison, both stacks: `./scripts/render_all.sh` → `out/{remotion,manim,compare}.mp4`
- Gates: `uv run scripts/check.py [spec.json]`
- Needs: node, ffmpeg, uv, brew `cairo pango pkg-config` (for Manim)

## Constraints
- Goal: one shared spec (`specs/*.json`, schema in `specs/scene.schema.json`) rendered by fixed scene templates; LLMs fill specs, never write animation code.
- Hard gates are code (`scripts/check.py`), never model judgment. Every number in a spec must trace to the source repo.
- Narration is the single source: audio, on-screen caption cues, subtitles and scene length all derive from `narration`.
- Scripts explain, not just describe: intuition → mechanism → proof per concept; on-screen jargon needs its plain phrase said first (glossary gate).
- Non-goals now: production TTS voice (scratch `say` only), Blender, publishing, LLM spec generation.
- Python via uv only (pinned 3.12 in renderers/manim).

## Key decisions
- 2026-09-27 — Scene spec JSON + fixed template set (title, pipeline, race, bars, metrics, outro). Keeps renders deterministic and LLM output checkable.
- 2026-09-27 — Bake-off Remotion vs Manim on the same spec before picking one stack. Compare look, authoring effort, render time.
- 2026-09-27 — Added readout + branch templates for architecture (mechanism) scenes. Explainers must show why, not just inputs/outputs.
- 2026-09-27 — Manim is the renderer, brutalist the default theme. User preferred Manim's look; Remotion kept only as a comparison reference.
- 2026-09-27 — Narration replaces captions as the spec's text field; TTS timing drives scene length and caption cues. One source keeps audio, captions and subtitles in sync and is what an LLM script step will fill.
- 2026-09-27 — Scene steps are paced by narration sentences (`self.beat(step, sentence)`; spec `data.beats` overrides). Front-loaded animations left 9–14 s of static screen per scene.

## Session
See STATUS.md. Hand-spec judgment calls are logged in specs/NOTES.md (future LLM prompt).
