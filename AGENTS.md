# explain-vid
Turn software projects into short explainer videos from a JSON scene spec; automated repo → facts → spec → video by agents.

## Run
- Render: `./scripts/render.sh <video>` (renders `videos/<video>/spec.json`) → `out/<video>/final.mp4` + `subtitles.srt` (voice → Manim, one process per scene in parallel → concat → mux; `THEME=`, `TTS=say|none`, `JOBS=`, `SCENES=` to re-render only changed scenes)
- Fast preview: `SPEC=<video> SCENES=id,id uv run manim -qh main.py Explainer` in `renderers/manim` (after voice.py)
- Gates: `uv run scripts/check.py <video>` (checks `out/<video>/`; grounding against `videos/<video>/facts.json`)
- New video end to end: `/make-explainer <source> <video>` (agents in `.claude/agents/`: fact-extractor, spec-author, template-builder, render-checker)
- Needs: ffmpeg, uv (Python via uv only, 3.12 pinned in renderers/manim), brew `cairo pango pkg-config` (for Manim)

## Constraints
- Goal: one shared spec format (`videos/<video>/spec.json`, schema in `videos/scene.schema.json`) rendered by fixed scene templates; LLMs fill specs, never write animation code.
- Hard gates are code (`scripts/check.py`), never model judgment. Every number on screen must trace to `facts.json` (grounding gate).
- Narration is the single source: audio, on-screen caption cues, subtitles and scene length all derive from `narration`.
- Scripts explain, not just describe: intuition → mechanism → proof per concept; on-screen jargon needs its plain phrase said first (glossary gate).
- Subagents only when the user asks, at most 2 at once; prefer inline work for spec edits and single-scene fixes.
- Non-goals now: production TTS voice (scratch `say` only), Blender, publishing, agents writing templates (template-builder is manual).

## Key decisions
- 2026-09-27 — Scene spec JSON + fixed, generic, data-driven templates (list in the schema); explainers show why (mechanism templates), not just inputs/outputs. Keeps renders deterministic and LLM output checkable.
- 2026-09-27 — Manim only, brutalist default theme. A Remotion bake-off on the same spec showed parity; not worth a second renderer.
- 2026-09-27 — Narration is the spec's only text; TTS timing drives scene length and caption cues, and steps are paced per sentence (`self.beat`, `data.beats` overrides). Keeps audio, captions and subtitles in sync; front-loaded animations left long static screens.
- 2026-09-27 — Figures are data: `flow` + deterministic layout (`renderers/manim/layout.py`), loops as a `cycle` ring. No per-figure code.
- 2026-09-27 — Spec generation via Claude Code subagents (facts → spec → render/gates loop); gates stay code; outputs in `out/<video>/`. No API infra yet.
- 2026-09-27 — Tool videos follow a tool arc (hook formula → flow → why → how you use it → commands) for a first-time viewer; no disclaimers. User preferred a plainer cut over mechanism detail.

## Notes
Judgment calls are logged in videos/NOTES.md; the agent prompts in `.claude/agents/` cite them by number.
