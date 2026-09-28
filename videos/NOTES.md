# Decisions made hand-writing videos/semif/spec.json
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

## Pass 5 (2026-09-27): two new subjects — agent-unwrapped (repo) and Habitat (OpenAI blog post)
22. **Pick one running example from the source itself.** agent-unwrapped: its own eval case "calculator for 21 * 2",
    carried through loop → transcript → evals. The transcript shows the real message shapes (tool result is
    `{"ok": true, "expression": "21*2", "value": 42.0}`, read from agent/tools.py), not a paraphrase.
23. **Prose sources need a story spine, not a section-by-section summary.** Habitat post has ~10 topics; the video keeps
    one arc ("scale 10x/yr by deliberate tradeoffs"): library → service, Python tail latency, LIFO→FIFO, Rust.
    Cut: constrained NoSQL API, Rockset/CDC, Envoy fan-in. Say what you cut in the spec review, not in the video.
24. **Illustrative ≠ invented.** Gantt timings and LIFO/FIFO loads are illustrative (labelled on screen); every stated
    number (70M+, 1B+, 500 PB+, 20M+, 6x, 15x, 95%, 2 engineers, Q2 2026) is quoted from the post.
25. **Templates generalise when they're data-shaped.** New ones take lists (nodes/messages, rows, services, segments,
    series), so an LLM fills data, never code. metrics now adapts to 4 cards and has a footnote; pipeline has a head.
26. **Glyph fallback bites:** Helvetica has no ✓ — draw marks as paths. Check any symbol that isn't ASCII.
27. **Blog pages may block fetchers (403):** read them in a real browser; keep the text as the fact source.

## Pass 6 (2026-09-27): figures from data (`flow`)
28. **Ghost-then-reveal on one canvas** (from the user's reference video): everything drawn faint up front, steps
    light parts up, so the viewer always sees where things go. Colour follows concept via `roles`, never per node.
29. **Loop-back edges:** in a cycle, the edge pointing to a node listed *earlier* in the spec is the loop-back
    (people list nodes in reading order). DFS alone picked the wrong edge and flattened a panel into one row.
30. **Manim traps:** `set_opacity` on a polyline also turns on its fill (filled wedges behind rails) — ghost via
    stroke only; `.animate` snapshots the mobject when called, so set any non-animated changes *before* it; an
    animated shape is drawn last, so re-raise labels on filled cells.
31. **Subscripts are markup, not glyphs:** Helvetica has ₁₂₃ but not ₙ. Write `S_{N}`; the renderer draws it.
32. For the LLM step: a figure is nodes (shape, role), edges, and ordered steps — no coordinates, ever.

## Pass 7 (2026-09-27): does it generalise? mlx-voice-clone (repo) + Anthropic long-running-agents post (blog)
33. **Yes, from data:** both videos (11 scenes) were expressed as specs only — no source-specific code. The harness
    figure (two panels, artifacts, "next session" loop-back) laid itself out correctly first time.
34. **What broke was generic, found by gates/measurement, fixed generically:** small figures stayed small (layout now
    scales up to 1.5x); edge labels got cut off (layout reserves gap width for labels); a final flow step overran its
    scene and shifted captions (steps now fit the time left; new gate: per-scene frame count == timing); the outro
    assumed one sentence and didn't fit long URLs.
35. **Spec-writing rules learned:** keep a figure to ~4 columns or text becomes unreadable; a sentence longer than
    ~5 s needs a second visible change (`beats: [sentence, fraction]`); tiny packets alone read as a still screen,
    so flows now pulse the node they reach.
36. **The jargon gate earned its keep:** it flagged "mlx-audio" on the title card before "Apple Silicon" was said.
37. **Speed:** iterate with `SCENES=` on the scene you changed; full re-renders of every video after each fix
    cost ~3 min per round for nothing.

## Pass 8 (2026-09-27): user review of the harness video
38. **Endings are a convention, not content.** "Open questions" outros added little; every video now ends on one
    generated card from `meta.source` (repo → "Check out the repo", blog/paper → "Read the full … at"). The
    harness video now ends right after its last point (checklist 1:40, card to 1:44).
39. **Subtitles must never cover content.** Templates had put footers inside the caption band. Now a render fails
    if a narrated scene leaves anything below `CAPTION_TOP`; checked across all specs with `manim --dry_run`
    (runs every scene's logic, writes no video — seconds, not minutes). It caught the gantt footer.
40. **Titles, headlines and URLs are fitted to the frame** — never assume a title is short.
41. **Silent scenes drifted by a frame:** Manim writes static waits as floor(duration·fps) frames but animated ones
    as ceil. Every wait now takes the animated path; the per-scene frame gate caught it.
