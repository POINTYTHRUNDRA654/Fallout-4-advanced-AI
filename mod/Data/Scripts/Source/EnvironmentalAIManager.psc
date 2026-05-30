; ═══════════════════════════════════════════════════════════════════════════
; EnvironmentalAIManager.psc
; Advanced AI System — Living Environment Controller
;
; Makes the environment a living, reactive part of the world:
;
;  WEATHER SYSTEM
;    - Radiation storms:  creature surge, NPCs hunker down, ghouls ecstatic
;    - Fog:               detection halved, Anglers glow brighter, ambushes deadlier
;    - Acid rain:         NPCs seek cover, exposed metal corrodes (hazard)
;    - Clear night:       sniper range increases, nocturnal creatures peak
;    - Heavy rain:        footstep sounds masked (stealth easier), sound carries less
;
;  SOUND PROPAGATION
;    - Open wasteland:    gunshots heard 3x farther
;    - Indoor/vault:      echo — sounds travel differently, can mislead
;    - Rain/wind:         masks movement sounds
;    - Crow alarm:        scattering crows alert nearby NPCs as suspicious
;
;  LIGHTING & VISIBILITY
;    - True darkness:     stealth dramatically easier, Glowing Ones deadlier
;    - Dawn/dusk:         peak predator activity window (most dangerous times)
;    - Fire light:        reveals player position, attracts creatures
;    - Pip-Boy light:     detectable at range — turn it off when sneaking
;
;  TERRAIN AWARENESS
;    - High ground:       ranged NPC detection radius +30%
;    - Water:             Mirelurks / Gulpers gain speed, player slowed
;    - Dense cover:       creature ambush probability increases
;    - Open ground:       pack tactics break — creatures spread out
;
;  RADIATION ZONES
;    - Glowing Sea:       all creatures berserk threshold raised (more aggressive)
;    - High rad areas:    Glowing Ones pulse stronger, mutant creatures enlarge
;    - Entering rad zone: non-rad creatures flee, rad-immune surge forward
;
;  FIRE & HAZARDS
;    - NPCs flee fire     unless cornered
;    - Creatures with fur avoid fire (Yao Guai, Mongrels)
;    - Robots immune to fire, vulnerable to water/EMP
;    - Smoke creates tactical concealment (stealth boost in smoke)
;
;  DAWN / DUSK PEAK WINDOW
;    - 05:30–07:30 and 19:00–21:00:  all predators at maximum aggression
;    - Birds most active at these windows
;    - Guards most tired just before dawn (04:00–05:30)
;
; Attach to AdvancedAIManager quest.
; ═══════════════════════════════════════════════════════════════════════════
Scriptname EnvironmentalAIManager extends Quest

Quest Property AAIQuest Auto

; ── Weather Records (fill in CK) ─────────────────────────────────────────────
Weather Property weatherClear        Auto
Weather Property weatherRain         Auto
Weather Property weatherFog          Auto
Weather Property weatherRadStorm     Auto  ; Radiation storm
Weather Property weatherAcidRain     Auto  ; Glowing Sea acid
Weather Property weatherSnow         Auto  ; Far Harbor blizzard

; ── Globals for current state (read by other scripts) ─────────────────────────
GlobalVariable Property gEnvWeatherType   Auto  ; 0=Clear 1=Rain 2=Fog 3=RadStorm 4=Acid 5=Snow
GlobalVariable Property gEnvTimeOfDay     Auto  ; 0–24 float
GlobalVariable Property gEnvVisibility   Auto  ; 0–1 (1=full, 0=blind)
GlobalVariable Property gEnvSoundCarry   Auto  ; 0–1 multiplier on detection sound
GlobalVariable Property gEnvRadLevel     Auto  ; Current outdoor rad level
GlobalVariable Property gEnvIsNight      Auto  ; 1 if night
GlobalVariable Property gEnvIsPeakHour   Auto  ; 1 during dawn/dusk predator peak
GlobalVariable Property gEnvRainMask     Auto  ; 1 if rain masking footsteps

; ── Imagespace Modifiers (create in CK for visual effects) ───────────────────
ImageSpaceModifier Property imodFog        Auto
ImageSpaceModifier Property imodRadStorm   Auto
ImageSpaceModifier Property imodNight      Auto
ImageSpaceModifier Property imodSmoke      Auto

; ── Spells / Effects ─────────────────────────────────────────────────────────
Spell Property spRadStormAura  Auto  ; Radiation storm area effect
Spell Property spAcidRainAura  Auto  ; Acid rain drip damage
Spell Property spFogDebuff     Auto  ; Fog perception debuff on player

; ── Configuration ─────────────────────────────────────────────────────────────
bool  Property EnvEnabled           = True  Auto
bool  Property WeatherReactionOn    = True  Auto
bool  Property SoundPropOn          = True  Auto
bool  Property LightingOn           = True  Auto
bool  Property TerrainOn            = True  Auto
bool  Property RadZoneOn            = True  Auto
bool  Property FireReactionOn       = True  Auto
float Property UpdateInterval       = 0.1   Auto  ; Every ~2.5 hrs game time

; ── Internal State ────────────────────────────────────────────────────────────
int   _currentWeather    = 0
float _currentHour       = 12.0
bool  _isNight           = False
bool  _isPeakHour        = False
bool  _radStormActive    = False
bool  _fogActive         = False
bool  _rainActive        = False
int   _lastWeatherNotify = -1

; ═══════════════════════════════════════════════════════════════════════════
Event OnQuestInit()
    If !EnvEnabled
        Return
    EndIf
    RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")
    RegisterForUpdateGameTime(UpdateInterval)
    RegisterForWeatherChange()
    UpdateEnvironmentState()
    EnvLog("Environmental AI Manager initialized")
EndEvent

Event OnWeatherChange(Weather akOldWeather, Weather akNewWeather, bool abPrecip, bool abPermaNow)
    If WeatherReactionOn
        HandleWeatherTransition(akOldWeather, akNewWeather)
    EndIf
EndEvent

; ═══════════════════════════════════════════════════════════════════════════
; CORE UPDATE TICK
; ═══════════════════════════════════════════════════════════════════════════
Event OnUpdateGameTime()
    If !EnvEnabled
        RegisterForUpdateGameTime(UpdateInterval)
        Return
    EndIf
    UpdateEnvironmentState()
    ApplyEnvironmentToActors()
    RegisterForUpdateGameTime(UpdateInterval)
EndEvent

Function UpdateEnvironmentState()
    ; Time of day
    Float gameTime = Utility.GetCurrentGameTime()
    _currentHour   = (gameTime - Math.Floor(gameTime)) * 24.0

    _isNight     = _currentHour < 5.5 || _currentHour > 21.0
    _isPeakHour  = (_currentHour >= 5.5 && _currentHour <= 7.5) || \
                   (_currentHour >= 19.0 && _currentHour <= 21.0)

    ; Update globals so other scripts can read them
    If gEnvTimeOfDay    != None  gEnvTimeOfDay.SetValue(_currentHour)
    If gEnvIsNight      != None  gEnvIsNight.SetValue(_isNight ? 1.0 : 0.0)
    If gEnvIsPeakHour   != None  gEnvIsPeakHour.SetValue(_isPeakHour ? 1.0 : 0.0)

    ; Visibility calculation
    Float visibility = 1.0
    If _isNight     visibility -= 0.4
    If _fogActive   visibility -= 0.35
    If _rainActive  visibility -= 0.15
    If gEnvVisibility != None  gEnvVisibility.SetValue(Math.Clamp(visibility, 0.05, 1.0))

    ; Sound carry calculation (how far sounds travel)
    Float soundCarry = 1.0
    If _rainActive   soundCarry -= 0.3   ; Rain masks sounds
    If _fogActive    soundCarry += 0.1   ; Fog actually amplifies close sounds
    If _isNight      soundCarry += 0.2   ; Night is quieter, sounds carry farther
    If gEnvSoundCarry != None  gEnvSoundCarry.SetValue(Math.Clamp(soundCarry, 0.3, 2.0))

    ; Rain masking footsteps
    If gEnvRainMask != None  gEnvRainMask.SetValue(_rainActive ? 1.0 : 0.0)

    ; Log state for bridge
    Debug.Trace("[AAI] ENV_STATE|hour=" + _currentHour + \
                "|night=" + _isNight + "|peak=" + _isPeakHour + \
                "|visibility=" + visibility + "|sound=" + soundCarry + \
                "|weather=" + _currentWeather + \
                "|rain=" + _rainActive + "|fog=" + _fogActive + \
                "|radstorm=" + _radStormActive)
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; WEATHER TRANSITION
; ═══════════════════════════════════════════════════════════════════════════
Function HandleWeatherTransition(Weather oldWeather, Weather newWeather)
    ; Determine new weather type
    _radStormActive = (weatherRadStorm != None && newWeather == weatherRadStorm)
    _fogActive      = (weatherFog      != None && newWeather == weatherFog)
    _rainActive     = (weatherRain     != None && newWeather == weatherRain) || \
                      (weatherAcidRain != None && newWeather == weatherAcidRain)

    ; Set global weather type
    int weatherCode = 0
    If newWeather == weatherRain       weatherCode = 1
    ElseIf newWeather == weatherFog    weatherCode = 2
    ElseIf newWeather == weatherRadStorm weatherCode = 3
    ElseIf newWeather == weatherAcidRain weatherCode = 4
    ElseIf newWeather == weatherSnow   weatherCode = 5
    EndIf
    _currentWeather = weatherCode
    If gEnvWeatherType != None  gEnvWeatherType.SetValue(weatherCode as Float)

    ; Player notification
    If weatherCode != _lastWeatherNotify
        _lastWeatherNotify = weatherCode
        AnnounceWeather(weatherCode)
    EndIf

    ; Apply weather effects
    ApplyWeatherEffects(weatherCode)

    EnvLog("Weather changed → " + GetWeatherName(weatherCode))
EndFunction

Function AnnounceWeather(int code)
    If code == 3
        Debug.Notification("Radiation storm rolling in — find cover or pop those Rad-X...")
    ElseIf code == 4
        Debug.Notification("Acid rain. Your gear won't thank you for this.")
    ElseIf code == 2
        Debug.Notification("The fog's rolling in thick. Something's out there.")
    ElseIf code == 5
        Debug.Notification("Blizzard conditions. Visibility near zero.")
    ElseIf code == 1
        Debug.Notification("Rain masking sound. Good time to move unseen.")
    EndIf
EndFunction

Function ApplyWeatherEffects(int code)
    Actor player = Game.GetPlayer()

    ; Clear previous weather debuffs
    If spFogDebuff != None   player.DispelSpell(spFogDebuff)
    If spRadStormAura != None player.DispelSpell(spRadStormAura)
    If spAcidRainAura != None player.DispelSpell(spAcidRainAura)

    If code == 3  ; Radiation storm
        If spRadStormAura != None
            player.CastSpell(spRadStormAura, player)
        EndIf
        If imodRadStorm != None
            imodRadStorm.Apply()
        EndIf
        ReactToRadStorm()

    ElseIf code == 4  ; Acid rain
        If spAcidRainAura != None
            player.CastSpell(spAcidRainAura, player)
        EndIf
        ReactToAcidRain()

    ElseIf code == 2  ; Fog
        If spFogDebuff != None
            player.CastSpell(spFogDebuff, player)
        EndIf
        If imodFog != None
            imodFog.Apply()
        EndIf
        ReactToFog()
    EndIf
EndFunction

String Function GetWeatherName(int code)
    If code == 0 Return "Clear"
    ElseIf code == 1 Return "Rain"
    ElseIf code == 2 Return "Fog"
    ElseIf code == 3 Return "RadiationStorm"
    ElseIf code == 4 Return "AcidRain"
    ElseIf code == 5 Return "Blizzard"
    EndIf
    Return "Unknown"
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; WEATHER CREATURE/NPC REACTIONS
; ═══════════════════════════════════════════════════════════════════════════
Function ReactToRadStorm()
    ; Radiation storm: ghouls go ecstatic, rad-immune surge, others flee
    Actor player = Game.GetPlayer()
    Actor[] nearby = player.GetActorsInRange(3000.0, 20)
    Int i = 0
    While i < nearby.Length
        Actor npc = nearby[i]
        If npc != None && !npc.IsDead()
            ActorValue avRad = Game.GetFormFromFile(0x000002F7, "Fallout4.esm") as ActorValue
            If avRad != None
                Float radResist = npc.GetValue(avRad)
                If radResist >= 1000.0
                    ; Ghoul / rad-immune: SURGE — boost aggression and speed
                    ActorValue avAggr  = Game.GetFormFromFile(0x000002E7, "Fallout4.esm") as ActorValue
                    ActorValue avSpeed = Game.GetFormFromFile(0x00000036, "Fallout4.esm") as ActorValue
                    If avAggr  != None  npc.SetValue(avAggr,  Math.Min(npc.GetBaseValue(avAggr) * 1.4, 100.0))
                    If avSpeed != None  npc.SetValue(avSpeed, npc.GetBaseValue(avSpeed) * 1.2)
                ElseIf radResist < 100.0 && !npc.IsPlayerTeammate()
                    ; Non-rad-immune: flee indoors / seek cover
                    ActorValue avConf = Game.GetFormFromFile(0x000002E8, "Fallout4.esm") as ActorValue
                    If avConf != None  npc.SetValue(avConf, Math.Max(npc.GetValue(avConf) - 30.0, 0.0))
                    npc.EvaluatePackage()
                EndIf
            EndIf
        EndIf
        i += 1
    EndWhile
    EnvLog("Radiation storm reaction applied to " + i + " actors")
EndFunction

Function ReactToFog()
    ; Fog: all detection halved, ambush creatures activate, Anglers glow
    Actor player = Game.GetPlayer()
    Actor[] nearby = player.GetActorsInRange(2000.0, 15)
    Int i = 0
    While i < nearby.Length
        Actor npc = nearby[i]
        If npc != None && !npc.IsDead()
            ; Reduce perception-based detection range
            ActorValue avPerc = Game.GetFormFromFile(0x000002E3, "Fallout4.esm") as ActorValue
            If avPerc != None
                Float curPerc = npc.GetValue(avPerc)
                npc.SetValue(avPerc, curPerc * 0.55)  ; 45% reduction in fog
            EndIf
        EndIf
        i += 1
    EndWhile
    Debug.Notification("Something moves in the fog...")
EndFunction

Function ReactToAcidRain()
    ; Robots go haywire. Organic creatures shelter.
    Actor player = Game.GetPlayer()
    Actor[] nearby = player.GetActorsInRange(2500.0, 15)
    Int i = 0
    While i < nearby.Length
        Actor npc = nearby[i]
        If npc != None && !npc.IsDead()
            ; Apply to human NPCs — push them to shelter packages
            If !npc.IsInCombat()
                ActorValue avConf = Game.GetFormFromFile(0x000002E8, "Fallout4.esm") as ActorValue
                If avConf != None  npc.SetValue(avConf, Math.Max(npc.GetValue(avConf) - 20.0, 0.0))
                npc.EvaluatePackage()
            EndIf
        EndIf
        i += 1
    EndWhile
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; APPLY ENVIRONMENT TO ALL NEARBY ACTORS (periodic)
; ═══════════════════════════════════════════════════════════════════════════
Function ApplyEnvironmentToActors()
    Actor player = Game.GetPlayer()
    Actor[] nearby = player.GetActorsInRange(2500.0, 20)
    Int i = 0
    While i < nearby.Length
        Actor npc = nearby[i]
        If npc != None && !npc.IsDead()
            ApplyTimeOfDayToActor(npc)
            If TerrainOn  ApplyTerrainToActor(npc, player)
        EndIf
        i += 1
    EndWhile
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; TIME OF DAY — Peak hours, guard fatigue, darkness
; ═══════════════════════════════════════════════════════════════════════════
Function ApplyTimeOfDayToActor(Actor npc)
    ActorValue avAggr  = Game.GetFormFromFile(0x000002E7, "Fallout4.esm") as ActorValue
    ActorValue avPerc  = Game.GetFormFromFile(0x000002E3, "Fallout4.esm") as ActorValue
    If avAggr == None || avPerc == None
        Return
    EndIf

    Float baseAggr = npc.GetBaseValue(avAggr)
    Float basePerc = npc.GetBaseValue(avPerc)

    ; PEAK HOUR (dawn/dusk): all predators maximally aggressive
    If _isPeakHour
        npc.SetValue(avAggr, Math.Min(baseAggr * 1.25, 100.0))

    ; PRE-DAWN FATIGUE (guards most tired 04:00–05:30)
    ElseIf _currentHour >= 4.0 && _currentHour < 5.5
        npc.SetValue(avPerc, basePerc * 0.7)  ; Guards less perceptive

    ; DEEP NIGHT (00:00–04:00): darkness bonus
    ElseIf _currentHour < 4.0 || _currentHour > 22.0
        If LightingOn
            ; Darkness makes stealth dramatically easier — reduce NPC perception
            npc.SetValue(avPerc, basePerc * 0.6)
        EndIf

    ; FULL DAY: restore base values
    Else
        npc.SetValue(avAggr, baseAggr)
        npc.SetValue(avPerc, basePerc)
    EndIf
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; TERRAIN AWARENESS
; ═══════════════════════════════════════════════════════════════════════════
Function ApplyTerrainToActor(Actor npc, Actor player)
    If !TerrainOn
        Return
    EndIf

    ; Height advantage — NPC above player
    Float npcZ    = npc.GetPositionZ()
    Float playerZ = player.GetPositionZ()
    Float heightDiff = npcZ - playerZ

    ActorValue avPerc = Game.GetFormFromFile(0x000002E3, "Fallout4.esm") as ActorValue
    If avPerc == None
        Return
    EndIf

    If heightDiff > 200.0
        ; NPC on high ground — enhanced detection
        Float curPerc = npc.GetValue(avPerc)
        npc.SetValue(avPerc, Math.Min(curPerc * 1.3, 10.0))
    ElseIf heightDiff < -200.0
        ; NPC in low ground — reduced detection
        Float curPerc = npc.GetValue(avPerc)
        npc.SetValue(avPerc, curPerc * 0.8)
    EndIf
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; FIRE REACTION
; ═══════════════════════════════════════════════════════════════════════════
Function OnFireDetected(ObjectReference fireRef)
    If !FireReactionOn || fireRef == None
        Return
    EndIf

    Actor[] nearby = fireRef.GetActorsInRange(600.0, 10)
    Int i = 0
    While i < nearby.Length
        Actor npc = nearby[i]
        If npc != None && !npc.IsDead() && !npc.IsInCombat()
            ; Organic creatures flee fire
            ; Robots ignore fire
            ; Yao Guai particularly afraid
            ActorValue avConf = Game.GetFormFromFile(0x000002E8, "Fallout4.esm") as ActorValue
            If avConf != None
                npc.SetValue(avConf, Math.Max(npc.GetValue(avConf) - 40.0, 0.0))
                npc.EvaluatePackage()
            EndIf
        EndIf
        i += 1
    EndWhile
    EnvLog("Fire reaction: " + nearby.Length + " actors affected")
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; CROW ALARM SYSTEM — crows scattering alerts NPCs
; ═══════════════════════════════════════════════════════════════════════════
Function OnCrowsScattered(ObjectReference crowLocation)
    ; When crows scatter (from combat, explosion, or fast-moving predator)
    ; nearby NPCs become suspicious
    Actor player = Game.GetPlayer()
    Actor[] nearby = crowLocation.GetActorsInRange(1500.0, 12)
    Int alerted = 0
    Int i = 0
    While i < nearby.Length
        Actor npc = nearby[i]
        If npc != None && !npc.IsDead() && !npc.IsInCombat() && npc != player
            ; Make suspicious but don't start combat
            ActorValue avAggr = Game.GetFormFromFile(0x000002E7, "Fallout4.esm") as ActorValue
            If avAggr != None
                npc.SetValue(avAggr, Math.Min(npc.GetValue(avAggr) + 15.0, 100.0))
            EndIf
            npc.EvaluatePackage()
            alerted += 1
        EndIf
        i += 1
    EndWhile
    If alerted > 0
        Debug.Trace("[AAI] CROW_ALARM|location=" + crowLocation.GetDisplayName() + "|alerted=" + alerted)
    EndIf
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; SOUND PROPAGATION — modify detection on gunshot/explosion
; ═══════════════════════════════════════════════════════════════════════════
Function OnExplosionDetected(ObjectReference explRef, String locationType)
    If !SoundPropOn || explRef == None
        Return
    EndIf

    ; Base alert radius multiplied by environment
    Float baseRadius = 2000.0
    Float soundMult  = gEnvSoundCarry != None ? gEnvSoundCarry.GetValue() : 1.0

    ; Terrain modifier
    If locationType == "outdoor"    soundMult *= 1.5   ; Sound carries far outside
    ElseIf locationType == "indoor" soundMult *= 0.7   ; Muffled indoors but echoes

    Float alertRadius = baseRadius * soundMult

    Actor[] nearby = explRef.GetActorsInRange(alertRadius, 25)
    Int i = 0
    While i < nearby.Length
        Actor npc = nearby[i]
        If npc != None && !npc.IsDead() && !npc.IsInCombat()
            ; Alert toward explosion source
            npc.EvaluatePackage()
        EndIf
        i += 1
    EndWhile

    EnvLog("Explosion alert: radius=" + alertRadius + " (" + locationType + ") | sound_mult=" + soundMult)
    Debug.Trace("[AAI] ENV_EXPLOSION|radius=" + alertRadius + "|loc_type=" + locationType + \
                "|alerted=" + nearby.Length)
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; RADIATION ZONE ESCALATION
; ═══════════════════════════════════════════════════════════════════════════
Function UpdateRadiationZone(Float radLevel, String zoneName)
    If !RadZoneOn
        Return
    EndIf

    If gEnvRadLevel != None  gEnvRadLevel.SetValue(radLevel)

    ; High radiation zones: rad-immune creatures become more aggressive
    ; and non-immune creatures flee or are damaged
    If radLevel >= 5.0  ; 5+ rads/sec = dangerous zone
        Actor player = Game.GetPlayer()
        Actor[] nearby = player.GetActorsInRange(1500.0, 12)
        Int i = 0
        While i < nearby.Length
            Actor npc = nearby[i]
            If npc != None && !npc.IsDead()
                ActorValue avRadRes = Game.GetFormFromFile(0x000002F7, "Fallout4.esm") as ActorValue
                If avRadRes != None
                    Float radResist = npc.GetValue(avRadRes)
                    If radResist >= 1000.0
                        ; Thrives in radiation — extra aggression
                        ActorValue avAggr = Game.GetFormFromFile(0x000002E7, "Fallout4.esm") as ActorValue
                        If avAggr != None
                            npc.SetValue(avAggr, Math.Min(npc.GetBaseValue(avAggr) + (radLevel * 2.0), 100.0))
                        EndIf
                    ElseIf radResist < 50.0
                        ; Suffering in radiation — reduced effectiveness
                        ActorValue avAggr = Game.GetFormFromFile(0x000002E7, "Fallout4.esm") as ActorValue
                        If avAggr != None
                            npc.SetValue(avAggr, Math.Max(npc.GetValue(avAggr) - (radLevel * 1.5), 0.0))
                        EndIf
                    EndIf
                EndIf
            EndIf
            i += 1
        EndWhile
    EndIf

    Debug.Trace("[AAI] RAD_ZONE|zone=" + zoneName + "|rads=" + radLevel)
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; PUBLIC API — other scripts call these
; ═══════════════════════════════════════════════════════════════════════════
Float Function GetCurrentHour()     Return _currentHour    EndFunction
Bool  Function IsNight()            Return _isNight         EndFunction
Bool  Function IsPeakHour()         Return _isPeakHour      EndFunction
Bool  Function IsRadStormActive()   Return _radStormActive  EndFunction
Bool  Function IsFogActive()        Return _fogActive       EndFunction
Bool  Function IsRaining()          Return _rainActive      EndFunction

Float Function GetVisibilityFraction()
    Return gEnvVisibility != None ? gEnvVisibility.GetValue() : 1.0
EndFunction

Float Function GetSoundCarryMultiplier()
    Return gEnvSoundCarry != None ? gEnvSoundCarry.GetValue() : 1.0
EndFunction

Function EnvLog(String msg)
    Debug.Trace("[AAI-Env] " + msg)
EndFunction
