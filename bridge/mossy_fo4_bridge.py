#!/usr/bin/env python3
"""
mossy_fo4_bridge.py
Fallout 4 Advanced AI System — Mossy Bridge Server
====================================================
Connects the Mossy desktop AI assistant to your Fallout 4 game session.

Features:
  - Reads Papyrus.0.log in real time (streams to Mossy)
  - Parses [AAI] tagged log lines for mod status
  - External NPC Memory System — stores conversation history on PC
    so NPCs can remember far more than Papyrus script memory allows
  - HTTP API on localhost:28485 for Mossy to query
  - Watches Fallout4.ini for game configuration

Requirements: Python 3.10+
"""

import os
import sys
import json
import time
import threading
import re
import sqlite3
import datetime
import subprocess
import random
import requests
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

BRIDGE_PORT     = 28485
BRIDGE_VERSION  = "1.0.0"

# Auto-detect Fallout 4 paths
DOCUMENTS_PATH  = Path(os.path.expandvars(r"%USERPROFILE%\Documents\My Games\Fallout4"))
PAPYRUS_LOG     = DOCUMENTS_PATH / "Logs" / "Script" / "Papyrus.0.log"
FO4_INI         = DOCUMENTS_PATH / "Fallout4.ini"
MEMORY_DB_PATH  = Path(r"H:\Mossy Memory\AdvancedAI_Memory.db")

def _find_fo4_game_path() -> Path:
    """Locate the Fallout 4 game install directory via registry then common paths."""
    try:
        import winreg
        for hive, subkey in [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Bethesda Softworks\Fallout4"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Bethesda Softworks\Fallout4"),
        ]:
            try:
                key = winreg.OpenKey(hive, subkey)
                p = Path(winreg.QueryValueEx(key, "Installed Path")[0])
                winreg.CloseKey(key)
                if p.exists():
                    return p
            except OSError:
                pass
        # Try Steam library
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SOFTWARE\WOW6432Node\Valve\Steam")
            steam = Path(winreg.QueryValueEx(key, "InstallPath")[0])
            winreg.CloseKey(key)
            candidate = steam / "steamapps" / "common" / "Fallout 4"
            if candidate.exists():
                return candidate
        except OSError:
            pass
    except ImportError:
        pass
    for p in [
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\Fallout 4"),
        Path(r"D:\Steam\steamapps\common\Fallout 4"),
        Path(r"D:\Games\Fallout 4"),
        Path(r"C:\Games\Fallout 4"),
    ]:
        if p.exists():
            return p
    return Path(r"C:\Program Files (x86)\Steam\steamapps\common\Fallout 4")

FO4_GAME_PATH     = _find_fo4_game_path()

# MO2 redirects ALL game file WRITES to the Overwrites folder (highest-priority
# virtual mod). bridge_input.json is written by Hydra:IO:File inside the game
# process, so MO2 intercepts it and puts it in Overwrites — not in the mod
# source folder. The bridge must watch Overwrites to see it.
# Hydra reads (Exists / ReadAllText) go through MO2's VFS, which includes
# Overwrites, so writing text_out.txt to Overwrites is visible to the game.
_MO2_OVERWRITES_F4AI = Path(r"E:\Mod.Organizer-2.5.2 Overwrites\Data\F4AI")
_MO2_MOD_F4AI        = Path(r"E:\Mod.Organizer-2.5.2 Game Mods\Fallout 4 Advanced AI - Mossy Industries\Data\F4AI")

def _find_f4ai_data_dir() -> Path:
    """Return the F4AI data directory the bridge should read/write.

    Priority: MO2 Overwrites (where Hydra writes land) → MO2 mod folder
    (non-Overwrites MO2 setups) → game Data folder (no MO2).
    """
    if _MO2_OVERWRITES_F4AI.parent.parent.exists():   # E:\Mod.Organizer-2.5.2 Overwrites exists
        _MO2_OVERWRITES_F4AI.mkdir(parents=True, exist_ok=True)
        return _MO2_OVERWRITES_F4AI
    if _MO2_MOD_F4AI.parent.exists():
        _MO2_MOD_F4AI.mkdir(parents=True, exist_ok=True)
        return _MO2_MOD_F4AI
    return FO4_GAME_PATH / "Data" / "F4AI"

F4AI_DATA_DIR     = _find_f4ai_data_dir()
BRIDGE_INPUT_PATH = F4AI_DATA_DIR / "bridge_input.json"
TEXT_OUT_PATH     = F4AI_DATA_DIR / "text_out.txt"

# Belt-and-suspenders: all locations to check for bridge_input.json.
# Checked in order; first match wins.  Covers MO2 Overwrites, mod folder,
# and bare game Data in one pass.
_BRIDGE_INPUT_CANDIDATES = [
    BRIDGE_INPUT_PATH,          # primary (MO2 Overwrites)
    _MO2_MOD_F4AI / "bridge_input.json",
    FO4_GAME_PATH / "Data" / "F4AI" / "bridge_input.json",
]

# ── Local AI Engine (KoboldCPP + TinyLlama) ──────────────────────────────────
# Mossy downloads these to its own runtime folder and tells us where they are.
# The bridge checks these paths and exposes /engine/status so the Mossy UI
# can show install state and trigger auto-download via its built-in installer.

def _find_mossy_runtime() -> Path:
    """Return the best-guess Mossy runtime directory for plugin binaries."""
    candidates = [
        Path(os.path.expandvars(r"%APPDATA%\mossy-ai\runtime")),
        Path(os.path.expandvars(r"%APPDATA%\Mossy\runtime")),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\mossy-ai\runtime")),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Mossy\resources\runtime")),
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


# The bridge lives at <F4AI base>/bridge/mossy_fo4_bridge.py — derive base from __file__
_F4AI_BASE: Path = Path(__file__).resolve().parent.parent


def _find_kobold_exe() -> Path:
    """Search all known KoboldCPP install locations."""
    runtime = _find_mossy_runtime()
    candidates = [
        _F4AI_BASE / "runtime" / "koboldcpp.exe",                # same F4AI install tree (any drive/MO2 path)
        _MO2_MOD_F4AI / ".." / ".." / ".." / "runtime" / "koboldcpp.exe",  # MO2 mod folder runtime
        Path(r"E:\Mod.Organizer-2.5.2 Game Mods\Fallout 4 Advanced AI - Mossy Industries\Data\F4AI\runtime\koboldcpp.exe"),
        runtime / "koboldcpp.exe",                                 # Mossy userData runtime
        Path(r"D:\koboldcpp-concedo\koboldcpp.exe"),
        Path(r"D:\koboldcpp\koboldcpp.exe"),
        Path(r"C:\koboldcpp\koboldcpp.exe"),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\koboldcpp\koboldcpp.exe")),
    ]
    return next((p for p in candidates if p.exists()), candidates[0])


def _find_gguf_model() -> Path:
    """Search all known model locations. Prefers Llama 3 8B over TinyLlama."""
    runtime = _find_mossy_runtime()
    candidates = [
        # Llama 3 8B Instruct — much better NPC dialogue quality (prefer over TinyLlama)
        Path(r"E:\.ai-navigator\models\meta-llama\Meta-Llama-3-8B-Instruct\Meta-Llama-3-8B-Instruct_Q4_K_M.gguf"),
        Path(r"E:\.ai-navigator\models\meta-llama\Meta-Llama-3-8B-Instruct\Meta-Llama-3-8B-Instruct_Q8_0.gguf"),
        # TinyLlama 1.1B fallback
        _F4AI_BASE / "models" / "tinyllama-1.1b-chat.gguf",
        _F4AI_BASE / "models" / "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
        Path(r"E:\Mod.Organizer-2.5.2 Game Mods\Fallout 4 Advanced AI - Mossy Industries\Data\F4AI\models\tinyllama-1.1b-chat.gguf"),
        runtime.parent / "models" / "tinyllama-1.1b-chat.gguf",
        Path(r"D:\koboldcpp-concedo\models\tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"),
        Path(r"D:\koboldcpp\models\tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"),
    ]
    return next((p for p in candidates if p.exists()), candidates[0])

MOSSY_RUNTIME   = _find_mossy_runtime()
KOBOLD_EXE      = _find_kobold_exe()
TINYLLAMA_MODEL = _find_gguf_model()
KOBOLD_API_URL  = "http://127.0.0.1:5001/api/v1/info"
KOBOLD_PORT     = 5001

# Credits (displayed in engine status so Mossy UI can surface them)
ENGINE_CREDITS = {
    "koboldcpp": {
        "name":    "KoboldCPP",
        "author":  "LostRuins / Henk717",
        "license": "AGPL-3.0",
        "url":     "https://github.com/LostRuins/koboldcpp",
        "download_url": "https://github.com/LostRuins/koboldcpp/releases/latest/download/koboldcpp.exe",
    },
    "tinyllama": {
        "name":    "TinyLlama 1.1B Chat v1.0 Q4_K_M",
        "author":  "TinyLlama team — GGUF by TheBloke",
        "license": "Apache 2.0",
        "url":     "https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
        "download_url": "https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
    },
}

def _kobold_running() -> bool:
    """Return True if KoboldCPP is already listening on port 5001."""
    try:
        r = requests.get(KOBOLD_API_URL, timeout=2)
        return r.status_code < 500
    except Exception:
        return False

def get_engine_status() -> dict:
    """Return install + running state for KoboldCPP and TinyLlama."""
    kobold_installed  = KOBOLD_EXE.exists()
    model_installed   = TINYLLAMA_MODEL.exists()
    kobold_running    = _kobold_running()

    return {
        "runtime_dir":       str(MOSSY_RUNTIME),
        "kobold_path":       str(KOBOLD_EXE),
        "model_path":        str(TINYLLAMA_MODEL),
        "kobold_installed":  kobold_installed,
        "model_installed":   model_installed,
        "kobold_running":    kobold_running,
        "api_url":           f"http://127.0.0.1:{KOBOLD_PORT}/api/v1",
        "ready":             kobold_installed and model_installed and kobold_running,
        "credits":           ENGINE_CREDITS,
    }

def start_kobold_engine() -> dict:
    """Start KoboldCPP with TinyLlama. Called by Mossy after auto-download."""
    if _kobold_running():
        return {"ok": True, "message": "KoboldCPP already running."}

    if not KOBOLD_EXE.exists():
        return {"ok": False, "message": f"koboldcpp.exe not found at {KOBOLD_EXE}. Run the Mossy initial install."}

    if not TINYLLAMA_MODEL.exists():
        return {"ok": False, "message": f"TinyLlama model not found at {TINYLLAMA_MODEL}. Run the Mossy initial install."}

    TINYLLAMA_MODEL.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(KOBOLD_EXE),
        "--model",       str(TINYLLAMA_MODEL),
        "--port",        str(KOBOLD_PORT),
        "--host",        "127.0.0.1",
        "--contextsize", "2048",
        "--threads",     "4",
        "--blasthreads", "4",
        "--nommap",
        "--quiet",
    ]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        return {"ok": False, "message": f"Failed to start KoboldCPP: {exc}"}

    # Wait up to 20s for it to respond
    for _ in range(10):
        time.sleep(2)
        if _kobold_running():
            return {"ok": True, "message": "KoboldCPP started successfully."}

    return {"ok": False, "message": "KoboldCPP started but did not respond within 20s."}

# ─────────────────────────────────────────────────────────────────────────────
# LLM Inference — llama-cpp-python (primary) → KoboldCPP HTTP (fallback)
# ─────────────────────────────────────────────────────────────────────────────
# pip install llama-cpp-python
# For NVIDIA GPU: pip install llama-cpp-python --extra-index-url
#   https://abetlen.github.io/llama-cpp-python/whl/cu121

try:
    from llama_cpp import Llama
    _LLAMA_AVAILABLE = True
except ImportError:
    Llama = None
    _LLAMA_AVAILABLE = False

_llm        = None   # cached Llama instance
_llm_lock   = threading.Lock()

# Model search paths — resolved at import time using the same multi-path finder
_MODEL_CANDIDATES = [
    _F4AI_BASE / "models" / "tinyllama-1.1b-chat.gguf",          # same F4AI install tree (primary)
    Path(os.path.expandvars(r"%APPDATA%\mossy-ai\models\tinyllama-1.1b-chat.gguf")),
    Path(os.path.expandvars(r"%LOCALAPPDATA%\mossy-ai\models\tinyllama-1.1b-chat.gguf")),
    TINYLLAMA_MODEL,  # resolved by _find_gguf_model() above
]

def _load_llm():
    """Lazy-load TinyLlama. Returns None if unavailable."""
    global _llm
    if _llm is not None:
        return _llm
    if not _LLAMA_AVAILABLE:
        return None
    with _llm_lock:
        if _llm is not None:
            return _llm
        try:
            local = next((p for p in _MODEL_CANDIDATES if p.exists()), None)
            if local:
                print(f"[Bridge/LLM] Loading from {local}")
                _llm = Llama(model_path=str(local), n_ctx=2048, n_threads=4, verbose=False)
                print("[Bridge/LLM] Model ready.")
            else:
                print("[Bridge/LLM] No local model found — skipping load. "
                      "Place a GGUF in the models/ folder or run KoboldCPP separately.")
        except Exception as exc:
            print(f"[Bridge/LLM] Load failed: {exc}")
            _llm = None
    return _llm

# ── NPC system prompt templates ───────────────────────────────────────────────

_NPC_PROMPTS = {
    "settler": (
        "You are {name}, a settler surviving in the post-apocalyptic Commonwealth of Fallout 4. "
        "You are weathered, practical, and wary of strangers. You speak plainly with a hint of exhaustion. "
        "You work for {faction}. "
        "{memory}"
        "Reply in character in 1-2 sentences. Never break character or mention being an AI."
    ),
    "companion": (
        "You are {name}, the Sole Survivor's trusted companion in Fallout 4. "
        "You have your own personality, opinions, and backstory. "
        "{memory}"
        "Reply with your character's voice in 1-2 sentences. Show your personality."
    ),
    "raider": (
        "You are {name}, a ruthless raider in the Fallout 4 Commonwealth. "
        "You are aggressive, greedy, and dangerous. You mock weakness. "
        "{memory}"
        "Reply with menace and bravado in 1-2 sentences."
    ),
    "robot": (
        "You are {name}, a robot unit operating in the Commonwealth. "
        "You follow your primary directive and speak in a logical, mechanical manner. "
        "{memory}"
        "Reply concisely and in-character in 1-2 sentences."
    ),
    "ghoul": (
        "You are {name}, a ghoul who has survived centuries of radiation in the Commonwealth. "
        "You carry deep wisdom from the old world but are treated as an outcast. "
        "{memory}"
        "Reply with the weight of lived experience in 1-2 sentences."
    ),
    "default": (
        "You are {name}, an NPC in the post-apocalyptic Commonwealth of Fallout 4. "
        "You are part of {faction}. "
        "{memory}"
        "Reply in character in 1-2 sentences."
    ),
}

_RACE_TO_TYPE = {
    "ghoul": "ghoul", "feral ghoul": "ghoul",
    "raider": "raider",
    "robot": "robot", "mr. handy": "robot", "protectron": "robot",
    "synth": "robot", "courser": "robot",
    "settler": "settler", "minuteman": "settler",
    "companion": "companion",
}

def _build_system_prompt(mem: dict) -> str:
    """Build an NPC-specific system prompt from their memory profile."""
    identity = mem.get("identity", {})
    name     = identity.get("npc_name", "Unknown")
    race     = (identity.get("npc_race") or "").lower()
    faction  = identity.get("npc_faction") or "no known faction"

    npc_type = _RACE_TO_TYPE.get(race, "default")
    template = _NPC_PROMPTS.get(npc_type, _NPC_PROMPTS["default"])

    # Build memory context string
    memory_lines = []
    for m in mem.get("memories", [])[:5]:
        memory_lines.append(f"- {m.get('detail','')}")
    rel = (mem.get("relationship") or {}).get("relationship", "stranger")
    memory_lines.insert(0, f"Your relationship with the player: {rel}.")
    memory_ctx = "What you remember:\n" + "\n".join(memory_lines) + "\n" if memory_lines else ""

    return template.format(name=name, faction=faction, memory=memory_ctx)

def _build_messages(system: str, dialogue_history: list, player_input: str) -> list:
    """Build the messages array for create_chat_completion."""
    messages = [{"role": "system", "content": system}]
    for d in reversed(dialogue_history[-6:]):  # last 6 lines, chronological
        role = "user" if d.get("speaker") == "player" else "assistant"
        messages.append({"role": role, "content": d.get("line", "")})
    messages.append({"role": "user", "content": player_input})
    return messages

def generate_npc_dialogue(npc_id: str, player_input: str) -> dict:
    """
    Generate an NPC response using llama-cpp-python.
    Falls back to KoboldCPP HTTP API if llama_cpp is not installed.
    """
    mem      = get_npc_memory(npc_id)
    system   = _build_system_prompt(mem) if mem.get("found") else _NPC_PROMPTS["default"].format(
        name="Unknown NPC", faction="the Commonwealth", memory="")
    dialogue = mem.get("dialogue", []) if mem.get("found") else []
    messages = _build_messages(system, dialogue, player_input)

    # ── Try llama-cpp-python ──────────────────────────────────────────────────
    llm = _load_llm()
    if llm is not None:
        try:
            result = llm.create_chat_completion(
                messages=messages,
                max_tokens=60,
                temperature=0.75,
                top_p=0.95,
                repeat_penalty=1.1,
                stop=["User:", "Player:", "\n\n", ".", "!", "?"],
            )
            text = result["choices"][0]["message"]["content"].strip()
            return {"ok": True, "text": text, "engine": "llama-cpp-python"}
        except Exception as exc:
            print(f"[Bridge/LLM] Inference error: {exc}")

    # ── Fallback: KoboldCPP OpenAI-compat endpoint ────────────────────────────
    if _kobold_running():
        try:
            r = requests.post(
                f"http://127.0.0.1:{KOBOLD_PORT}/v1/chat/completions",
                json={"model": "tinyllama", "messages": messages, "max_tokens": 60, "temperature": 0.75},
                timeout=30,
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
            return {"ok": True, "text": text, "engine": "koboldcpp"}
        except Exception as exc:
            print(f"[Bridge] KoboldCPP error: {exc}")

    return {"ok": False, "error": "No local AI engine available (llama-cpp-python / KoboldCPP)."}

# Status tracking
_status = {
    "bridge_version": BRIDGE_VERSION,
    "connected": False,
    "game_running": False,
    "mod_enabled": False,
    "actors_overridden": 0,
    "session_errors": 0,
    "modules": {
        "creatures": False,
        "npcs": False,
        "companions": False,
        "robots": False,
        "group_tactics": False,
    },
    "last_log_line": "",
    "last_update": "",
    "log_path": str(PAPYRUS_LOG),
}

_log_buffer     = []   # Last 200 [AAI] log lines
_log_buffer_max = 200
_log_lock       = threading.Lock()

# Pending request from Papyrus (bridge_input.json → text_out.txt round-trip)
_pending_request = None
_pending_lock    = threading.Lock()

# ─────────────────────────────────────────────────────────────────────────────
# External NPC Memory Database
# ─────────────────────────────────────────────────────────────────────────────
# This is the PC-side memory store. Papyrus can only hold a few int slots;
# Mossy stores the full conversation history here and syncs back via the bridge.

def init_memory_db():
    """Initialize SQLite database for NPC external memory."""
    conn = sqlite3.connect(MEMORY_DB_PATH)
    c = conn.cursor()

    # NPC identity table
    c.execute("""
        CREATE TABLE IF NOT EXISTS npc_identities (
            npc_id      TEXT PRIMARY KEY,
            npc_name    TEXT NOT NULL,
            npc_race    TEXT,
            npc_faction TEXT,
            first_met   TEXT,
            last_seen   TEXT,
            affinity    REAL DEFAULT 0.0,
            emotion     INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Conversation memory events
    c.execute("""
        CREATE TABLE IF NOT EXISTS npc_memories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            npc_id      TEXT NOT NULL,
            event_code  INTEGER NOT NULL,
            event_label TEXT,
            detail      TEXT,
            game_time   REAL,
            real_time   TEXT DEFAULT CURRENT_TIMESTAMP,
            recalled    INTEGER DEFAULT 0,
            FOREIGN KEY (npc_id) REFERENCES npc_identities(npc_id)
        )
    """)

    # Full dialogue history (what was actually said)
    c.execute("""
        CREATE TABLE IF NOT EXISTS dialogue_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            npc_id      TEXT NOT NULL,
            speaker     TEXT NOT NULL,  -- 'npc' or 'player'
            topic       TEXT,
            line        TEXT NOT NULL,
            game_time   REAL,
            real_time   TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (npc_id) REFERENCES npc_identities(npc_id)
        )
    """)

    # NPC relationship state
    c.execute("""
        CREATE TABLE IF NOT EXISTS npc_relationships (
            npc_id          TEXT PRIMARY KEY,
            player_name     TEXT DEFAULT 'Sole Survivor',
            relationship    TEXT DEFAULT 'stranger',  -- stranger/acquaintance/friend/loyal/idolize/hostile
            total_encounters INTEGER DEFAULT 0,
            notes           TEXT,
            FOREIGN KEY (npc_id) REFERENCES npc_identities(npc_id)
        )
    """)

    conn.commit()
    conn.close()
    print(f"[Bridge] Memory database initialized: {MEMORY_DB_PATH}")

def get_npc_memory(npc_id: str) -> dict:
    """Retrieve full memory profile for an NPC."""
    conn = sqlite3.connect(MEMORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get identity
    c.execute("SELECT * FROM npc_identities WHERE npc_id = ?", (npc_id,))
    identity = c.fetchone()
    if not identity:
        conn.close()
        return {"found": False, "npc_id": npc_id}

    # Get recent memories (last 20)
    c.execute("""
        SELECT * FROM npc_memories
        WHERE npc_id = ?
        ORDER BY real_time DESC LIMIT 20
    """, (npc_id,))
    memories = [dict(row) for row in c.fetchall()]

    # Get recent dialogue (last 10 exchanges)
    c.execute("""
        SELECT * FROM dialogue_history
        WHERE npc_id = ?
        ORDER BY real_time DESC LIMIT 10
    """, (npc_id,))
    dialogue = [dict(row) for row in c.fetchall()]

    # Get relationship
    c.execute("SELECT * FROM npc_relationships WHERE npc_id = ?", (npc_id,))
    rel = c.fetchone()

    conn.close()
    return {
        "found": True,
        "npc_id": npc_id,
        "identity": dict(identity),
        "memories": memories,
        "dialogue": dialogue,
        "relationship": dict(rel) if rel else None,
    }

def record_npc_memory(npc_id: str, npc_name: str, event_code: int,
                      event_label: str = "", detail: str = "", game_time: float = 0.0):
    """Record a new memory event for an NPC."""
    conn = sqlite3.connect(MEMORY_DB_PATH)
    c = conn.cursor()
    now = datetime.datetime.now().isoformat()

    # Ensure NPC identity exists
    c.execute("""
        INSERT OR IGNORE INTO npc_identities (npc_id, npc_name, first_met, last_seen)
        VALUES (?, ?, ?, ?)
    """, (npc_id, npc_name, now, now))

    # Update last seen
    c.execute("UPDATE npc_identities SET last_seen = ? WHERE npc_id = ?", (now, npc_id))

    # Record memory event
    c.execute("""
        INSERT INTO npc_memories (npc_id, event_code, event_label, detail, game_time)
        VALUES (?, ?, ?, ?, ?)
    """, (npc_id, event_code, event_label, detail, game_time))

    # Update encounter count
    c.execute("""
        INSERT OR IGNORE INTO npc_relationships (npc_id) VALUES (?)
    """, (npc_id,))
    c.execute("""
        UPDATE npc_relationships SET total_encounters = total_encounters + 1
        WHERE npc_id = ?
    """, (npc_id,))

    conn.commit()
    conn.close()

def record_dialogue(npc_id: str, npc_name: str, speaker: str, topic: str,
                    line: str, game_time: float = 0.0):
    """Store a dialogue line in the external memory."""
    conn = sqlite3.connect(MEMORY_DB_PATH)
    c = conn.cursor()
    now = datetime.datetime.now().isoformat()

    c.execute("""
        INSERT OR IGNORE INTO npc_identities (npc_id, npc_name, first_met, last_seen)
        VALUES (?, ?, ?, ?)
    """, (npc_id, npc_name, now, now))
    c.execute("UPDATE npc_identities SET last_seen = ? WHERE npc_id = ?", (now, npc_id))

    c.execute("""
        INSERT INTO dialogue_history (npc_id, speaker, topic, line, game_time)
        VALUES (?, ?, ?, ?, ?)
    """, (npc_id, speaker, topic, line, game_time))

    conn.commit()
    conn.close()

def update_npc_affinity(npc_id: str, affinity: float, emotion: int):
    """Sync affinity value from game to external database."""
    conn = sqlite3.connect(MEMORY_DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE npc_identities SET affinity = ?, emotion = ?
        WHERE npc_id = ?
    """, (affinity, emotion, npc_id))
    conn.commit()
    conn.close()

def get_all_npcs() -> list:
    """Get summary of all NPCs with memories."""
    conn = sqlite3.connect(MEMORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT i.*, r.relationship, r.total_encounters,
               (SELECT COUNT(*) FROM npc_memories m WHERE m.npc_id = i.npc_id) as memory_count,
               (SELECT COUNT(*) FROM dialogue_history d WHERE d.npc_id = i.npc_id) as dialogue_count
        FROM npc_identities i
        LEFT JOIN npc_relationships r ON i.npc_id = r.npc_id
        ORDER BY i.last_seen DESC
    """)
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows

# ─────────────────────────────────────────────────────────────────────────────
# Papyrus Log Reader
# ─────────────────────────────────────────────────────────────────────────────

AAI_LOG_PATTERN    = re.compile(r'\[AAI(?:-[A-Za-z]+)?\]\s*(.*)')
AAI_STATUS_PATTERN = re.compile(
    r'AAI_STATUS\|enabled=(\w+)\|overridden=(\d+)\|errors=(\d+)\|'
    r'creatures=(\w+)\|npcs=(\w+)\|robots=(\w+)\|companions=(\w+)\|'
    r'groupTactics=(\w+)'
)
AAI_MEMORY_PATTERN = re.compile(
    r'AAI_MEM\|npc_id=([^|]+)\|npc_name=([^|]+)\|event=(\d+)\|detail=([^|]*)\|time=([\d.]+)'
)
AAI_DIALOGUE_PATTERN = re.compile(
    r'AAI_DIAL\|npc_id=([^|]+)\|npc_name=([^|]+)\|speaker=([^|]+)\|topic=([^|]*)\|line=(.+)'
)
AAI_AFFINITY_PATTERN = re.compile(
    r'AAI_AFF\|npc_id=([^|]+)\|affinity=([\d.-]+)\|emotion=(\d+)'
)

def parse_log_line(line: str):
    """Parse an [AAI] tagged log line and update status / memory."""
    global _status

    aai_match = AAI_LOG_PATTERN.search(line)
    if not aai_match:
        return

    content = aai_match.group(1).strip()
    now = datetime.datetime.now().isoformat()

    with _log_lock:
        _log_buffer.append({"time": now, "line": content})
        if len(_log_buffer) > _log_buffer_max:
            _log_buffer.pop(0)

    _status["last_log_line"] = content
    _status["last_update"] = now
    _status["mod_enabled"] = True

    # Parse status report
    s_match = AAI_STATUS_PATTERN.search(content)
    if s_match:
        _status["mod_enabled"]        = s_match.group(1).lower() == "true"
        _status["actors_overridden"]  = int(s_match.group(2))
        _status["session_errors"]     = int(s_match.group(3))
        _status["modules"]["creatures"]    = s_match.group(4).lower() == "true"
        _status["modules"]["npcs"]         = s_match.group(5).lower() == "true"
        _status["modules"]["robots"]       = s_match.group(6).lower() == "true"
        _status["modules"]["companions"]   = s_match.group(7).lower() == "true"
        _status["modules"]["group_tactics"]= s_match.group(8).lower() == "true"
        return

    # Parse external memory event
    m_match = AAI_MEMORY_PATTERN.search(content)
    if m_match:
        record_npc_memory(
            npc_id=m_match.group(1),
            npc_name=m_match.group(2),
            event_code=int(m_match.group(3)),
            event_label="",
            detail=m_match.group(4),
            game_time=float(m_match.group(5)),
        )
        return

    # Parse dialogue line
    d_match = AAI_DIALOGUE_PATTERN.search(content)
    if d_match:
        record_dialogue(
            npc_id=d_match.group(1),
            npc_name=d_match.group(2),
            speaker=d_match.group(3),
            topic=d_match.group(4),
            line=d_match.group(5),
        )
        return

    # Parse affinity update
    a_match = AAI_AFFINITY_PATTERN.search(content)
    if a_match:
        update_npc_affinity(
            npc_id=a_match.group(1),
            affinity=float(a_match.group(2)),
            emotion=int(a_match.group(3)),
        )
        return

def _load_f4ai_config() -> dict:
    """Load Data/F4AI/config.json; return {} on any error."""
    try:
        cfg_path = F4AI_DATA_DIR / "config.json"
        if cfg_path.exists():
            with open(cfg_path, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

_RACE_TO_ROLE = {
    "robot": "robot", "synth": "robot", "protectron": "robot",
    "assaultron": "robot", "sentry bot": "robot", "mr. handy": "robot",
    "ghoul": "ghoul", "feral ghoul": "ghoul",
    "super mutant": "raider", "raider": "raider",
    "settler": "settler", "minuteman": "settler",
    "companion": "companion",
}

# ── NPC Persona Pool ──────────────────────────────────────────────────────────
# Generic NPCs (settlers, unnamed wastelanders) are assigned one of these
# personas deterministically via formID % len(pool), so the same NPC always
# speaks with the same voice across sessions.
_SETTLER_PERSONAS = [
    "A gruff ex-military veteran. Speaks in short, direct sentences. Doesn't trust outsiders easily.",
    "A young optimist who never knew pre-war life. Curious and energetic, finds the wasteland exciting.",
    "A former raider going straight. Dark sense of humor, carries obvious guilt about the past.",
    "An older survivor full of pre-war stories. Gets nostalgic easily, misses the old world dearly.",
    "The settlement gossip. Always knows everyone's business and loves to share news and rumors.",
    "A paranoid survivalist who trusts no one. Constantly watching, speaks like someone's listening.",
    "A former caravan trader with stories from across the Commonwealth. Practical and deal-minded.",
    "A quiet, grieving parent who lost their family. Rarely speaks but says meaningful things.",
]

def _get_npc_persona(npc_form_id: str) -> str:
    """Deterministic persona by formID — same NPC always gets the same personality."""
    try:
        return _SETTLER_PERSONAS[int(npc_form_id) % len(_SETTLER_PERSONAS)]
    except (ValueError, TypeError):
        return _SETTLER_PERSONAS[0]

def _get_dialogue_history_for_mossy(npc_id: str) -> list:
    """Pull the last 6 dialogue lines from SQLite, formatted for Mossy's dialogue_history field."""
    try:
        mem = get_npc_memory(npc_id)
        if not mem.get("found"):
            return []
        history = []
        for d in reversed(mem.get("dialogue", [])[:6]):
            line = d.get("line", "")
            if line:
                history.append({"speaker": d.get("speaker", "npc"), "line": line})
        return history
    except Exception:
        return []

_AMBIENT_TOPICS = [
    "daily life in the settlement", "food and supplies", "the weather lately",
    "rumors they heard", "a nearby threat", "the good old days before the war",
    "their hopes for the future", "something they found on patrol",
    "a disagreement with someone", "repairs that need doing",
]

def _pick_topic(last_topic: str = "") -> str:
    """Pick an ambient conversation topic, avoiding the last one."""
    available = [t for t in _AMBIENT_TOPICS if t != last_topic]
    return random.choice(available or _AMBIENT_TOPICS)

# ── Mod / Load Order Awareness ────────────────────────────────────────────────
# Scans plugins.txt once at startup and converts the load order into a natural-
# language context string that every AI call receives.  NPCs then naturally
# reference Sim Settlements city plans, Horizon scarcity, True Storms weather,
# custom quest storylines, etc. without any CK work.

_MOD_KEYWORD_CATEGORIES: list[tuple[list[str], str]] = [
    (["horizon"],                                         "horizon"),
    (["survival", "scarcity", "starv", "hardcor"],        "survival"),
    (["simsettlement", "sim_settlement", "ss2"],          "sim_settlements"),
    (["truestorm", "true_storm", "nacx", "vivid", "nac"], "weather_mod"),
    (["companion", "follower", "partner"],                "companion_mod"),
    (["minuteman", "minutemen"],                          "minuteman_mod"),
    (["economy", "trade", "barter", "currency"],          "economy_mod"),
    (["weapon", "gun", "rifle", "pistol", "ammo",
      "arsenal", "firearm"],                              "weapons_mod"),
    (["armor", "cloth", "apparel", "outfit"],             "armor_mod"),
    (["settlement", "workshop", "homemaker", "structur"], "settlement_mod"),
    (["quest", "mission", "story", "adventure",
      "project", "tale", "rising"],                       "quest_mod"),
    (["radio", "music", "soundtrack", "broadcast"],       "radio_mod"),
    (["food", "cook", "recipe", "hunger", "thirst"],      "food_mod"),
    (["medical", "drug", "chem", "stimpak"],              "medical_mod"),
    (["stealth", "sneak", "detection"],                   "stealth_mod"),
    (["perk", "leveling", "progression", "skill"],        "progression_mod"),
    (["lighting", "enb", "reshade", "dark"],              "visual_mod"),
    (["loot", "container", "junk", "scrap"],              "loot_mod"),
]

_MOD_CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "horizon":          "Horizon overhaul is active: crafting, economy, damage, and progression are dramatically changed. Resources feel truly scarce and dangerous.",
    "survival":         "Survival mechanics are on: food, water, and sleep matter. NPCs know that basic needs are a constant struggle.",
    "sim_settlements":  "Sim Settlements 2 is running: settlements operate around city plans, residents have assigned roles (farmer, guard, merchant), and the Commonwealth is being rebuilt city by city.",
    "weather_mod":      "Advanced weather is installed: storms, fog, and radiation weather are more dramatic, immersive, and dangerous than vanilla.",
    "companion_mod":    "Custom companions are available with unique personalities and questlines.",
    "minuteman_mod":    "Minuteman content is expanded with new missions, fortifications, and lore.",
    "economy_mod":      "Economy mods change how caps, trade, and bartering work across the Commonwealth.",
    "weapons_mod":      "Expanded weapons add real-world firearms alongside wasteland-crafted weapons.",
    "armor_mod":        "Additional armor and apparel mods give NPCs and settlers more varied looks.",
    "settlement_mod":   "Settlement building is greatly expanded with more structures and decorations.",
    "quest_mod":        "Major quest mods add new storylines, factions, and locations across the Commonwealth.",
    "radio_mod":        "Radio mods add new stations, music, or commentary to the Commonwealth airwaves.",
    "food_mod":         "Food and cooking mods add more recipes, nutritional depth, and food variety.",
    "medical_mod":      "Medical/chem mods change how healing and chems work.",
    "stealth_mod":      "Stealth overhauls change detection and sneaking significantly.",
    "progression_mod":  "Perk and leveling mods alter how characters grow and develop.",
    "visual_mod":       "Visual enhancement mods change how the Commonwealth looks.",
    "loot_mod":         "Loot mods change what is found in containers and on enemies.",
}

_mod_context_cache: str | None = None
_mod_context_lock  = threading.Lock()


def _find_plugins_txt() -> Path | None:
    """Find the active plugins.txt — checks MO2 profiles first, then game AppData."""
    mo2_bases = [
        Path(r"E:\Mod.Organizer-2.5.2"),
        Path(r"E:\ModOrganizer2"),
        Path(r"D:\Mod Organizer 2"),
        Path(os.path.expandvars(r"%APPDATA%\ModOrganizer")),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\ModOrganizer2")),
    ]
    for base in mo2_bases:
        if not base.exists():
            continue
        # Take the most recently modified profile's plugins.txt
        candidates = list(base.glob("profiles/*/plugins.txt"))
        if candidates:
            return max(candidates, key=lambda p: p.stat().st_mtime)

    fo4_appdata = Path(os.path.expandvars(r"%LOCALAPPDATA%\Fallout4\plugins.txt"))
    if fo4_appdata.exists():
        return fo4_appdata
    return None


def _parse_active_plugins(path: Path) -> list[str]:
    """Return active plugin names from plugins.txt (lines prefixed with * are active)."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        plugins: list[str] = []
        for line in lines:
            line = line.strip()
            if line.startswith("*"):
                name = line[1:].strip()
                if name:
                    plugins.append(name)
            elif line and not line.startswith("#"):
                plugins.append(line)   # format without * prefix (all enabled)
        return plugins
    except Exception:
        return []


def _categorize_plugins(plugins: list[str]) -> dict[str, list[str]]:
    """Group plugin filenames into categories by keyword matching."""
    result: dict[str, list[str]] = {}
    for plugin in plugins:
        lower = plugin.lower()
        for keywords, category in _MOD_KEYWORD_CATEGORIES:
            if any(kw in lower for kw in keywords):
                result.setdefault(category, []).append(plugin)
                break
    return result


def build_mod_context() -> str:
    """Scan plugins.txt once, return a natural-language description of the active mod setup.

    Cached for the process lifetime — mods don't change while the bridge runs.
    """
    global _mod_context_cache
    with _mod_context_lock:
        if _mod_context_cache is not None:
            return _mod_context_cache

        path = _find_plugins_txt()
        if not path:
            _mod_context_cache = ""
            print("[Bridge] Mod context: plugins.txt not found — NPC dialogue will use vanilla context.")
            return ""

        plugins  = _parse_active_plugins(path)
        cats     = _categorize_plugins(plugins)
        if not cats:
            _mod_context_cache = ""
            return ""

        descs = [_MOD_CATEGORY_DESCRIPTIONS[c] for c in cats if c in _MOD_CATEGORY_DESCRIPTIONS]
        if not descs:
            _mod_context_cache = ""
            return ""

        ctx = "Active mods context: " + " ".join(descs)
        _mod_context_cache = ctx
        print(f"[Bridge] Mod context built from {len(plugins)} plugins — "
              f"categories: {list(cats.keys())}")
        return ctx


def _read_world_state() -> dict:
    """Read the latest world_state.json written by F4AI_WorldMonitor (every 30s)."""
    for d in [F4AI_DATA_DIR, _MO2_MOD_F4AI, FO4_GAME_PATH / "Data" / "F4AI"]:
        p = d / "world_state.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def _build_full_context(payload: dict) -> str:
    """Combine live world state + mod awareness + payload location into one context string.

    This is injected into every AI call so NPCs are aware of:
      - Where they are and what the weather / time is (from WorldMonitor)
      - What season it is (Seasons Change mod or vanilla)
      - The player's faction alignment and approximate experience level
      - Which DLCs are active (NPCs can reference Far Harbor, Nuka-World by reputation)
      - Which major mod systems are running (SS2, Horizon, True Storms, quest mods…)
    """
    parts: list[str] = []

    # Payload location/weather (freshest — written by Papyrus just now)
    location = payload.get("location", "")
    weather  = payload.get("weather", "")
    if location:
        parts.append(f"Location: {location}.")
    if weather:
        parts.append(f"Weather: {weather}.")

    # Live world state from WorldMonitor (richer detail, updates every 30s)
    world = _read_world_state()
    if world:
        season = world.get("season", "")
        tod    = world.get("time_of_day", "")
        if season and season not in ("Unknown", ""):
            parts.append(f"Season: {season}.")
        if tod:
            parts.append(f"Time of day: {tod}.")
        if world.get("is_storming"):
            parts.append("A radstorm or heavy storm is currently active.")
        elif world.get("is_raining"):
            parts.append("It is raining.")
        if world.get("is_night"):
            parts.append("It is night.")

        # Player progression — use level as a proxy for experience
        level = int(world.get("player_level", 0))
        if level > 0:
            if level < 10:
                parts.append("The player is a newcomer still finding their footing.")
            elif level < 30:
                parts.append("The player is an experienced wastelander.")
            elif level < 60:
                parts.append("The player is a seasoned veteran of the Commonwealth.")
            else:
                parts.append("The player is a legendary figure whose reputation precedes them.")

        # Faction alignment — NPCs react differently based on who the player works with
        faction = world.get("player_faction", "None")
        if faction and faction != "None":
            parts.append(f"The player is aligned with the {faction}.")

        # Active DLCs — NPCs can reference locations/events from DLC areas
        dlcs = world.get("dlc", "Base Game Only")
        if dlcs and dlcs != "Base Game Only":
            dlc_list = [d.strip().rstrip(",") for d in dlcs.split(",") if d.strip()]
            if dlc_list:
                parts.append(f"DLC regions available: {', '.join(dlc_list)}.")

    # Creature / ecosystem awareness — NPCs can organically reference nearby predator activity
    with _ecosystem_lock:
        eco = dict(_latest_ecosystem)
    if eco:
        eco_state  = eco.get("ecosystem_state", "")
        territory  = eco.get("territory_owner", "")
        pred_count = int(eco.get("predator_count", 0))
        prey_count = int(eco.get("prey_count", 0))
        if eco_state == "predator_starving" and territory:
            parts.append(
                f"Danger: {territory}s in this area are starving and behaving erratically — very aggressive."
            )
        elif eco_state == "overhunted" and territory:
            parts.append(
                f"This area is overrun with {territory}s. Prey animals have fled. It is unusually dangerous."
            )
        elif eco_state == "winter_balanced" and pred_count > 0 and territory:
            parts.append(
                f"Winter scarcity: {territory}s are hunting more aggressively than usual."
            )
        elif eco_state in ("prey_boom", "prey_abundant") and prey_count > 0:
            parts.append("Local wildlife is thriving — prey animals are numerous and predators are well-fed.")
        elif eco_state == "balanced" and territory:
            parts.append(f"A {territory} has claimed this territory. Keep watch.")
        elif eco_state == "prey_dominant" and pred_count == 0:
            parts.append("The area is relatively safe from large predators right now.")

    # Mod context (cached from plugin scan at startup)
    mod_ctx = build_mod_context()
    if mod_ctx:
        parts.append(mod_ctx)

    return " ".join(parts)


def _call_mossy(payload: dict, dialogue_history: list | None = None) -> dict:
    """POST the game request to the Mossy desktop AI endpoint.

    Mossy listens on http://127.0.0.1:8765/f4ai/bridge and expects Mossy-format
    fields (npc_id, npc_role, player_input). It returns {"dialogue": "..."}.
    We also accept text/response/content/npc_response for forward-compat.
    Mossy uses Groq (free cloud API) as its AI backend.
    """
    cfg = _load_f4ai_config()
    if not cfg.get("enable_mossy_bridge", 1):
        return {"ok": False, "error": "Mossy bridge disabled in config.json"}

    endpoint = cfg.get("mossy_endpoint", "http://127.0.0.1:8765/f4ai/bridge")
    timeout  = float(cfg.get("mossy_timeout", 15.0))

    # Transform from bridge_input.json format to Mossy's expected format.
    # Mossy needs: npc_id, npc_name, npc_role, player_input, dialogue_history, context
    npc_name     = payload.get("npc_name", "Settler")
    npc_race     = (payload.get("npc_race") or "").lower()
    location     = payload.get("location", "The Commonwealth")
    player_input = payload.get("player_speech") or payload.get("player_input") or ""

    mossy_payload = {
        "npc_id":           npc_name.lower().replace(" ", "_"),
        "npc_name":         npc_name,
        "npc_role":         _RACE_TO_ROLE.get(npc_race, "default"),
        "player_input":     player_input,
        "dialogue_history": dialogue_history or [],
        "context":          _build_full_context(payload),
    }

    try:
        r = requests.post(endpoint, json=mossy_payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        # Mossy returns {"dialogue": "..."} — also accept text/response/npc_response/content
        text = (data.get("dialogue") or
                data.get("npc_response") or
                data.get("response") or
                data.get("text") or
                data.get("content") or
                ((data.get("choices") or [{}])[0].get("message") or {}).get("content", ""))
        if text and str(text).strip():
            return {"ok": True, "text": str(text).strip(), "engine": "mossy"}
        return {"ok": False, "error": f"Mossy returned empty body: {data}"}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "Mossy not running — start the Mossy AI launcher first"}
    except requests.exceptions.Timeout:
        return {"ok": False, "error": f"Mossy timed out after {timeout}s — try increasing mossy_timeout in config.json"}
    except Exception as exc:
        return {"ok": False, "error": f"Mossy error: {exc}"}

_TEXT_OUT_CANDIDATES = [
    TEXT_OUT_PATH,                         # MO2 Overwrites (primary)
    _MO2_MOD_F4AI / "text_out.txt",        # mod folder (Hydra may resolve here via VFS)
    FO4_GAME_PATH / "Data" / "F4AI" / "text_out.txt",  # bare game Data (no MO2)
]

def _write_text_out(text: str):
    """Write the NPC reply to all candidate text_out.txt locations.

    Hydra:IO:File.Exists resolves 'Data/F4AI/text_out.txt' through MO2's VFS,
    which may prefer Overwrites, the mod folder, or the bare game Data folder
    depending on MO2 version and profile settings.  Writing to all three
    guarantees Papyrus finds the response regardless of VFS redirect behaviour.
    """
    written = []
    for p in _TEXT_OUT_CANDIDATES:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            written.append(p)
        except Exception as exc:
            print(f"[Bridge] Could not write text_out.txt to {p}: {exc}")
    if written:
        print(f"[Bridge] text_out.txt written to {len(written)} location(s): "
              + ", ".join(p.parent.name for p in written))

def _call_ollama(payload: dict, dialogue_history: list | None = None) -> dict:
    """POST to Ollama's OpenAI-compatible endpoint (http://127.0.0.1:11434).

    Install Ollama from https://ollama.com then run: ollama pull llama3.1:8b
    Ollama auto-detects NVIDIA GPU and uses CUDA — no config needed.
    Recommended models (best to fastest): llama3.1:8b, mistral:7b, phi4-mini
    """
    npc_name     = payload.get("npc_name", "Settler")
    npc_race     = (payload.get("npc_race") or "").lower()
    location     = payload.get("location", "The Commonwealth")
    player_input = payload.get("player_speech") or payload.get("player_input") or "Hello."
    npc_form_id  = payload.get("npc_form_id", "0")

    # Persona gives each generic NPC a distinct, consistent voice
    persona     = _get_npc_persona(npc_form_id)
    full_ctx    = _build_full_context(payload)

    system = (
        f"You are {npc_name}, a survivor in the post-apocalyptic Commonwealth of Fallout 4. "
        f"{persona} "
        f"{full_ctx} "
        "Reply in character in 1-2 short sentences. Never break character or mention AI."
    )

    # Check which model Ollama has available — prefer larger/better models
    preferred = ["llama3.1:8b", "llama3:8b", "mistral:7b", "gemma3:9b",
                 "phi4-mini", "phi3:mini", "llama3.2:3b", "tinyllama"]
    model = "llama3.1:8b"
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        if r.ok:
            available = [m["name"] for m in r.json().get("models", [])]
            model = next((m for m in preferred if any(m in a for a in available)), model)
    except Exception:
        pass

    # Build message list: system + conversation history + current input
    messages = [{"role": "system", "content": system}]
    for d in (dialogue_history or []):
        role = "assistant" if d.get("speaker") == "npc" else "user"
        line = d.get("line", "")
        if line:
            messages.append({"role": role, "content": line})
    messages.append({"role": "user", "content": player_input})

    try:
        r = requests.post(
            "http://127.0.0.1:11434/v1/chat/completions",
            json={
                "model":       model,
                "messages":    messages,
                "max_tokens":  80,
                "temperature": 0.75,
                "stream":      False,
            },
            timeout=30,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()
        if text:
            return {"ok": True, "text": text, "engine": f"ollama/{model}"}
        return {"ok": False, "error": "Ollama returned empty response"}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "Ollama not running — install from https://ollama.com"}
    except Exception as exc:
        return {"ok": False, "error": f"Ollama error: {exc}"}


def _auto_respond(payload: dict):
    """Route an NPC dialogue request: Mossy → Ollama → KoboldCPP → fallback message."""
    npc_name      = payload.get("npc_name", "Unknown NPC")
    player_speech = payload.get("player_speech", "") or "Hello."

    # 1. Mossy (Groq cloud via Mossy desktop app) — primary, best quality
    result = _call_mossy(payload)
    if result.get("ok"):
        _write_text_out(result["text"])
        print(f"[Bridge] Mossy: {result['text'][:100]}")
        return

    print(f"[Bridge] Mossy unavailable: {result['error']}")

    # 2. Ollama — best local option; install from https://ollama.com
    #    then: ollama pull llama3.1:8b  (auto GPU, no config needed)
    result = _call_ollama(payload)
    if result.get("ok"):
        _write_text_out(result["text"])
        print(f"[Bridge] {result.get('engine','Ollama')}: {result['text'][:100]}")
        return

    print(f"[Bridge] Ollama unavailable: {result['error']}")

    # 3. KoboldCPP / llama-cpp-python — manual GGUF fallback
    result = generate_npc_dialogue(npc_name, player_speech)
    if result.get("ok"):
        _write_text_out(result["text"])
        print(f"[Bridge] Local AI ({result.get('engine','')}): {result['text'][:100]}")
        return

    print(f"[Bridge] Local AI unavailable: {result['error']}")

    # 4. Last resort — tell the player something useful
    _write_text_out("Start the Mossy AI launcher, then try again.")
    print("[Bridge] No AI engine available — wrote fallback in-game message.")

def _get_npc_text_out_paths(npc_form_id: str) -> list:
    """Return all candidate text_out paths for a specific NPC form ID."""
    fname = f"text_out_{npc_form_id}.txt"
    return [
        F4AI_DATA_DIR / fname,
        _MO2_MOD_F4AI / fname,
        FO4_GAME_PATH / "Data" / "F4AI" / fname,
    ]

def _write_npc_text_out(text: str, npc_form_id: str):
    """Write NPC response to per-NPC text_out file (all candidate locations)."""
    paths = _get_npc_text_out_paths(npc_form_id)
    written = []
    for p in paths:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
            written.append(p)
        except Exception as exc:
            print(f"[Bridge] Could not write {p.name}: {exc}")
    if written:
        print(f"[Bridge] {paths[0].name} written ({len(written)} location(s))")

def _handle_npc_request(found_path: Path):
    """Process a single per-NPC bridge_input file in its own thread."""
    # Extract NPC form ID from filename: bridge_input_<id>.json
    stem = found_path.stem  # e.g. "bridge_input_16909325"
    parts = stem.split("_")
    npc_form_id = parts[-1] if len(parts) >= 3 else "0"

    try:
        payload = json.loads(found_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[Bridge] Bad {found_path.name}: {exc}")
        return
    try:
        found_path.unlink()
    except Exception:
        pass

    npc_name_str = payload.get("npc_name", "Unknown NPC")
    location     = payload.get("location", "?")
    print(f"[Bridge] Request — NPC={npc_name_str} loc={location} id={npc_form_id}")

    with _pending_lock:
        global _pending_request
        _pending_request = {
            "payload":     payload,
            "received_at": datetime.datetime.now().isoformat(),
            "responded":   False,
        }

    # Expose formID to AI calls (persona lookup)
    payload["npc_form_id"] = npc_form_id

    player_speech_raw = payload.get("player_speech", "")
    player_speech     = player_speech_raw or "Hello."

    # ── Generate AI response (Mossy → Ollama → KoboldCPP → fallback) ────────
    # Hard 50-second deadline: Papyrus polls for 60s (300×0.2s), so we must
    # write the response file before that window closes regardless of AI speed.
    response_text = "I'm having trouble thinking right now. Try again in a moment."
    _ai_result    = [response_text]

    def _run_ai_chain():
        try:
            history = _get_dialogue_history_for_mossy(npc_form_id)
            result  = _call_mossy(payload, dialogue_history=history)
            if result.get("ok"):
                _ai_result[0] = result["text"]
                print(f"[Bridge] Mossy → {npc_name_str}: {result['text'][:80]}")
                return
            print(f"[Bridge] Mossy unavailable: {result['error']}")
            result = _call_ollama(payload, dialogue_history=history)
            if result.get("ok"):
                _ai_result[0] = result["text"]
                print(f"[Bridge] {result.get('engine','Ollama')} → {npc_name_str}: {result['text'][:80]}")
                return
            print(f"[Bridge] Ollama unavailable: {result['error']}")
            result = generate_npc_dialogue(npc_name_str, player_speech)
            if result.get("ok"):
                _ai_result[0] = result["text"]
                print(f"[Bridge] KoboldCPP → {npc_name_str}: {result['text'][:80]}")
                return
            _ai_result[0] = "Start the Mossy AI launcher, then try again."
            print("[Bridge] No AI engine available.")
        except Exception as exc:
            print(f"[Bridge] AI generation error: {exc}")

    ai_thread = threading.Thread(target=_run_ai_chain, daemon=True)
    ai_thread.start()
    ai_thread.join(timeout=50)
    if ai_thread.is_alive():
        print(f"[Bridge] AI chain hit 50s deadline for {npc_name_str} — using fallback")
    response_text = _ai_result[0]

    # ── Write response FIRST — SQLite errors must never block this ────────────
    _write_npc_text_out(response_text, npc_form_id)
    _write_text_out(response_text)  # legacy single-file fallback

    # ── Persist to memory DB (best-effort, non-blocking) ─────────────────────
    try:
        if player_speech_raw:
            record_dialogue(npc_form_id, npc_name_str, "player", "", player_speech_raw)
        record_dialogue(npc_form_id, npc_name_str, "npc", "", response_text)
        record_npc_memory(npc_form_id, npc_name_str, 1, "player_conversation",
                          f"Said to player: {response_text[:80]}")
    except Exception as exc:
        print(f"[Bridge] Memory DB error (non-fatal): {exc}")


def _generate_npc_line(npc_name: str, npc_id: str, npc_race: str,
                        other_name: str, context: str,
                        dialogue_history: list, behavior_hint: str) -> str | None:
    """Generate a single NPC dialogue line for ambient NPC-to-NPC conversations.

    Tries Mossy (Groq) first, falls back to Ollama.  Returns the text or None.
    context is the social event context string (location, relationship, topic).
    The mod context and world state are appended automatically.
    """
    persona   = _get_npc_persona(npc_id)
    cfg       = _load_f4ai_config()
    endpoint  = cfg.get("mossy_endpoint", "http://127.0.0.1:8765/f4ai/bridge")
    timeout   = float(cfg.get("mossy_timeout", 15.0))
    mod_ctx   = build_mod_context()

    full_context = f"{context} {mod_ctx}".strip() if mod_ctx else context

    mossy_payload = {
        "npc_id":           npc_name.lower().replace(" ", "_"),
        "npc_name":         npc_name,
        "npc_role":         _RACE_TO_ROLE.get(npc_race.lower(), "default"),
        "player_input":     f"[talking to {other_name}]",
        "dialogue_history": dialogue_history,
        "context":          f"{full_context} {behavior_hint}",
    }
    try:
        r = requests.post(endpoint, json=mossy_payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        text = (data.get("dialogue") or data.get("npc_response") or
                data.get("response") or data.get("text") or "")
        if text and str(text).strip():
            return str(text).strip()[:220]
    except Exception:
        pass

    # Ollama fallback
    preferred = ["llama3.1:8b", "llama3:8b", "mistral:7b", "phi4-mini", "phi3:mini", "tinyllama"]
    model = "llama3.1:8b"
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        if r.ok:
            available = [m["name"] for m in r.json().get("models", [])]
            model = next((m for m in preferred if any(m in a for a in available)), model)
    except Exception:
        pass

    system = (
        f"You are {npc_name}, a survivor in the post-apocalyptic Commonwealth of Fallout 4. "
        f"{persona} "
        f"{full_context} {behavior_hint} "
        "1-2 sentences. In character. Never mention AI."
    )
    messages = [{"role": "system", "content": system}]
    for d in (dialogue_history or []):
        role = "assistant" if d.get("speaker") == "npc" else "user"
        line = d.get("line", "")
        if line:
            messages.append({"role": role, "content": line})
    messages.append({"role": "user", "content": f"[{behavior_hint} Talk to {other_name}]"})

    try:
        r = requests.post(
            "http://127.0.0.1:11434/v1/chat/completions",
            json={"model": model, "messages": messages,
                  "max_tokens": 80, "temperature": 0.82, "stream": False},
            timeout=20,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()
        if text:
            return text[:220]
    except Exception:
        pass

    return None


_BEHAVIOR_HINTS = {
    "converse":  "Have a natural, casual conversation.",
    "greet":     "Greet them briefly.",
    "warn":      "Warn them about something dangerous.",
    "argue":     "Disagree about something.",
    "threaten":  "Make a thinly veiled threat.",
    "trade":     "Discuss trading or bartering.",
    "comfort":   "Offer comfort or support.",
}


def _handle_social_event(path: Path):
    """Read social_event.json from NPCDirector, generate two NPC lines, write social_directive.json.

    NPCDirector writes social_event.json with NPC pair + relationship context.
    Bridge generates line_a (NPC-A speaks) and line_b (NPC-B responds), writes
    social_directive.json with behavior + both lines.  NPCDirector consumes the
    directive on its next 45-second scan cycle and executes the conversation.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        path.unlink()
    except Exception as exc:
        print(f"[Bridge] Bad {path.name}: {exc}")
        return

    npc_a = data.get("npc_a", {})
    npc_b = data.get("npc_b", {})
    name_a, id_a = npc_a.get("name", "Settler"), npc_a.get("id", "0")
    name_b, id_b = npc_b.get("name", "Settler"), npc_b.get("id", "0")
    race_a  = npc_a.get("race", "Human")
    race_b  = npc_b.get("race", "Human")
    location    = data.get("location", "The Commonwealth")
    rel_score   = float(data.get("relationship", 0.0))
    rel_label   = data.get("relationship_label", "neutral")
    last_topic  = data.get("last_topic", "")
    weather     = data.get("weatherStr", "Clear")
    time_of_day = data.get("time_of_day", "")
    season      = data.get("season", "")

    print(f"[Bridge] Social — {name_a} ↔ {name_b} [{rel_label}] at {location}")

    # Pick behavior based on relationship score
    if rel_score <= -50.0:
        behavior, rel_delta = "threaten", -5.0
    elif rel_score <= -20.0:
        behavior, rel_delta = "argue", -2.0
    elif rel_score >= 60.0:
        behavior, rel_delta = random.choice(["converse", "comfort"]), 3.0
    else:
        behavior, rel_delta = "converse", 1.0

    hint = _BEHAVIOR_HINTS.get(behavior, "Have a natural conversation.")
    topic = _pick_topic(last_topic)

    ctx_parts = [f"Location: {location}."]
    if time_of_day:
        ctx_parts.append(f"Time: {time_of_day}.")
    if season:
        ctx_parts.append(f"Season: {season}.")
    if weather:
        ctx_parts.append(f"Weather: {weather}.")
    ctx_parts.append(f"Relationship with {name_b}: {rel_label}.")
    ctx_parts.append(f"Talking about: {topic}.")
    context = " ".join(ctx_parts)

    # Load each NPC's history from SQLite
    history_a = _get_dialogue_history_for_mossy(id_a)
    history_b = _get_dialogue_history_for_mossy(id_b)

    # Generate NPC-A's opening line
    line_a = _generate_npc_line(name_a, id_a, race_a, name_b, context, history_a, hint)
    if not line_a:
        print(f"[Bridge] Social — no AI response for {name_a}, skipping")
        return

    # Generate NPC-B's reply, with A's line as context
    ctx_b = context + f" {name_a} just said: \"{line_a}\""
    history_b_ctx = history_b + [{"speaker": "npc_other", "line": line_a}]
    line_b = _generate_npc_line(name_b, id_b, race_b, name_a, ctx_b, history_b_ctx, "Respond naturally.") or "..."

    # Write social_directive.json for NPCDirector to consume on next cycle
    directive = {
        "behavior":           behavior,
        "npc_a_id":           id_a,
        "npc_b_id":           id_b,
        "topic":              topic,
        "line_a":             line_a[:200],
        "line_b":             line_b[:200],
        "relationship_delta": rel_delta,
    }
    watch_dirs = [F4AI_DATA_DIR, _MO2_MOD_F4AI, FO4_GAME_PATH / "Data" / "F4AI"]
    for d in watch_dirs:
        out = d / "social_directive.json"
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(directive, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            print(f"[Bridge] Could not write social_directive.json to {d}: {exc}")

    # Persist both lines to SQLite so future conversations reference them
    record_dialogue(id_a, name_a, "npc", f"social_to_{name_b}", line_a)
    record_dialogue(id_b, name_b, "npc", f"social_to_{name_a}", line_b)
    record_npc_memory(id_a, name_a, 2, "ambient_conversation",
                      f"Said to {name_b}: {line_a[:60]}")
    record_npc_memory(id_b, name_b, 2, "ambient_conversation",
                      f"Replied to {name_a}: {line_b[:60]}")

    print(f"[Bridge] Social directive: {name_a}: {line_a[:60]} | {name_b}: {line_b[:60]}")


# ─────────────────────────────────────────────────────────────────────────────
# Ecosystem / Creature AI Handler
# ─────────────────────────────────────────────────────────────────────────────

# Shared cache so _build_full_context() can inject creature activity into NPC dialogue
_latest_ecosystem: dict = {}
_ecosystem_lock = threading.Lock()

# Per-species behavior profiles used to select creature_directive
_SPECIES_IS_PREDATOR = {
    "Deathclaw", "Yao Guai", "Radscorpion", "Mirelurk",
    "Fog Crawler", "Gulper", "Angler", "Stingwing", "Bloatfly",
}

# nocturnal predators hunt more aggressively at night
_NOCTURNAL = {"Radscorpion", "Bloatfly", "Stingwing"}

# apex predators prefer solitary territorial behavior; pack hunters go for "hunt"
_PACK_HUNTERS = {"Yao Guai", "Dog", "Mirelurk"}


def _write_creature_directive(directive: dict):
    _write_directive("creature_directive.json", directive)


def _write_eco_directive(directive: dict):
    _write_directive("ecosystem_directive.json", directive)


def _handle_ecosystem_event(path: Path):
    """Process ecosystem_event.json from EcosystemMonitor and write creature directives.

    Decision matrix (ecosystem_state → creature + ecosystem directives):
      predator_starving → desperate hunt + territorial_pressure
      overhunted        → aggressive hunt (daytime) or ambush (night)
      prey_boom         → relaxed ambush (predators well-fed) / prey scatter
      prey_dominant     → prey graze freely; if predators exist they ambush
      prey_abundant     → daytime patrol, nighttime ambush
      balanced          → natural variety: patrol/challenge/graze/herd
      winter_balanced   → elevated hunt pressure (lean season)
      empty             → no directive
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        path.unlink()
    except Exception as exc:
        print(f"[Bridge/Eco] Bad {path.name}: {exc}")
        return

    with _ecosystem_lock:
        global _latest_ecosystem
        _latest_ecosystem = data

    eco_region  = data.get("ecoRegion", "The Commonwealth")
    season      = data.get("season", "Summer")
    eco_state   = data.get("ecosystem_state", "balanced")
    territory   = data.get("territory_owner", "")
    pred_count  = int(data.get("predator_count", 0))
    prey_count  = int(data.get("prey_count", 0))
    species_raw = data.get("species", {})

    # Normalize species counts — JSON values may come as strings from Papyrus
    species_counts = {k: int(v) for k, v in species_raw.items()}

    # Pick the most-populated predator and prey species present
    predators = [s for s in _SPECIES_IS_PREDATOR if species_counts.get(s, 0) > 0]
    prey_list = [s for s in ("Brahmin", "Dog", "Radroach", "Bloodbug")
                 if species_counts.get(s, 0) > 0]

    dominant_pred = max(predators, key=lambda s: species_counts.get(s, 0)) if predators else (territory or "Radscorpion")
    dominant_prey = max(prey_list, key=lambda s: species_counts.get(s, 0)) if prey_list else "Brahmin"

    world    = _read_world_state()
    is_night = world.get("is_night", False)
    is_nocturnal_pred = dominant_pred in _NOCTURNAL

    creature_directive: dict | None = None
    eco_directive: dict | None = None

    if eco_state == "empty":
        pass  # No creatures to direct

    elif eco_state == "predator_starving":
        # No prey → predators hunt desperately, will enter settlement perimeters
        creature_directive = {
            "directive": "hunt",
            "species": dominant_pred,
            "intensity": 0.95,
        }
        eco_directive = {
            "directive": "territorial_pressure",
            "species": dominant_pred,
            "ecoRegion": eco_region,
            "target_ecoRegion": eco_region,
            "new_owner": dominant_pred,
        }

    elif eco_state == "overhunted":
        # Too many predators, prey getting wiped out — high-aggression hunting + prey scatter
        creature_directive = {
            "directive": "ambush" if is_night else "hunt",
            "species": dominant_pred,
            "intensity": 0.75,
        }
        eco_directive = {
            "directive": "migrate",
            "species": dominant_prey,
            "ecoRegion": eco_region,
            "target_ecoRegion": "The Commonwealth",
            "new_owner": dominant_pred,
        }

    elif eco_state in ("prey_boom", "prey_abundant"):
        # Prey population surging — predators well-fed and relaxed, prey graze
        if pred_count > 0:
            # Well-fed predators: daytime patrol territory, night ambush opportunistically
            creature_directive = {
                "directive": "ambush" if is_night else "patrol",
                "species": dominant_pred,
                "intensity": 0.3,
            }
        else:
            # No predators at all — prey graze/herd in peace
            creature_directive = {
                "directive": "herd" if dominant_prey == "Brahmin" else "graze",
                "species": dominant_prey,
                "intensity": 0.2,
            }
        eco_directive = {
            "directive": "prey_boom",
            "species": dominant_prey,
            "ecoRegion": eco_region,
            "target_ecoRegion": eco_region,
            "new_owner": territory or dominant_pred,
        }

    elif eco_state == "prey_dominant":
        # Lots of prey, no predators — herd grazes freely
        creature_directive = {
            "directive": "graze",
            "species": dominant_prey,
            "intensity": 0.2,
        }
        eco_directive = {
            "directive": "prey_boom",
            "species": dominant_prey,
            "ecoRegion": eco_region,
            "target_ecoRegion": eco_region,
            "new_owner": "",
        }

    elif eco_state == "winter_balanced":
        # Winter scarcity — predators must hunt harder than normal
        intensity = 0.7
        creature_directive = {
            "directive": "hunt" if is_night or is_nocturnal_pred else "patrol",
            "species": dominant_pred,
            "intensity": intensity,
        }
        eco_directive = {
            "directive": "territorial_pressure",
            "species": dominant_pred,
            "ecoRegion": eco_region,
            "target_ecoRegion": eco_region,
            "new_owner": dominant_pred,
        }

    else:  # "balanced" (default, spring, summer, fall normal ratios)
        if is_night:
            # Night: nocturnal hunters ambush, others patrol territory
            if is_nocturnal_pred:
                creature_directive = {
                    "directive": "ambush",
                    "species": dominant_pred,
                    "intensity": 0.6,
                }
            elif pred_count > 0:
                creature_directive = {
                    "directive": "patrol",
                    "species": dominant_pred,
                    "intensity": 0.4,
                }
            else:
                creature_directive = {
                    "directive": "graze",
                    "species": dominant_prey,
                    "intensity": 0.2,
                }
        else:
            # Daytime balanced — vary behavior to feel natural
            if pred_count > 0 and prey_count > 0:
                # Weighted random: mostly patrol + challenge, some graze
                behaviors = ["patrol", "challenge", "graze", "herd"]
                weights   = [0.45,     0.20,       0.20,    0.15]
                behavior  = random.choices(behaviors, weights=weights)[0]
                if behavior in ("patrol", "challenge"):
                    target = dominant_pred
                elif behavior == "herd":
                    target = dominant_prey
                else:
                    target = dominant_prey
                creature_directive = {
                    "directive": behavior,
                    "species": target,
                    "intensity": 0.45,
                }
            elif pred_count > 0:
                creature_directive = {
                    "directive": "patrol",
                    "species": dominant_pred,
                    "intensity": 0.4,
                }
            else:
                creature_directive = {
                    "directive": "graze",
                    "species": dominant_prey,
                    "intensity": 0.2,
                }

    # Write directives for Papyrus to consume
    if creature_directive:
        _write_creature_directive(creature_directive)

    if eco_directive:
        _write_eco_directive(eco_directive)

    cdir = creature_directive.get("directive", "none") if creature_directive else "none"
    print(f"[Bridge/Eco] {eco_region} | {eco_state} | pred={pred_count}({dominant_pred})"
          f" prey={prey_count}({dominant_prey}) | night={is_night} → {cdir}")


# ─────────────────────────────────────────────────────────────────────────────
# Generic Directive Writer
# ─────────────────────────────────────────────────────────────────────────────

def _write_directive(filename: str, payload: dict):
    """Write a directive JSON file to all watched directories."""
    text = json.dumps(payload, ensure_ascii=False)
    watch_dirs = [F4AI_DATA_DIR, _MO2_MOD_F4AI, FO4_GAME_PATH / "Data" / "F4AI"]
    for d in watch_dirs:
        out = d / filename
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
        except Exception as exc:
            print(f"[Bridge] Could not write {filename} to {d}: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Combat Event Handler
# ─────────────────────────────────────────────────────────────────────────────

def _handle_combat_event(path: Path):
    """Read combat_event.json from CombatMonitor, write combat_directive.json.

    Rule-based decisions (no AI needed — frequency too high for LLM calls):
      hp < flee_threshold → flee
      hp < 0.4 and event=start → take_cover
      hp recovering (update, not start) → regroup
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        path.unlink()
    except Exception as exc:
        print(f"[Bridge/Combat] Bad {path.name}: {exc}")
        return

    event_type   = data.get("combat_event", "update")
    npc_id       = data.get("npc_id", "")
    hp_pct       = float(data.get("hp_pct", 1.0))
    flee_thr     = float(data.get("flee_threshold", 0.25))
    prefers_cover = bool(data.get("prefers_cover", False))

    if event_type == "end" or hp_pct < 0:
        return  # no directive on combat end

    directive: str | None = None

    if hp_pct <= flee_thr:
        directive = "flee"
    elif hp_pct < 0.4 and event_type == "start":
        directive = "take_cover"
    elif hp_pct < 0.5 and prefers_cover:
        directive = "take_cover"
    elif hp_pct >= 0.7 and event_type == "update":
        directive = "regroup"

    if directive:
        _write_directive("combat_directive.json", {
            "npc_id": npc_id,
            "directive": directive,
            "learned_flee_threshold": flee_thr,
            "prefers_cover": prefers_cover,
            "new_target": "",
        })
        print(f"[Bridge/Combat] {npc_id} hp={hp_pct:.0%} → {directive}")


# ─────────────────────────────────────────────────────────────────────────────
# Settlement Attack Handler
# ─────────────────────────────────────────────────────────────────────────────

def _handle_settlement_event(path: Path):
    """Read settlement_event.json from SettlementMonitor, write settlement_directive.json.

    Decision matrix:
      defense < 20  → call_aid + raise_alarm (desperate)
      defense < 50  → rally_defenders (manageable)
      defense >= 50 → prioritize_gate (well-defended, just tighten up)
      triangle AND under attack → always raise_alarm
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        path.unlink()
    except Exception as exc:
        print(f"[Bridge/Settlement] Bad {path.name}: {exc}")
        return

    ws_id      = int(data.get("settlement_id", 0))
    ws_name    = data.get("settlement_name", "Settlement")
    defense    = int(data.get("defense", 0))
    population = int(data.get("population", 0))
    is_triangle = bool(data.get("is_triangle", False))

    if defense < 20:
        directive = "call_aid"
        if is_triangle:
            directive = "raise_alarm"
    elif defense < 50:
        directive = "rally_defenders"
    else:
        directive = "prioritize_gate"

    _write_directive("settlement_directive.json", {
        "directive": directive,
        "settlement_id": ws_id,
        "aid_from": ws_name,
    })
    print(f"[Bridge/Settlement] {ws_name} (defense={defense}, triangle={is_triangle}) → {directive}")


# ─────────────────────────────────────────────────────────────────────────────
# Minuteman Network Attack Handler
# ─────────────────────────────────────────────────────────────────────────────

def _handle_network_event(path: Path):
    """Read network_event.json from MinutemanNetwork, write network_directive.json.

    Decision matrix:
      is_triangle → fortify + advisory warning player
      defense < 30 → fortify target
      connections exist → reroute_supply_lines to spread load
      else → rebuild_network_map
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        path.unlink()
    except Exception as exc:
        print(f"[Bridge/Network] Bad {path.name}: {exc}")
        return

    attacked_id      = int(data.get("attacked_id", 0))
    attacked_name    = data.get("attacked_name", "Settlement")
    attacked_defense = int(data.get("attacked_defense", 0))
    is_triangle      = bool(data.get("is_triangle", False))
    connections      = data.get("connected_settlements", "")
    network_size     = int(data.get("total_network_size", 0))

    if is_triangle:
        advisory = (
            f"Triangle alert: {attacked_name} is under attack! "
            "Sanctuary, Red Rocket, and Abernathy Farm are mobilizing."
        )
        _write_directive("network_directive.json", {
            "directive": "fortify",
            "target_settlement_id": attacked_id,
            "player_advisory": advisory,
            "from_id": "",
            "to_id": "",
        })
    elif attacked_defense < 30 and connections:
        # Pull in a neighbor settlement for defense
        first_connection = connections.split(",")[0].strip()
        _write_directive("network_directive.json", {
            "directive": "reroute_supply_lines",
            "target_settlement_id": attacked_id,
            "player_advisory": f"{attacked_name} is critically under-defended — rerouting supply lines.",
            "from_id": first_connection,
            "to_id": str(attacked_id),
        })
    elif attacked_defense < 50:
        _write_directive("network_directive.json", {
            "directive": "fortify",
            "target_settlement_id": attacked_id,
            "player_advisory": f"Reinforce {attacked_name} — defenses are low.",
            "from_id": "",
            "to_id": "",
        })
    else:
        _write_directive("network_directive.json", {
            "directive": "rebuild_network_map",
            "target_settlement_id": attacked_id,
            "player_advisory": "",
            "from_id": "",
            "to_id": "",
        })

    print(f"[Bridge/Network] {attacked_name} attacked (defense={attacked_defense}, triangle={is_triangle})")


# ─────────────────────────────────────────────────────────────────────────────
# Training Feedback Handler
# ─────────────────────────────────────────────────────────────────────────────

def _handle_training_feedback(path: Path):
    """Read training_feedback.json (like/dislike from FeedbackMonitor) and record to SQLite."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        path.unlink()
    except Exception as exc:
        print(f"[Bridge/Feedback] Bad {path.name}: {exc}")
        return

    npc_name = data.get("npc_name", "Unknown")
    score    = int(data.get("reward_score", 0))
    label    = "👍 liked" if score > 0 else "👎 disliked"

    try:
        record_dialogue(
            npc_id="feedback", npc_name=npc_name,
            speaker="feedback", topic=f"reward_{score}",
            line=f"Player {label} {npc_name}'s response",
        )
    except Exception as exc:
        print(f"[Bridge/Feedback] SQLite error (non-fatal): {exc}")

    print(f"[Bridge/Feedback] {npc_name}: {label} (score={score})")


# ─────────────────────────────────────────────────────────────────────────────
# World Event Handler
# ─────────────────────────────────────────────────────────────────────────────

def _handle_world_event(path: Path):
    """WorldMonitor writes world_event.json every 30s as a push notification.
    The bridge already reads world_state.json directly on each AI call, so this
    event is informational — just delete it to prevent file accumulation.
    """
    try:
        path.unlink()
    except Exception:
        pass


def watch_bridge_input():
    """Poll for per-NPC bridge_input_<id>.json files; dispatch each in its own thread."""
    print(f"[Bridge] Primary watch path: {F4AI_DATA_DIR}")
    print(f"[Bridge] Also checking: {[str(p) for p in _BRIDGE_INPUT_CANDIDATES[1:]]}")

    # Watch dirs: Overwrites, mod folder, bare game Data
    watch_dirs = [
        F4AI_DATA_DIR,
        _MO2_MOD_F4AI,
        FO4_GAME_PATH / "Data" / "F4AI",
    ]

    while True:
        try:
            for watch_dir in watch_dirs:
                if not watch_dir.exists():
                    continue
                # Per-NPC files: bridge_input_<formID>.json
                for candidate in list(watch_dir.glob("bridge_input_*.json")):
                    t = threading.Thread(
                        target=_handle_npc_request, args=(candidate,), daemon=True
                    )
                    t.start()
                # Legacy single file (bridge_input.json) — handles old saves / non-PTT triggers
                legacy = watch_dir / "bridge_input.json"
                if legacy.exists():
                    t = threading.Thread(
                        target=_handle_npc_request, args=(legacy,), daemon=True
                    )
                    t.start()
                # NPC-to-NPC social events from F4AI_NPCDirector
                social = watch_dir / "social_event.json"
                if social.exists():
                    t = threading.Thread(
                        target=_handle_social_event, args=(social,), daemon=True
                    )
                    t.start()
                # Creature ecosystem events from F4AI_EcosystemMonitor
                eco_event = watch_dir / "ecosystem_event.json"
                if eco_event.exists():
                    t = threading.Thread(
                        target=_handle_ecosystem_event, args=(eco_event,), daemon=True
                    )
                    t.start()
                # NPC combat state from F4AI_CombatMonitor
                combat_event = watch_dir / "combat_event.json"
                if combat_event.exists():
                    t = threading.Thread(
                        target=_handle_combat_event, args=(combat_event,), daemon=True
                    )
                    t.start()
                # Settlement attack from F4AI_SettlementMonitor
                settle_event = watch_dir / "settlement_event.json"
                if settle_event.exists():
                    t = threading.Thread(
                        target=_handle_settlement_event, args=(settle_event,), daemon=True
                    )
                    t.start()
                # Minuteman network attack from F4AI_MinutemanNetwork
                net_event = watch_dir / "network_event.json"
                if net_event.exists():
                    t = threading.Thread(
                        target=_handle_network_event, args=(net_event,), daemon=True
                    )
                    t.start()
                # Player like/dislike feedback from F4AI_FeedbackMonitor
                feedback = watch_dir / "training_feedback.json"
                if feedback.exists():
                    t = threading.Thread(
                        target=_handle_training_feedback, args=(feedback,), daemon=True
                    )
                    t.start()
                # WorldMonitor push events (informational, just clean up)
                world_ev = watch_dir / "world_event.json"
                if world_ev.exists():
                    threading.Thread(
                        target=_handle_world_event, args=(world_ev,), daemon=True
                    ).start()
        except Exception as exc:
            print(f"[Bridge] Input watcher error: {exc}")
        time.sleep(0.25)

def watch_papyrus_log():
    """Tail Papyrus.0.log in a background thread."""
    print(f"[Bridge] Watching log: {PAPYRUS_LOG}")
    last_inode = None
    file_pos   = 0

    while True:
        try:
            if not PAPYRUS_LOG.exists():
                time.sleep(2)
                _status["game_running"] = False
                continue

            current_inode = PAPYRUS_LOG.stat().st_ino
            if current_inode != last_inode:
                # File rotated or first open
                last_inode = current_inode
                file_pos   = 0
                print("[Bridge] Log file opened/rotated")
                _status["game_running"] = True

            with open(PAPYRUS_LOG, "r", encoding="utf-8", errors="replace") as f:
                f.seek(file_pos)
                for line in f:
                    parse_log_line(line)
                file_pos = f.tell()

        except Exception as e:
            print(f"[Bridge] Log watch error: {e}")

        time.sleep(0.5)

# ─────────────────────────────────────────────────────────────────────────────
# HTTP API Server
# ─────────────────────────────────────────────────────────────────────────────

class BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress HTTP logs — Mossy handles display

    def send_json(self, data: dict, code: int = 200):
        body = json.dumps(data, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        params = parse_qs(parsed.query)

        # ── Status ──────────────────────────────────────────────────────────
        if path == "/status":
            self.send_json({**_status, "connected": True})

        # ── Log stream (last N lines) ────────────────────────────────────────
        elif path == "/log":
            n = int(params.get("n", ["50"])[0])
            with _log_lock:
                self.send_json({"lines": _log_buffer[-n:]})

        # ── NPC Memory: get all ──────────────────────────────────────────────
        elif path == "/memory/npcs":
            self.send_json({"npcs": get_all_npcs()})

        # ── NPC Memory: get single ───────────────────────────────────────────
        elif path == "/memory/npc":
            npc_id = params.get("id", [""])[0]
            if npc_id:
                self.send_json(get_npc_memory(npc_id))
            else:
                self.send_json({"error": "npc_id required"}, 400)

        # ── Local AI Engine install/run status (used by Mossy UI) ──────────
        elif path == "/engine/status":
            self.send_json(get_engine_status())

        # ── Pending game request (Mossy polls this to pick up AI work) ────────
        elif path == "/request/pending":
            with _pending_lock:
                if _pending_request and not _pending_request["responded"]:
                    self.send_json({"pending": True, **_pending_request})
                else:
                    self.send_json({"pending": False})

        # ── Ping ────────────────────────────────────────────────────────────
        elif path == "/ping":
            self.send_json({"pong": True, "version": BRIDGE_VERSION})

        else:
            self.send_json({"error": "Unknown endpoint"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length)) if length else {}

        # ── Record memory event from external source (Mossy AI analysis) ────
        if path == "/memory/record":
            npc_id    = body.get("npc_id", "")
            npc_name  = body.get("npc_name", "Unknown")
            event_code= int(body.get("event_code", 0))
            detail    = body.get("detail", "")
            if npc_id:
                record_npc_memory(npc_id, npc_name, event_code, detail=detail)
                self.send_json({"ok": True})
            else:
                self.send_json({"error": "npc_id required"}, 400)

        # ── Record dialogue from Mossy ────────────────────────────────────────
        elif path == "/memory/dialogue":
            record_dialogue(
                npc_id  = body.get("npc_id", ""),
                npc_name= body.get("npc_name", "Unknown"),
                speaker = body.get("speaker", "npc"),
                topic   = body.get("topic", ""),
                line    = body.get("line", ""),
            )
            self.send_json({"ok": True})

        # ── Update NPC affinity ───────────────────────────────────────────────
        elif path == "/memory/affinity":
            update_npc_affinity(
                npc_id   = body.get("npc_id", ""),
                affinity = float(body.get("affinity", 0.0)),
                emotion  = int(body.get("emotion", 0)),
            )
            self.send_json({"ok": True})

        # ── Get NPC context for AI generation (Mossy sends this to its LLM) ──
        elif path == "/memory/context":
            npc_id = body.get("npc_id", "")
            mem    = get_npc_memory(npc_id)
            if mem.get("found"):
                # Build a natural language context string Mossy's AI can use
                ctx  = f"NPC: {mem['identity']['npc_name']}\n"
                ctx += f"Race: {mem['identity'].get('npc_race','Unknown')}\n"
                ctx += f"Faction: {mem['identity'].get('npc_faction','Unknown')}\n"
                ctx += f"Affinity: {mem['identity']['affinity']:.0f}\n"
                ctx += f"Relationship: {(mem.get('relationship') or {}).get('relationship','stranger')}\n"
                ctx += f"Total Encounters: {(mem.get('relationship') or {}).get('total_encounters', 0)}\n\n"
                ctx += "Recent Memories:\n"
                for m in mem.get("memories", [])[:5]:
                    ctx += f"  - [{m['real_time'][:10]}] {m['event_label'] or 'Event ' + str(m['event_code'])}: {m['detail']}\n"
                ctx += "\nRecent Dialogue:\n"
                for d in reversed(mem.get("dialogue", [])[:6]):
                    ctx += f"  {d['speaker'].upper()}: {d['line']}\n"
                self.send_json({"context": ctx, "raw": mem})
            else:
                self.send_json({"context": f"No memory found for NPC {npc_id}.", "raw": mem})

        # ── NPC dialogue generation ───────────────────────────────────────────
        elif path == "/generate":
            npc_id       = body.get("npc_id", "")
            player_input = body.get("player_input", body.get("prompt", ""))
            if not npc_id or not player_input:
                self.send_json({"error": "npc_id and player_input required"}, 400)
                return
            result = generate_npc_dialogue(npc_id, player_input)
            if result["ok"]:
                # Auto-record the generated line into dialogue history
                mem = get_npc_memory(npc_id)
                npc_name = mem["identity"]["npc_name"] if mem.get("found") else npc_id
                record_dialogue(npc_id, npc_name, "npc", "", result["text"])
                record_dialogue(npc_id, npc_name, "player", "", player_input)
            self.send_json(result, 200 if result["ok"] else 500)

        # ── General text generation (non-NPC, used by Mossy chat) ────────────
        elif path == "/generate/text":
            prompt    = body.get("prompt", "")
            system    = body.get("system", "You are Mossy, an AI assistant for Fallout 4 modding.")
            max_tok   = int(body.get("max_tokens", 256))
            if not prompt:
                self.send_json({"error": "prompt required"}, 400)
                return
            messages = [
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ]
            llm = _load_llm()
            if llm is not None:
                try:
                    result = llm.create_chat_completion(
                        messages=messages, max_tokens=max_tok,
                        temperature=0.7, top_p=0.95,
                    )
                    text = result["choices"][0]["message"]["content"].strip()
                    self.send_json({"ok": True, "text": text, "engine": "llama-cpp-python"})
                    return
                except Exception as exc:
                    self.send_json({"ok": False, "error": str(exc)}, 500)
                    return
            self.send_json({"ok": False, "error": "llama-cpp-python not available"}, 503)

        # ── Mossy sends the NPC reply back; bridge writes text_out.txt ─────────
        elif path == "/request/respond":
            text = body.get("text", "")
            if not text:
                self.send_json({"error": "text required"}, 400)
                return
            _write_text_out(text)
            with _pending_lock:
                if _pending_request:
                    _pending_request["responded"] = True
            print(f"[Bridge] Mossy responded: {text[:80]}")
            self.send_json({"ok": True})

        # ── LLM engine status ─────────────────────────────────────────────────
        elif path == "/llm/status":
            self.send_json({
                "llama_cpp_available": _LLAMA_AVAILABLE,
                "model_loaded":        _llm is not None,
                "koboldcpp_running":   _kobold_running(),
                "model_candidates":    [str(p) for p in _MODEL_CANDIDATES],
                "model_found":         next((str(p) for p in _MODEL_CANDIDATES if p.exists()), None),
            })

        # ── Start KoboldCPP engine (called by Mossy after auto-download) ────
        elif path == "/engine/start":
            result = start_kobold_engine()
            self.send_json(result, 200 if result["ok"] else 500)

        else:
            self.send_json({"error": "Unknown endpoint"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def _startup_cleanup():
    """Delete stale text_out*.txt and bridge_input*.json from previous sessions."""
    watch_dirs = [F4AI_DATA_DIR, _MO2_MOD_F4AI, FO4_GAME_PATH / "Data" / "F4AI"]
    for d in watch_dirs:
        if not d.exists():
            continue
        for pattern in (
            "text_out*.txt", "bridge_input*.json",
            "social_event.json",    "social_directive.json",
            "ecosystem_event.json", "ecosystem_directive.json",
            "creature_directive.json",
            "combat_event.json",    "combat_directive.json",
            "settlement_event.json", "settlement_directive.json",
            "network_event.json",   "network_directive.json",
            "training_feedback.json",
            "world_event.json",
            "vision_trigger.json",
        ):
            for stale in d.glob(pattern):
                try:
                    stale.unlink()
                    print(f"[Bridge] Cleaned up stale {stale.name}")
                except Exception as exc:
                    print(f"[Bridge] Could not remove {stale}: {exc}")

def _preload_llm_background():
    """Warm up TinyLlama in a background thread so the first game request is fast."""
    if not _LLAMA_AVAILABLE:
        return
    print("[Bridge/LLM] Pre-loading TinyLlama in background…")
    _load_llm()   # populates the _llm cache; subsequent calls return instantly

def main():
    print("=" * 60)
    print(f"  Mossy FO4 Advanced AI Bridge v{BRIDGE_VERSION}")
    print("=" * 60)
    print(f"[Bridge] F4AI data dir: {F4AI_DATA_DIR}")
    print(f"[Bridge] bridge_input : {BRIDGE_INPUT_PATH}")
    print(f"[Bridge] text_out     : {TEXT_OUT_PATH}")

    # Init memory database
    init_memory_db()

    # Scan load order at startup so mod context is ready before first NPC request
    build_mod_context()

    # Remove any leftover text_out.txt from the previous session
    _startup_cleanup()

    # Pre-load TinyLlama so the first in-game request doesn't wait on model load
    preload_thread = threading.Thread(target=_preload_llm_background, daemon=True)
    preload_thread.start()

    # Start log watcher in background
    log_thread = threading.Thread(target=watch_papyrus_log, daemon=True)
    log_thread.start()

    # Start bridge_input.json watcher in background
    input_thread = threading.Thread(target=watch_bridge_input, daemon=True)
    input_thread.start()

    # Start HTTP server
    server = HTTPServer(("localhost", BRIDGE_PORT), BridgeHandler)
    print(f"[Bridge] Listening on localhost:{BRIDGE_PORT}")
    print(f"[Bridge] FO4 game path: {FO4_GAME_PATH}")
    print(f"[Bridge] Papyrus log: {PAPYRUS_LOG}")
    print(f"[Bridge] Memory DB:   {MEMORY_DB_PATH}")
    print(f"[Bridge] Press Ctrl+C to stop\n")

    _status["connected"] = True

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Bridge] Shutting down...")
        server.shutdown()

if __name__ == "__main__":
    main()
