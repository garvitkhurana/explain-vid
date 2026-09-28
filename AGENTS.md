# explain-vid
Turn software projects into short explainer videos from a JSON scene spec; automated repo → facts → spec → video by agents.

## Run
- Render: `./scripts/render.sh <video>` (renders `videos/<video>/spec.json`) → `out/<video>/final.mp4` + `subtitles.srt` (voice → Manim, one process per scene in parallel → concat → mux; `THEME=`, `TTS=say|none`, `JOBS=`)
- Fast preview: `SPEC=<video> SCENES=id,id uv run manim -qh main.py Explainer` in `renderers/manim` (after voice.py)
- Reference comparison, both stacks: `./scripts/render_all.sh <video>` → `out/{remotion,manim,compare}.mp4`
- Gates: `uv run scripts/check.py <video>` (checks `out/<video>/`; grounding against `videos/<video>/facts.json`)
- New video end to end: `/make-explainer <source> <video>` (agents in `.claude/agents/`: fact-extractor, spec-author, template-builder, render-checker)
- Needs: node, ffmpeg, uv (Python via uv only, 3.12 pinned in renderers/manim), brew `cairo pango pkg-config` (for Manim)

## Constraints
- Goal: one shared spec format (`videos/<video>/spec.json`, schema in `videos/scene.schema.json`) rendered by fixed scene templates; LLMs fill specs, never write animation code.
- Hard gates are code (`scripts/check.py`), never model judgment. Every number on screen must trace to `facts.json` (grounding gate).
- Narration is the single source: audio, on-screen caption cues, subtitles and scene length all derive from `narration`.
- Scripts explain, not just describe: intuition → mechanism → proof per concept; on-screen jargon needs its plain phrase said first (glossary gate).
- Non-goals now: production TTS voice (scratch `say` only), Blender, publishing, agents writing templates (template-builder is manual).

## Key decisions
- 2026-09-27 — Scene spec JSON + fixed template set (title, pipeline, race, bars, metrics, outro). Keeps renders deterministic and LLM output checkable.
- 2026-09-27 — Bake-off Remotion vs Manim on the same spec before picking one stack. Compare look, authoring effort, render time.
- 2026-09-27 — Added readout + branch templates for architecture (mechanism) scenes. Explainers must show why, not just inputs/outputs.
- 2026-09-27 — Manim is the renderer, brutalist the default theme. User preferred Manim's look; Remotion kept only as a comparison reference.
- 2026-09-27 — Narration replaces captions as the spec's text field; TTS timing drives scene length and caption cues. One source keeps audio, captions and subtitles in sync and is what an LLM script step will fill.
- 2026-09-27 — Scene steps are paced by narration sentences (`self.beat(step, sentence)`; spec `data.beats` overrides). Front-loaded animations left 9–14 s of static screen per scene.
- 2026-09-27 — Templates stay generic and data-driven (loop, checklist, fanout, gantt, balance added for agent-unwrapped + Habitat); outputs go to `out/<video>/` so videos don't collide.
- 2026-09-27 — Spec generation via Claude Code subagents (facts → spec → render/gates loop); gates stay code. Reuses dev-agent prompts; no API infra yet. Videos live in `videos/<video>/{spec,facts}.json`.

## Notes
Judgment calls are logged in videos/NOTES.md; the agent prompts in `.claude/agents/` cite them by number.
