# Fallout 4 – Advanced AI System

A Nexus mod that extends and enhances Fallout 4's built-in Radiant AI engine
across three core functional areas: **Daily Life Routines**, **Combat Logic**,
and **Radiant Quest Generation**.

---

## Overview

Fallout 4 uses Bethesda's proprietary *Radiant AI* engine to drive NPC
behaviours through pre-programmed rule sets, conditional states, and script
packages.  This mod builds on top of that foundation without replacing it,
adding richer schedules, smarter tactical combat decisions, and more varied
radiant quest content.

---

## Features

### 1 · Daily Life Routines (AI Packages)

NPCs live out dynamic daily schedules governed by a priority-ordered package
stack.  The `AIPackageScheduler` evaluates the stack every game-hour tick and
activates the first eligible package:

| Time window   | Package  | Location     |
|---------------|----------|--------------|
| 22:00 – 06:00 | Sleep    | Bed          |
| 06:00 – 08:00 | Eat      | Bar          |
| 08:00 – 18:00 | Work     | Crop field   |
| 18:00 – 22:00 | Relax    | Bar          |
| (no match)    | Sandbox  | Anywhere     |

**Sandbox behaviour** – when no package is active, NPCs wander within a
defined zone and interact with random ambient objects (chairs, brooms, cooking
stations, workbenches, …).

### 2 · Combat Logic

Tactical decisions powered by a grid-based NavMesh representation:

* **Cover-seeking** – Enemies prefer `HIGH_COVER` > `LOW_COVER` > open ground;
  the nearest reachable node is chosen.
* **Flanking** – Attackers move to positions offset from the target, favouring
  covered flanking spots.
* **Detection states** – `HIDDEN → CAUTION → DANGER`, driven by a combined
  score of visibility × light-level + noise × 0.5.
* **Morale / flee** – Faction average health is monitored every 5 seconds.
  When it falls below the configured threshold (default 25 %) *or* the named
  leader dies, surviving members are forced onto a flee package.

### 3 · Radiant Quest Generation

An automated quest director fills three template slots from live game state:

1. **Target Location** – An uncleared dungeon within the player's level range.
2. **Hostile Faction** – Enemy type spawned at the destination (Raiders, Super
   Mutants, Ghouls, Gunners, or Institute), weighted by configurable spawn
   probabilities.
3. **Kidnapped Target** – A randomly selected settler for rescue quests; the
   system falls back to a *Clear Location* quest when no settler is available.

Quest types: **Rescue Settler** (30 %), **Clear Location** (40 %),
**Supply Run** (30 %).

---

## Repository Structure

```
Fallout-4-advanced-AI/
├── src/
│   └── ai/
│       ├── __init__.py           # Public API re-exports
│       ├── daily_routines.py     # AI Package scheduler & sandbox behaviour
│       ├── combat_ai.py          # NavMesh, detection, morale, cover/flank
│       └── radiant_quests.py     # Radiant quest director
├── Scripts/
│   └── Source/
│       ├── AdvancedAI_DailyRoutines.psc   # Papyrus – NPC schedules
│       ├── AdvancedAI_CombatLogic.psc     # Papyrus – combat AI
│       └── AdvancedAI_RadiantQuests.psc   # Papyrus – quest generation
├── tests/
│   ├── test_daily_routines.py
│   ├── test_combat_ai.py
│   └── test_radiant_quests.py
├── pyproject.toml
└── README.md
```

The `src/ai/` modules are a **Python reference implementation** – a
prototype that can be tested independently of the Creation Kit.  The
`Scripts/Source/` Papyrus scripts are the actual in-game mod components that
wire the same logic into Fallout 4's engine.

---

## Installation (Nexus / mod manager)

1. Download the latest release from the Nexus mod page.
2. Install with **Mod Organizer 2** or **Vortex** (drag-and-drop the archive).
3. Activate the mod and ensure it loads *after* any base-game patch ESPs.
4. The three quest scripts auto-initialise on `OnInit`; no MCM configuration
   is required for default behaviour.

### Manual Creation Kit setup

If you want to modify the scripts:

1. Copy the three `.psc` files from `Scripts/Source/` into your CK scripts
   source folder (typically `Data/Scripts/Source/`).
2. Open the mod's ESP in the Creation Kit and configure the exported
   properties on each quest:
   - `AdvancedAI_DailyRoutines` – assign the target NPC and the five Package
     references.
   - `AdvancedAI_CombatLogic` – assign the faction leader Actor, the
     `FactionMembers` FormList, and the flee Package.
   - `AdvancedAI_RadiantQuests` – assign the `LocationPool` and `SettlerPool`
     FormLists, and the two Reference Aliases.
3. Compile the scripts (`Ctrl+Shift+F7` in the CK script editor).

---

## Development

### Python environment

```bash
python -m pytest tests/ -v
```

All 63 unit tests should pass with Python 3.10+.  No third-party dependencies
are required beyond `pytest`.

### Quick demo

```python
from src.ai.daily_routines import AIPackageScheduler, PackageType

scheduler = AIPackageScheduler()
settler   = AIPackageScheduler.build_settler_schedule("Marcy Long")

for hour in range(24):
    pkg = scheduler.tick(settler, current_hour=hour)
    label = pkg.package_type.name if pkg else "SANDBOX"
    print(f"{hour:02d}:00  →  {label}")
```

```python
from src.ai.radiant_quests import RadiantQuestDirector

director = RadiantQuestDirector.default_commonwealth(player_level=15)
quest    = director.generate_quest()
print(quest.description)
```

---

## Compatibility

| Requirement        | Version         |
|--------------------|-----------------|
| Fallout 4          | 1.10.163+       |
| F4SE               | 0.6.23+ (optional, not required) |
| Python (dev tools) | 3.10+           |

Fully compatible with:
- **Sim Settlements 2**
- **Horizon**
- **Survival Options**

Not compatible with mods that wholesale replace the vanilla AI Package system
(e.g. some full-overhaul packs).

---

## Community & Generative AI Mods

This mod targets the vanilla Radiant AI layer.  It is designed to work
alongside popular LLM/voice-generation mods:

* **Mantella** – Unscripted NPC conversations via ChatGPT + TTS.
* **RED** – New voice-acted dialogue using ElevenLabs.
* **Real.AI** – Aggressive enemy detection and hunting overhaul.

---

## License

[MIT](LICENSE) © 2026 Pointytundra654