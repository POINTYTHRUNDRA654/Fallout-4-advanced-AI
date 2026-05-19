# Fallout-4-advanced-AI

Reference materials and starter modules for an offline Fallout 4 AI mod pipeline.

## Nexus Mods landing page template

Copy/paste into Nexus description editor:

```markdown
# Fallout 4 Advanced Local AI System (Alpha 0.1)

A 100% free, fully offline artificial intelligence framework that replaces vanilla dialogue scripts with open-source Large Language Models (LLMs) and neural Text-to-Speech (TTS). Characters remember your actions, coordinate tactical shout responses during combat, and procedurally generate completely automated lipsync data on your machine.

---

## 🚀 Key Features

* **Local Dialogue Processing**: Infinite unscripted interactions running completely free via local Llama-3 models.
* **Persistent Memory Stores**: Companions and settlers log your past choices and evaluate your moral alignment over time.
* **Smart Crowd Control**: Global dialogue queue manager prevents overlapping NPC audio feeds.
* **Dynamic Lipsync Injection**: Headless legacy integration generates structural mouth vector animation frames in real time.
* **In-Game Configuration**: Fine-tune your generation metrics (creativity temperature, memory toggles) straight from your Pip-Boy via a custom holotape.

---

## 🛠️ Step-by-Step Setup Guide

### 1. Prerequisite Installations
* Download and install the <a href="https://silverlock.org">Fallout 4 Script Extender (F4SE)</a>.
* Download and run the standalone server utility <a href="https://github.com">KoboldCPP</a>.

### 2. Model Acquisition (Free)
* Download any text generation model in **GGUF format**. We highly recommend the **Llama-3-8B-Instruct-Q4_K_M.gguf** model file from HuggingFace.
* Launch KoboldCPP, load your GGUF file, and verify the backend is idling on standard local port `5001`.

### 3. Mod Installation
* Download this archive file and drop it into your preferred mod manager (**Mod Organizer 2** or **Vortex**).
* Follow the interactive FOMOD installation wizard to pick your local Piper neural voice configuration pack.
* Navigate to your game's root directory at `Data/F4AI/` and double-click **Fallout4_AI_Engine.exe** to fire up the background file bridge before booting your game client.

---

## 🤝 Open Source & Attributions

This framework stands on the shoulders of the open-source community:
* **LLM API Interface Framework**: Built using the API design parameters established by <a href="https://github.com">KoboldCPP</a>.
* **TTS Pipeline Logic**: Developed utilizing open asset components matching the <a href="https://github.com">Piper TTS Engine</a>.
* **Bethesda Engine Mod Bridges**: Inspired by structural C++ and Papyrus translation work managed via <a href="https://github.com">The Mantella Project Framework</a>.
```

## Creation Kit alpha build walkthrough

1. Create `F4AI_Core.esp` in CK after loading `Fallout4.esm`.
2. Create quest `F4AI_QueueManagerQuest` (Priority `50`, `Start Game Enabled`).
3. Add and compile `F4AI_QueueManager` script on the quest.
4. Map `F4AI_AudioOutputSound` property to a valid sound descriptor.
5. Add and compile `F4AI_CrowdNPC` for your test NPC and wire `QueueManager` property.
6. Package:
   - `Data/F4AI_Core.esp`
   - `Data/Scripts/F4AI_QueueManager.pex`
   - `Data/Scripts/F4AI_CrowdNPC.pex`
   - `Data/F4AI/` runtime files (engine exe, Piper model/config, mod config).
7. Runtime order: launch model backend, launch bridge executable, launch game with F4SE, enable plugin, run NPC activation test.

## Python modules included in this repository

- `src/ai/auto_updater.py`: GitHub-release update checker and Windows hot-swap updater.
- `src/ai/vision_pipeline.py`: semantic-vision prompt helper, optional FO4 window capture, and local VLM query helper.

## Vision architecture summary

- **Semantic vision raycast path (fast):** Papyrus sends detected object metadata to Python; Python builds contextual NPC prompt text.
- **True multimodal path (heavy):** Python captures `Fallout4` window frame and sends it to a local VLM endpoint (for example Ollama + Moondream).
