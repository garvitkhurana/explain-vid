# explain-vid

Explainer videos for software projects, generated from a JSON scene spec.

Sample (100 s), made from Rich Sutton's essay *The Bitter Lesson* with one command in Claude Code:
```
/make-explainer http://www.incompleteideas.net/IncIdeas/BitterLesson.html bitter_lesson
```

https://github.com/user-attachments/assets/7205e1c0-1a89-41f7-ba52-2ba94467b6e0

## Quickstart
Needs an Apple Silicon Mac, [Homebrew](https://brew.sh) and [Claude Code](https://claude.com/claude-code).
```bash
git clone https://github.com/garvitkhurana/explain-vid.git && cd explain-vid
claude
```
Then, in Claude Code:
```
/make-explainer https://example.com/some-post my_video
```
The first run installs everything (`scripts/setup.sh`, a few minutes: Homebrew tools, the Manim environment and a
~350 MB voice model). Each video takes about 5–10 minutes and lands in `out/my_video/final.mp4` with `subtitles.srt`.
The source can be a blog post, a paper or a repo (URL or local path).

## Pipeline
```
source (repo, blog, paper)
  → video-specs/<video>/facts.json   what the video may claim, each with a source quote   (fact-extractor agent)
  → video-specs/<video>/spec.json    arc + scenes: narration and template data             (spec-author agent)
  → scripts/voice.py                 narration → audio, captions, scene timing              (Kokoro, local)
  → renderers/manim/main.py          one fixed template per scene type, driven by the data
  → scripts/check.py                 hard gates: structure, grounding, timing, render
  → out/<video>/final.mp4 + subtitles.srt
```
The source's medium only changes how facts are read and what the closing card says. The story follows the content:
`meta.arc` is `tool` (something you run), `concept` (an idea) or `result` (a finding), and each scene's `role`
places it in that arc. Each scene's `type` is picked by what it shows (a loop → `cycle`, a pipeline → `flow`,
two options → `compare`, …). The list is in `video-specs/scene.schema.json`, and each template's data keys are
in its `scene_<type>` docstring in `main.py`.

## Setup
```bash
./scripts/setup.sh    # Homebrew tools, Manim environment, voice model; safe to re-run
```
Apple Silicon only (Kokoro runs on MLX). `/make-explainer` runs it for you on the first run.

## Use
```bash
./scripts/render.sh ai_harness                   # voice → dry run (spec gates, predicted stills) → render → gates
DRY=1 ./scripts/render.sh ai_harness             # stop after the dry run (~30 s): spec gates + predicted stills
SCENES=thesis ./scripts/render.sh ai_harness     # re-render one scene, reuse the rest (narration unchanged)
uv run scripts/check.py ai_harness               # gates only
```
New video from a source, end to end (in Claude Code): `/make-explainer <repo path or URL> <video>`.

## Writing a spec
- `narration` is the only text source: audio, captions, subtitles and scene length all come from it.
  Each sentence reveals one step of the scene (`data.beats` remaps steps to sentences).
- Every number on screen or written as digits must match a `value` in `facts.json`; commands and code must appear
  there verbatim.
- `meta.thesis` is the video's point in one sentence; it must be said in the narration of the hook (tool), takeaway
  (concept) or proof (result).
- Open on a `title` scene (role `hook`); end on `{"id": "source", "type": "source", ...}`, the only call to action.
  It reads "Clone the repo to get started" / "Read the full post at" / "Read the full paper at" + `meta.source.url`,
  and may be narrated.
- Judgment calls behind these rules: `video-specs/NOTES.md`.

## Template tips
- Manim text doesn't wrap: `fit()` anything that might overflow. Animated text: `on_change(key, build)`, never
  `always_redraw` (per-frame rebuilds made one scene take 2 minutes).
- Captions own the bottom band: a render fails if content reaches below `CAPTION_TOP`.
- Pace steps with `self.beat(step, sentence_index)` so each lands when its sentence is spoken.
- Themes: `THEME=brutalist|midnight|neon|pop` (presets in `renderers/manim/theme.py`).
