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

## Pass 2 (2026-09-27): architecture scenes
8. **README-only specs miss the mechanism.** The first spec showed the interface (inputs → probabilities), not *why* it's fast.
   The architecture came from source: `core.py` (options relabelled A/B/C), `direct.py` (single-token slot check,
   `logits_to_keep=1`, softmax over slot logits only), `shared.py` (prefill state once, replicate KV cache, batch suffixes).
   → The facts extractor must read source code and emit mechanism facts, not just summarize the README.
9. **Pick one mechanism scene per speed claim:** readout explains the 5.21x race; KV branching explains 20.03 vs 2.33 decisions/s.
   Put each mechanism right before or after the number it explains.
10. **Don't mix workloads:** the decisions/s rates are the 37×21 shape777 run (~8,000-char states); label it so.
    Don't pair them with the 1,812-token prefix from the single-state comparison.
11. **Merge redundant scenes:** readout ends on the same probabilities as the old bars scene, so bars was dropped.
    Backends became a metrics card instead of its own scene.
12. **Illustrative logits** (25.0/21.9/21.2) were chosen so softmax reproduces the bars (0.94/0.04/0.02). Caption says illustrative.
