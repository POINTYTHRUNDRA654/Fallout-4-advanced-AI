"""Game-master style utilities: inter-NPC scene generation and mod-aware context."""

from __future__ import annotations

import os
from pathlib import Path


def query_local_llm(prompt: str) -> str:
    """Placeholder LLM request."""
    return prompt


def process_split_script_to_audio(raw_script: str, actor_a: str, actor_b: str) -> dict[str, str]:
    """Placeholder split step for two-speaker script output."""
    return {
        "actor_a": f"{actor_a}: {raw_script}",
        "actor_b": f"{actor_b}: {raw_script}",
    }


def generate_internpc_scene(actor_a: str, actor_b: str, location: str) -> dict[str, str]:
    """Generate one two-line inter-NPC scene in a single model call."""
    system_prompt = (
        "You are a scenario script writer for Fallout 4. "
        f"Write a short, immersive, two-sentence conversation between {actor_a} and {actor_b}. "
        f"They are standing near each other in {location}. "
        "Format output exactly as:\n"
        f"{actor_a}: [Line]\n"
        f"{actor_b}: [Line]"
    )
    raw_script = query_local_llm(system_prompt)
    return process_split_script_to_audio(raw_script, actor_a, actor_b)


def detect_user_load_order() -> list[str]:
    """Read active plugin list and produce context tags."""
    app_data_dir = Path(os.path.expandvars(r"%LOCALAPPDATA%\Fallout4"))
    plugins_file = app_data_dir / "plugins.txt"
    mod_awareness_tags: list[str] = []

    if plugins_file.exists():
        try:
            active_plugins = plugins_file.read_text(encoding="utf-8").splitlines()
            for line in active_plugins:
                plugin = line.strip().lower()
                if "simsettlements" in plugin:
                    mod_awareness_tags.append(
                        "Sim Settlements is active. Communities are rebuilding advanced structures."
                    )
                if "grim" in plugin or "whisperinghills" in plugin:
                    mod_awareness_tags.append(
                        "A horror atmosphere mod is active. The world is dark, fog-covered, and terrifying."
                    )
                if "southofsea" in plugin:
                    mod_awareness_tags.append(
                        "The Glowing Sea expansion is active. The southern border wastes are expanding."
                    )
        except (OSError, UnicodeDecodeError, PermissionError) as exc:
            print(f"[Mod Scanner Error] Could not read load order context: {exc}")

    return mod_awareness_tags


def build_mod_aware_system_prompt(npc_name: str, baseline_prompt: str) -> str:
    """Append load-order context notes to baseline prompt."""
    _ = npc_name
    active_mod_contexts = detect_user_load_order()
    if active_mod_contexts:
        awareness_string = "\nENVIRONMENT MOD DATA:\n- " + "\n- ".join(active_mod_contexts)
        return baseline_prompt + awareness_string
    return baseline_prompt


def apply_racial_persona_rules(npc_name: str, race_tag: str, baseline_prompt: str) -> str:
    """Append race-specific behavioral constraints to preserve lore consistency."""
    _ = npc_name
    racial_rules = ""
    if race_tag == "Super Mutant":
        racial_rules = (
            "You are a Super Mutant. You are violent, aggressive, loud, and view humans as weak flesh-bags. "
            "Speak in brutal, simplified sentences with primitive grammar."
        )
    elif race_tag == "Ghoul":
        racial_rules = (
            "You are a Ghoul. Your voice is raspy and worn out by radiation. "
            "You are cynical but still human and resent being called feral."
        )
    elif race_tag == "Synth":
        racial_rules = (
            "You are a Generation 3 Synth from the Institute, speaking with analytical and existential tone."
        )

    if racial_rules:
        return f"{baseline_prompt}\nRACIAL PERSONALITY CONSTRAINTS:\n{racial_rules}"
    return baseline_prompt
