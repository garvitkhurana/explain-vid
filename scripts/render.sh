#!/usr/bin/env bash
# Usage: ./scripts/render.sh <video>   (renders video-specs/<video>/spec.json)
# narration → voice + timing → Manim, one process per scene in parallel → concat → mux audio.
# Outputs in out/<video>/: final.mp4 (video + narration), manim.mp4 (silent), subtitles.srt. Then runs the gates.
# Env: THEME (default brutalist), SKIN (cast setting for specs with meta.cast; output goes to out/<video>-<skin>),
#      DRY=1 (stop after the dry run: spec gates + predicted stills, ~30 s with the voice),
#      JOBS (parallel scene renders, default = CPU cores),
#      SCENES=id,id (re-render only these; reuse the other scenes' existing renders — narration must be unchanged).
set -euo pipefail
cd "$(dirname "$0")/.."
SPEC="${1:?usage: ./scripts/render.sh <video>   (a folder in video-specs/)}"
OUT="out/$SPEC${SKIN:+-$SKIN}"
JOBS="${JOBS:-$(sysctl -n hw.ncpu)}"
mkdir -p "$OUT"
start=$(date +%s)

uv run scripts/voice.py "$SPEC"
cast=$(uv run --no-project python -c "import json; print(1 if json.load(open('video-specs/$SPEC/spec.json'))['meta'].get('cast') else '')")
if [[ -n "$cast" ]]; then
  uv run scripts/words.py "$SPEC"  # word timings: mouths and phrase-anchored acts
  export THEME="${THEME:-pixel}"
fi
# Dry run: every scene's timeline without drawing a frame (~15 s), then the spec gates and predicted still screens.
# A failure here stops before the render.
rm -rf "$OUT/plan"
(cd renderers/manim && SPEC="$SPEC" PLAN=1 uv run manim --dry_run --disable_caching --progress_bar none \
  --media_dir "../../$OUT/plan" main.py Explainer) > "$OUT/plan.log" 2>&1 || { echo "dry run failed:"; tail -20 "$OUT/plan.log"; exit 1; }
uv run scripts/check.py "$SPEC" --plan || { echo "fix the spec before rendering"; exit 1; }
[[ -n "${DRY:-}" ]] && exit 0
ids=$(uv run --no-project python -c "import json; print(' '.join(s['id'] for s in json.load(open('video-specs/$SPEC/spec.json'))['scenes']))")

# Each scene gets its own media dir: parallel Manim runs would otherwise overwrite each other's partial files.
# Text SVG caches live inside it and are cleared (they're keyed on text+size, not layout width).
if [[ -n "${SCENES:-}" ]]; then
  todo=$(echo "$SCENES" | tr ',' ' ')
  for id in $todo; do rm -rf "$OUT/scenes/$id"; done
else
  todo=$ids
  rm -rf "$OUT/scenes" && mkdir -p "$OUT/scenes"
fi
render_scene() {
  local id=$1
  if ! (cd renderers/manim && SPEC="$SPEC" SCENES="$id" uv run manim -qh --disable_caching --progress_bar none \
    -o "$id.mp4" --media_dir "../../$OUT/scenes/$id" main.py Explainer) > "$OUT/scenes/$id.log" 2>&1; then
    echo "scene $id failed:"; tail -20 "$OUT/scenes/$id.log"; return 1
  fi
}
export -f render_scene; export SPEC OUT
echo "$todo" | tr ' ' '\n' | xargs -P "$JOBS" -I{} bash -c 'render_scene {}'
for id in $ids; do
  [[ -f "$OUT/scenes/$id/videos/main/1080p30/$id.mp4" ]] || { echo "missing render for scene $id (run without SCENES first)"; exit 1; }
done

# Scenes are frame-exact, so stream-copy concatenation keeps them in sync with the narration timeline.
: > "$OUT/scenes/list.txt"
for id in $ids; do echo "file '$id/videos/main/1080p30/$id.mp4'" >> "$OUT/scenes/list.txt"; done
ffmpeg -v error -y -f concat -safe 0 -i "$OUT/scenes/list.txt" -c copy "$OUT/manim.mp4"

if [[ -f "$OUT/voice/narration.wav" ]]; then
  ffmpeg -v error -y -i "$OUT/manim.mp4" -i "$OUT/voice/narration.wav" -map 0:v -map 1:a \
    -c:v copy -c:a aac -b:a 160k -shortest "$OUT/final.mp4"
else
  cp "$OUT/manim.mp4" "$OUT/final.mp4"
fi
# Contact sheet: one frame from the middle of every narration sentence, for a quick look at overlaps and crops.
times=$(uv run --no-project python -c "
import json; t=json.load(open('$OUT/voice/timing.json'))['scenes']
print(' '.join(f\"{s['start']+(l['start']+l['end'])/2:.2f}\" for s in t.values() for l in s.get('lines', [])))")
rm -rf "$OUT/contact" && mkdir -p "$OUT/contact"
k=0; for t in $times; do ffmpeg -v error -y -ss "$t" -i "$OUT/final.mp4" -frames:v 1 -vf scale=480:-1 "$OUT/contact/$(printf %03d $k).png"; k=$((k+1)); done
[[ $k -gt 0 ]] && ffmpeg -v error -y -pattern_type glob -i "$OUT/contact/*.png" -vf "tile=4x$(( (k+3)/4 )):padding=6:color=white" "$OUT/contact.png"
echo "render: $(( $(date +%s) - start ))s ($JOBS jobs) → $OUT/final.mp4, $OUT/subtitles.srt, $OUT/contact.png"
uv run scripts/check.py "$SPEC"
