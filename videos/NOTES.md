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

## Pass 9 (2026-09-27): user review of mlx-voice-clone — structure over detail
42. **A tool video needs a tool's arc, not a result's arc.** The user preferred a reference cut (~95 s) that goes
    hook formula ("voice clip + script = narration") → simple pipeline → why local → plain steps → two ways in
    (CLI / browser) → speed vs quality → three commands. Longer, but every scene answers the next obvious question.
43. **Too technical = implementation detail the viewer can't use.** 24 kHz, ~450-char chunks, paragraph/sentence
    delimiters, FastAPI/subprocess were accurate but unhelpful. "Split into pieces, joined into one file" is enough.
    The reference also claimed chunks "overlap a little"; the code does a hard splice. Never copy a reference's claims,
    only its structure — facts come from the source.
44. **No disclaimers.** An earlier cut ended "only clone voices you have permission to use"; the user didn't want it.
45. **Text-heavy slots got real templates:** `compare` (two columns, per-row winner left/right/both/none, drawn
    ticks/crosses) and `commands` (terminal panel, commands type in). Cloud-side cells in a compare are generic
    wording, never a claim about a named service.
46. **Manim trap:** two `.animate` calls on one mobject in the same play overwrite each other's target (it's stored
    on the mobject) — the flow `highlight` of a ghosted node stayed ghosted. Build the second after the first plays.
47. **A step must fit its own sentence** (`step_time`): otherwise short sentences push later steps late and the
    scene overruns its narration (frame gate catches it).
48. **Grounding gate read role colours (`c1`) as numbers.** Digits glued to a word are names, not claims.
49. **Remotion vs Manim, per scene (checklist, metrics, compare, commands; same timing.json + theme):** parity in
    look and frame-exact timing. Remotion fades cleaner, lays out text with no coordinate maths and is faster on long
    scenes (~2–3 s fixed start-up); Manim ticks are crisper and it keeps the caption-band check. Flow stays Manim-only.
    No case where switching stacks is worth a second renderer to maintain.
50. **Open:** the last `commands` line can still be mid-typing at the fade when its sentence is very short (both stacks).
    Flow figures laid out as one long row (agent_unwrapped `course`) render too small, and short figures sit at
    the top of the frame (ai_harness `loop`).

## Pass 10 (2026-09-27): user review of the new voice-clone cut
51. **Say the name.** The cut opened on a formula card and never showed "mlx-voice-clone". Open on the name.
52. **Alternatives aren't a flow.** CLI vs browser drawn as two boxes feeding "same engine" read as a pipeline;
    it's two ways to do one thing → side-by-side windows (terminal vs browser page). Flow = things moving.
53. **A simple idea chart beats a formula of cards:** clip (waveform) + script (text lines) → model → narration
    (waveform). Small drawn art on nodes says "audio" / "text" without words.
54. **A headline said first goes at the top.** ai_harness used the metrics `footnote` as its opening line: it showed
    alone mid-screen, then cards appeared above it. Metrics now has `title`; a footnote narrated before its cards
    fails the render.
55. **Don't over-plain a term the audience already uses.** agent-unwrapped said "tests" for evals; the user found
    it odd. If the source's own word is the common one in its field (evals), say it.
56. **Template by content kind.** Each kind of thing has its own template (moving parts → flow; options → compare /
    alternatives; checks → checklist; setup → commands; numbers → metrics/race). spec-author maps content to kind first.
57. **No hardcoded copy in templates.** Audit: the semif-era `race` ("21 decisions"), `readout` ("Next-token
    scores…", "softmax over A, B, C", the "Account" row) and `branch` ("prefilled once") carry source text in code;
    moved to data. Rule: every on-screen string comes from the spec.
58. **Manim traps (alternatives/flow art):** a `Succession` adds its mobjects to the scene incl. ValueTrackers — fading
    one at scene end changes its value and rebuilds `on_change` rows mid-fade (remove trackers once played); draw
    order is add order (use z_index); animations record their end state when *built*, so build them after layout;
    never use `hash()` for deterministic art (salted per process) — use crc32.
59. **Gate hole closed:** the verbatim-command check now walks every `cmd` in a scene (alternatives panels too).
60. **A loop is a ring, not an if/then.** The user: "an agent is a loop, and a harness is basically an agent loop,
    plus knobs to control it" and "not if, then loop". The generic `cycle` template (3–6 nodes on a ring, a marker
    that goes round, optional enter/exit and a growing side panel) replaced the hardcoded `loop` template and its
    `tool_calls?` decision box. The loop exit is an edge label, not a branch; a retry is a lap (`lap: true`).
61. **ai_harness spine:** agent = model + harness (title, roles) → an agent is a loop (cycle) → a harness is that
    loop plus knobs (the same ring, knobs lighting the step they control) → failures → thesis.
62. **Figures fill the frame:** a long single-row flow chain wraps into rows (only at single-node layers, so the
    connector never crosses a node); rows are centred and the connector drops into the next row's top — the
    first cut (left-aligned row, connector along the frame edge) looked off to the user. Never wrap to a lone last
    step (voice-clone `generate` left "Join" alone on row 2): a smaller one-row figure reads better. Metrics cards stay centred on the cards shown so far.
63. **Open on the question, not the bookkeeping.** "Take a task from the repo's evals: twenty-one times two" sounded
    odd as an opening line; "Start with a simple question: what's twenty-one times two?" Where it came from belongs
    on screen (the illustrative note), not in the first sentence.
64. **Don't re-introduce inputs, and name the scene.** voice-clone `generate` re-listed clip + script (already the
    `idea` scene) and added "+ exact transcript" next to "script", which read as a mistake: true (the clip's
    transcript is an optional speed-up) but a detail a first-time viewer doesn't need. A scene that zooms into one
    moment gets a heading saying which ("When you hit generate"), and starts from inputs the viewer already knows.
65. **"What happens when you hit generate" = a numbered walkthrough, not another flow chart.** The user's reference
    video (0:40–1:30) lists the steps on the left, building up one per sentence, with the real code for the current
    step in a window on the right, then zooms into the one mechanism worth a picture (chunks → one pass each → joined).
    New templates: `steps` (list + code window, optional wave art) and `chunks` (split / pass / join). A second
    flow chart of the same inputs read as repetitive. Code lines are quoted source: `check.py` requires each one
    verbatim in facts.json (shortened to exact fragments so they stay readable), like `cmd`.
