# STATUS — Claude Code, 2026-09-27

## True now
- SemIf explainer, narrated: 8 scenes, 98.4 s, out/final.mp4 + out/subtitles.srt. 13/13 gates pass. Render ~43 s.
- **Visuals paced to the voice:** every template step waits for its narration sentence via `self.beat(step, i, frac)`
  (timing.json now has per-scene `sentences`; spec `data.beats` can override). Longest static stretch 14 s → 4.4 s
  (ffmpeg freezedetect, captions cropped out).
- New `problem` scene: ticket → LLM writes prose (streams) → parse() → `if queue == ...`, crossed out on
  "why write anything at all?". Title narration cut to one line.
- Narration is the single source (audio, caption cues, subtitles, scene length). Scratch voice: macOS `say`.
- Render: voice → Manim one process per scene in parallel → frame-exact concat → mux. Race scene uses `on_change()`.
- Stack: Manim + brutalist theme. MLX: useful for a better TTS voice, not for rendering.
- Git: PR #1 merged. PR #2 open (architecture-scenes → main) with all narration/pacing/speed work; tree clean.

## Next action
User reviews out/final.mp4. Candidates: review/merge PR #2; MLX TTS voice; Paperclip as video #2.

## Open first
out/final.mp4, renderers/manim/main.py (beat/span, scene_problem), specs/semif.json

## Blockers
None.
