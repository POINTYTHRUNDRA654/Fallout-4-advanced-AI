# Creation Kit Build Guide
## Fallout 4 Advanced AI — Mossy Industries

This guide covers everything you need to do in FO4Edit and the Creation Kit
to get the mod compiling and running. Most form references are now self-resolved
in `OnInit` via `Game.GetForm()` — so **no manual property assignment in CK** is needed.

---

## Step 1 — FO4Edit: Look up 3 FormIDs

Open **xEdit (FO4Edit)** and load the following plugins. For each lookup,
right-click the record and choose **Copy as FormID**.

### 1a. Build budget global — ✅ NOT NEEDED

The mod uses **Sim Settlements 2**, which manages its own plot-based build system
(255 objects/plot, 128 plots/settlement). The vanilla `WorkshopObjectSizeLimit`
global does not control SS2's limits. Mossy now tracks estimated plot usage and
recommends efficient plot types instead of trying to raise a vanilla global.
No FO4Edit action required.

### 1b. Seasons.esm globals — ✅ DONE

- Plugin: **`Seasons.esm`**
- Season global EditorID: `GlobalSeason`, local FormID **`0x002B1E3D`**
- No season-day global exists — day is computed from vanilla `GameDaysPassed`
- Already wired into `F4AI_WorldMonitor.psc` — no action needed

### 1c. Verify Triangle Workshop IDs

- Load `Fallout4.esm`
- Navigate: **Quest** → `WorkshopParent` (FormID 0x0002058E)
- Find the Workshops array and look for Sanctuary Hills (ID 0), Red Rocket Truck Stop (ID 1), Abernathy Farm (ID 5)
- If any IDs differ, update the `Const` properties at the top of:
  - `papyrus/F4AI_SettlementMonitor.psc`
  - `papyrus/F4AI_MinutemanNetwork.psc`

---

## Step 2 — Set up the .esp in Creation Kit

1. Open **Creation Kit** (launch via MO2 so load order is applied)
2. **File → Data** → load `Fallout4.esm` and any masters needed by your mod
   (at minimum: `Fallout4.esm`, `DLCCoast.esm`, `DLCRobot.esm`, `DLCNukaWorld.esm`,
   `Seasons Change.esp`, and your mod's `.esp` if it already exists)
3. If starting fresh: **File → Save** to create `F4AI_MossyIndustries.esp`

> **Note:** You do NOT need to attach scripts to any Quest in CK.
> All scripts bind to PlayerRef automatically via
> `Data/Hydra/ScriptObjects/F4AI_Monitors.json` at runtime.

---

## Step 3 — Copy scripts to the CK source folder

The CK compiler looks in `Data/Scripts/Source/`. Copy all `.psc` files:

```
D:\Projects\Fallout-4-advanced-AI\papyrus\*.psc
  → E:\Steam\steamapps\common\Fallout 4\Data\Scripts\Source\User\
```

(Create the `User\` subfolder if it doesn't exist — CK uses it for non-vanilla scripts.)

---

## Step 4 — Compile all scripts

**Option A — CK script compiler (GUI):**

1. In CK: **Gameplay → Papyrus Scripts...**
2. In the search box filter by `F4AI_`
3. Select all 7 scripts:
   - `F4AI_CombatMonitor`
   - `F4AI_WorldMonitor`
   - `F4AI_EcosystemMonitor`
   - `F4AI_CreatureDirector`
   - `F4AI_NPCDirector`
   - `F4AI_SettlementMonitor`
   - `F4AI_MinutemanNetwork`
4. Click **Compile** (bottom right)
5. Watch the output log — green = success, red = error (see Troubleshooting below)
6. Compiled `.pex` files land in `Data/Scripts/`

**Option B — command line (faster for recompiles):**

```bat
cd "E:\Steam\steamapps\common\Fallout 4"
"Papyrus Compiler\PapyrusCompiler.exe" "Data\Scripts\Source\User\F4AI_CombatMonitor.psc" ^
  -f="Institute_Papyrus_Flags.flg" ^
  -i="Data\Scripts\Source\;Data\Scripts\Source\User\" ^
  -o="Data\Scripts\"
```

Repeat for each script, or batch them. The `-f` flag file is in `Data\Scripts\Source\`.

---

## Step 5 — Copy compiled scripts to MO2

MO2 needs the `.pex` files inside the mod's own folder, not the base game Data:

```
E:\Steam\steamapps\common\Fallout 4\Data\Scripts\F4AI_*.pex
  → E:\Mod.Organizer-2.5.2 Game Mods\Fallout 4 Advanced AI - Mossy Industries\Data\Scripts\
```

MO2 VFS will then overlay them at runtime.

---

## Step 6 — Verify Hydra ScriptObjects JSON is deployed

Make sure this file exists in the MO2 mod folder:

```
E:\Mod.Organizer-2.5.2 Game Mods\Fallout 4 Advanced AI - Mossy Industries\
  Data\Hydra\ScriptObjects\F4AI_Monitors.json
```

This is what tells Hydra to bind all 7 scripts to PlayerRef on game load.
It's already written at `D:\Projects\Fallout-4-advanced-AI\Data\Hydra\ScriptObjects\F4AI_Monitors.json`.

---

## Step 7 — Test in-game

1. Launch FO4 via MO2
2. Open the console (`~`) and type: `cgf "Debug.Trace" "F4AI test"`
   (just to confirm console works)
3. Load a save near a settlement
4. Open console and type: `sqv WorkshopParent`
   — verify it shows the Workshops array populated
5. Wait ~30 seconds — check `E:\Steam\steamapps\common\Fallout 4\Data\F4AI\`
   for `world_state.json` appearing (written by WorldMonitor)
6. If `world_state.json` appears: scripts are running ✓

---

## Troubleshooting

### "Property WorkshopParent is None"
The `Game.GetForm(0x0002058E)` call failed. Verify the FormID in FO4Edit —
confirm it's `WorkshopParent` in `Fallout4.esm`. Should not normally fail.

### Script compiles but doesn't run
- Check Hydra is installed and active in MO2
- Check `F4AI_Monitors.json` is in `Data\Hydra\ScriptObjects\`
- Check Hydra Script Object Runner is enabled in Hydra's MCM (or config)

### Season always reads "Summer"
The SC_Season global wasn't resolved — the `Game.GetFormFromFile` lines in
`F4AI_WorldMonitor.psc` are still commented out. Complete Step 1b above.

### Build budget not raising
The `WorkshopBudgetGlobal` line in `F4AI_SettlementMonitor.psc` is still
commented out. Complete Step 1a above. Until then, build budget is unchanged
but everything else works fine.

### Compile error: "unknown type WorkshopParentScript"
Copy `WorkshousParentScript.psc` from `Data\Scripts\Source\` (it ships with FO4)
into your source path. Also ensure all Hydra source files are on the `-i` include path.

---

## Summary of what DOESN'T need CK

Thanks to Hydra Script Object Runner + `Game.GetForm()` self-resolution:
- ✅ No Quest attachment in CK
- ✅ No manual property filling in CK  
- ✅ WorkshopParent auto-resolved (FormID 0x0002058E)
- ✅ MinutemanFaction auto-resolved (FormID 0x0002A8A8)
- ✅ GameHour auto-resolved (FormID 0x00000039)
- ✅ SS2 build limits — no global needed; Mossy tracks plot usage (255 obj/plot, 128 plots max)
- ✅ SC_Season — wired to `GlobalSeason` (0x002B1E3D in Seasons.esm)
- ✅ Season day — computed from vanilla GameDaysPassed mod 30
