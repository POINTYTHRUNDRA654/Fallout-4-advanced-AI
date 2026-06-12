"""
build_nexus_release.py
Builds the MO2/Nexus FOMOD zip from staged files.

Usage:
    python tools/build_nexus_release.py [--channel alpha|release]

Output:
    dist/nexus/Fallout4_AdvancedAI_<channel>_<date>.zip
"""

import argparse
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT        = Path(__file__).resolve().parent.parent
STAGING     = ROOT / "release_staging" / "core"
MOD_DIR     = ROOT / "mod"
BRIDGE_DIR  = ROOT / "bridge"
SRC_DIR     = ROOT / "src"
PACKAGING   = ROOT / "packaging" / "nexus" / "core-template"
DIST_DIR    = ROOT / "dist" / "nexus"

# Files that must exist in staging before we can build
REQUIRED_STAGING = [
    "Data/F4AI/config.json",
    "Data/F4AI/MOSSY_LAUNCH.bat",
    "Data/F4AI/MOSSY_CHECK.bat",
]

# Optional staging files (warn if missing, don't fail)
OPTIONAL_STAGING = [
    "Data/F4AI/Fallout4_AI_Engine.exe",   # compiled on Windows via build_engine_executable.py
    "Data/F4AI/koboldcpp.exe",
    "Data/F4AI/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
]


def check_staging():
    missing_required = []
    missing_optional = []
    for rel in REQUIRED_STAGING:
        if not (STAGING / rel).exists():
            missing_required.append(rel)
    for rel in OPTIONAL_STAGING:
        if not (STAGING / rel).exists():
            missing_optional.append(rel)
    if missing_optional:
        for f in missing_optional:
            print(f"[WARN] Optional staging file missing: {f}")
    if missing_required:
        for f in missing_required:
            print(f"[ERROR] Required staging file missing: {f}")
        return False
    return True


def sync_latest_files():
    """Copy the latest src/ and packaging/ files into staging before zipping."""
    STAGING_F4AI = STAGING / "Data" / "F4AI"
    STAGING_F4AI.mkdir(parents=True, exist_ok=True)

    # config.json
    src_cfg = SRC_DIR / "config.json"
    if src_cfg.exists():
        shutil.copy2(src_cfg, STAGING_F4AI / "config.json")
        print(f"[SYNC] config.json")

    # MOSSY_LAUNCH.bat + MOSSY_CHECK.bat from packaging template
    for bat in ["MOSSY_LAUNCH.bat", "MOSSY_CHECK.bat"]:
        src = PACKAGING / "Data" / "F4AI" / bat
        if src.exists():
            shutil.copy2(src, STAGING_F4AI / bat)
            print(f"[SYNC] {bat}")


def build_zip(channel: str) -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    date_str  = datetime.now().strftime("%Y%m%d")
    zip_name  = f"Fallout4_AdvancedAI_{channel}_{date_str}.zip"
    zip_path  = DIST_DIR / zip_name

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:

        # ── fomod/ metadata ──────────────────────────────────────────────────
        for f in (MOD_DIR / "fomod").iterdir():
            if f.is_file():
                zf.write(f, f"fomod/{f.name}")
                print(f"  [fomod] {f.name}")

        # ── Core: staging files (scripts, config, bats, exe if present) ─────
        for f in STAGING.rglob("*"):
            if f.is_file():
                rel = f.relative_to(STAGING)
                zf.write(f, f"Core/{rel}")
                print(f"  [Core] {rel}")

        # ── Core: Papyrus scripts from mod/ ──────────────────────────────────
        scripts_src = MOD_DIR / "Data" / "Scripts" / "Source"
        if scripts_src.exists():
            for f in scripts_src.rglob("*.psc"):
                rel = f.relative_to(MOD_DIR)
                zf.write(f, f"Core/{rel}")
                print(f"  [Core/scripts] {f.name}")

        # ── MCM_Helper: MCM config ───────────────────────────────────────────
        mcm_src = MOD_DIR / "Data" / "MCM"
        if mcm_src.exists():
            for f in mcm_src.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(MOD_DIR)
                    zf.write(f, f"MCM_Helper/{rel}")
                    print(f"  [MCM_Helper] {rel}")

        # ── MossyBridge: bridge server + launcher ────────────────────────────
        for fname in ["mossy_fo4_bridge.py", "start_fo4_bridge.bat"]:
            f = BRIDGE_DIR / fname
            if f.exists():
                zf.write(f, f"MossyBridge/{fname}")
                print(f"  [MossyBridge] {fname}")

    return zip_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", default="alpha", choices=["alpha", "release"])
    args = parser.parse_args()

    print(f"\n[Build] Channel: {args.channel}")
    print(f"[Build] Staging: {STAGING}")
    print()

    print("[Build] Syncing latest files into staging...")
    sync_latest_files()
    print()

    print("[Build] Checking staging directory...")
    if not check_staging():
        print("\n[ERROR] Staging check failed. Aborting.")
        sys.exit(1)
    print("[OK] Staging check passed.")
    print()

    print("[Build] Building FOMOD zip...")
    zip_path = build_zip(args.channel)
    size_mb  = zip_path.stat().st_size / (1024 * 1024)
    print()
    print(f"[OK] Built: {zip_path}")
    print(f"[OK] Size:  {size_mb:.1f} MB")
    print()


if __name__ == "__main__":
    main()
