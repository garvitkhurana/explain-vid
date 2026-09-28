#!/usr/bin/env bash
# Usage: ./scripts/render.sh <video>   (renders videos/<video>/spec.json)
# narration → voice + timing → Manim, one process per scene in parallel → concat → mux audio.
# Outputs in out/<video>/: final.mp4 (video + narration), manim.mp4 (silent), subtitles.srt.
# Env: THEME (default brutalist), TTS=say|none (none = silent, timing estimated from word count),
#      JOBS (parallel scene renders, default = CPU cores).
set -euo pipefail
cd "$(dirname "$0")/.."
SPEC="${1:?usage: ./scripts/render.sh <video>   (a folder in videos/)}"
OUT="out/$SPEC"
JOBS="${JOBS:-$(sysctl -n hw.ncpu)}"
mkdir -p "$OUT"
start=$(date +%s)

uv run scripts/voice.py "$SPEC"
ids=$(uv run --no-project python -c "import json; print(' '.join(s['id'] for s in json.load(open('videos/$SPEC/spec.json'))['scenes']))")

# Each scene gets its own media dir: parallel Manim runs would otherwise overwrite each other's partial files.
# Text SVG caches live inside it and are cleared (they're keyed on text+size, not layout width).
rm -rf "$OUT/scenes" && mkdir -p "$OUT/scenes"
render_scene() {
  local id=$1
  if ! (cd renderers/manim && SPEC="$SPEC" SCENES="$id" uv run manim -qh --disable_caching --progress_bar none \
    -o "$id.mp4" --media_dir "../../$OUT/scenes/$id" main.py Explainer) > "$OUT/scenes/$id.log" 2>&1; then
    echo "scene $id failed:"; tail -20 "$OUT/scenes/$id.log"; return 1
  fi
}
export -f render_scene; export SPEC OUT
echo "$ids" | tr ' ' '\n' | xargs -P "$JOBS" -I{} bash -c 'render_scene {}'

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
echo "render: $(( $(date +%s) - start ))s ($JOBS jobs) → $OUT/final.mp4, $OUT/subtitles.srt"
