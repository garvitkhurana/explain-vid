# explain-vid
Turn software projects into short explainer videos from a JSON scene spec; automated repo → facts → spec → video by agents.

## Run
- Render: `./scripts/render.sh <video>` (renders `video-specs/<video>/spec.json`; a frameless dry run checks spec + predicted still screens first, then full gates) → `out/<video>/final.mp4` + `subtitles.srt` (voice → Manim, one process per scene in parallel → concat → mux; `DRY=1` stop after it, `SCENES=` re-render only changed scenes, `THEME=`, `JOBS=`)
- Gates only: `uv run scripts/check.py <video>` (structure + grounding against `video-specs/<video>/facts.json`, then `out/<video>/`)
- New video end to end: `/make-explainer <source> <video>` (agents in `.claude/agents/`: fact-extractor, spec-author; template-builder is manual)
- Needs: Apple Silicon (Kokoro TTS via mlx-audio; model fetched on first run), ffmpeg, uv (Python via uv only, 3.12 pinned in renderers/manim), brew `cairo pango pkg-config` (for Manim)

## Constraints
- Goal: one shared spec format (`video-specs/<video>/spec.json`, schema in `video-specs/scene.schema.json`) rendered by fixed scene templates; LLMs fill specs, never write animation code.
- Hard gates are code (`scripts/check.py`), never model judgment. Every number on screen must trace to `facts.json` (grounding gate).
- Story follows the content, not the medium: `meta.arc` tool | concept | result, every scene has a `role` in it, `meta.thesis` said aloud, one title opening and one source-card ending (structure gates).
- Narration is the single source: audio, on-screen caption cues, subtitles and scene length all derive from `narration`.
- Scripts explain, not just describe: intuition → mechanism → proof per concept; on-screen jargon needs its plain phrase said first (glossary gate).
- Subagents only when the user asks, at most 2 at once; prefer inline work for spec edits and single-scene fixes.
- Non-goals now: voice cloning, Blender, publishing, agents writing templates (template-builder is manual).

## Key decisions
- 2026-09-27 — Scene spec JSON + fixed, generic, data-driven templates (list in the schema); explainers show why (mechanism templates), not just inputs/outputs. Keeps renders deterministic and LLM output checkable.
- 2026-09-27 — Manim only, brutalist default theme. A Remotion bake-off on the same spec showed parity; not worth a second renderer.
- 2026-09-27 — Narration is the spec's only text; TTS timing drives scene length and caption cues, and steps are paced per sentence (`self.beat`, `data.beats` overrides). Keeps audio, captions and subtitles in sync; front-loaded animations left long static screens.
- 2026-09-27 — Figures are data: `flow` + deterministic layout (`renderers/manim/layout.py`), loops as a `cycle` ring. No per-figure code.
- 2026-09-27 — Spec generation via Claude Code subagents (facts → spec → render/gates loop); gates stay code; outputs in `out/<video>/`. No API infra yet.
- 2026-09-27 — Tool videos follow a tool arc (hook formula → flow → why → how you use it → commands) for a first-time viewer; no disclaimers. User preferred a plainer cut over mechanism detail.
- 2026-09-28 — Narration voice: Kokoro-82M via mlx-audio, local (voice `af_heart`), replacing macOS `say` as default. Free, offline after first run and deterministic; `say` sounded bad. User picked it over their own cloned voice.
- 2026-09-28 — Cleanup: dropped the semif and long_running_agents videos (no facts.json) with their one-off templates, unused templates, silent figure mode, `say` TTS and the render-checker agent. Every video needs facts.json. Fewer parts to keep in sync.

## Notes
Judgment calls are logged in video-specs/NOTES.md; the agent prompts in `.claude/agents/` cite them by number.
