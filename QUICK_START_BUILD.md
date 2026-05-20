# Quick Start: Building Your First Release

This is the fast-track version. For detailed explanations, see `BUILD_GUIDE.md`.

## 1. Setup Staging (✅ DONE)

```bash
python tools/setup_staging_directory.py
```

Directory structure created at: `release_staging/core/`

---

## 2. Build Python Executable (5 minutes)

```bash
python tools/build_engine_executable.py
```

This will:
- Install PyInstaller if needed
- Compile `src/main.py` → `Fallout4_AI_Engine.exe`
- Auto-copy to staging directory

---

## 3. Download Voice Models (5 minutes)

1. Go to: https://github.com/rhasspy/piper/releases/
2. Download **BOTH** files:
   - `en_US-lessac-medium.onnx` (~60 MB)
   - `en_US-lessac-medium.onnx.json` (~1 KB)
3. Copy both to: `release_staging/core/Data/F4AI/`

---

## 4. Create Plugin & Compile Scripts (30-60 minutes)

### A. Create Plugin (Quick Test Version)
1. Open Creation Kit
2. **File > New**
3. Save as `F4AI_Core.esp`
4. Copy to: `release_staging/core/Data/F4AI_Core.esp`

### B. Compile Papyrus Scripts
1. In Creation Kit: **Gameplay > Papyrus Script Manager**
2. Compile all `.psc` files from `papyrus/` folder
3. Copy resulting `.pex` files to: `release_staging/core/Data/Scripts/`

**Required .pex files:**
- F4AI_QueueManager.pex
- F4AI_FeedbackMonitor.pex
- F4AI_PushToTalkTrigger.pex
- F4AI_VisionWidgetManager.pex
- F4AI_InterNpcManager.pex

---

## 5. Build Release Package (1 minute)

```bash
python tools/build_nexus_release.py --channel alpha
```

**Output:** `dist/nexus/F4AI_Advanced_System_v0.1.0-Alpha.3_Core_FOMOD.zip`

---

## 6. Test Installation

### Mod Organizer 2:
1. Install from archive
2. FOMOD installer appears
3. Select "Recommended - Core Runtime"
4. Enable mod and plugin

### Test in-game:
1. Start KoboldCPP with GGUF model
2. Run `Data/F4AI/Launch_F4AI_Bridge.bat`
3. Launch Fallout 4 with F4SE
4. Talk to NPC → verify AI response

---

## Checklist

- [ ] Staging directory created
- [ ] Python executable built
- [ ] Voice models downloaded
- [ ] Plugin created (F4AI_Core.esp)
- [ ] Scripts compiled (5 .pex files)
- [ ] Release package built
- [ ] Tested in MO2/Vortex
- [ ] Functional test passed

---

## Quick Commands Reference

```bash
# Setup (run once)
python tools/setup_staging_directory.py

# Build executable
python tools/build_engine_executable.py

# Check status (see what's missing)
python tools/setup_staging_directory.py

# Build final package
python tools/build_nexus_release.py --channel alpha
```

---

## Need Help?

- **Detailed guide:** `docs/BUILD_GUIDE.md`
- **Validation report:** `NEXUS_RELEASE_DEEP_SCAN_REPORT.md`
- **Troubleshooting:** Check README files in each staging subdirectory
