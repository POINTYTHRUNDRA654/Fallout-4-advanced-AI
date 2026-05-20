# Nexus Release Checklist - Step by Step

**Version:** 0.1.0-Alpha.3  
**Date:** 2025-01-22  
**Status:** In Progress

---

## Phase 1: Initial Setup ✅ COMPLETE

- [x] Deep scan performed
- [x] Staging directory structure created
- [x] Build tools created
- [x] Documentation written
- [x] Batch files created for Windows

**Created Files:**
- ✅ `tools/setup_staging_directory.py`
- ✅ `tools/build_engine_executable.py`
- ✅ `docs/BUILD_GUIDE.md`
- ✅ `QUICK_START_BUILD.md`
- ✅ `BUILD_TOOLS_SUMMARY.md`
- ✅ `NEXUS_RELEASE_DEEP_SCAN_REPORT.md`
- ✅ `setup_staging.bat`
- ✅ `build_executable.bat`
- ✅ `build_release.bat`

---

## Phase 2: Asset Compilation ⏳ IN PROGRESS

### 2.1: Python Executable
- [ ] Install PyInstaller (auto-handled by script)
- [ ] Run `build_executable.bat` OR `python tools/build_engine_executable.py`
- [ ] Verify output: `release_staging/core/Data/F4AI/Fallout4_AI_Engine.exe`
- [ ] Check executable size (~50-150 MB is normal)

**Commands:**
```bash
# Windows
build_executable.bat

# Cross-platform
python tools/build_engine_executable.py
```

---

### 2.2: Voice Models
- [ ] Visit https://github.com/rhasspy/piper/releases/
- [ ] Download `en_US-lessac-medium.onnx` (~60 MB)
- [ ] Download `en_US-lessac-medium.onnx.json` (~1 KB)
- [ ] Copy both files to `release_staging/core/Data/F4AI/`
- [ ] Verify files exist in correct location

**Download Links:**
- Main: https://github.com/rhasspy/piper/releases/
- Alternative voices: Search for other `en_US-*-medium` models

**Target Location:**
```
release_staging/core/Data/F4AI/
├── en_US-lessac-medium.onnx
└── en_US-lessac-medium.onnx.json
```

---

### 2.3: Creation Kit - Plugin File
- [ ] Install Creation Kit (if not installed)
- [ ] Launch Creation Kit
- [ ] Create new plugin: **File > New**
- [ ] Save as `F4AI_Core.esp`
- [ ] (Optional) Add forms: quests, globals, messages
- [ ] Copy plugin to `release_staging/core/Data/F4AI_Core.esp`
- [ ] Verify file size (should be at least a few KB)

**Target Location:**
```
release_staging/core/Data/F4AI_Core.esp
```

**Notes:**
- For initial testing, an empty plugin is fine
- For full release, add proper quest/form structure
- Ensure plugin loads without errors in xEdit

---

### 2.4: Creation Kit - Papyrus Scripts
- [ ] Open Creation Kit
- [ ] Load `F4AI_Core.esp`
- [ ] Go to **Gameplay > Papyrus Script Manager**
- [ ] Compile each script:
  - [ ] `F4AI_QueueManager.psc` → `.pex`
  - [ ] `F4AI_FeedbackMonitor.psc` → `.pex`
  - [ ] `F4AI_PushToTalkTrigger.psc` → `.pex`
  - [ ] `F4AI_VisionWidgetManager.psc` → `.pex`
  - [ ] `F4AI_InterNpcManager.psc` → `.pex`
- [ ] Copy all 5 `.pex` files to `release_staging/core/Data/Scripts/`
- [ ] Verify all files present

**Source Files:** `papyrus/*.psc`

**Target Location:**
```
release_staging/core/Data/Scripts/
├── F4AI_QueueManager.pex
├── F4AI_FeedbackMonitor.pex
├── F4AI_PushToTalkTrigger.pex
├── F4AI_VisionWidgetManager.pex
└── F4AI_InterNpcManager.pex
```

**Alternative Method:**
- Use standalone Papyrus compiler
- Command-line compilation (see BUILD_GUIDE.md)

---

### 2.5: Verify All Assets
- [ ] Run `setup_staging.bat` OR `python tools/setup_staging_directory.py`
- [ ] Check output - should show all files present
- [ ] Manually verify file count:
  - 1 plugin file (.esp)
  - 5 script files (.pex)
  - 1 executable (.exe)
  - 2 voice files (.onnx + .json)
  - 4 template files (config, bat, txt files)

**Verification Command:**
```bash
python tools/setup_staging_directory.py
```

**Expected Output:**
```
[setup-staging] ✅ All required files are present!
[setup-staging] Ready to build release package.
```

---

## Phase 3: Build Release Package ⏸️ WAITING

### 3.1: Build Nexus ZIP
- [ ] Ensure Phase 2 is 100% complete
- [ ] Run `build_release.bat` OR `python tools/build_nexus_release.py --channel alpha`
- [ ] Wait for build to complete
- [ ] Verify output exists: `dist/nexus/F4AI_Advanced_System_v0.1.0-Alpha.3_Core_FOMOD.zip`
- [ ] Check file size (should be 60-120 MB)

**Commands:**
```bash
# Windows
build_release.bat

# Cross-platform
python tools/build_nexus_release.py --channel alpha
```

**Output Location:**
```
dist/nexus/F4AI_Advanced_System_v0.1.0-Alpha.3_Core_FOMOD.zip
```

---

### 3.2: Extract and Verify ZIP Structure
- [ ] Extract ZIP to test folder
- [ ] Verify FOMOD structure:
  - [ ] `fomod/info.xml` exists
  - [ ] `fomod/ModuleConfig.xml` exists
  - [ ] `00 Core/Data/` structure exists
- [ ] Verify all files present in `00 Core/Data/`
- [ ] Check version in `fomod/info.xml` matches current version

**Test Command:**
```powershell
Expand-Archive -Path "dist/nexus/*.zip" -DestinationPath "test_extract"
Get-ChildItem -Path "test_extract" -Recurse
```

**Expected Structure:**
```
F4AI_Advanced_System_v0.1.0-Alpha.3_Core_FOMOD/
├── fomod/
│   ├── info.xml (version should be 0.1.0-Alpha.3)
│   └── ModuleConfig.xml
└── 00 Core/
	└── Data/
		├── F4AI_Core.esp
		├── Scripts/
		│   └── [5 .pex files]
		└── F4AI/
			├── Fallout4_AI_Engine.exe
			├── config.json
			├── Launch_F4AI_Bridge.bat
			├── en_US-lessac-medium.onnx
			├── en_US-lessac-medium.onnx.json
			├── release_manifest.json
			├── FIRST_RUN.txt
			└── NEXUS_TROUBLESHOOTING.txt
```

---

## Phase 4: Testing ⏸️ WAITING

### 4.1: Mod Organizer 2 Test
- [ ] Create new clean MO2 profile
- [ ] Install mod from archive
- [ ] Verify FOMOD installer appears
- [ ] Select "Recommended - Core Runtime"
- [ ] Verify installation completes
- [ ] Enable mod in left pane
- [ ] Enable `F4AI_Core.esp` in right pane (plugins)
- [ ] Check file structure in MO2 Data tab
- [ ] Verify no conflicts/overwrites (unless expected)

**Success Criteria:**
- Mod installs without errors
- All files appear in correct Data paths
- Plugin loads in load order
- No missing file warnings

---

### 4.2: Vortex Test
- [ ] Create new clean Vortex profile
- [ ] Install mod from file
- [ ] Verify FOMOD installer appears
- [ ] Select "Recommended - Core Runtime"
- [ ] Deploy mods
- [ ] Verify deployment completes
- [ ] Enable plugin in plugins tab
- [ ] Check for deployment conflicts

**Success Criteria:**
- Mod deploys without errors
- Files appear in Fallout 4 Data folder
- Plugin enabled in load order

---

### 4.3: Manual Installation Test
- [ ] Extract ZIP manually
- [ ] Copy `00 Core/Data/*` to Fallout 4 Data folder
- [ ] Verify files copied correctly
- [ ] Enable plugin in launcher/mod manager

**Success Criteria:**
- Files in correct locations
- No file permission errors
- Plugin loads

---

### 4.4: Functional Smoke Test

#### Prerequisites Check:
- [ ] KoboldCPP installed
- [ ] GGUF model downloaded
- [ ] F4SE installed
- [ ] Fallout 4 installed (with DLC recommended)

#### Test Steps:
- [ ] Start KoboldCPP
- [ ] Load GGUF model in KoboldCPP
- [ ] Verify KoboldCPP API accessible: http://localhost:5001
- [ ] Navigate to Fallout 4 Data folder
- [ ] Run `Data/F4AI/Launch_F4AI_Bridge.bat`
- [ ] Verify bridge starts (minimizes to background)
- [ ] Launch Fallout 4 using F4SE loader
- [ ] Load save or start new game
- [ ] Find and talk to NPC (Codsworth in Sanctuary recommended)
- [ ] Observe dialogue generation
- [ ] Check for generated audio file
- [ ] Verify no crashes or errors

**Success Criteria:**
- Bridge starts without errors
- Game loads with plugin active
- NPC dialogue generates
- Audio plays correctly
- `bridge_output.json` created
- No crashes during 5-minute test

#### Troubleshooting If Test Fails:
- Check `Data/F4AI/bridge_input.json` and `bridge_output.json`
- Verify KoboldCPP is running and responding
- Check bridge console for errors (if visible)
- Review Papyrus logs: `Documents/My Games/Fallout4/Logs/Script/`
- Verify all .pex scripts loaded without errors

---

## Phase 5: Pre-Release Validation ⏸️ WAITING

### 5.1: Documentation Review
- [ ] Update README.md if needed
- [ ] Review FIRST_RUN.txt is clear for end users
- [ ] Review NEXUS_TROUBLESHOOTING.txt covers common issues
- [ ] Verify version numbers consistent across all docs
- [ ] Check all links in documentation work

---

### 5.2: License and Attribution
- [ ] Verify LICENSE file present (MIT)
- [ ] Check attribution in README for dependencies:
  - [ ] KoboldCPP
  - [ ] Piper
  - [ ] F4SE
  - [ ] Creation Kit
- [ ] Verify no proprietary assets included

---

### 5.3: Version Control
- [ ] Current version: `0.1.0-Alpha.3`
- [ ] Version in VERSION file matches
- [ ] Git working directory clean
- [ ] All changes committed
- [ ] Consider creating git tag for release

**Commands:**
```bash
git status
git add .
git commit -m "Release v0.1.0-Alpha.3 preparation"
git tag -a v0.1.0-Alpha.3 -m "Alpha release 3"
git push origin main --tags
```

---

## Phase 6: Nexus Upload ⏸️ WAITING

### 6.1: Nexus Mod Page Setup
- [ ] Log in to Nexus Mods
- [ ] Create new mod page for Fallout 4
- [ ] Fill in mod details:
  - [ ] Name: "Fallout 4 Advanced AI"
  - [ ] Summary: Brief description (160 chars max)
  - [ ] Category: Gameplay/AI/Dialogue
  - [ ] Version: 0.1.0-Alpha.3
  - [ ] Game: Fallout 4

---

### 6.2: Mod Description
- [ ] Write compelling description
- [ ] Include features list
- [ ] Add requirements section:
  - [ ] Fallout 4
  - [ ] F4SE (latest)
  - [ ] KoboldCPP (free)
  - [ ] GGUF model (free)
- [ ] Add installation instructions (copy from FIRST_RUN.txt)
- [ ] Add troubleshooting section
- [ ] Include link to GitHub repository
- [ ] Add credits/attribution

**Description Template:**
```markdown
# Fallout 4 Advanced AI

Offline AI-powered NPC dialogue system using local LLMs.

## Features
- Fully offline/free (no API keys)
- Real-time NPC dialogue generation
- Voice synthesis with Piper
- Memory system for persistent conversations
- FOMOD installer for easy installation

## Requirements
[List requirements]

## Installation
[Copy from FIRST_RUN.txt]

## Troubleshooting
[Copy from NEXUS_TROUBLESHOOTING.txt]
```

---

### 6.3: Upload Files
- [ ] Upload main file: `F4AI_Advanced_System_v0.1.0-Alpha.3_Core_FOMOD.zip`
- [ ] Set as main file
- [ ] Set version: 0.1.0-Alpha.3
- [ ] Mark as alpha release
- [ ] Add file description/changelog

---

### 6.4: Media
- [ ] Upload at least 3 screenshots
- [ ] (Optional) Upload video demonstration
- [ ] Upload header image
- [ ] Upload thumbnail image

**Screenshot Ideas:**
- KoboldCPP running with model loaded
- In-game dialogue with NPC
- FOMOD installer screen
- File structure in MO2

---

### 6.5: Additional Settings
- [ ] Set requirements:
  - [ ] F4SE (mark as required)
  - [ ] No other mod dependencies
- [ ] Set tags/keywords
- [ ] Set permissions (MIT License - open)
- [ ] Enable comments
- [ ] Enable endorsements

---

### 6.6: Publish
- [ ] Review all sections one final time
- [ ] Click "Publish Mod"
- [ ] Verify mod page is live
- [ ] Test download link
- [ ] Check page displays correctly

---

## Phase 7: Post-Release ⏸️ WAITING

### 7.1: GitHub Release
- [ ] Go to GitHub repository
- [ ] Create new release
- [ ] Tag: `v0.1.0-Alpha.3`
- [ ] Title: "Fallout 4 Advanced AI - Alpha Release 3"
- [ ] Description: Copy from Nexus + add GitHub-specific notes
- [ ] Attach ZIP file (optional - can link to Nexus)
- [ ] Mark as pre-release (alpha)
- [ ] Publish release

---

### 7.2: Monitoring
- [ ] Monitor Nexus comments for issues
- [ ] Check bug reports
- [ ] Watch for common issues
- [ ] Update troubleshooting guide if needed
- [ ] Respond to questions

---

### 7.3: Planning Next Release
- [ ] Collect feedback from users
- [ ] Create issues for reported bugs
- [ ] Plan features for next alpha
- [ ] Update roadmap in README
- [ ] Increment version for next release

---

## Summary Checklist

### Critical Path (Must Complete):
- [ ] Phase 2: Asset Compilation
- [ ] Phase 3: Build Release Package
- [ ] Phase 4: Testing (at least 4.1 and 4.4)
- [ ] Phase 5: Pre-Release Validation
- [ ] Phase 6: Nexus Upload

### Optional (Recommended):
- [ ] Test in both MO2 and Vortex
- [ ] Create video demonstration
- [ ] Add screenshots
- [ ] GitHub release

### Quick Start Order:
1. Run `build_executable.bat` (Phase 2.1)
2. Download voice models (Phase 2.2)
3. Create plugin in Creation Kit (Phase 2.3)
4. Compile scripts in Creation Kit (Phase 2.4)
5. Run `build_release.bat` (Phase 3.1)
6. Test in MO2 (Phase 4.1)
7. Functional test (Phase 4.4)
8. Upload to Nexus (Phase 6)

---

## Estimated Time Remaining

| Phase | Time | Can Start Now? |
|-------|------|----------------|
| 2.1 - Executable | 5 min | ✅ Yes |
| 2.2 - Voice models | 5 min | ✅ Yes |
| 2.3 - Plugin | 10 min | ✅ Yes (if CK installed) |
| 2.4 - Scripts | 15 min | ⏸️ Needs plugin |
| 3 - Build | 1 min | ⏸️ Needs Phase 2 |
| 4 - Testing | 30 min | ⏸️ Needs Phase 3 |
| 5 - Validation | 15 min | ⏸️ Needs Phase 4 |
| 6 - Upload | 30 min | ⏸️ Needs Phase 5 |
| **Total** | **~2 hours** | |

---

## Current Status: Ready to Begin Asset Compilation

**Next Action:** Run `build_executable.bat` or download voice models (can be done in parallel).

**Help Resources:**
- Detailed guide: `docs/BUILD_GUIDE.md`
- Quick reference: `QUICK_START_BUILD.md`
- Tool summary: `BUILD_TOOLS_SUMMARY.md`
- Validation report: `NEXUS_RELEASE_DEEP_SCAN_REPORT.md`

---

**Last Updated:** 2025-01-22  
**Checklist Version:** 1.0
