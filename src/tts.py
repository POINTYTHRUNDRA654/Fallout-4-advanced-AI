"""TTS and lipgen execution helpers."""

from __future__ import annotations

import subprocess


def execute_headless_lipgen(wav_relative_path: str, subtitle_string: str) -> None:
    """Invoke CreationKit32.exe lip generation with safe argument quoting."""
    command = [
        "CreationKit32.exe",
        f"-GenerateSingleLip:{wav_relative_path}",
        subtitle_string,
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
