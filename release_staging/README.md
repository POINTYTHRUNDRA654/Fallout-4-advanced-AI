# Release staging (single core package)

Place all final shipping assets in `release_staging/core/` before building:

- `Data/F4AI_Core.esp`
- `Data/Scripts/F4AI_QueueManager.pex`
- `Data/Scripts/F4AI_FeedbackMonitor.pex`
- `Data/Scripts/F4AI_PushToTalkTrigger.pex`
- `Data/Scripts/F4AI_VisionWidgetManager.pex`
- `Data/Scripts/F4AI_InterNpcManager.pex`
- `Data/F4AI/Fallout4_AI_Engine.exe`
- `Data/F4AI/en_US-lessac-medium.onnx`
- `Data/F4AI/en_US-lessac-medium.onnx.json`

`config.json`, `Launch_F4AI_Bridge.bat`, `FIRST_RUN.txt`, and `NEXUS_TROUBLESHOOTING.txt`
are supplied by `packaging/nexus/core-template` and can be overridden by placing replacement files in `release_staging/core/Data/F4AI/`.

Build the Nexus archive:

```bash
python tools/build_nexus_release.py --version 0.1.0
```

Output:
- `dist/nexus/F4AI_Advanced_System_v0.1.0_Core_FOMOD.zip`
