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
MEMORY_DB_PATH  = DOCUMENTS_PATH / "AdvancedAI_Memory.db"

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

def main():
    print("=" * 60)
    print(f"  Mossy FO4 Advanced AI Bridge v{BRIDGE_VERSION}")
    print("=" * 60)

    # Init memory database
    init_memory_db()

    # Start log watcher in background
    log_thread = threading.Thread(target=watch_papyrus_log, daemon=True)
    log_thread.start()

    # Start HTTP server
    server = HTTPServer(("localhost", BRIDGE_PORT), BridgeHandler)
    print(f"[Bridge] Listening on localhost:{BRIDGE_PORT}")
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
