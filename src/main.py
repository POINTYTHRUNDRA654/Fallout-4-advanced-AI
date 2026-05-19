"""Production-style standalone bridge loop for Fallout 4 AI integration."""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

from tts import check_lipgen_eligibility, execute_headless_lipgen, normalize_audio_for_lipgen

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

if hasattr(sys, "_MEIPASS"):
    DATA_DIR = Path(sys.executable).resolve().parent
else:
    DATA_DIR = Path(__file__).resolve().parent

INPUT_FILE = DATA_DIR / "bridge_input.json"
OUTPUT_FILE = DATA_DIR / "bridge_output.json"
CONFIG_FILE = DATA_DIR / "config.json"
MEMORY_DIR = DATA_DIR / "NPC_Memories"
FALLOUT_ROOT = DATA_DIR.parent.parent.resolve()
CK_32_EXE = FALLOUT_ROOT / "CreationKit32.exe"
KOBOLD_API_URL = os.getenv("F4AI_KOBOLD_API_URL", "http://localhost:5001/api/v1/generate")


def locate_installed_voice_model() -> str | None:
    """Find the first ONNX voice model file in runtime directory."""
    found_models = glob.glob(str(DATA_DIR / "*.onnx"))
    return found_models[0] if found_models else None


def load_user_config() -> dict:
    """Load local config file with safe defaults."""
    defaults = {"ai_temperature": 0.7, "enable_memory": 1, "speech_speed": 1.0}
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return defaults
    return defaults


def load_or_create_memory(npc_name: str) -> dict:
    """Load or initialize NPC memory with Curie unification guard."""
    if "Curie" in npc_name:
        npc_name = "Curie"
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    memory_file = MEMORY_DIR / f"{npc_name.replace(' ', '_')}.json"
    if memory_file.exists():
        try:
            with memory_file.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            pass
    return {"conversations": []}


def update_npc_memory(npc_name: str, player_line: str, npc_line: str) -> None:
    """Write rolling dialogue memory with VRAM-safe turn cap."""
    if "Curie" in npc_name:
        npc_name = "Curie"
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    memory_file = MEMORY_DIR / f"{npc_name.replace(' ', '_')}.json"
    memory_data = load_or_create_memory(npc_name)
    memory_data["conversations"].append({"p": player_line, "n": npc_line})
    if len(memory_data["conversations"]) > 5:
        memory_data["conversations"].pop(0)
    try:
        with memory_file.open("w", encoding="utf-8") as handle:
            json.dump(memory_data, handle, indent=2)
    except OSError:
        pass


def query_local_llm(prompt: str, temperature: float) -> str:
    """Query local Kobold endpoint with firewall-safe fallback text."""
    payload = {
        "prompt": prompt,
        "max_context_length": 1024,
        "max_length": 50,
        "temperature": temperature,
    }
    try:
        response = requests.post(KOBOLD_API_URL, json=payload, timeout=5)
        response.raise_for_status()
        data = response.json()
        if "results" in data and data["results"]:
            return data["results"][0].get("text", "").strip()
    except requests.exceptions.ConnectionError:
        print(
            f"\n[CRITICAL ERROR] Allow '{os.path.basename(sys.executable)}' through firewall and verify local backend.\n"
        )
        return "[Cognitive Matrix Offline]"
    except (requests.RequestException, ValueError):
        return "System logic matrices are running behind schedule."
    return "My processors failed to yield a prompt response clear enough to speak."


def extract_emotion_id(raw_llm_output: str) -> int:
    """Map emotion tags to compact Papyrus-friendly integer ids."""
    if "[ANGRY]" in raw_llm_output:
        return 1
    if "[SAD]" in raw_llm_output:
        return 2
    if "[WHISPER]" in raw_llm_output:
        return 3
    return 0


def strip_emotion_tag(raw_llm_output: str) -> str:
    """Remove leading [TAG] marker from generated line."""
    return re.sub(r"^\[(NORMAL|ANGRY|SAD|WHISPER)\]\s*", "", raw_llm_output).strip()


def process_game_event() -> None:
    """Read bridge packet, generate response, render audio, and return payload."""
    time.sleep(0.05)
    try:
        with INPUT_FILE.open("r", encoding="utf-8") as handle:
            context = json.load(handle)
    except (OSError, ValueError):
        return

    try:
        INPUT_FILE.unlink(missing_ok=True)
    except OSError:
        pass

    npc = context.get("npc_name", "Settler")
    location = context.get("location", "The Commonwealth")
    player_input = context.get("player_speech", "[Greets you silently]")
    config = load_user_config()

    history_string = ""
    if config.get("enable_memory") == 1:
        memory = load_or_create_memory(npc)
        for turn in memory.get("conversations", []):
            history_string += f"Player: {turn['p']}\nYou: {turn['n']}\n"

    system_prompt = (
        f"You are the companion {npc} in Fallout 4. "
        f"You are currently located at {location}. "
        "Respond in character with one short sentence."
    )
    full_prompt = (
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
        f"{system_prompt}\n\n{history_string}"
        "<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
        f"{player_input}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    )
    raw_ai_output = query_local_llm(full_prompt, float(config.get("ai_temperature", 0.7)))
    emotion_id = extract_emotion_id(raw_ai_output)
    ai_response = strip_emotion_tag(raw_ai_output).replace("*", "").replace('"', "").strip()
    print(f"[{npc}]: {ai_response}")

    voice_model = locate_installed_voice_model()
    audio_wav_path = DATA_DIR / "f4ai_voice.wav"
    if voice_model:
        cmd = [
            "piper",
            "--model",
            voice_model,
            "--length_scale",
            str(config.get("speech_speed", 1.0)),
            "--output_file",
            str(audio_wav_path),
        ]
        subprocess.run(cmd, input=ai_response, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if audio_wav_path.exists():
            normalize_audio_for_lipgen(str(audio_wav_path))
            if CK_32_EXE.exists() and check_lipgen_eligibility(npc):
                rel_wav = os.path.relpath(audio_wav_path, FALLOUT_ROOT)
                execute_headless_lipgen(rel_wav, ai_response)

    if config.get("enable_memory") == 1:
        update_npc_memory(npc, player_input, ai_response)

    output_payload = {
        "subtitle_text": ai_response,
        "audio_file": "F4AI/f4ai_voice.wav",
        "emotion_id": emotion_id,
        "display_duration": max(2.5, len(ai_response) / 13.0),
    }
    try:
        with OUTPUT_FILE.open("w", encoding="utf-8") as out_f:
            json.dump(output_payload, out_f)
    except OSError:
        print("[System Fault] Failed to write response payload.")


if __name__ == "__main__":
    print("==============================================================================")
    print("FALLOUT 4 ADVANCED AI STANDALONE ENGINE BACKGROUND BRIDGE SERVICE RUNNING...")
    print("==============================================================================")
    while True:
        if INPUT_FILE.exists():
            process_game_event()
        time.sleep(0.1)
