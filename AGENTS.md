# explain-vid
Turn software projects into short explainer videos from a JSON scene spec; automated repo → facts → spec → video by agents.

## Run
- One-shot video (current way): `./scripts/oneshot.sh <video>` renders `renderers/manim/oneshot_<video>.py` (bespoke visuals on the channel kit `oneshot.py`) with narration from `video-specs/<video>/spec.json` → `out/<video>/final.mp4` + `subtitles.srt` + `contact.png`; one process per scene in parallel (~20 s); `DRAFT=1` 480p, `SCENES=` re-render some
- Old template videos: `./scripts/render.sh <video>` (renders `video-specs/<video>/spec.json`; a frameless dry run checks spec + predicted still screens first, then full gates) → `out/<video>/final.mp4` + `subtitles.srt` (voice → Manim, one process per scene in parallel → concat → mux; `DRY=1` stop after it, `SCENES=` re-render only changed scenes, `THEME=`, `JOBS=`); gates `uv run scripts/check.py <video>`
- `/make-explainer` (template flow, to be rewritten for one-shot); setup: `./scripts/setup.sh`. Needs: Apple Silicon (Kokoro TTS via mlx-audio), ffmpeg, uv (Python via uv only, 3.12 pinned in renderers/manim), brew `cairo pango pkg-config` (for Manim)

## Constraints
- Goal: each video's visuals are drawn fresh for its ideas (one Manim file per video); the channel look (cast, board, captions, wordmark, end card, voice) comes only from `oneshot.py`. Templates (`main.py`) are kept for old videos only.
- Hard gates are code (`scripts/check.py`), never model judgment. Every number on screen must trace to `facts.json` (grounding gate).
- Story follows the content, not the medium: `meta.arc` tool | concept | result, every scene has a `role` in it, `meta.thesis` said aloud, one title opening and one source-card ending (structure gates).
- Narration is the single source: audio, on-screen caption cues, subtitles and scene length all derive from `narration`.
- Scripts explain, not just describe: intuition → mechanism → proof per concept; on-screen jargon needs its plain phrase said first (glossary gate).
- Subagents only when the user asks, at most 2 at once; prefer inline work for spec edits and single-scene fixes.
- Non-goals now: voice cloning, Blender, publishing, agents writing templates (template-builder is manual), general topics without one source (a trial on company finances fit poorly; the pipeline is for coding blogs, papers and repos).

## Key decisions
- 2026-09-27 — Scene spec JSON + fixed, generic, data-driven templates (list in the schema); explainers show why (mechanism templates), not just inputs/outputs. Keeps renders deterministic and LLM output checkable.
- 2026-09-27 — Manim only, brutalist default theme. A Remotion bake-off on the same spec showed parity; not worth a second renderer.
- 2026-09-27 — Narration is the spec's only text; TTS timing drives scene length and caption cues, and steps are paced per sentence (`self.beat`, `data.beats` overrides). Keeps audio, captions and subtitles in sync; front-loaded animations left long static screens.
- 2026-09-27 — Figures are data: `flow` + deterministic layout (`renderers/manim/layout.py`), loops as a `cycle` ring. No per-figure code.
- 2026-09-27 — Spec generation via Claude Code subagents (facts → spec → render/gates loop); gates stay code; outputs in `out/<video>/`. No API infra yet.
- 2026-09-27 — Tool videos follow a tool arc (hook formula → flow → why → how you use it → commands) for a first-time viewer; no disclaimers. User preferred a plainer cut over mechanism detail.
- 2026-09-28 — Narration voice: Kokoro-82M via mlx-audio, local (voice `af_heart`), replacing macOS `say` as default. Free, offline after first run and deterministic; `say` sounded bad. User picked it over their own cloned voice.
- 2026-09-28 — Cleanup: dropped the semif and long_running_agents videos (no facts.json) with their one-off templates, unused templates, silent figure mode, `say` TTS and the render-checker agent. Every video needs facts.json. Fewer parts to keep in sync.
- 2026-10-13 — Pixel cast, office skin, is the look of the "AI explained" series on The Uninitiated (16:9, one channel). Body scenes sit close on the board (readable on a phone; zooming out to the cast each time looked odd) and the asker pops up in the corner; title and end card carry the channel wordmark (renderers/manim/brand/). Clean and credible like Money Lens; the asker is "the uninitiated".
- 2026-10-13 — One-shot visuals replace templates for new videos (Gemini 4 Argon, Muse Wonder first). Templates forced ideas into fixed boxes; the bespoke Jev cut explained better. `/make-explainer` and the subagents still describe templates (to update).
## Notes
Judgment calls are logged in video-specs/NOTES.md; the agent prompts in `.claude/agents/` cite them by number.
