"""Minimal bridge loop skeleton showing safe input/output handoff sequencing."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ai.dialogue_memory import verify_identity_integrity
from config import get_bridge_paths


def safely_read_game_json(file_path: Path, max_attempts: int = 5) -> dict[str, Any] | None:
    """Read and parse JSON with retry handling for temporary file locks."""
    for _ in range(max_attempts):
        try:
            with file_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except OSError:
            time.sleep(0.05)
        except json.JSONDecodeError:
            time.sleep(0.02)
    return None


def read_then_delete(path: Path) -> dict[str, Any] | None:
    """Read file payload and delete immediately to unblock the game engine."""
    payload = safely_read_game_json(path)
    if payload is not None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    return payload


def write_output(path: Path, payload: dict[str, Any]) -> None:
    """Write output payload for Papyrus and keep format stable."""
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)


def clean_llm_text(raw_ai_text: str) -> str:
    """Strip common formatting artifacts before TTS/subtitle handoff."""
    return raw_ai_text.replace("*", "").replace('"', "").strip()


def query_local_llm_backend(npc: str, user_input: str) -> str:
    """Placeholder backend call."""
    return f"{npc}: I heard you say {user_input}."


def process_game_bridge_loop(input_file: Path, output_file: Path) -> None:
    """Single parser cycle for reading, cleaning, and writing bridge data."""
    game_context = read_then_delete(input_file)
    if game_context is None:
        return
    if not verify_identity_integrity(game_context):
        return

    npc = game_context.get("npc_name", "Settler")
    user_input = game_context.get("player_speech", "Hello")
    raw_ai_text = query_local_llm_backend(npc, user_input)
    clean_ai_text = clean_llm_text(raw_ai_text)

    output_payload = {
        "subtitle_text": clean_ai_text,
        "audio_file": "F4AI/f4ai_voice.wav",
    }
    write_output(output_file, output_payload)


def main_loop(poll_seconds: float = 0.1) -> None:
    """Demonstrate strict data handoff sequence between game and Python bridge."""
    paths = get_bridge_paths()
    input_file = paths["input"]
    output_file = paths["output"]

    while True:
        if input_file.exists():
            process_game_bridge_loop(input_file, output_file)
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main_loop()
