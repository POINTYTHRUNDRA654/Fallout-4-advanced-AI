# Bundle Piper Implementation Guide

This guide shows you how to bundle Piper TTS with your mod for true one-click installation.

---

## Step 1: Download Piper Executable

### Windows Binary
1. Go to: https://github.com/rhasspy/piper/releases/latest
2. Look for **Windows** build (example: `piper_windows_amd64.zip`)
3. Download the ZIP file
4. Extract `piper.exe` from the archive

### Direct Link (check for latest version):
https://github.com/rhasspy/piper/releases/

**Expected file:** `piper.exe` (~10-20 MB)

---

## Step 2: Place Piper in Staging Directory

Copy `piper.exe` to:
```
release_staging/core/Data/F4AI/piper.exe
```

**Final structure:**
```
release_staging/core/Data/F4AI/
├── piper.exe                    ← NEW
├── Fallout4_AI_Engine.exe
├── config.json
├── Launch_F4AI_Bridge.bat
├── en_US-lessac-medium.onnx
├── en_US-lessac-medium.onnx.json
└── ...
```

---

## Step 3: Update Build Script

Edit `tools/build_nexus_release.py`:

Find the `REQUIRED_CORE_FILES` list and add `piper.exe`:

```python
REQUIRED_CORE_FILES = [
	"Data/F4AI_Core.esp",
	"Data/Scripts/F4AI_QueueManager.pex",
	"Data/Scripts/F4AI_FeedbackMonitor.pex",
	"Data/Scripts/F4AI_PushToTalkTrigger.pex",
	"Data/Scripts/F4AI_VisionWidgetManager.pex",
	"Data/Scripts/F4AI_InterNpcManager.pex",
	"Data/F4AI/Fallout4_AI_Engine.exe",
	"Data/F4AI/piper.exe",  # ← ADD THIS LINE
	"Data/F4AI/config.json",
	"Data/F4AI/en_US-lessac-medium.onnx",
	"Data/F4AI/en_US-lessac-medium.onnx.json",
	"Data/F4AI/Launch_F4AI_Bridge.bat",
	"Data/F4AI/FIRST_RUN.txt",
	"Data/F4AI/NEXUS_TROUBLESHOOTING.txt",
	"Data/F4AI/release_manifest.json",
]
```

---

## Step 4: Update Python Code to Use Bundled Piper

Edit `src/main.py`:

### Option A: Simple Fix (Recommended)

Find this section (around line 32):
```python
FALLOUT_ROOT = DATA_DIR.parent.parent.resolve()
CK_32_EXE = FALLOUT_ROOT / "CreationKit32.exe"
KOBOLD_API_URL = os.getenv("F4AI_KOBOLD_API_URL", "http://localhost:5001/api/v1/generate")
MOSSY_DEFAULT_ENDPOINT = "http://127.0.0.1:8765/f4ai/bridge"
```

Add this line:
```python
PIPER_EXE = DATA_DIR / "piper.exe"
```

Then find this code (around line 317):
```python
cmd = [
	"piper",
	"--model",
	voice_model,
	"--length_scale",
	str(config.get("speech_speed", 1.0)),
	"--output_file",
	str(audio_wav_path),
]
```

Replace `"piper"` with `str(PIPER_EXE)`:
```python
cmd = [
	str(PIPER_EXE),  # ← CHANGED
	"--model",
	voice_model,
	"--length_scale",
	str(config.get("speech_speed", 1.0)),
	"--output_file",
	str(audio_wav_path),
]
```

### Option B: Fallback to PATH (More Robust)

Create a helper function that tries bundled first, falls back to PATH:

```python
def find_piper_executable() -> str:
	"""Locate piper executable (bundled first, then PATH)."""
	bundled_piper = DATA_DIR / "piper.exe"
	if bundled_piper.exists():
		return str(bundled_piper)
	# Fallback to PATH
	return "piper"
```

Then use:
```python
cmd = [
	find_piper_executable(),  # ← CHANGED
	"--model",
	voice_model,
	...
]
```

---

## Step 5: Update emotion_tts.py (If Used)

If you're using `src/ai/emotion_tts.py`, update it similarly:

Find the `render_emotional_speech_piper` function (around line 38):

```python
def render_emotional_speech_piper(
	raw_llm_output: str,
	output_wav_path: str,
	model_path: str,
) -> str:
	"""Apply emotion-based Piper controls and render WAV."""
	# ... emotion detection code ...

	# ADD THIS
	from main import PIPER_EXE  # Import from main

	command = [
		str(PIPER_EXE),  # ← CHANGED from "piper"
		"--model",
		model_path,
		"--length_scale",
		str(length_scale),
		"--noise_scale",
		str(noise_scale),
		"--output_file",
		output_wav_path,
	]
	# ... rest of function ...
```

---

## Step 6: Update README Files

### Update `release_staging/core/Data/F4AI/_README.txt`:

Add a note about Piper being bundled:

```
Place runtime files here:
- Fallout4_AI_Engine.exe (build with: python tools/build_engine_executable.py)
- piper.exe (download from https://github.com/rhasspy/piper/releases/)
- en_US-lessac-medium.onnx (download from Piper)
- en_US-lessac-medium.onnx.json (download from Piper)

Piper TTS is bundled for one-click installation.
No need to install Piper separately or add to PATH.
```

### Update `packaging/nexus/core-template/Data/F4AI/FIRST_RUN.txt`:

Remove any Piper installation requirements:

```
Fallout 4 Advanced AI - First Run

Required (free):
- Fallout 4
- F4SE (https://f4se.silverlock.org/)
- KoboldCPP with a GGUF model loaded
- This core package files in Data/

Installation:
1) Install this archive with Mod Organizer 2 or Vortex (FOMOD handles paths automatically).
2) Download KoboldCPP: https://github.com/LostRuins/koboldcpp/releases
3) Download a GGUF model (see README for recommendations)
4) Start KoboldCPP and load the GGUF model
5) Launch Data/F4AI/Launch_F4AI_Bridge.bat
6) Start Fallout 4 with F4SE
7) Talk to an NPC and verify subtitles/audio are generated

For alpha updates, install new versions over the existing mod (overwrite in MO2/Vortex; no uninstall required).

If audio is missing:
- Confirm Data/F4AI/en_US-lessac-medium.onnx and .onnx.json are present
- Confirm KoboldCPP is running on localhost:5001
- Check Data/F4AI/bridge_output.json for error messages
```

---

## Step 7: Add Attribution

### Update `README.md`:

Add Piper to the credits section:

```markdown
## Credits & Attribution

This mod bundles and uses the following open-source projects:

- **Piper TTS** - https://github.com/rhasspy/piper
  - License: MIT
  - Used for offline voice synthesis

- **KoboldCPP** - https://github.com/LostRuins/koboldcpp
  - Used as LLM inference backend

- **F4SE** - https://f4se.silverlock.org/
  - Fallout 4 Script Extender
```

### Create `packaging/nexus/core-template/Data/F4AI/CREDITS.txt`:

```
Fallout 4 Advanced AI - Credits

This mod includes:

Piper TTS
- https://github.com/rhasspy/piper
- License: MIT
- Copyright (c) 2023 Michael Hansen
- Bundled for offline voice synthesis

Voice Model: en_US-lessac-medium
- Part of Piper TTS project
- License: MIT
- High-quality English TTS voice

See https://github.com/rhasspy/piper for full Piper documentation.
```

---

## Step 8: Test Bundled Installation

### Build the Package:
```bash
python tools/build_nexus_release.py --channel alpha
```

### Extract and Verify:
```powershell
Expand-Archive -Path "dist/nexus/*.zip" -DestinationPath "test_bundle"
Test-Path "test_bundle/*/00 Core/Data/F4AI/piper.exe"
```

Should return: `True`

### Test Executable Directly:
```powershell
cd test_bundle/*/00 Core/Data/F4AI
.\piper.exe --help
```

Should display Piper help text.

### Test Voice Generation:
```powershell
echo "Hello from Fallout 4!" | .\piper.exe --model en_US-lessac-medium.onnx --output_file test.wav
```

Should generate `test.wav` file.

---

## Step 9: Update Build Checklist

Update `NEXUS_RELEASE_CHECKLIST.md` Phase 2.2 to include Piper:

```markdown
### 2.2: Download Runtime Binaries
- [ ] Download Piper executable from https://github.com/rhasspy/piper/releases/
- [ ] Extract `piper.exe` (~10-20 MB)
- [ ] Copy to `release_staging/core/Data/F4AI/piper.exe`
- [ ] Download voice models:
  - [ ] `en_US-lessac-medium.onnx` (~60 MB)
  - [ ] `en_US-lessac-medium.onnx.json` (~1 KB)
- [ ] Copy voice models to `release_staging/core/Data/F4AI/`
- [ ] Verify all 3 files present (piper.exe + 2 voice files)
```

---

## Troubleshooting

### "piper.exe not found" after installation
- Check file was included in ZIP
- Verify FOMOD installed files correctly
- Check Data/F4AI/ folder in game directory

### "piper.exe won't run"
- Download correct Windows version (amd64)
- Check Windows SmartScreen didn't block
- Right-click → Properties → Unblock

### Voice generation fails
- Verify .onnx files are present
- Check voice model is compatible with Piper version
- Test piper.exe manually from command line

### Build script fails validation
- Ensure `piper.exe` is in `release_staging/core/Data/F4AI/`
- Check you updated `REQUIRED_CORE_FILES` list
- Run `python tools/setup_staging_directory.py` to verify

---

## File Size Impact

Adding Piper increases package size:

| Component | Size |
|-----------|------|
| piper.exe | ~10-20 MB |
| Voice model (.onnx) | ~60 MB |
| Python executable | ~50-150 MB |
| Scripts + Plugin | ~1 MB |
| **Total** | **~120-230 MB** |

This is reasonable for a one-click AI mod.

---

## License Compliance

Piper is licensed under **MIT License**, which allows:
- ✅ Commercial use
- ✅ Modification
- ✅ Distribution
- ✅ Private use

**Requirements:**
- Include license text (covered by CREDITS.txt)
- Include copyright notice (covered by CREDITS.txt)

You're fully compliant by including attribution.

---

## Alternative: Lightweight Fallback

If you want to keep package size smaller:

1. Bundle Piper but make it **optional**
2. Detect if Piper is missing
3. Show user-friendly error with download link

**Code:**
```python
PIPER_EXE = DATA_DIR / "piper.exe"

if not PIPER_EXE.exists():
	print("[ERROR] Piper TTS not found!")
	print("[ERROR] Download: https://github.com/rhasspy/piper/releases/")
	print("[ERROR] Extract piper.exe to Data/F4AI/")
	# Optionally: write error to bridge_output.json
	return
```

**Not recommended** - defeats the one-click goal.

---

## Summary

**Bundling Piper gives you:**
- ✅ True one-click installation
- ✅ No user configuration needed
- ✅ Lower support burden
- ✅ Professional user experience

**Required steps:**
1. Download piper.exe from GitHub
2. Copy to staging directory
3. Update build script
4. Update Python code (5 line change)
5. Add attribution
6. Test and release

**Time estimate:** 30-45 minutes

---

**Next:** Run through these steps, then rebuild your package with bundled Piper for true one-click installation!
