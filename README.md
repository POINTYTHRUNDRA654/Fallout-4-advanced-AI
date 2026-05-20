# Fallout-4-advanced-AI

Reference materials and starter modules for an offline Fallout 4 AI mod pipeline.

## Free/offline baseline stack (no paid APIs)

This repository is designed to run fully local with free/open tools:

- **Text generation backend:** [KoboldCPP](https://github.com/LostRuins/koboldcpp)
- **LLM model format:** local **GGUF** model file (example: Llama-3 Instruct quant)
- **Voice synthesis:** [Piper](https://github.com/rhasspy/piper) local ONNX voice model
- **Speech-to-text (optional):** `faster-whisper` local CPU transcription
- **Bridge runtime:** `src/main.py` file loop (`bridge_input.json` -> `bridge_output.json`)

No cloud API keys are required for the baseline flow.

## Quick start (one-command Python setup)

From the repository root:

```bash
python -m pip install -r requirements.txt
```

Optional local STT extras:

```bash
python -m pip install faster-whisper SpeechRecognition pyaudio
```

## First-run config template

A default config is provided at `src/config.json`:

```json
{
  "ai_temperature": 0.7,
  "enable_memory": 1,
  "speech_speed": 1.0
}
```

When packaging for game runtime, place this as `Data/F4AI/config.json` beside the engine executable.

## Startup checklist before launching Fallout 4

- [ ] KoboldCPP is running and serving `http://localhost:5001/api/v1/generate`.
- [ ] A GGUF model is loaded in KoboldCPP.
- [ ] `piper` is installed and available on `PATH`.
- [ ] At least one voice model `.onnx` file exists in the runtime folder (`Data/F4AI/` in packaged install, `src/` in local run).
- [ ] `bridge_input.json` and `bridge_output.json` paths are writable in the runtime folder.
- [ ] If using STT, microphone access is enabled and optional STT dependencies are installed.

## Quick smoke test (bridge read/write loop)

Open terminal #1:

```bash
cd src
python main.py
```

Open terminal #2:

```bash
cd src
python -c "import json, pathlib; pathlib.Path('bridge_input.json').write_text(json.dumps({'npc_name':'Codsworth','location':'Sanctuary','player_speech':'Status report.'}), encoding='utf-8')"
python -c "import json, pathlib; print(json.loads(pathlib.Path('bridge_output.json').read_text(encoding='utf-8')))"
```

Expected result: `bridge_output.json` contains `subtitle_text`, `audio_file`, `emotion_id`, and `display_duration`.

## Troubleshooting (common local failures)

- **`piper` command not found**
  - Install Piper and ensure the binary is on your system `PATH`.
- **No `.onnx` voice model found**
  - Place the Piper voice model file in the runtime directory used by `main.py`.
- **Kobold backend not reachable on localhost:5001**
  - Start KoboldCPP, load a GGUF model, and verify the API endpoint is active.
  - If using a custom URL, set environment variable `F4AI_KOBOLD_API_URL`.
- **Firewall/connection errors**
  - Allow the executable/Python process through local firewall prompts so it can reach the local backend.

## Nexus Mods landing page template

Copy/paste into Nexus description editor:

```markdown
# Fallout 4 Advanced Local AI System (Alpha 0.1)

A 100% free, fully offline Fallout 4 AI framework with automatic mod-manager install support.

---

## 🚀 Key Features

* **One core package install**: Single FOMOD path that installs directly into `Data/` for MO2 and Vortex.
* **No external add-on packs required**: Baseline voice pair and runtime defaults are expected in the core package.
* **Fully local AI runtime**: Local model backend + local speech generation.
* **Persistent NPC memory + bridge loop**: Runtime writes responses back to game through file bridge.

---

## 🛠️ Installation (Automatic)

1. Install this archive in **Mod Organizer 2** or **Vortex**.
2. In FOMOD, keep **Recommended - Core Runtime** selected.
3. Launch your free local backend stack:
   - <a href="https://f4se.silverlock.org/">F4SE</a>
   - <a href="https://github.com/LostRuins/koboldcpp">KoboldCPP</a> with any free GGUF model
4. Run `Data/F4AI/Launch_F4AI_Bridge.bat`.
5. Start Fallout 4 with F4SE and begin dialogue.

---

## Troubleshooting (required free prerequisites only)

* Verify KoboldCPP is running on `http://localhost:5001/api/v1/generate`.
* Verify Fallout 4 is launched via F4SE.
* Verify `Data/F4AI/Fallout4_AI_Engine.exe` and baseline voice files exist after install.
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

## Alpha deployment package blueprint

Recommended release archive layout:

```text
F4AI_Advanced_System_v0.1.0_Core_FOMOD.zip
├── fomod/
│   ├── info.xml
│   └── ModuleConfig.xml
└── 00 Core/
    └── Data/
        ├── F4AI_Core.esp
        ├── Scripts/
        │   ├── F4AI_QueueManager.pex
        │   ├── F4AI_FeedbackMonitor.pex
        │   ├── F4AI_PushToTalkTrigger.pex
        │   ├── F4AI_VisionWidgetManager.pex
        │   └── F4AI_InterNpcManager.pex
        └── F4AI/
            ├── Fallout4_AI_Engine.exe
            ├── config.json
            ├── en_US-lessac-medium.onnx
            ├── en_US-lessac-medium.onnx.json
            ├── Launch_F4AI_Bridge.bat
            ├── FIRST_RUN.txt
            └── NEXUS_TROUBLESHOOTING.txt
```

Release automation:

```bash
python tools/build_nexus_release.py --version 0.1.0
```

The release builder validates required files before creating the zip.

Final checks:
- Keep the published package as one core archive (no external add-on packs).
- Include only compiled `.pex` in release package (keep `.psc` in source repo).
- Build executable with required runtime dependencies.
- Ship default `config.json` and baseline voice pair in core package.
- Ensure testers run local free Kobold backend before game launch.
