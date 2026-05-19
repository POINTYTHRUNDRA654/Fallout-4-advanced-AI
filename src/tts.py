"""TTS and lipgen execution helpers."""

from __future__ import annotations

import subprocess

import numpy as np
import scipy.io.wavfile as wavf


def execute_headless_lipgen(wav_relative_path: str, subtitle_string: str) -> None:
    """Invoke CreationKit32.exe lip generation with safe argument quoting."""
    command = [
        "CreationKit32.exe",
        f"-GenerateSingleLip:{wav_relative_path}",
        subtitle_string,
    ]
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if result.returncode != 0:
        print(f"[LipGen Error] CreationKit32.exe returned code {result.returncode}.")


def normalize_audio_for_lipgen(input_wav_path: str) -> None:
    """Normalize WAV into strict 16-bit mono 16000Hz PCM format."""
    sample_rate, data = wavf.read(input_wav_path)
    if data.dtype == np.float32:
        data = (data * 32767).astype(np.int16)
    elif data.dtype != np.int16:
        data = data.astype(np.int16)

    if len(data.shape) > 1:
        data = data[:, 0]

    _ = sample_rate
    wavf.write(input_wav_path, 16000, data)
