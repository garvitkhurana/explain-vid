# STATUS — Claude Code, 2026-09-27

## True now
- Branch `videos-agent-unwrapped-openai-storage` (from main after PR #2 merge), committed and opened as a PR to main.
- Three specs render end to end, each into `out/<spec>/` (final.mp4, manim.mp4, subtitles.srt, voice/, scenes/):
  - `semif.json` — 98 s (previous work).
  - `agent_unwrapped.json` — 84 s, 6 scenes; running example = the repo's own eval case (calculator 21*2). 13/13 gates.
  - `habitat.json` — 110 s, 7 scenes, from OpenAI's "scaling storage… part one" post. 13/13 gates.
    Illustrative on-screen timings/loads are labelled; all stated numbers quoted from the post.
- New generic templates: loop (cycle + growing message transcript), checklist (drawn ticks), fanout (library in many
  services → rollout/rollback → central service), gantt (per-row segments, shared time axis), balance (per-server
  load bars over steps, one panel per strategy). metrics: up to 4 cards + footnote; pipeline: configurable head.
- Pacing: longest still stretch 4.9 s (agent-unwrapped), 5.9 s (Habitat). Render ~70 s each (10 parallel jobs).
- OpenAI page returns 403 to fetchers; read via the in-app browser.

## Next action
Review/merge the PR. Proposed next (not started): reusable graph pipeline — graph IR, mermaid extractor,
deterministic layered layout, `flow` scene; node shapes, semantic colour roles, ghost-then-reveal steps,
narrated vs silent figure modes. Plan: ~/.claude/plans/animated-charts-like-these-refactored-hellman.md.

## Open first
out/habitat/final.mp4, out/agent_unwrapped/final.mp4, specs/habitat.json, specs/agent_unwrapped.json

## Blockers
None.
