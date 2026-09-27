#!/usr/bin/env bash
# Usage: ./scripts/render.sh [spec.json]   (default semif.json, looked up in specs/)
# narration → voice + timing → Manim, one process per scene in parallel → concat → mux audio.
# Outputs: out/final.mp4 (video + narration), out/manim.mp4 (silent), out/subtitles.srt.
# Env: THEME (default brutalist), TTS=say|none (none = silent, timing estimated from word count),
#      JOBS (parallel scene renders, default = CPU cores).
set -euo pipefail
cd "$(dirname "$0")/.."
SPEC="${1:-semif.json}"
JOBS="${JOBS:-$(sysctl -n hw.ncpu)}"
mkdir -p out
start=$(date +%s)

uv run scripts/voice.py "$SPEC"
ids=$(uv run --no-project python -c "import json; print(' '.join(s['id'] for s in json.load(open('specs/$SPEC'))['scenes']))")

# Each scene gets its own media dir: parallel Manim runs would otherwise overwrite each other's partial files.
# Text SVG caches live inside it and are cleared (they're keyed on text+size, not layout width).
rm -rf out/scenes && mkdir -p out/scenes
render_scene() {
  local id=$1
  if ! (cd renderers/manim && SPEC="$SPEC" SCENES="$id" uv run manim -qh --disable_caching --progress_bar none \
    -o "$id.mp4" --media_dir "../../out/scenes/$id" main.py Explainer) > "out/scenes/$id.log" 2>&1; then
    echo "scene $id failed:"; tail -20 "out/scenes/$id.log"; return 1
  fi
}
export -f render_scene; export SPEC
echo "$ids" | tr ' ' '\n' | xargs -P "$JOBS" -I{} bash -c 'render_scene {}'

# Scenes are frame-exact, so stream-copy concatenation keeps them in sync with the narration timeline.
: > out/scenes/list.txt
for id in $ids; do echo "file '$id/videos/main/1080p30/$id.mp4'" >> out/scenes/list.txt; done
ffmpeg -v error -y -f concat -safe 0 -i out/scenes/list.txt -c copy out/manim.mp4

if [[ -f out/voice/narration.wav ]]; then
  ffmpeg -v error -y -i out/manim.mp4 -i out/voice/narration.wav -map 0:v -map 1:a \
    -c:v copy -c:a aac -b:a 160k -shortest out/final.mp4
else
  cp out/manim.mp4 out/final.mp4
fi
echo "render: $(( $(date +%s) - start ))s ($JOBS jobs) → out/final.mp4, out/subtitles.srt"
