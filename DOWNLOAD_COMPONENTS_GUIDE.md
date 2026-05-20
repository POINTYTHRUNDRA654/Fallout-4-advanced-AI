# 📥 DOWNLOAD GUIDE - Bundled Components

## ✅ Summary

For TRUE one-click installation, you need to download these components and place them in the staging directory before building:

---

## 📦 Required Downloads

### 1. **TinyLlama AI Model** (~668 MB) ⏳ REQUIRED

**Download URL:**
```
https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
```

**Save to:**
```
release_staging\core\Data\F4AI\models\tinyllama-1.1b-chat.gguf
```

**Method 1: PowerShell Script (Recommended)**
```powershell
.\download_model_improved.ps1
```

**Method 2: Browser Download**
1. Open URL in browser
2. Save file
3. Rename to `tinyllama-1.1b-chat.gguf`
4. Move to `release_staging\core\Data\F4AI\models\`

**License:** Apache 2.0 ✅ (can redistribute)

---

### 2. **KoboldCPP Runtime** (~15 MB) ⏳ REQUIRED

**Download URL:**
```
https://github.com/LostRuins/koboldcpp/releases/latest/download/koboldcpp.exe
```

**Save to:**
```
release_staging\core\Data\F4AI\runtime\koboldcpp.exe
```

**Method 1: PowerShell Script (Recommended)**
```powershell
.\download_koboldcpp_improved.ps1
```

**Method 2: Browser Download**
1. Go to: https://github.com/LostRuins/koboldcpp/releases/latest
2. Download `koboldcpp.exe`
3. Move to `release_staging\core\Data\F4AI\runtime\`

**License:** AGPL-3.0 ✅ (can bundle)

---

### 3. **Piper TTS** (~15 MB) ⏳ REQUIRED

**Download URL:**
```
https://github.com/rhasspy/piper/releases/latest/download/piper_windows_amd64.zip
```

**Extract and save:**
```
release_staging\core\Data\F4AI\piper.exe
```

**Method: Browser Download**
1. Open URL or go to: https://github.com/rhasspy/piper/releases/latest
2. Download `piper_windows_amd64.zip`
3. Extract `piper.exe`
4. Move to `release_staging\core\Data\F4AI\`

**License:** MIT ✅ (can redistribute)

---

### 4. **Voice Model** (~60 MB) ⏳ REQUIRED

**Download URLs:**
```
https://github.com/rhasspy/piper/releases/download/v0.0.2/en_US-lessac-medium.onnx
https://github.com/rhasspy/piper/releases/download/v0.0.2/en_US-lessac-medium.onnx.json
```

**Save to:**
```
release_staging\core\Data\F4AI\en_US-lessac-medium.onnx
release_staging\core\Data\F4AI\en_US-lessac-medium.onnx.json
```

**Method: Browser Download**
1. Download both files from URLs above
2. Move both to `release_staging\core\Data\F4AI\`

**License:** MIT ✅ (can redistribute)

---

## ✅ Verification Checklist

After downloading, verify all files exist:

```powershell
# Run this to check
Test-Path "release_staging\core\Data\F4AI\models\tinyllama-1.1b-chat.gguf"
Test-Path "release_staging\core\Data\F4AI\runtime\koboldcpp.exe"
Test-Path "release_staging\core\Data\F4AI\piper.exe"
Test-Path "release_staging\core\Data\F4AI\en_US-lessac-medium.onnx"
Test-Path "release_staging\core\Data\F4AI\en_US-lessac-medium.onnx.json"
```

All should return `True`

---

## 📁 Expected Directory Structure

```
release_staging\core\Data\F4AI\
├── models\
│   └── tinyllama-1.1b-chat.gguf          ✅ (~668 MB)
├── runtime\
│   └── koboldcpp.exe                     ✅ (~15 MB)
├── piper.exe                             ✅ (~15 MB)
├── en_US-lessac-medium.onnx              ✅ (~60 MB)
├── en_US-lessac-medium.onnx.json         ✅ (~1 KB)
├── AUTO_START.bat                        ✅ (already in template)
├── config.json                           ✅ (already in template)
└── ... (other template files)
```

---

## 📊 Download Summary

| Component | Size | Time (avg) | License |
|-----------|------|------------|---------|
| TinyLlama model | 668 MB | 5-10 min | Apache 2.0 ✅ |
| KoboldCPP | 15 MB | 1 min | AGPL-3.0 ✅ |
| Piper TTS | 15 MB | 1 min | MIT ✅ |
| Voice models | 60 MB | 2 min | MIT ✅ |
| **Total** | **~758 MB** | **~10-15 min** | **All redistributable** |

---

## 🚀 After Downloads Complete

### 1. Verify All Files
```powershell
python tools/setup_staging_directory.py
```

Should show all bundled components present.

### 2. Continue Build Process
```powershell
# Build Python executable
build_executable.bat

# (Do Creation Kit work for plugin + scripts)

# Build release package
build_release.bat
```

### 3. Final Package
- **Output:** `dist/nexus/*.zip`
- **Size:** ~1.8-2.0 GB
- **Contains:** Everything needed for one-click installation

---

## 🆘 Troubleshooting

### Large File Download Issues

**Problem:** Python urllib fails on large files  
**Solution:** Use PowerShell scripts or browser downloads

**Problem:** Connection timeout  
**Solution:** Try again, or download via browser

**Problem:** File incomplete  
**Solution:** Delete and re-download

### File Verification

```powershell
# Check file sizes
Get-Item "release_staging\core\Data\F4AI\models\tinyllama-1.1b-chat.gguf" | Select-Object Length
# Should be ~700 million bytes

Get-Item "release_staging\core\Data\F4AI\runtime\koboldcpp.exe" | Select-Object Length
# Should be ~15 million bytes
```

---

## 💡 Alternative: Manual Download Links

### All Downloads in One Place:

1. **TinyLlama:**  
   https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF

2. **KoboldCPP:**  
   https://github.com/LostRuins/koboldcpp/releases/latest

3. **Piper:**  
   https://github.com/rhasspy/piper/releases/latest

4. **Voice Models:**  
   https://github.com/rhasspy/piper/releases

Just click, download, and place in correct folders!

---

## ✨ Why This Works

### Legal ✅
- All licenses allow redistribution
- Proper attribution in CREDITS.txt
- Open source components

### Technical ✅
- TinyLlama optimized for CPU
- KoboldCPP portable (no installation)
- Piper works offline
- Total ~1.8-2.0 GB (acceptable for Nexus)

### User Experience ✅
- Single Nexus download
- No external dependencies
- AUTO_START.bat does everything
- True one-click!

---

**After downloading all 4 components, you're ready to build!**

**Total download time:** ~10-15 minutes  
**Build time:** ~30 minutes (after Creation Kit work)  
**Result:** True one-click installation for Nexus! 🎉

---

Mossy Industries - Advancing AI in Gaming
