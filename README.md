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
* Download and install the <a href="https://f4se.silverlock.org/">Fallout 4 Script Extender (F4SE)</a>.
* Download and run the standalone server utility <a href="https://github.com/LostRuins/koboldcpp">KoboldCPP</a>.

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
* **LLM API Interface Framework**: Built using API design parameters established by <a href="https://github.com/LostRuins/koboldcpp">KoboldCPP</a>.
* **TTS Pipeline Logic**: Developed using open components from <a href="https://github.com/rhasspy/piper">Piper TTS</a>.
* **Bethesda Engine Mod Bridges**: Inspired by C++/Papyrus bridge architecture in <a href="https://github.com/art-from-the-machine/Mantella">Mantella</a>.
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

## Public repository formatting

Recommended layout:

```text
fallout4-ai-bridge/
├── src/
│   ├── main.py
│   ├── vision.py
│   ├── tts.py
│   └── config.py
├── papyrus/
│   ├── F4AI_QueueManager.psc
│   ├── F4AI_CrowdNPC.psc
│   └── F4AI_VisionWidgetManager.psc
├── .gitignore
├── LICENSE
└── README.md
```

Notes:
- Keep heavy binaries (`.exe`, `.onnx`, `.wav`) out of Git; ship them in release archives.
- Keep Papyrus source in Git (`.psc`) and package compiled `.pex` from CK output separately.

## Closed alpha process (Nexus Mods)

- Keep page visibility hidden during early QA.
- Require structured bug reports (hardware, FPS overhead, crash log, latency timing).
- Use a dedicated issue thread/Discord channel and require attached logs/artifacts.

## Script location + compilation

- Author `.psc` files in `Data/Scripts/Source/User/` inside your game install for CK compilation.
- CK compiles to `Data/Scripts/*.pex`; do not rename generated `.pex` files manually.

## Robust runtime file paths

`src/config.py` includes runtime-relative path detection so installed users are not tied to one absolute drive path.

## Required file handoff sequence

1. Game writes `bridge_input.json`.
2. Python reads and immediately deletes `bridge_input.json`.
3. Python generates output and writes `bridge_output.json`.
4. Game reads and immediately deletes `bridge_output.json`.

This avoids stale packets and repeated playback loops.

## Advanced roadmap: Game Master agent

- Inter-NPC multi-agent conversations in settlements.
- Autonomous objective trees from settlement telemetry.
- Mod-aware prompt conditioning from active plugin load order.
- Dynamic tactical routing and spatial response synthesis.
- Local LoRA adaptation for long-play personality drift.

## STT noise filtering and alpha build checklist

- Install STT stack: `pip install faster-whisper SpeechRecognition pyaudio`.
- Install noise-filter dependency: `pip install scipy`.
- `src/stt.py` includes an acoustic noise gate (`numpy`) that:
  - mutes low-energy microphone noise floor,
  - clamps high-amplitude spikes (gunshots/explosions cross-talk),
  - then transcribes filtered audio with Faster-Whisper in CPU `int8` mode.

Build command for one-file executable:

```bash
pyinstaller --onefile --noconsole --collect-all faster_whisper --name="Fallout4_AI_Engine" main.py
```

Final distribution verification (high level):
- `Data/F4AI_Core.esp`
- `Data/Scripts/F4AI_QueueManager.pex`
- `Data/Scripts/F4AI_CrowdNPC.pex`
- `Data/Scripts/F4AI_PushToTalkTrigger.pex`
- `Data/Scripts/F4AI_VisionWidgetManager.pex`
- `Data/F4AI/Fallout4_AI_Engine.exe`
- `Data/F4AI/config.json`
- `Data/F4AI/en_US-lessac-medium.onnx`
- `Data/F4AI/en_US-lessac-medium.onnx.json`

## Emotional voice rendering (offline)

- `src/ai/emotion_tts.py` includes:
  - `build_emotional_system_prompt(...)` for strict `[NORMAL|ANGRY|SAD|WHISPER]` tag output,
  - `render_emotional_speech_piper(...)` for tag-driven `length_scale`/`noise_scale`,
  - `render_emotional_speech_xvasynth(...)` for native xVASynth emotion sliders.
- Feed `mental_state` from gameplay context (combat, stealth, panic) so the model emits a matching tag.
