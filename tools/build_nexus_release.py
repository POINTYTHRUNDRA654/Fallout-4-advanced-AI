#!/usr/bin/env python3
"""Build Nexus-ready Fallout 4 release archives with FOMOD structure."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


REQUIRED_CORE_FILES = [
    "Data/F4AI_Core.esp",
    "Data/Scripts/F4AI_QueueManager.pex",
    "Data/Scripts/F4AI_FeedbackMonitor.pex",
    "Data/Scripts/F4AI_PushToTalkTrigger.pex",
    "Data/Scripts/F4AI_VisionWidgetManager.pex",
    "Data/Scripts/F4AI_InterNpcManager.pex",
    "Data/F4AI/Fallout4_AI_Engine.exe",
    "Data/F4AI/config.json",
    "Data/F4AI/en_US-lessac-medium.onnx",
    "Data/F4AI/en_US-lessac-medium.onnx.json",
    "Data/F4AI/Launch_F4AI_Bridge.bat",
    "Data/F4AI/FIRST_RUN.txt",
    "Data/F4AI/NEXUS_TROUBLESHOOTING.txt",
]

REQUIRED_CONFIG_KEYS = ["ai_temperature", "enable_memory", "speech_speed"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Nexus release archives.")
    parser.add_argument("--version", required=True, help="Version tag, e.g. 0.1.0")
    parser.add_argument(
        "--release-name",
        default="F4AI_Advanced_System",
        help="Base archive name prefix.",
    )
    parser.add_argument(
        "--staging-dir",
        default="release_staging",
        help="Directory containing core/ staging content.",
    )
    parser.add_argument(
        "--output-dir",
        default="dist/nexus",
        help="Output directory for built zip archives.",
    )
    return parser.parse_args()


def copy_tree(src: Path, dest: Path) -> None:
    if not src.exists():
        return
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        target = dest / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def ensure_required_files(root: Path) -> None:
    missing = [item for item in REQUIRED_CORE_FILES if not (root / item).exists()]
    if missing:
        message = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(f"Missing required core files:\n{message}")

    config_path = root / "Data/F4AI/config.json"
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    for key in REQUIRED_CONFIG_KEYS:
        if key not in config:
            raise ValueError(f"{config_path} is missing required key: {key}")


def make_zip(source_dir: Path, destination_zip: Path) -> None:
    destination_zip.parent.mkdir(parents=True, exist_ok=True)
    archive_base = destination_zip.with_suffix("")
    shutil.make_archive(str(archive_base), "zip", root_dir=str(source_dir))


def build_release(repo_root: Path, args: argparse.Namespace) -> Path:
    staging_dir = (repo_root / args.staging_dir).resolve()
    output_dir = (repo_root / args.output_dir).resolve()
    work_dir = output_dir / f"_work_{args.version}"

    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    package_root = work_dir / f"{args.release_name}_v{args.version}"
    package_root.mkdir(parents=True, exist_ok=True)

    fomod_src = repo_root / "packaging/nexus/fomod"
    core_template_src = repo_root / "packaging/nexus/core-template"

    copy_tree(fomod_src, package_root / "fomod")

    core_dst = package_root / "00 Core"
    copy_tree(core_template_src, core_dst)

    staged_core = staging_dir / "core"
    if not staged_core.exists():
        raise FileNotFoundError(
            f"Staging core directory not found: {staged_core}\n"
            "Create it and place runtime/plugin/script assets there before building."
        )
    copy_tree(staged_core, core_dst)

    ensure_required_files(core_dst)

    core_archive = output_dir / f"{args.release_name}_v{args.version}_Core_FOMOD.zip"
    make_zip(package_root, core_archive)

    return core_archive


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    try:
        artifact = build_release(repo_root, args)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"[release-builder] ERROR: {exc}")
        return 1

    print("[release-builder] Build complete:")
    print(f"  - {artifact}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
