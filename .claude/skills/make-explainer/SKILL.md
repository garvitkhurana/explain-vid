---
name: make-explainer
description: Turn a source (repo path or URL) into a gated explainer video by running the fact-extractor → spec-author agents and render.sh, looping on gate failures. Use when asked to make a new explainer video.
argument-hint: <source> <video>
---

# /make-explainer <source> <video>

Runs the explain-vid agents in order. Each role is defined in `.claude/agents/`. Gates in `scripts/check.py` are the only
verdict; never pass a video that fails a gate, and never edit a gate to make it pass.

`<video>` is a new folder name in `video-specs/` (lowercase, `_` between words). Stop if `video-specs/<video>/spec.json`
already exists, unless the user asked to redo it.

1. **Source text.** For a URL, check that it can be fetched. If it returns 403 or an empty page, read it in the in-app
   browser, save the article text to the scratchpad, and pass that path on. For a repo, pass the path.
2. **Facts:** spawn `fact-extractor` with the source and `<video>`, then read its report. If it couldn't read the
   source, stop and tell the user.
3. **Spec:** spawn `spec-author` with `<video>`. If it reports a missing template, stop and tell the user what the
   scene needs. Building templates is a separate, reviewed step (`template-builder`) and never part of this loop.
4. **Check:** run `./scripts/render.sh <video>` yourself, with the voice (~15 s: timing is exact, a silent estimate
   isn't). A dry run (~15 s) checks the spec and predicted still screens first and stops there on a FAIL; otherwise
   it renders (~60 s) and ends with the gates.
   If the dry run or a scene crashes, read the last 20 lines of `out/<video>/plan.log` or `out/<video>/scenes/<id>.log`.
5. **Loop (at most 3 rounds):** send each FAIL line exactly as printed to the agent that owns it (continue it with
   SendMessage if it's still around, otherwise spawn it with the failure text), then repeat step 4:
   - spec: schema, arc and roles, opening, ending, glossary, grounding, labels, still screen, caption length → `spec-author`
   - a number that's correct in the source but missing from facts.json → `fact-extractor`
   - a scene crash, wrong format, black frames, or a still screen the template can't fix → tell the user (templates are a
     separate, reviewed `template-builder` step)
6. **Final:** once step 4 passes, that render is the final one. Show the user the story spine, what was cut, the gate
   results, `out/<video>/final.mp4`, and any gate left failing, with the reason.

Run at most 2 agents at once. Each agent's final report is ≤ 15 lines (files changed, gate results, blockers);
ask for details in a scratchpad file, not in the report. Don't commit. Suggest adding the judgment calls that were new for this source to `video-specs/NOTES.md`.
