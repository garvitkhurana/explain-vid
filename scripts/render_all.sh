#!/usr/bin/env bash
# Usage: ./scripts/render_all.sh [spec.json]   (default semif.json, looked up in specs/)
# Render the spec with both stacks, then build a labeled side-by-side comparison.
set -euo pipefail
cd "$(dirname "$0")/.."
SPEC="${1:-semif.json}"
mkdir -p out

echo "== Remotion"
start=$(date +%s)
(cd renderers/remotion && npx remotion render src/index.ts Explainer ../../out/remotion.mp4 --props="../../specs/$SPEC" --log=error)
echo "remotion: $(( $(date +%s) - start ))s"

echo "== Manim"
start=$(date +%s)
(cd renderers/manim && SPEC="$SPEC" uv run manim -qh --disable_caching --progress_bar none \
  -o manim.mp4 --media_dir ../../out/manim_media main.py Explainer 2>/dev/null)
cp out/manim_media/videos/main/1080p30/manim.mp4 out/manim.mp4
echo "manim: $(( $(date +%s) - start ))s"

echo "== Compare"
# Left = Remotion, right = Manim (this ffmpeg build has no drawtext for labels).
ffmpeg -v error -y -i out/remotion.mp4 -i out/manim.mp4 -filter_complex \
  "[0]scale=960:-2,pad=iw+8:ih:0:0:white[a];[1]scale=960:-2[b];[a][b]hstack" \
  -c:v libx264 -pix_fmt yuv420p out/compare.mp4
echo "wrote out/remotion.mp4 out/manim.mp4 out/compare.mp4"
