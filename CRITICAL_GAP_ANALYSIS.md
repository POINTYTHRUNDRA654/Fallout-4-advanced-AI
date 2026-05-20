# Critical Gap Analysis - One-Click Installation Requirements

## 🔴 CRITICAL GAPS FOUND

Your project currently has **external dependencies** that prevent true one-click installation. Here's what needs to be fixed:

---

## Gap #1: Piper TTS Not Bundled ⚠️ BLOCKER

### Current State:
- Code calls `piper` as external command: `subprocess.run(["piper", "--model", ...])`
- Assumes Piper is installed and available on PATH
- Users must manually install Piper separately

### Impact:
- ❌ NOT one-click installation
- ❌ Users must download Piper separately
- ❌ Users must add Piper to PATH
- ❌ Extra technical knowledge required

### Solution Options:

#### Option A: Bundle Piper Executable (RECOMMENDED)
**Bundle `piper.exe` with your mod package**

**Pros:**
- ✅ True one-click installation
- ✅ No user configuration needed
- ✅ Version control (you control which Piper version)
- ✅ Works offline immediately

**Cons:**
- Larger download size (~10-20 MB)
- Need to handle licensing/attribution

**Implementation:**
1. Download Piper Windows binary from: https://github.com/rhasspy/piper/releases/
2. Include `piper.exe` in `release_staging/core/Data/F4AI/`
3. Update build script to include piper.exe
4. Modify `src/main.py` to use bundled piper.exe path
5. Add Piper attribution to credits

**Code changes needed:**
```python
# In src/main.py, replace:
cmd = ["piper", "--model", voice_model, ...]

# With:
PIPER_EXE = DATA_DIR / "piper.exe"  # Bundled location
cmd = [str(PIPER_EXE), "--model", voice_model, ...]
```

#### Option B: Instructions + Manual Install (NOT RECOMMENDED)
**Require users to install Piper separately**

**Pros:**
- Smaller download size

**Cons:**
- ❌ NOT one-click
- ❌ High support burden (users will struggle)
- ❌ Many users will fail to install correctly
- ❌ PATH configuration issues

---

## Gap #2: KoboldCPP External Dependency ⚠️ EXPECTED

### Current State:
- Requires KoboldCPP running on localhost:5001
- Requires GGUF model loaded

### Impact:
- Users must download and run KoboldCPP separately
- Users must download a GGUF model (can be several GB)

### Assessment:
✅ **This is acceptable** - KoboldCPP is too large to bundle and needs GPU/CPU configuration.

### Solution:
- Clear documentation on how to download/run KoboldCPP
- Link to KoboldCPP releases
- Suggest specific GGUF models with download links
- Include in FIRST_RUN.txt and Nexus description

---

## Gap #3: F4SE Dependency ✅ STANDARD

### Current State:
- Requires F4SE to be installed

### Assessment:
✅ **This is standard for Fallout 4 mods** - all script-heavy mods require F4SE.

### Solution:
- List as required dependency on Nexus
- Include installation link in documentation

---

## Gap #4: CreationKit32.exe for Lip Generation ⚠️ OPTIONAL

### Current State:
- Code checks for `CreationKit32.exe` in Fallout 4 root
- Used for automatic lip sync generation
- Gracefully degrades if not found

### Assessment:
✅ **Acceptable as optional feature** - code handles absence gracefully.

### Solution:
- Document as optional enhancement
- Note that lip sync will be missing without CK
- This is fine for alpha release

---

## Gap #5: Voice Models Bundled ✅ HANDLED

### Current State:
- Voice models (.onnx + .json) must be included in package

### Assessment:
✅ **Already in your build checklist** - voice models will be bundled.

### Solution:
- Download en_US-lessac-medium.onnx + .json
- Include in release package
- Already covered in your build process

---

## Gap #6: PyInstaller Executable Dependencies ⚠️ VERIFY NEEDED

### Current State:
- Building `Fallout4_AI_Engine.exe` with PyInstaller
- May not include all runtime dependencies

### Potential Issues:
- **requests** module - bundled by PyInstaller ✅
- **numpy** - bundled by PyInstaller ✅
- **scipy** - bundled by PyInstaller ✅
- **tts.py** module - needs explicit inclusion ⚠️

### Solution:
Update `tools/build_engine_executable.py` to ensure all modules are included:

```python
cmd = [
	sys.executable,
	"-m", "PyInstaller",
	"--onefile",
	"--noconsole",
	"--name", "Fallout4_AI_Engine",
	"--hidden-import", "tts",              # Explicitly include tts module
	"--hidden-import", "scipy.io.wavfile", # Explicitly include scipy.io.wavfile
	"--distpath", str(dist_dir),
	"--workpath", str(work_dir),
	"--specpath", str(work_dir),
	"--clean",
	str(src_main)
]
```

---

## Gap #7: FOMOD Compatibility ✅ ALREADY SUPPORTED

### Current State:
- FOMOD structure already exists
- info.xml and ModuleConfig.xml present

### Assessment:
✅ **Works with both MO2 and Vortex**

FOMOD is a universal standard supported by:
- Mod Organizer 2 ✅
- Vortex ✅
- Nexus Mod Manager ✅
- Manual installation ✅

Your current FOMOD structure with `<folder source="00 Core" destination="" />` will work perfectly for both MO2 and Vortex.

---

## Recommended Priority Actions

### 🔴 Priority 1: Bundle Piper (CRITICAL for one-click)

**Action:**
1. Download Piper Windows binary
2. Add `piper.exe` to `release_staging/core/Data/F4AI/`
3. Update `build_nexus_release.py` required files list
4. Modify code to use bundled Piper path

**Estimated time:** 30 minutes

### 🟡 Priority 2: Update Build Script

**Action:**
1. Update `tools/build_engine_executable.py` with hidden imports
2. Test executable build with all dependencies

**Estimated time:** 15 minutes

### 🟢 Priority 3: Documentation

**Action:**
1. Update FIRST_RUN.txt with KoboldCPP download links
2. Update Nexus description with clear prerequisites
3. Add troubleshooting for common issues

**Estimated time:** 20 minutes

---

## Updated Required Files Checklist

### Must Be Bundled in Package:
- [x] `F4AI_Core.esp` (plugin)
- [x] `*.pex` scripts (5 files)
- [x] `Fallout4_AI_Engine.exe` (Python bridge)
- [x] `en_US-lessac-medium.onnx` (voice model)
- [x] `en_US-lessac-medium.onnx.json` (voice config)
- [ ] **`piper.exe`** ← NEW REQUIREMENT
- [x] `config.json` (settings)
- [x] `Launch_F4AI_Bridge.bat` (launcher)
- [x] User documentation files

### External Dependencies (User Must Install):
- [ ] **KoboldCPP** - Document with download links
- [ ] **GGUF Model** - Suggest specific models with links
- [ ] **F4SE** - Standard mod requirement
- [ ] **Fallout 4** - Obviously required

### Optional Enhancements:
- [ ] CreationKit32.exe - For lip sync (optional)

---

## One-Click Installation Definition

For your mod to be truly **one-click**:

✅ **User installs mod via MO2/Vortex** → Files deploy to Data folder  
✅ **User downloads KoboldCPP** → External tool (documented)  
✅ **User downloads GGUF model** → External file (documented)  
✅ **User clicks Launch_F4AI_Bridge.bat** → Everything else works  

This is **reasonable one-click** for an AI mod. The only external dependencies are:
1. KoboldCPP (too large to bundle)
2. GGUF model (too large to bundle)

---

## Comparison: Current vs Fixed

### Current State (WITHOUT Piper bundled):
```
1. Install mod via MO2/Vortex ✅
2. Download and install Piper ❌ (extra step)
3. Add Piper to PATH ❌ (technical knowledge)
4. Download KoboldCPP ❌ (expected)
5. Download GGUF model ❌ (expected)
6. Run Launch_F4AI_Bridge.bat ✅
7. Launch game ✅
```
**Steps: 7** | **Technical steps: 5**

### Fixed State (WITH Piper bundled):
```
1. Install mod via MO2/Vortex ✅
2. Download KoboldCPP ❌ (expected, documented)
3. Download GGUF model ❌ (expected, documented)
4. Run Launch_F4AI_Bridge.bat ✅
5. Launch game ✅
```
**Steps: 5** | **Technical steps: 2**

---

## Conclusion

Your mod is **very close** to one-click installation, but needs:

1. **Bundle `piper.exe`** in the package (critical)
2. **Update build script** to include hidden imports (important)
3. **Improve documentation** for external dependencies (helpful)

Without bundling Piper, users will face:
- Download errors
- PATH configuration issues
- "Command not found" errors
- High support burden

**Recommendation: Bundle Piper for true one-click experience.**

---

## Next Steps

1. Read the detailed implementation guide: `BUNDLE_PIPER_GUIDE.md` (creating next)
2. Update build scripts
3. Test bundled executable
4. Verify FOMOD installation in MO2 and Vortex
5. Update documentation

