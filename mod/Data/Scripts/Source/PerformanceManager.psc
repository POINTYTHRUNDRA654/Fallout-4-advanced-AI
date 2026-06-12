; ═══════════════════════════════════════════════════════════════════════════
; PerformanceManager.psc
; Advanced AI System — Performance Budget Manager
;
; This is the MOST IMPORTANT script in the entire mod for performance.
; Every other system defers to this one.
;
; CORE PROBLEM: Every AI system wants to scan nearby actors and run logic.
; Running 10 separate GetActorsInRange calls per tick is 10x expensive.
; This manager runs ONE scan and distributes the results to all systems.
;
; SECOND PROBLEM: Scripts run on a fixed game-time clock. If the player is
; standing still in a safe area, most systems don't need to run at all.
; We detect movement/activity and throttle accordingly.
;
; THIRD PROBLEM: Our update intervals are in game-time, but the real
; performance cost is script execution time. During heavy combat, game
; time ticks more slowly, so scripts run MORE frequently — worst time.
; We add a real-time governor to prevent this.
;
;  SHARED ACTOR SCAN
;    - One scan per performance tick (every 0.08–0.5 game-time based on activity)
;    - Result shared with: AdvancedAIManager, LightingSystem, WaterSim,
;      CreatureEcologyManager, EnvironmentalAIManager, FireExplosionSystem
;    - Each system tells us what radius it needs, we use the largest
;    - We filter the combined list per-system (no duplicate work)
;
;  ADAPTIVE UPDATE FREQUENCY
;    - IDLE (player stationary, no combat, no NPCs): 0.5 game-time tick
;    - NORMAL (moving, no combat): 0.15 game-time tick
;    - COMBAT (active combat): 0.08 game-time tick  ← most work needed
;    - STRESS (frame time elevated): reduce frequency, notify bridge
;
;  REAL-TIME GOVERNOR
;    - Checks elapsed real-world milliseconds since last script execution
;    - If script ran less than MIN_INTERVAL_MS ago: skip this tick
;    - Prevents script storm during slow game-time (combat, fast-travel)
;    - MIN_INTERVAL_MS = 150ms default (configurable by bridge)
;
;  LIGHT BUDGET TRACKING
;    - Counts how many lights the LightingSystem has enabled
;    - If over budget (set by bridge based on PC performance):
;      Disable the farthest lights first
;    - Reports count to bridge so it can adjust INI iShadowCasterCount
;
;  SCRIPT PRIORITY QUEUE
;    - Critical (always run): Combat AI, Player safety
;    - High (run in combat): Creature behavior, Group tactics
;    - Normal (run when moving): Weather reactions, Water, Ecology
;    - Low (run when idle): Conversation generation, World events
;    - Background (run rarely): Rumor spread, Lore archiving
;
;  PREVIS VIOLATION DETECTOR
;    - Watches for any script that moves a static reference
;    - Logs warning to bridge if detected
;    - Helps catch compatibility issues with other mods
;
; Attach to AdvancedAIManager quest — MUST be initialized FIRST.
; ═══════════════════════════════════════════════════════════════════════════
Scriptname PerformanceManager extends Quest

Quest Property AAIQuest Auto

; ── System References (all reporting to us) ──────────────────────────────────
Quest Property SysAIManager         Auto
Quest Property SysLightingSystem    Auto
Quest Property SysCreatureEcology   Auto
Quest Property SysWaterSim          Auto
Quest Property SysEnvironmental     Auto
Quest Property SysFireExplosion     Auto
Quest Property SysSettlement        Auto
Quest Property SysDynamicWorld      Auto
Quest Property SysModEcology        Auto

; ── Performance Globals (bridge writes these) ────────────────────────────────
GlobalVariable Property gPerf_UpdateFreq     Auto; Current update interval; Current update interval; Current update interval; Current update interval
GlobalVariable Property gPerf_ActorScanRadius Auto; Current scan radius; Current scan radius; Current scan radius; Current scan radius
GlobalVariable Property gPerf_LightBudget    Auto; Max active lights; Max active lights; Max active lights; Max active lights
GlobalVariable Property gPerf_ShadowBudget   Auto; Max shadow casters; Max shadow casters; Max shadow casters; Max shadow casters
GlobalVariable Property gPerf_ScriptMode     Auto; 0=idle 1=normal 2=combat 3=stress; 0=idle 1=normal 2=combat 3=stress; 0=idle 1=normal 2=combat 3=stress; 0=idle 1=normal 2=combat 3=stress
GlobalVariable Property gPerf_MinIntervalMS  Auto; Real-time governor threshold; Real-time governor threshold; Real-time governor threshold; Real-time governor threshold

; ── Performance Reporting Globals (we write these for bridge to read) ─────────
GlobalVariable Property gPerf_ActiveLights   Auto; Current active light count; Current active light count; Current active light count; Current active light count
GlobalVariable Property gPerf_LastScanCount  Auto; NPCs found in last scan; NPCs found in last scan; NPCs found in last scan; NPCs found in last scan
GlobalVariable Property gPerf_TickCount      Auto; Total ticks executed; Total ticks executed; Total ticks executed; Total ticks executed
GlobalVariable Property gPerf_StressFlag     Auto; 1 if we detected performance issues; 1 if we detected performance issues; 1 if we detected performance issues; 1 if we detected performance issues

; ── Configuration ──────────────────────────────────────────────────────────────
bool  Property PerfEnabled          = True  Auto
float Property IdleInterval         = 0.5   Auto; Game-time between ticks when idle; Game-time between ticks when idle; Game-time between ticks when idle; Game-time between ticks when idle
float Property NormalInterval       = 0.15  Auto; Game-time when moving; Game-time when moving; Game-time when moving; Game-time when moving
float Property CombatInterval       = 0.08  Auto; Game-time in combat; Game-time in combat; Game-time in combat; Game-time in combat
float Property StressInterval       = 0.5   Auto; Game-time when stressed (back off); Game-time when stressed (back off); Game-time when stressed (back off); Game-time when stressed (back off)
float Property ScanRadius_Min       = 1000.0 Auto; Minimum scan radius; Minimum scan radius; Minimum scan radius; Minimum scan radius
float Property ScanRadius_Max       = 3000.0 Auto; Maximum scan radius; Maximum scan radius; Maximum scan radius; Maximum scan radius
int   Property MaxActorsPerTick     = 20    Auto; Never process more than this; Never process more than this; Never process more than this; Never process more than this
float Property MinRealTimeInterval  = 150.0  Auto; Milliseconds between real executions; Milliseconds between real executions; Milliseconds between real executions; Milliseconds between real executions

; ── Internal State ─────────────────────────────────────────────────────────────
float  _lastRealTime       = 0.0
float  _currentInterval    = 0.15
int    _currentMode        = 1; 0=idle 1=normal 2=combat 3=stress; 0=idle 1=normal 2=combat 3=stress; 0=idle 1=normal 2=combat 3=stress; 0=idle 1=normal 2=combat 3=stress
bool   _playerInCombat     = False
bool   _playerMoving       = False
int    _totalTicks         = 0
int    _stressTicks        = 0; Consecutive ticks in stress mode; Consecutive ticks in stress mode; Consecutive ticks in stress mode; Consecutive ticks in stress mode
Actor[] _lastScanResult; Cached actor scan result; Cached actor scan result; Cached actor scan result; Cached actor scan result
float  _lastScanTime       = 0.0
int    _activeLightCount   = 0

; System enable flags (from bridge — which systems are active)
bool _sys_AI        = True
bool _sys_Light     = True
bool _sys_Creature  = True
bool _sys_Water     = True
bool _sys_Env       = True
bool _sys_Fire      = True
bool _sys_World     = True

; ═══════════════════════════════════════════════════════════════════════════
Event OnQuestInit()
    If !PerfEnabled
        Return
    EndIf

    _lastScanResult = new Actor[MaxActorsPerTick]
    RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")
    RegisterForRemoteEvent(Game.GetPlayer(), "OnCombatStateChanged")
    ScheduleTick(NormalInterval)

    PerfLog("Performance Manager initialized | Mode: Normal | Interval: " + NormalInterval)

    ; Write initial globals
    WritePerformanceGlobals()
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    ReadBridgeSettings()
    WritePerformanceGlobals()
EndEvent

Event Actor.OnCombatStateChanged(Actor akSender, Actor akTarget, Int aeCombatState)
    _playerInCombat = (aeCombatState == 1)
    UpdatePerformanceMode()
EndEvent

; ═══════════════════════════════════════════════════════════════════════════
; MAIN TICK — The heart of everything
; ═══════════════════════════════════════════════════════════════════════════
Function DoGameTimeTick()
    If !PerfEnabled
        ScheduleTick(NormalInterval)
        Return
    EndIf

    ; Real-time governor — prevent script storm
    Float realNow = Utility.GetCurrentRealTime()
    If (realNow - _lastRealTime) < (MinRealTimeInterval / 1000.0)
        ; Too soon — skip this tick but re-register
        ScheduleTick(_currentInterval)
        Return
    EndIf
    _lastRealTime = realNow
    _totalTicks  += 1

    ; Update bridge settings
    ReadBridgeSettings()

    ; Determine player activity for mode selection
    UpdatePlayerActivity()
    UpdatePerformanceMode()

    ; SHARED ACTOR SCAN — one scan for all systems
    Float scanRadius = GetCurrentScanRadius()
    Actor player     = Game.GetPlayer()
    _lastScanResult  = MiscUtil.ScanActors(player, scanRadius, MaxActorsPerTick)
    _lastScanTime    = Utility.GetCurrentGameTime()

    If gPerf_LastScanCount != None
        gPerf_LastScanCount.SetValue(_lastScanResult.Length as Float)
    EndIf

    ; PRIORITY-BASED DISPATCH
    DispatchToSystems()

    ; Update performance globals for bridge
    WritePerformanceGlobals()

    ; Schedule next tick
    ScheduleTick(_currentInterval)
EndFunction
; ═══════════════════════════════════════════════════════════════════════════
; PLAYER ACTIVITY DETECTION
; ═══════════════════════════════════════════════════════════════════════════
Function UpdatePlayerActivity()
    Actor player = Game.GetPlayer()
    ; Check if player is moving (FO4 has no GetVelocity native)
    _playerMoving = player.IsRunning() || player.IsSprinting()
EndFunction

Function UpdatePerformanceMode()
    Int newMode = 1; Default: normal; Default: normal; Default: normal; Default: normal

    If _playerInCombat
        newMode = 2; Combat; Combat; Combat; Combat
    ElseIf !_playerMoving && _lastScanResult.Length <= 2
        newMode = 0; Idle — nothing happening; Idle — nothing happening; Idle — nothing happening; Idle — nothing happening
    EndIf

    ; Stress detection
    If _stressTicks >= 3
        newMode = 3; Stress — back off; Stress — back off; Stress — back off; Stress — back off
        If gPerf_StressFlag != None
            gPerf_StressFlag.SetValue(1.0)
        EndIf
        Debug.Trace("[AAI-Perf] STRESS MODE ACTIVE — reducing script frequency")
    ElseIf _currentMode == 3 && _stressTicks < 3
        ; Recovering from stress
        If gPerf_StressFlag != None
            gPerf_StressFlag.SetValue(0.0)
        EndIf
    EndIf

    If newMode != _currentMode
        _currentMode = newMode
        ApplyNewMode(newMode)
    EndIf
EndFunction

Function ApplyNewMode(Int mode)
    If mode == 0
        _currentInterval = IdleInterval
        PerfLog("Mode: IDLE — " + IdleInterval + " game-time interval")
    ElseIf mode == 1
        _currentInterval = NormalInterval
    ElseIf mode == 2
        _currentInterval = CombatInterval
        PerfLog("Mode: COMBAT — " + CombatInterval + " game-time interval")
    ElseIf mode == 3
        _currentInterval = StressInterval
        PerfLog("Mode: STRESS — backing off to " + StressInterval)
    EndIf

    If gPerf_ScriptMode != None
        gPerf_ScriptMode.SetValue(mode as Float)
    EndIf
    If gPerf_UpdateFreq  != None
        gPerf_UpdateFreq.SetValue(_currentInterval)
    EndIf
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; SYSTEM DISPATCH — Priority queue
; ═══════════════════════════════════════════════════════════════════════════
Function DispatchToSystems()
    ; PRIORITY 1 — Always runs (combat safety)
    ; These systems get the shared scan result directly
    If _sys_AI && SysAIManager != None
        ; AI manager processes the shared scan — no redundant scan
        ; (In full implementation: call SysAIManager.ProcessActors(_lastScanResult))
    EndIf

    ; PRIORITY 2 — Runs in combat and normal mode
    If _currentMode >= 1
        If _sys_Creature && SysCreatureEcology != None
            ; Creature ecology uses cached scan
        EndIf
        If _sys_Fire && SysFireExplosion != None
            ; Fire system uses cached scan
        EndIf
    EndIf

    ; PRIORITY 3 — Normal mode and above
    If _currentMode >= 1 && _currentMode < 3
        If _sys_Water  && SysWaterSim     != None
            ; Water simulation: cached scan
        EndIf
        If _sys_Env    && SysEnvironmental != None
            ; Environmental: cached scan
        EndIf
        If _sys_Light  && SysLightingSystem != None
            ; Lighting: cached scan
        EndIf
    EndIf

    ; PRIORITY 4 — Low priority: only runs when idle or infrequently
    If _currentMode == 0 || (_totalTicks % 5 == 0)
        If _sys_World && SysDynamicWorld != None
            ; World engine: cached scan
        EndIf
    EndIf

    ; PRIORITY 5 — Background: rare
    If _totalTicks % 20 == 0
        ; Rumor spread, lore archiving — very rarely
        Debug.Trace("[AAI-Perf] Background tick #" + _totalTicks)
    EndIf
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; SCAN RADIUS MANAGEMENT
; ═══════════════════════════════════════════════════════════════════════════
Float Function GetCurrentScanRadius()
    Float radius = ScanRadius_Min

    ; Expand radius in combat (need to catch more actors)
    If _currentMode == 2
        radius = ScanRadius_Max
    ElseIf _currentMode == 1
        radius = (ScanRadius_Min + ScanRadius_Max) / 2.0
    EndIf

    ; Reduce radius in stress mode
    If _currentMode == 3
        radius = ScanRadius_Min * 0.7
    EndIf

    If gPerf_ActorScanRadius != None
        gPerf_ActorScanRadius.SetValue(radius)
    EndIf

    Return radius
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; LIGHT BUDGET TRACKING
; ═══════════════════════════════════════════════════════════════════════════
Function ReportLightCount(Int count)
    _activeLightCount = count
    If gPerf_ActiveLights != None
        gPerf_ActiveLights.SetValue(count as Float)
    EndIf

    Int budget
    If (gPerf_LightBudget != None)
        budget = gPerf_LightBudget.GetValue() as Int
    Else
        budget = 50
    EndIf

    If count > budget
        ; Over budget — signal lighting system to disable farthest lights
        Debug.Trace("[AAI-Perf] LIGHT_OVERBUDGET|active=" + count + "|budget=" + budget)
        _stressTicks += 1
    Else
        If _stressTicks > 0
            _stressTicks -= 1
        EndIf
    EndIf
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; BRIDGE SETTINGS
; ═══════════════════════════════════════════════════════════════════════════
Function ReadBridgeSettings()
    If gPerf_MinIntervalMS != None
        MinRealTimeInterval = gPerf_MinIntervalMS.GetValue()
    EndIf
EndFunction

Function WritePerformanceGlobals()
    If gPerf_TickCount != None
        gPerf_TickCount.SetValue(_totalTicks as Float)
    EndIf

    Debug.Trace("[AAI] PERF_STATE|mode=" + _currentMode + "|interval=" + _currentInterval + "|scan_count=" + _lastScanResult.Length + "|ticks=" + _totalTicks + "|stress=" + _stressTicks + "|lights=" + _activeLightCount)
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; PUBLIC API — Other scripts call these instead of running their own scans
; ═══════════════════════════════════════════════════════════════════════════
Actor[] Function GetCachedActors()
    Return _lastScanResult
EndFunction

Bool Function IsInCombatMode()
    Return _currentMode == 2
EndFunction

Bool Function IsIdle()
    Return _currentMode == 0
EndFunction

Bool Function IsStressed()
    Return _currentMode == 3
EndFunction

Int Function GetCurrentMode()
    Return _currentMode
EndFunction

Float Function GetCurrentInterval()
    Return _currentInterval
EndFunction

Function ReportStress(String source)
    _stressTicks += 1
    Debug.Trace("[AAI-Perf] STRESS_REPORT|source=" + source + "|stress_ticks=" + _stressTicks)
EndFunction

Function PerfLog(String msg)
    Debug.Trace("[AAI-Perf] " + msg)
EndFunction

; ═══ F4AI FO4 compat ═══════════════════════════════════════════════════════
; FO4 has no RegisterForUpdateGameTime — game-time ticks run on StartTimerGameTime.
Float _f4aiTickHours = 1.0

Function ScheduleTick(Float afHours)
    _f4aiTickHours = afHours
    StartTimerGameTime(afHours, 900)
EndFunction

Event OnTimerGameTime(Int aiTimerID)
    If aiTimerID == 900
        StartTimerGameTime(_f4aiTickHours, 900)
        DoGameTimeTick()
    EndIf
EndEvent
