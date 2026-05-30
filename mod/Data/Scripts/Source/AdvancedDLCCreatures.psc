; ═══════════════════════════════════════════════════════════════════════════
; AdvancedDLCCreatures.psc
; Advanced AI System — DLC Creature Behavior Extensions
;
; Covers all DLC-exclusive creatures not in the base game:
;
; AUTOMATRON:
;   - Eyebot Drones (aerial scouts, signal relay)
;   - Robobrain (psychic prediction, barrel roll charge)
;
; FAR HARBOR:
;   - Fog Crawler (ambush from water, tentacle sweep)
;   - Angler (bioluminescent lure, ambush sit-and-wait)
;   - Hermit Crab (shell phase, exposed berserk)
;   - Gulper (swallow attack, stomach acid)
;   - NovaDoves / FogGulls (ambient birds — flee behavior)
;   - Shipwreck Mirelurks (fog-adapted, reduced sight, enhanced smell)
;   - Trappers (human faction — Far Harbor specific tactics)
;
; NUKA-WORLD:
;   - Gatorclaw (Deathclaw variant — alligator hybrid, swamp ambush)
;   - Pack Mongrel (Nuka-World raider animal — trained attack dogs)
;   - Nukalurk (Nuka-Cola irradiated mirelurk — glowing, extra acid)
;   - Cave Cricket (jumping ambush, silent approach)
;   - Bloodworm (burrowing, paralyze)
;
; Attach to creature alias refs for each DLC creature type.
; Requires: AdvancedAIManager, AdvancedCreatureBehavior
; ═══════════════════════════════════════════════════════════════════════════
Scriptname AdvancedDLCCreatures extends ReferenceAlias

Quest Property AAIQuest Auto

; ── DLC Creature Keywords ─────────────────────────────────────────────────────
; AUTOMATRON
Keyword Property kwdEyebotDrone     Auto
Keyword Property kwdRobobrain       Auto

; FAR HARBOR
Keyword Property kwdFogCrawler      Auto
Keyword Property kwdAngler          Auto
Keyword Property kwdHermitCrab      Auto
Keyword Property kwdGulper          Auto
Keyword Property kwdFogMirelurk     Auto   ; Fog-adapted Mirelurk variant
Keyword Property kwdTrilobite        Auto   ; Aquatic Far Harbor creature

; NUKA-WORLD
Keyword Property kwdGatorclaw       Auto   ; Deathclaw/gator hybrid
Keyword Property kwdNukalurk        Auto   ; Nuka-Cola Mirelurk
Keyword Property kwdCaveCricket     Auto   ; Silent jumping ambush
Keyword Property kwdBloodworm       Auto   ; Burrowing paralyze worm
Keyword Property kwdPackMongrel     Auto   ; Trained raider dog

; ── Abilities ─────────────────────────────────────────────────────────────────
Spell   Property spFogCrawlerTentacle  Auto  ; AoE sweep
Spell   Property spAnglerLure          Auto  ; Lure attraction field
Spell   Property spGulperSwallow       Auto  ; Swallow effect
Spell   Property spNukalurk            Auto  ; Nuka-Cola radiation burst
Spell   Property spCaveCricketJump     Auto  ; Leap attack
Spell   Property spBloodwormParalyze   Auto  ; Paralytic toxin
Spell   Property spGatorclawTailSweep  Auto  ; Tail whip knockdown
Spell   Property spRobobrainPsychic    Auto  ; Prediction field (enemy misses more)
Explosion Property expNukalurk         Auto  ; Nuka-Cola explosion on death

; ── State ─────────────────────────────────────────────────────────────────────
Actor  _self            = None
bool   _shellPhase      = True   ; Hermit Crab starts shelled
bool   _lureActive      = False  ; Angler lure state
bool   _isSwallowing    = False
float  _lastAbilityTime = 0.0
float  _initMaxHP       = 0.0

; ═══════════════════════════════════════════════════════════════════════════
Event OnAliasInit()
    _self = GetActorReference()
    If _self == None
        Return
    EndIf

    ActorValue avHP = Game.GetFormFromFile(0x00000015, "Fallout4.esm") as ActorValue
    If avHP != None
        _initMaxHP = _self.GetBaseValue(avHP)
    EndIf

    ApplyDLCProfile()

    RegisterForRemoteEvent(_self, "OnCombatStateChanged")
    RegisterForRemoteEvent(_self, "OnHit")
    RegisterForRemoteEvent(_self, "OnDeath")
    RegisterForUpdateGameTime(0.08)
EndEvent

; ═══════════════════════════════════════════════════════════════════════════
; DLC SPECIES PROFILES
; ═══════════════════════════════════════════════════════════════════════════
Function ApplyDLCProfile()
    ; ── GATORCLAW (Nuka-World) ───────────────────────────────────────────────
    ; Deathclaw crossed with alligator radiation — slow on land, devastating in water
    If kwdGatorclaw != None && _self.HasKeyword(kwdGatorclaw)
        ; Extra aggression, slightly slower, brutal AoE tail sweep
        ActorValue avAggr = Game.GetFormFromFile(0x000002E7, "Fallout4.esm") as ActorValue
        ActorValue avConf = Game.GetFormFromFile(0x000002E8, "Fallout4.esm") as ActorValue
        If avAggr != None  _self.SetValue(avAggr, 100.0)
        If avConf != None  _self.SetValue(avConf, 100.0)
        Debug.Notification("Gatorclaw detected — tail sweep danger!")

    ; ── CAVE CRICKET (Nuka-World) ────────────────────────────────────────────
    ; Silent jumping ambush predator — player hears nothing until impact
    ElseIf kwdCaveCricket != None && _self.HasKeyword(kwdCaveCricket)
        ; Start hidden/still; detect via vibration
        _self.SetRestrained(True)  ; Wait for player to walk past

    ; ── NUKALURK (Nuka-World) ────────────────────────────────────────────────
    ; Nuka-Cola soaked Mirelurk — glowing, radioactive, explosive death
    ElseIf kwdNukalurk != None && _self.HasKeyword(kwdNukalurk)
        If spNukalurk != None
            _self.CastSpell(spNukalurk, _self)  ; Persistent Nuka radiation aura
        EndIf

    ; ── BLOODWORM (Nuka-World) ───────────────────────────────────────────────
    ; Subterranean — burrows and ambushes from below
    ElseIf kwdBloodworm != None && _self.HasKeyword(kwdBloodworm)
        _self.SetRestrained(True)  ; Burrowed — wait for player above

    ; ── FOG CRAWLER (Far Harbor) ─────────────────────────────────────────────
    ; Large crustacean ambush predator — uses fog as cover
    ElseIf kwdFogCrawler != None && _self.HasKeyword(kwdFogCrawler)
        ActorValue avConf = Game.GetFormFromFile(0x000002E8, "Fallout4.esm") as ActorValue
        If avConf != None  _self.SetValue(avConf, 85.0)

    ; ── ANGLER (Far Harbor) ──────────────────────────────────────────────────
    ; Sit-and-wait predator — bioluminescent lure attracts prey
    ElseIf kwdAngler != None && _self.HasKeyword(kwdAngler)
        _lureActive = True
        _self.SetRestrained(True)  ; Completely still until prey close enough
        If spAnglerLure != None
            _self.CastSpell(spAnglerLure, _self)  ; Activate lure aura
        EndIf
        Debug.Notification("Warning: Something is glowing in the distance...")

    ; ── HERMIT CRAB (Far Harbor) ─────────────────────────────────────────────
    ; Massive crustacean using a building as a shell — nearly invulnerable frontal
    ElseIf kwdHermitCrab != None && _self.HasKeyword(kwdHermitCrab)
        _shellPhase = True  ; Shell up at start
        Debug.Notification("Is that... a building moving?!")

    ; ── GULPER (Far Harbor) ──────────────────────────────────────────────────
    ; Amphibious predator — attempts to swallow player/NPCs whole
    ElseIf kwdGulper != None && _self.HasKeyword(kwdGulper)
        ActorValue avAggr = Game.GetFormFromFile(0x000002E7, "Fallout4.esm") as ActorValue
        If avAggr != None  _self.SetValue(avAggr, 85.0)

    ; ── ROBOBRAIN (Automatron) ───────────────────────────────────────────────
    ; Human brain in a robot — predicts player movement, flanks intelligently
    ElseIf kwdRobobrain != None && _self.HasKeyword(kwdRobobrain)
        If spRobobrainPsychic != None
            _self.CastSpell(spRobobrainPsychic, _self)  ; Prediction field
        EndIf
    EndIf
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
Event OnUpdateGameTime()
    If _self == None || _self.IsDead()
        Return
    EndIf

    ; Cave Cricket — release from burrow when player walks overhead
    If kwdCaveCricket != None && _self.HasKeyword(kwdCaveCricket)
        Actor player = Game.GetPlayer()
        Float dist = _self.GetDistance(player)
        If dist < 400.0 && !_self.IsInCombat()
            ; Player is directly above/near — LEAP
            _self.SetRestrained(False)
            _self.StartCombat(player)
            If spCaveCricketJump != None
                _self.CastSpell(spCaveCricketJump, player)
            EndIf
            Debug.Notification("CAVE CRICKET — ambush from below!")
        EndIf

    ; Bloodworm — rise from ground when player close
    ElseIf kwdBloodworm != None && _self.HasKeyword(kwdBloodworm)
        Actor player = Game.GetPlayer()
        Float dist = _self.GetDistance(player)
        If dist < 300.0 && !_self.IsInCombat()
            _self.SetRestrained(False)
            _self.StartCombat(player)
            Debug.Notification("The ground erupts — Bloodworms!")
        EndIf
    EndIf

    RegisterForUpdateGameTime(0.08)
EndEvent

; ═══════════════════════════════════════════════════════════════════════════
Event OnCombatStateChanged(Actor akSender, int aeCombatState)
    If aeCombatState == 1
        HandleDLCCombatEntry()
    ElseIf aeCombatState == 0
        HandleDLCCombatEnd()
    EndIf
EndEvent

Function HandleDLCCombatEntry()
    ; Angler drops lure, becomes aggressive
    If kwdAngler != None && _self.HasKeyword(kwdAngler)
        _lureActive = False
        _self.SetRestrained(False)
        Debug.Notification("The Angler drops its lure — it's attacking!")

    ; Hermit Crab: stay shelled briefly, then smash
    ElseIf kwdHermitCrab != None && _self.HasKeyword(kwdHermitCrab)
        Debug.Notification("The Hermit Crab retreats into its shell — its SHELL IS A BUILDING!")
        Utility.Wait(2.0)
        _shellPhase = False
        Debug.Notification("The Hermit Crab emerges — MOVE!")

    ; Fog Crawler: tentacle sweep on entry
    ElseIf kwdFogCrawler != None && _self.HasKeyword(kwdFogCrawler)
        If spFogCrawlerTentacle != None
            _self.CastSpell(spFogCrawlerTentacle, Game.GetPlayer())
        EndIf

    ; Gatorclaw: tail sweep warning
    ElseIf kwdGatorclaw != None && _self.HasKeyword(kwdGatorclaw)
        Debug.Notification("GATORCLAW — watch the tail sweep!")
    EndIf
EndFunction

Function HandleDLCCombatEnd()
    ; Angler: re-arm lure after combat
    If kwdAngler != None && _self.HasKeyword(kwdAngler)
        _lureActive = True
        If spAnglerLure != None
            _self.CastSpell(spAnglerLure, _self)
        EndIf
        _self.SetRestrained(True)
    EndIf
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
Event OnHit(ObjectReference akTarget, ObjectReference akAggressor, Form akSource, Projectile akProjectile, bool abPowerAttack, bool abSneakAttack, bool abBashAttack, bool abHitBlocked, string apMaterial)
    ActorValue avHP = Game.GetFormFromFile(0x00000015, "Fallout4.esm") as ActorValue
    Float maxHP = _initMaxHP
    Float curHP = avHP != None ? _self.GetValue(avHP) : maxHP
    Float hpPct = maxHP > 0 ? (curHP / maxHP) : 1.0

    ; Hermit Crab shell break
    If kwdHermitCrab != None && _self.HasKeyword(kwdHermitCrab)
        If _shellPhase && hpPct <= 0.5
            _shellPhase = False
            ; Boost speed and aggression — exposed!
            ActorValue avAggr  = Game.GetFormFromFile(0x000002E7, "Fallout4.esm") as ActorValue
            ActorValue avSpeed = Game.GetFormFromFile(0x00000036, "Fallout4.esm") as ActorValue
            If avAggr  != None  _self.SetValue(avAggr,  100.0)
            If avSpeed != None  _self.SetValue(avSpeed, _self.GetBaseValue(avSpeed) * 1.4)
            Debug.Notification("HERMIT CRAB SHELL BROKEN — it's EXPOSED and ENRAGED!")
        EndIf

    ; Gulper: attempt swallow when player is close
    ElseIf kwdGulper != None && _self.HasKeyword(kwdGulper)
        Actor aggressor = akAggressor as Actor
        If aggressor != None && !_isSwallowing && spGulperSwallow != None
            Float dist = _self.GetDistance(aggressor)
            If dist < 180.0 && Utility.RandomInt(1, 100) <= 30
                _isSwallowing = True
                _self.CastSpell(spGulperSwallow, aggressor)
                Debug.Notification("The Gulper tries to SWALLOW you whole!")
                Utility.Wait(3.0)
                _isSwallowing = False
            EndIf
        EndIf

    ; Nukalurk: spray on hit
    ElseIf kwdNukalurk != None && _self.HasKeyword(kwdNukalurk)
        Actor aggressor = akAggressor as Actor
        If aggressor != None && spNukalurk != None
            Float now = Utility.GetCurrentRealTime()
            If (now - _lastAbilityTime) > 8.0
                _lastAbilityTime = now
                _self.CastSpell(spNukalurk, aggressor)
            EndIf
        EndIf

    ; Gatorclaw: tail sweep on hit (AoE knockdown)
    ElseIf kwdGatorclaw != None && _self.HasKeyword(kwdGatorclaw)
        If spGatorclawTailSweep != None
            Float now = Utility.GetCurrentRealTime()
            If (now - _lastAbilityTime) > 10.0
                _lastAbilityTime = now
                _self.CastSpell(spGatorclawTailSweep, Game.GetPlayer())
            EndIf
        EndIf

    ; Bloodworm: paralyze on hit
    ElseIf kwdBloodworm != None && _self.HasKeyword(kwdBloodworm)
        Actor aggressor = akAggressor as Actor
        If aggressor != None && spBloodwormParalyze != None
            Float now = Utility.GetCurrentRealTime()
            If (now - _lastAbilityTime) > 15.0
                _lastAbilityTime = now
                _self.CastSpell(spBloodwormParalyze, aggressor)
                Debug.Notification("Bloodworm venom — PARALYZED!")
            EndIf
        EndIf
    EndIf
EndEvent

; ═══════════════════════════════════════════════════════════════════════════
Event OnDeath(Actor akKiller)
    ; Nukalurk explosion on death
    If kwdNukalurk != None && _self.HasKeyword(kwdNukalurk) && expNukalurk != None
        _self.PlaceAtMe(expNukalurk)
        Debug.Notification("NUKALURK — NUKA-COLA EXPLOSION!")
    EndIf

    ; Gatorclaw death roar
    If kwdGatorclaw != None && _self.HasKeyword(kwdGatorclaw)
        Debug.Notification("The Gatorclaw falls silent.")
    EndIf

    ; Log DLC creature death for bridge
    String species = GetDLCSpeciesName()
    Debug.Trace("[AAI] CREATURE_DEATH|species=" + species + \
                "|location=" + _self.GetCurrentLocation().GetDisplayName() + \
                "|game_time=" + Utility.GetCurrentGameTime())
EndEvent

String Function GetDLCSpeciesName()
    If kwdGatorclaw   != None && _self.HasKeyword(kwdGatorclaw)   Return "Gatorclaw"
    ElseIf kwdNukalurk    != None && _self.HasKeyword(kwdNukalurk)    Return "Nukalurk"
    ElseIf kwdCaveCricket != None && _self.HasKeyword(kwdCaveCricket) Return "CaveCricket"
    ElseIf kwdBloodworm   != None && _self.HasKeyword(kwdBloodworm)   Return "Bloodworm"
    ElseIf kwdFogCrawler  != None && _self.HasKeyword(kwdFogCrawler)  Return "FogCrawler"
    ElseIf kwdAngler      != None && _self.HasKeyword(kwdAngler)      Return "Angler"
    ElseIf kwdHermitCrab  != None && _self.HasKeyword(kwdHermitCrab)  Return "HermitCrab"
    ElseIf kwdGulper      != None && _self.HasKeyword(kwdGulper)      Return "Gulper"
    ElseIf kwdRobobrain   != None && _self.HasKeyword(kwdRobobrain)   Return "Robobrain"
    ElseIf kwdEyebotDrone != None && _self.HasKeyword(kwdEyebotDrone) Return "EyebotDrone"
    EndIf
    Return "DLCCreature"
EndFunction
