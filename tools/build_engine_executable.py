#!/usr/bin/env python3
"""Build Fallout4_AI_Engine.exe from src/main.py using PyInstaller.

Part of Mossy Industries - Advancing AI in Gaming
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def check_pyinstaller() -> bool:
    """Check if PyInstaller is installed."""
    try:
        import PyInstaller
        return True
    except ImportError:
        return False


def install_pyinstaller() -> bool:
    """Install PyInstaller via pip."""
    print("[build-engine] Installing PyInstaller...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        return True
    except subprocess.CalledProcessError:
        return False


def build_executable(repo_root: Path) -> Path | None:
    """Build the executable using PyInstaller."""
    src_main = repo_root / "src/main.py"
    if not src_main.exists():
        print(f"[build-engine] ERROR: {src_main} not found.")
        return None

    dist_dir = repo_root / "build_output"
    work_dir = repo_root / "build_temp"

    # Clean previous builds
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if work_dir.exists():
        shutil.rmtree(work_dir)

    print("[build-engine] Building Fallout4_AI_Engine.exe...")
    print(f"[build-engine] Source: {src_main}")
    print(f"[build-engine] Output: {dist_dir}")

    # PyInstaller command
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--onefile",                          # Single executable
        "--noconsole",                        # No console window (change to --console for debugging)
        "--name", "Fallout4_AI_Engine",       # Output name
        "--hidden-import", "tts",             # Explicitly include tts module
        "--hidden-import", "scipy.io.wavfile", # Explicitly include scipy.io.wavfile
        "--distpath", str(dist_dir),          # Output directory
        "--workpath", str(work_dir),          # Work directory
        "--specpath", str(work_dir),          # Spec file location
        "--clean",                            # Clean cache
        str(src_main)
    ]

    try:
        subprocess.check_call(cmd)
        exe_path = dist_dir / "Fallout4_AI_Engine.exe"
        if exe_path.exists():
            print(f"[build-engine] ✅ Build successful: {exe_path}")
            return exe_path
        else:
            print("[build-engine] ❌ Build completed but executable not found.")
            return None
    except subprocess.CalledProcessError as exc:
        print(f"[build-engine] ❌ Build failed: {exc}")
        return None


def copy_to_staging(exe_path: Path, repo_root: Path) -> bool:
    """Copy built executable to staging directory."""
    staging_target = repo_root / "release_staging/core/Data/F4AI/Fallout4_AI_Engine.exe"
    staging_target.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy2(exe_path, staging_target)
        print(f"[build-engine] ✅ Copied to staging: {staging_target}")
        return True
    except OSError as exc:
        print(f"[build-engine] ❌ Failed to copy to staging: {exc}")
        return False


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]

    print("[build-engine] Fallout4_AI_Engine.exe Builder")
    print("=" * 60)

    # Check PyInstaller
    if not check_pyinstaller():
        print("[build-engine] PyInstaller not found.")
        response = input("[build-engine] Install PyInstaller now? (y/n): ").strip().lower()
        if response == "y":
            if not install_pyinstaller():
                print("[build-engine] ❌ Failed to install PyInstaller.")
                return 1
        else:
            print("[build-engine] ❌ PyInstaller required. Install with: pip install pyinstaller")
            return 1

    # Build executable
    exe_path = build_executable(repo_root)
    if not exe_path:
        return 1

    # Copy to staging
    if not copy_to_staging(exe_path, repo_root):
        print("[build-engine] ⚠️ Built successfully but not copied to staging.")
        print(f"[build-engine] Manual copy: {exe_path}")
        print(f"[build-engine] Target: release_staging/core/Data/F4AI/")
        return 0

    print("=" * 60)
    print("[build-engine] ✅ Build complete and staged for release!")
    print(f"[build-engine] Executable size: {exe_path.stat().st_size / (1024*1024):.2f} MB")

    return 0


if __name__ == "__main__":
    sys.exit(main())
