#!/usr/bin/env python3
"""Build Nexus-ready Fallout 4 release archives with FOMOD structure.

Part of Mossy Industries - Advancing AI in Gaming
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


REQUIRED_CORE_FILES = [
    "Data/F4AI_Core.esp",
    "Data/Scripts/F4AI_QueueManager.pex",
    "Data/Scripts/F4AI_FeedbackMonitor.pex",
    "Data/Scripts/F4AI_PushToTalkTrigger.pex",
    "Data/Scripts/F4AI_VisionWidgetManager.pex",
    "Data/Scripts/F4AI_InterNpcManager.pex",
    "Data/F4AI/Fallout4_AI_Engine.exe",
    "Data/F4AI/piper.exe",
    "Data/F4AI/models/tinyllama-1.1b-chat.gguf",
    "Data/F4AI/runtime/koboldcpp.exe",
    "Data/F4AI/runtime/koboldcpp_nocuda.dll",
    "Data/F4AI/AUTO_START.bat",
    "Data/F4AI/config.json",
    "Data/F4AI/en_US-lessac-medium.onnx",
    "Data/F4AI/en_US-lessac-medium.onnx.json",
    "Data/F4AI/Launch_F4AI_Bridge.bat",
    "Data/F4AI/FIRST_RUN.txt",
    "Data/F4AI/NEXUS_TROUBLESHOOTING.txt",
    "Data/F4AI/release_manifest.json",
]

REQUIRED_CONFIG_KEYS = [
    "ai_temperature",
    "enable_memory",
    "speech_speed",
    "enable_mossy_bridge",
    "mossy_endpoint",
    "mossy_timeout",
    "enable_plugin_hooks",
    "plugin_endpoints",
    "plugin_timeout",
    "disable_auto_update",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Nexus release archives.")
    parser.add_argument("--version", help="Version tag, e.g. 0.1.0 (defaults to VERSION file).")
    parser.add_argument(
        "--channel",
        default="alpha",
        choices=["alpha", "beta", "stable"],
        help="Release channel label used for metadata and artifact naming.",
    )
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


def read_default_version(repo_root: Path) -> str:
    """Read default release version from repository VERSION file."""
    version_file = repo_root / "VERSION"
    if version_file.exists():
        value = version_file.read_text(encoding="utf-8").strip()
        if value:
            return value
    return "0.1.0"


def format_release_version(version: str, channel: str) -> str:
    """Format version + channel label consistently."""
    return f"{version}-{channel.capitalize()}"


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
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON in {config_path}: {exc}") from exc

    for key in REQUIRED_CONFIG_KEYS:
        if key not in config:
            raise ValueError(f"{config_path} is missing required key: {key}")


def make_zip(source_dir: Path, destination_zip: Path) -> None:
    destination_zip.parent.mkdir(parents=True, exist_ok=True)
    archive_base = destination_zip.with_suffix("")
    shutil.make_archive(str(archive_base), "zip", root_dir=str(source_dir))


def write_release_manifest(core_root: Path, version: str, channel: str) -> None:
    """Write in-package release metadata used for in-place updates."""
    manifest_path = core_root / "Data/F4AI/release_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": version,
        "channel": channel,
        "update_strategy": "in_place_overwrite",
        "mod_manager_update_supported": True,
        "stable_paths": [
            "Data/F4AI_Core.esp",
            "Data/Scripts/",
            "Data/F4AI/",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def write_fomod_version(package_root: Path, version: str, channel: str) -> None:
    """Update fomod info.xml version field for generated artifact metadata."""
    info_xml = package_root / "fomod/info.xml"
    if not info_xml.exists():
        return
    tree = ET.parse(info_xml)
    root = tree.getroot()
    version_node = root.find("Version")
    if version_node is not None:
        version_node.text = format_release_version(version, channel)
        tree.write(info_xml, encoding="utf-8", xml_declaration=True)


def build_release(repo_root: Path, args: argparse.Namespace) -> Path:
    version = args.version or read_default_version(repo_root)
    staging_dir = (repo_root / args.staging_dir).resolve()
    output_dir = (repo_root / args.output_dir).resolve()
    work_dir = output_dir / f"_work_{version}"

    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    package_root = work_dir / f"{args.release_name}_v{version}"
    package_root.mkdir(parents=True, exist_ok=True)

    fomod_src = repo_root / "packaging/nexus/fomod"
    core_template_src = repo_root / "packaging/nexus/core-template"

    copy_tree(fomod_src, package_root / "fomod")
    write_fomod_version(package_root, version, args.channel)

    core_dst = package_root / "00 Core"
    copy_tree(core_template_src, core_dst)

    staged_core = staging_dir / "core"
    if not staged_core.exists():
        raise FileNotFoundError(
            f"Staging core directory not found: {staged_core}\n"
            "Create it and place runtime/plugin/script assets there before building."
        )
    copy_tree(staged_core, core_dst)
    write_release_manifest(core_dst, version, args.channel)

    ensure_required_files(core_dst)

    core_archive = output_dir / f"{args.release_name}_v{format_release_version(version, args.channel)}_Core_FOMOD.zip"
    make_zip(package_root, core_archive)

    return core_archive


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    try:
        artifact = build_release(repo_root, args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[release-builder] ERROR: {exc}")
        return 1

    print("[release-builder] Build complete:")
    print(f"  - {artifact}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
