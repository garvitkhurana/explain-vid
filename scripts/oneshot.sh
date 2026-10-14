#!/usr/bin/env bash
# Usage: ./scripts/oneshot.sh <video>   (renders renderers/manim/oneshot_<video>.py with video-specs/<video>/spec.json)
# narration → voice + word timings (skipped if out/<video>/voice is newer than the spec) → one Manim process per scene
# in parallel → concat → mux. Outputs in out/<video>/: final.mp4, subtitles.srt, contact.png.
# Env: DRAFT=1 (480p preview, a few times faster), SCENES=id,id (re-render only these), JOBS (default = CPU cores).
set -euo pipefail
cd "$(dirname "$0")/.."
V="${1:?usage: ./scripts/oneshot.sh <video>}"
OUT="out/$V"
JOBS="${JOBS:-$(sysctl -n hw.ncpu)}"
Q=$([[ -n "${DRAFT:-}" ]] && echo l || echo h)
start=$(date +%s)
mkdir -p "$OUT"

if [[ ! -f "$OUT/voice/words.json" || "video-specs/$V/spec.json" -nt "$OUT/voice/words.json" ]]; then
  uv run scripts/voice.py "$V"
  uv run scripts/words.py "$V"
fi
ids=$(uv run --no-project python -c "import json; print(' '.join(json.load(open('$OUT/voice/timing.json'))['scenes']))")
todo=$([[ -n "${SCENES:-}" ]] && echo "$SCENES" | tr ',' ' ' || echo "$ids")
mkdir -p "$OUT/scenes"
for id in $todo; do rm -rf "$OUT/scenes/$id"; done

render_scene() {
  local id=$1
  if ! (cd renderers/manim && ONE="$id" uv run manim "-q$Q" --disable_caching --progress_bar none \
    -o "$id.mp4" --media_dir "../../$OUT/scenes/$id" "oneshot_$V.py" Video) > "$OUT/scenes/$id.log" 2>&1; then
    echo "scene $id failed:"; tail -20 "$OUT/scenes/$id.log"; return 1
  fi
}
export -f render_scene; export V OUT Q
echo "$todo" | tr ' ' '\n' | xargs -P "$JOBS" -I{} bash -c 'render_scene {}'

: > "$OUT/scenes/list.txt"
for id in $ids; do
  f=$(find "$OUT/scenes/$id/videos" -name "$id.mp4" 2>/dev/null | head -1)
  [[ -n "$f" ]] || { echo "missing render for scene $id (run without SCENES first)"; exit 1; }
  echo "file '${f#"$OUT/scenes/"}'" >> "$OUT/scenes/list.txt"
done
ffmpeg -v error -y -f concat -safe 0 -i "$OUT/scenes/list.txt" -c copy "$OUT/manim.mp4"
ffmpeg -v error -y -i "$OUT/manim.mp4" -i "$OUT/voice/narration.wav" -map 0:v -map 1:a \
  -c:v copy -c:a aac -b:a 160k -shortest "$OUT/final.mp4"

# Contact sheet: one frame from the middle of every sentence, for a quick look at overlaps and crops.
times=$(uv run --no-project python -c "
import json; t=json.load(open('$OUT/voice/timing.json'))['scenes']
print(' '.join(f\"{s['start']+(l['start']+l['end'])/2:.2f}\" for s in t.values() for l in s.get('lines', [])))")
rm -rf "$OUT/contact" && mkdir -p "$OUT/contact"
k=0; for t in $times; do ffmpeg -v error -y -ss "$t" -i "$OUT/final.mp4" -frames:v 1 -vf scale=480:-1 "$OUT/contact/$(printf %03d $k).png"; k=$((k+1)); done
[[ $k -gt 0 ]] && ffmpeg -v error -y -pattern_type glob -i "$OUT/contact/*.png" -vf "tile=4x$(( (k+3)/4 )):padding=6:color=white" "$OUT/contact.png"
echo "render: $(( $(date +%s) - start ))s ($JOBS jobs, -q$Q) → $OUT/final.mp4, $OUT/subtitles.srt, $OUT/contact.png"
