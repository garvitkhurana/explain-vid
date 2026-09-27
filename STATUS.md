# STATUS — Claude Code, 2026-09-27

## True now
- SemIf explainer: 52 s, silent + captions, from `specs/semif.json`, both stacks. 9/9 gates pass.
- Story: title → overview → readout (A/B/C logits → softmax) → race (5.21x) → shared state (KV branch, 20.03 vs 2.33/s) → numbers → outro.
- New templates `readout` and `branch` in both renderers; bars scene dropped from this spec (template kept).
- Architecture facts taken from SemIf source (core.py, direct.py, shared.py); lessons in specs/NOTES.md items 8–12.
- Readout logits/probabilities are illustrative (captioned); all other numbers from SemIf README.
- Git: pushed initial commit to private github.com/garvitkhurana/explain-vid. This pass is on branch architecture-scenes (PR to main).
- Render times: Remotion ~20 s, Manim ~46 s.

## Observations for the stack choice
- Manim again needed layout fixes (caption overflow, clipped label, overlap). Remotion's new scenes rendered clean first try.

## Next action
User reviews out/compare.mp4, picks a stack. Then facts.json extractor that reads source, not just README.

## Open first
out/compare.mp4, specs/semif.json, specs/NOTES.md

## Blockers
None. Narration deferred by choice.
