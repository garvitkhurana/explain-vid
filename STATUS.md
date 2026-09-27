# STATUS — Claude Code, 2026-09-27

## True now
- SemIf explainer: 39 s (was 59 s), silent + captions, from `specs/semif.json`, both stacks.
- Pacing pass: scene lengths cut to fit a silent video, faster entrances in both renderers,
  race slow-mo now `data.time_scale` (1.1) in the spec instead of hardcoded.
- Spec input unified: `./scripts/render_all.sh <name>.json` → Remotion `--props`, Manim `SPEC` env.
- Render times now: Remotion ~12 s, Manim ~43 s. `scripts/check.py`: 9/9 pass.
- Bars scene values are illustrative (captioned); other numbers from SemIf README.
- Own git repo at ~/Projects/explain-vid (initial commit, no remote). out/, node_modules, .venv ignored.

## Observations for the stack choice
- Manim: no text layout engine (needs `fit()`), ~3.5x slower render. Remotion: live studio, browser layout.

## Next action
User reviews out/compare.mp4 and picks a stack. Then: facts.json extractor + grounding gate. Maybe a pacing gate (max idle seconds per scene).

## Open first
out/compare.mp4, specs/semif.json

## Blockers
None. Narration deferred by choice.
