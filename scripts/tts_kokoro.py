# /// script
# requires-python = ">=3.12"
# dependencies = ["mlx-audio==0.4.2", "misaki[en]", "numpy", "soundfile"]
# ///
"""Kokoro-82M (MLX, local) text-to-speech for voice.py. Loads the model once and speaks a batch of sentences.

Usage: uv run scripts/tts_kokoro.py < jobs.json
  jobs.json: {"voice": "af_heart", "speed": 1.0, "items": [["sentence", "out/…/scene_00.wav"], ...]}
First run downloads mlx-community/Kokoro-82M-bf16 (~350 MB) to the Hugging Face cache.
"""

import json
import sys
import warnings

import numpy as np
import soundfile as sf

warnings.filterwarnings("ignore")
from mlx_audio.tts.utils import load_model  # noqa: E402

MODEL = "mlx-community/Kokoro-82M-bf16"
RATE = 24000  # Kokoro's native sample rate


def main() -> None:
    jobs = json.load(sys.stdin)
    model = load_model(MODEL)
    voice, speed = jobs.get("voice", "af_heart"), jobs.get("speed", 1.0)
    lang = voice[0]  # Kokoro voice ids start with their language code: a = US English, b = UK English
    for text, path in jobs["items"]:
        audio = np.concatenate([np.array(r.audio) for r in model.generate(text=text, voice=voice, speed=speed, lang_code=lang)])
        sf.write(path, audio, RATE)


if __name__ == "__main__":
    main()
