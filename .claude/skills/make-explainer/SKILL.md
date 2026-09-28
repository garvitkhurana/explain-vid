---
name: make-explainer
description: Turn a source (repo path or URL) into a gated explainer video by running the fact-extractor → spec-author → render-checker agents, looping on gate failures. Use when asked to make a new explainer video.
argument-hint: <source> <video>
---

# /make-explainer <source> <video>

Runs the explain-vid agents in order. Each role is defined in `.claude/agents/`. Gates in `scripts/check.py` are the only
verdict; never pass a video that fails a gate, and never edit a gate to make it pass.

`<video>` is a new folder name in `videos/` (lowercase, `_` between words). Stop if `videos/<video>/spec.json`
already exists, unless the user asked to redo it.

1. **Source text.** For a URL, check that it can be fetched. If it returns 403 or an empty page, read it in the in-app
   browser, save the article text to the scratchpad, and pass that path on. For a repo, pass the path.
2. **Facts:** spawn `fact-extractor` with the source and `<video>`, then read its report. If it couldn't read the
   source, stop and tell the user.
3. **Spec:** spawn `spec-author` with `<video>`. If it reports a missing template, stop and tell the user what the
   scene needs. Building templates is a separate, reviewed step (`template-builder`) and never part of this loop.
4. **Check:** spawn `render-checker` with `<video>` and `TTS=none`.
5. **Loop (at most 3 rounds):** send each FAIL line exactly as printed to the agent that owns it, according to render-checker's
   report (continue that agent with SendMessage if it's still around, otherwise spawn it with the failure text), then
   repeat step 4.
6. **Final:** run `./scripts/render.sh <video>` with the voice, then `uv run scripts/check.py <video>`. Show the user
   the story spine, what was cut, the gate results, `out/<video>/final.mp4`, and any gate left failing, with the reason.

Don't commit. Suggest adding the judgment calls that were new for this source to `videos/NOTES.md`.
