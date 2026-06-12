# F4AI Master Framework Dependencies
# Download all of these and set them as masters before building new systems.
# Last scanned: June 2026

---

## TIER 1 — REQUIRED FOUNDATIONS (every system depends on these)

### F4SE — Fallout 4 Script Extender
- **Nexus:** https://www.nexusmods.com/fallout4/mods/42147
- **Why:** Everything else requires it. Already using it.
- **Use in our mod:** RegisterForKey, RegisterForControl, raycast, all native extensions.

### Address Library for F4SE Plugins
- **Nexus:** https://www.nexusmods.com/fallout4/mods/47327
- **Why:** Required by most modern F4SE plugins. Version-independent offsets.
- **Updated:** December 2025 — actively maintained.
- **Use in our mod:** Required dependency for SUP F4SE, Garden of Eden, Lighthouse.

### PapyrusUtil (MiscUtil / StringUtil / JsonUtil)
- **Already in use** (MiscUtil.WriteToFile, ReadFromFile, etc.)
- **Use in our mod:** All file IPC. Keep as-is.

---

## TIER 2 — SCRIPTING POWER (unlocks what vanilla Papyrus cannot do)

### ⭐ HYDRA — Primary Scripting Framework (REPLACES Papyrus Common Library)
- **Nexus:** https://www.nexusmods.com/fallout4/mods/93653
- **Supports:** Old-Gen, Next-Gen, and Anniversary Edition
- **Why:** 2800+ Papyrus functions, data structures that Papyrus has never had
  (hash-maps, hash-sets, mutexes, 64-bit integers/floats), engine patches that
  make native function calls up to 1600x faster, and — most importantly for F4AI
  — the Script Object Runner: bind scripts to game forms via JSON files under
  Data/Hydra/ScriptObjects/ with no CK work at all. This eliminates the entire
  CK quest-form setup burden for every monitor script we need to write.
- **Subsystems critical to F4AI:**

  **Script Object Runner** — `Data/Hydra/ScriptObjects/*.json`
  Bind any script to any form (Actor, Quest, Reference, etc.) purely through
  JSON. No CK. No dummy quests. CombatMonitor, WorldMonitor, EcosystemMonitor,
  CreatureDirector, and NPCDirector all launch this way.
  ```json
  { "script": "F4AI_CombatMonitor", "form": "0x000A91A2" }
  ```

  **Script Function Runner** — `Data/Hydra/ScriptFunctions/*.json`
  Register OnPostLoadGame / OnGameLoaded callbacks via JSON. Our world-state
  initialization runs on game load without quest wrappers.

  **Hydra:SaveMap / Hydra:TempMap** — persistent and in-memory hash-maps.
  Store per-NPC combat patterns, relationship scores, territory ownership, and
  season counters as proper key→value maps inside Papyrus. Replaces the clunky
  array-of-actors workarounds and reduces H-drive file I/O for game-state data.
  ```papyrus
  Hydra_SaveMap.SetFloat("NPC_" + npcID + "_hostility", hostilityScore)
  Hydra_SaveMap.SetFloat("NPC_" + npcID + "_territory_x", territoryX)
  Hydra_TempMap.SetBool("combat_active_" + npcID, true)
  ```

  **Hydra:Mutex** — thread-safe Papyrus operations.
  Critical for F4AI: multiple scripts (CombatMonitor, EcosystemMonitor,
  NPCDirector) all touch the same bridge_input.json concurrently. Mutex prevents
  race conditions. Also protects SaveMap writes from concurrent script access.

  **Hydra:IO:Json** — real JSON parsing in Papyrus.
  QueueManager currently does fragile manual StringUtil.Find() to parse
  bridge_output.json. Hydra:IO:Json replaces all of that with proper key lookup.
  ```papyrus
  Var subtitleText = Hydra_Json.GetKey(rawJson, "subtitle_text")
  Var emotionID = Hydra_Json.GetKey(rawJson, "emotion_id")
  ```

  **Hydra:Sky** — direct sky/weather scripting.
  Set weather type, fog density, sky color, precipitation intensity from Papyrus.
  Powers our seasonal weather transitions without requiring external weather mods.

  **Hydra:Timer** — proper timer callbacks.
  Replace Utility.Wait polling loops with event-driven timer callbacks. Our
  ecosystem scan (currently a While loop) becomes a RegisterForHydraTimer call.

  **Hydra:Regex** — regex in Papyrus.
  Parse emotion tags from AI output (`\[(NORMAL|ANGRY|SAD|WHISPER)\]`) directly
  in Papyrus rather than doing it in Python then passing the tag separately.

  **Script Reflection Runner** — hook existing scripts without modifying them.
  Intercept vanilla NPC combat script functions to feed combat events into our
  Mossy learning pipeline. No edits to base game scripts = no conflicts.

  **Menu Runner** — `Data/Hydra/Menus/*.json`
  Define custom Flash menus via JSON without SWF compilation. Replaces the
  Debug.Notification approach for dialogue display. Build a proper subtitle box
  with NPC name header, emotion indicator, and response text.

  **File Cache Runner** — cache frequently read files in memory.
  Cache config.json, creature territory maps, and season data in memory.
  Eliminates repeated disk reads in our 100ms polling loop.

  **AS3 Code Object** — call Papyrus functions asynchronously from Flash UI.
  Makes HUDFramework widget communication bidirectional and non-blocking.

  **Engine Patch (opt-in)** — native Papyrus function calls up to 1600x faster.
  Our polling-heavy architecture benefits enormously. The frame-queuing delay
  that makes Utility.Wait unreliable at short intervals is addressed by this
  patch. Enable in Hydra's MCM.

### ~~SUP F4SE-NG~~ — ABANDONED, DO NOT USE
- **Status:** No updates in 2+ years. Abandoned F4SE plugin = potential crash
  with any game patch and no fix ever coming. Dropped.
- **Replacement:** Hydra's 2800+ functions cover everything SUP provided and more.

### Garden of Eden Papyrus Script Extender
- **Nexus:** https://www.nexusmods.com/fallout4/mods/74160
- **Why:** 80+ additional native functions. Adds weather set/get, camera
  position, animation events, cell fog, LOD control, condition results.
- **Key functions for our systems:**
  - SetWeatherSounds — control weather audio per-season
  - GetCameraPosition — vision system positioning
  - SendAnimationEvent — creature/NPC animation triggers
  - GetConditionResults — AI condition evaluation
  - GetClosestNodeToPosition — navmesh/territory queries

### Lighthouse Papyrus Extender
- **Nexus:** https://www.nexusmods.com/fallout4/mods/71420
- **Status:** SUPERSEDED by Hydra (2800+ functions vs 187). Only pull in if a
  specific Lighthouse function is needed that neither Hydra nor SUP provides.
  Do not use as a general scripting dependency.

### Creation Framework
- **GitHub only** (not on Nexus): https://github.com/F4CF/Creation-Framework
- **Install:** `gh repo clone F4CF/Creation-Framework`
- **Why:** General purpose scripting library. Utility functions for mod authors.
- **Use in our mod:** Utility glue where needed.

---

## TIER 3 — UI & DISPLAY (makes responses visible and professional)

### FallUI Suite (HUD + Inventory + Workbench + Map)
- **Nexus HUD:** https://www.nexusmods.com/fallout4/mods/51813
- **Why:** Full HUD replacement with HUDFramework support built in, MCM
  layout manager, widget positioning. Replaces Debug.Notification with
  proper subtitle panels. Actively maintained 2025.
- **Use in our mod:** Display AI dialogue responses as proper subtitle widgets
  instead of toast notifications. NPC name + response text + emotion indicator.

### HUDFramework
- **Nexus:** https://www.nexusmods.com/fallout4/mods/20309
- **Why:** The underlying API that lets mods add custom HUD elements.
  FallUI uses it. We use it directly to push dialogue panels.
- **Use in our mod:** F4AI_DialogueWidget — custom subtitle box for NPC responses.

### Extended Dialogue Interface (XDI)
- **Nexus:** https://www.nexusmods.com/fallout4/mods/27216
- **GitHub:** https://github.com/reg2k/xdi
- **Why:** Removes the vanilla 4-option dialogue limit. Scrollable dialogue
  menus. Number key selection. THIS is how players pick follow-up questions.
- **Use in our mod:** Player can see AI-generated response options and choose
  what to say next. Turns our dialogue from one-way broadcast to real conversation.

### ~~MCM Helper~~ — WAITING FOR UPDATE, SKIP FOR NOW
- **Status:** Pending compatibility update. Don't depend on it.
- **Fallback A:** F4Settings (see below) — actively maintained 2025.
- **Fallback B:** Hydra's Menu Runner — define our settings UI in JSON under
  Data/Hydra/Menus/ with no SWF compilation needed. Most likely our primary
  approach given we're deep in Hydra already.
- **Fallback C:** config.json direct editing — already works, fine for alpha.

### F4Settings — In-Game Settings Manager
- **Nexus:** https://www.nexusmods.com/fallout4/mods/105617
- **Why:** Actively maintained 2025. Use this over MCM Helper until MCM catches up.
- **Use in our mod:** In-game toggles for enable_stt, enable_mossy_bridge,
  speech_speed, activation mode (controller/keyboard), debug mode.

---

## TIER 4 — NPC & AI BEHAVIOR (layer our Mossy directives on top of these)

### Fallout 4 AI Overhaul
- **Nexus:** https://www.nexusmods.com/fallout4/mods/57741
- **Why:** Reworks default AI packages, adds custom markers in Diamond City
  and Goodneighbor, makes NPCs seek shelter during radstorms. Daily routine
  improvements. USE AS MASTER — our Mossy directives tune on top of its packages.
- **Key integration:** NPCs already seek shelter in radstorms. Our weather
  system amplifies this rather than replacing it.

### Fallout 4 Enhanced — NPCs
- **Nexus:** https://www.nexusmods.com/fallout4/mods/79970
- **Why:** NPCs eat, hunt, scavenge, loot, rest, visit. More alive daily
  routines. USE AS MASTER for the NPC behavior layer.

### More NPCs Sandbox Expansion
- **Nexus:** https://www.nexusmods.com/fallout4/mods/37579
- **Why:** Modifies DefaultSandboxExteriorEditorLocation used by hundreds
  of NPCs. Wider sandbox ranges, more varied behavior.

### Advanced AI Tweaks
- **Nexus:** https://www.nexusmods.com/fallout4/mods/27763
- **Why:** Combat, stealth, detection, sandbox behavior upgrades. Tune
  combat detection ranges and reaction speeds.

### Combat AI Uncapped
- **Nexus:** https://www.nexusmods.com/fallout4/mods/66446
- **Updated:** June 2025
- **Why:** NPC combat behavior overhaul, works with Next-Gen update.

### Combat AI Empowered
- **Nexus:** https://www.nexusmods.com/fallout4/mods/72678
- **Why:** Modifies combat styles, accuracy, enemy AI behaviors.

### MORE AI MORE NPCs
- **Nexus:** https://www.nexusmods.com/fallout4/mods/82635
- **Why:** Raises simultaneous working AI cap from 20 to 128/255.
  CRITICAL for ecosystem simulation — without this only 20 creatures/NPCs
  can run AI at once. Our predator/prey system needs more than 20.

---

## TIER 5 — CREATURE ECOSYSTEM (build our system alongside these)

### Mutant Menagerie — Life Finds A Way
- **Nexus:** https://www.nexusmods.com/fallout4/mods/68187
- **Why:** Dynamic leveled spawns split into predators and prey, region-specific
  ecosystems across Commonwealth biomes. THIS IS THE ECOSYSTEM FOUNDATION.
  Set as master, our Mossy ecosystem AI directs behavior within its population.

### Enhanced Creatures AI Overhaul
- **Nexus:** https://www.nexusmods.com/fallout4/mods/78179
- **Updated:** January 2024
- **Why:** Group combat behaviors (Mirelurks blind prey while crabs engage
  melee). Tactical creature AI. Layer our directives on top.

### Wildlife Overhaul — Less Aggressive Creatures
- **Nexus:** https://www.nexusmods.com/fallout4/mods/49792
- **Why:** Prey creatures flee instead of attacking. Deer scared of humans.
  Insects require close approach. Real prey behavior baseline.

### Less Foolhardy Creatures
- **Nexus:** https://www.nexusmods.com/fallout4/mods/98337
- **Updated:** November 2025
- **Why:** Predator variants more confident. Sets behavioral differentiation
  between predator and prey creature variants.

### Predators — The Concrete Jungle
- **Nexus:** https://www.nexusmods.com/fallout4/mods/56880
- **Why:** Predator AI behaviors in urban environments.

---

## TIER 6 — WEATHER & SEASONS (sync our seasonal system with these)

### Seasons Change — A Merry Modding Days Mod (v3.1)
- **Nexus:** https://www.nexusmods.com/fallout4/mods/76710
- **Updated:** May 2025 — actively maintained
- **Why:** Uses Papyrus globals to control weather probability per season.
  Has xEdit integration script for automatic compatibility patching.
  Set as master — read its season globals to stay in sync.
- **Integration:** Our WorldMonitor.psc reads SeasonsChange globals to know
  current season rather than tracking independently.

### Seasonal Weather for Seasons Change — Vivid Weathers
- **Nexus:** https://www.nexusmods.com/fallout4/mods/98889
- **Updated:** December 2025
- **Why:** Adds complex seasonal weather to Seasons Change + Vivid Weathers.

### Vivid Weathers — FO4 Edition
- **Nexus:** https://www.nexusmods.com/fallout4/mods/15466
- **Why:** Weather overhaul with volume sliders for rain/thunder. Our weather
  directives push Vivid Weathers records, not vanilla ones.

### True Storms — Wasteland Edition
- **Search Nexus for "True Storms Fallout 4"**
- **Why:** Realistic storm system. If installed, our Radstorm weather directives
  use True Storms records.

### Threads of the Seasons
- **Nexus:** https://www.nexusmods.com/fallout4/mods/102097
- **Why:** Newer seasonal framework (2024+). Check if it supersedes
  Seasons Change for our use case.

### MS Weather Control
- **Nexus:** https://www.nexusmods.com/fallout4/mods/97218
- **Why:** Scripted weather control API. May be the right hook for our
  Python→Papyrus weather directives.

---

## HYDRA ARCHITECTURE IMPACT — HOW THIS CHANGES EVERYTHING

The most transformative thing Hydra does for F4AI is eliminate the CK dependency
for script attachment. Here is the before/after for every planned monitor script:

### Before Hydra (the painful way)
```
1. Open Creation Kit
2. Create a dummy Quest form (F4AI_CombatMonitorQuest)
3. Add script F4AI_CombatMonitor to quest's Script tab
4. Assign quest stage triggers
5. Repeat for WorldMonitor, EcosystemMonitor, CreatureDirector, NPCDirector
6. Save .esp, reopen to verify
7. Re-do if script changes break the form binding
```

### After Hydra (JSON config, no CK)
Create `Data/Hydra/ScriptObjects/F4AI_Monitors.json`:
```json
[
  {
    "script": "F4AI_CombatMonitor",
    "bindTo": "PlayerRef",
    "events": ["OnPostLoadGame"]
  },
  {
    "script": "F4AI_WorldMonitor",
    "bindTo": "PlayerRef",
    "events": ["OnPostLoadGame"]
  },
  {
    "script": "F4AI_EcosystemMonitor",
    "bindTo": "PlayerRef",
    "events": ["OnPostLoadGame"]
  },
  {
    "script": "F4AI_CreatureDirector",
    "bindTo": "PlayerRef",
    "events": ["OnPostLoadGame"]
  },
  {
    "script": "F4AI_NPCDirector",
    "bindTo": "PlayerRef",
    "events": ["OnPostLoadGame"]
  }
]
```
That's it. No CK. All five monitors start on game load automatically.

### Hydra:SaveMap — NPC State Storage
Instead of writing per-NPC JSON files to H:\Mossy Memory\ for everything,
use SaveMap for in-game state that only Papyrus needs:
```papyrus
; Store combat learning data
Hydra_SaveMap.SetFloat("cmbt_" + npcEditorID + "_fleeHP", fleeThreshold)
Hydra_SaveMap.SetBool("cmbt_" + npcEditorID + "_prefersCover", true)
Hydra_SaveMap.SetInt("eco_territory_" + regionID + "_apex", apexCreatureFormID)

; Read it back next session — persists in save game
Float threshold = Hydra_SaveMap.GetFloat("cmbt_" + npcEditorID + "_fleeHP")
```
H:\Mossy Memory\ is still used for large AI memories, training data, and
relationship logs — but light game-state (combat prefs, territory ownership,
last-seen location) lives in SaveMap and survives save/load automatically.

### Hydra:Mutex — Race Condition Fix
CombatMonitor, EcosystemMonitor, and the PushToTalk trigger all write to the
bridge in parallel. Mutex prevents them from stepping on each other:
```papyrus
Hydra_Mutex mtx = Hydra_Mutex.Acquire("F4AI_BridgeLock")
MiscUtil.WriteToFile(InputPath, jsonPayload, append = false)
Hydra_Mutex.Release(mtx)
```

### Hydra:IO:Json — Replace String Parsing in QueueManager
Current QueueManager has 30+ lines of StringUtil.Find() hacks to parse JSON.
Replace with:
```papyrus
String rawJson = MiscUtil.ReadFromFile(OutputPath)
String subtitle = Hydra_Json.GetString(rawJson, "subtitle_text")
Float duration  = Hydra_Json.GetFloat(rawJson, "display_duration")
Int emotionID   = Hydra_Json.GetInt(rawJson, "emotion_id")
```

### Hydra:Regex — Parse Emotion Tags In Papyrus
Instead of Python stripping `[ANGRY]` before writing text_out.txt, Papyrus
can parse it directly:
```papyrus
String rawText = MiscUtil.ReadFromFile(TextOutPath)
String emotionTag = Hydra_Regex.Match(rawText, "\\[(NORMAL|ANGRY|SAD|WHISPER)\\]")
String cleanText  = Hydra_Regex.Replace(rawText, "\\[\\w+\\]\\s*", "")
```

---

## INTEGRATION STRATEGY

When our mod detects these in the load order (via plugins.txt), it adjusts:

| Detected mod           | Our behavior change                                      |
|------------------------|----------------------------------------------------------|
| Hydra                  | Use Script Object Runner for all monitor scripts; use    |
|                        | SaveMap for NPC state; use Hydra:IO:Json for all parsing |
| Seasons Change         | Read its season globals instead of tracking our own      |
| Vivid Weathers         | Push weather directives using VW weather records         |
| True Storms            | Use TS storm records for radstorm/rain events            |
| FO4 AI Overhaul        | Use its packages as base, add Mossy tuning on top        |
| Mutant Menagerie       | Use its creature populations for ecosystem tracking      |
| MORE AI MORE NPCs      | Raise our creature scan radius (more AI budget available)|
| XDI                    | Enable multi-option player dialogue responses            |
| FallUI / HUDFramework  | Use HUDFramework API for dialogue display widget         |
| F4Settings / Hydra Menu| Register our settings in-game instead of config.json only|

---

## DOWNLOAD PRIORITY ORDER

1. F4SE (required first — everything depends on it)
2. Address Library for F4SE Plugins (required by #3-7)
3. **Hydra** ← NEW #3 — Script Object Runner eliminates CK work entirely
4. Garden of Eden Papyrus Script Extender (weather audio, camera, animation)
5. PapyrusUtil — MiscUtil/StringUtil (still needed for file IPC)
7. HUDFramework (required by FallUI)
8. FallUI HUD
9. XDI (removes 4-option dialogue limit — test AE version for compatibility)
10. F4Settings (replaces MCM Helper until it gets updated)
11. MORE AI MORE NPCs (CRITICAL — raises AI cap from 20 to 128/255)
12. Mutant Menagerie (ecosystem creature populations)
13. FO4 AI Overhaul (base NPC behavior packages)
14. Fallout 4 Enhanced NPCs (eat/sleep/scavenge routines)
15. Seasons Change (season globals we sync to)
16. Vivid Weathers + Seasonal Weather patch
17. Wildlife Overhaul (prey flee behavior baseline)
18. Enhanced Creatures AI Overhaul (group creature tactics)
19. Less Foolhardy Creatures (predator confidence differentiation)
20. Combat AI Uncapped / Empowered
21. More NPCs Sandbox Expansion
22. Predators — The Concrete Jungle
