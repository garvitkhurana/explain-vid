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

## Pass 3 (2026-09-27): narration as the source, explanation over description
13. **Captions were a second script.** Hand-written captions drifted from what a narrator would say. Now `narration`
    (sentences) is the only text field; voice.py derives audio, caption cues (≤64 chars, split at commas) and .srt.
14. **Describe vs explain.** First narration draft restated the visuals ("keeps the A/B/C scores"). Explaining means
    giving the *why*: intuition (multiple-choice vs essay) → mechanism (scores exist before any word is written)
    → proof (111 passes vs 1 → 5x). Every concept gets that order.
15. **Jargon lives on screen, plain words in the voice.** Visuals keep precise terms (logits, KV cache, token);
    narration says "scores", "notes", "word". Glossary gate: a term may appear on screen only after its plain
    phrase was spoken in the same or an earlier scene.
16. **Show the explanation, don't only say it:** race footer now counts passes (111 vs 1), matching the narration.
17. **Length:** explanatory narration took the video from 52 s to ~94 s at 175 wpm. Title (15 s) is now long for its
    static visual — next pass: sync markers so narration beats trigger animations.

## Pass 4 (2026-09-27): pace visuals to the voice
18. **Front-loaded animation + long narration = dead screen.** Scenes animated in their first 1–5 s, then held for
    9–14 s while the narrator talked. Measured with ffmpeg freezedetect (caption area cropped out).
19. **One step per sentence.** Each template names its steps; `beat(step, default_sentence, frac)` waits for that
    sentence to start. Map every sentence to something visible; a sentence with no step ("Those scores are its
    answer.") is a still screen. Result: longest still stretch 14 s → 4.4 s.
20. **A title card can't carry an argument.** The problem ("model writes prose → parse → if") moved from the title's
    narration into its own `problem` scene that shows it, then crosses out the writing and parsing.
21. For the LLM step: output `data.beats` only when a scene's sentences don't follow the template's default order.
