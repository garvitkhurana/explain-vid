#!/usr/bin/env bash
# Usage: ./scripts/setup.sh   One-time setup; safe to re-run.
# Checks for an Apple Silicon Mac, installs the Homebrew tools, the Manim environment and the Kokoro voice model.
set -euo pipefail
cd "$(dirname "$0")/.."

[[ "$(uname -s)-$(uname -m)" == "Darwin-arm64" ]] || { echo "Needs an Apple Silicon Mac (the Kokoro voice runs on MLX)."; exit 1; }
command -v brew >/dev/null || { echo "Needs Homebrew: https://brew.sh"; exit 1; }

missing=$(for f in cairo pango pkg-config ffmpeg uv; do brew list --formula "$f" >/dev/null 2>&1 || echo "$f"; done)
if [[ -n "$missing" ]]; then
  echo "Installing: $(echo $missing)"
  brew install $missing
fi

echo "Manim environment…"
(cd renderers/manim && uv sync --quiet)

# Speak one short line so the voice model (~350 MB) and its Python packages download now, not mid-render.
echo "Voice model (first time: ~350 MB)…"
tmp=$(mktemp -d)
echo "{\"voice\": \"af_heart\", \"items\": [[\"Ready.\", \"$tmp/ready.wav\"]]}" | uv run --quiet scripts/tts_kokoro.py
rm -rf "$tmp"

echo "Ready. In Claude Code: /make-explainer <url or repo path> <video_name>"
