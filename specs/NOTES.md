# Decisions made hand-writing specs/semif.json
(These are the judgment calls a future LLM step must make; they become its prompt.)

1. **The aha:** "stop generating text you parse back into an if" — lead with the problem in the title kicker.
2. **Story order:** problem → mechanism (pipeline) → proof of speed (race) → what you get (bars) → quality/limits (metrics) → call to action.
3. **Pick the most visual evidence:** the 1.023 s vs 5.332 s race (README "Speed" table) beats any table; the repo's own replay GIF confirms it.
4. **Compare like with like:** Jev's 0.883 is *TypeSafe-subset agreement*, so pair it with SemIf's 0.845 (same column), not 0.813 (balanced accuracy). Easy to get wrong — grounding gate must check column, not just value.
5. **Label non-measured data:** no committed probabilities for examples/decisions.jsonl route-1, so bars are marked illustrative in the caption.
6. **Drop nuance that doesn't fit 60 s:** 18/21 argmax agreement, BF16 flips, reranker row. Keep them for a longer cut.
7. **Budget:** ~60 s total, captions ≤ 120 chars, 6 scenes.

Sources: README.md (Speed, Quality, Calibration tables), examples/decisions.jsonl, results/raw/decision-vs-compact-array.json.
