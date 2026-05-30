; ═══════════════════════════════════════════════════════════════════════════
; AdvancedCreatureBehavior.psc
; Advanced AI System — Realistic Creature Behavior
;
; Transforms Fallout 4 creatures from damage sponges into living animals.
; Each species has a unique behavioral profile covering:
;
;   - Hunting states: Patrol → Stalk → Ambush → Attack → Feed → Rest
;   - Territorial & den defense (more aggressive near nest/eggs)
;   - Sensory profiles: smell, hearing, vibration, echolocation, bioluminescence
;   - Social structure: solitary, mated pair, pack, swarm, hive
;   - Wounded state changes: limping, berserk, retreat, surrender
;   - Day/Night activity: nocturnal vs diurnal vs crepuscular
;   - Species-specific special behaviors and attacks
;
; Attach to ReferenceAlias filled per-creature type.
; Requires: AdvancedAIManager quest running
; ═══════════════════════════════════════════════════════════════════════════
Scriptname AdvancedCreatureBehavior extends ReferenceAlias

; ── Manager ─────────────────────────────────────────────────────────────────
Quest Property AAIQuest Auto

; ── Species Keywords (assign in CK) ─────────────────────────────────────────
Keyword Property kwdDeathclaw      Auto
Keyword Property kwdRadscorpion    Auto
Keyword Property kwdMirelurk       Auto
Keyword Property kwdMirelurkQueen  Auto
Keyword Property kwdYaoGuai        Auto
Keyword Property kwdBloodbug       Auto
Keyword Property kwdRadroach       Auto
Keyword Property kwdBloatfly       Auto
Keyword Property kwdGlowingOne     Auto
Keyword Property kwdFogCrawler     Auto
Keyword Property kwdAngler         Auto
Keyword Property kwdHermitCrab     Auto
Keyword Property kwdGulper         Auto
Keyword Property kwdGorilla        Auto
Keyword Property kwdStingwing      Auto
Keyword Property kwdMolerat        Auto

; ── Den / Nest ───────────────────────────────────────────────────────────────
ObjectReference Property DenMarker Auto  ; Place this near the creature's spawn point in CK
float Property DenDefenseRadius    = 800.0  Auto  ; Rage if player enters this range
float Property DenReturnRadius     = 3000.0 Auto  ; Return to den if combat ends this far away
bool  Property HasEggs             = False  Auto  ; Extra aggression when eggs are present

; ── Sensory Profile ──────────────────────────────────────────────────────────
; Override these per-species in CK or leave at species defaults set in OnAliasInit
float Property SmellRadius         = 0.0   Auto  ; Extra detection from smell (stacks on sight)
float Property VibrationRadius     = 0.0   Auto  ; Feel footsteps through ground
float Property EcholocationRadius  = 0.0   Auto  ; Bats, blind creatures
bool  Property BlindCreature       = False  Auto  ; Uses only hearing/smell
bool  Property Nocturnal           = False  Auto  ; More aggressive at night, reduced detection in daylight
bool  Property Diurnal             = False  Auto  ; Less aggressive at night

; ── Social Structure ─────────────────────────────────────────────────────────
; "solitary" "pair" "pack" "swarm" "hive"
string Property SocialType         = "solitary" Auto
float  Property PackAlertRadius    = 1200.0      Auto
bool   Property IsAlphaLeader      = False       Auto  ; Alpha boosts pack
bool   Property IsAlphaPresent     = False       Auto  ; Set by ecology manager

; ── Hunting State Machine ─────────────────────────────────────────────────────
; 0=Rest  1=Patrol  2=Stalk  3=Ambush  4=Attack  5=Feed  6=Retreat  7=DenDefense
int Property HuntingState = 1 Auto

; Stalk config
float Property StalkDistanceMin    = 600.0  Auto  ; Start stalk when target this far
float Property StalkDistanceMax    = 1200.0 Auto  ; Lose interest if target goes farther
float Property AmbushTriggerDist   = 350.0  Auto  ; Break from stalk, charge

; Feed / Rest
float Property FeedDuration        = 8.0   Auto  ; Real seconds feeding on corpse
float Property RestAfterKill       = False  Auto  ; Does this species rest after eating?

; ── Wounded Behavior ─────────────────────────────────────────────────────────
float Property BerserkThreshold    = 0.35  Auto  ; HP% — go berserk
float Property RetreatThreshold    = 0.15  Auto  ; HP% — attempt retreat
float Property LimpThreshold       = 0.50  Auto  ; HP% — slow movement begins
bool  Property CanBerserk          = True  Auto
bool  Property CanRetreat          = False Auto  ; Most creatures don't retreat

; ── Species-Specific Abilities ────────────────────────────────────────────────
Spell   Property spSpecialAbility1  Auto  ; Primary special (e.g. Radscorp paralyze)
Spell   Property spSpecialAbility2  Auto  ; Secondary special (e.g. Mirelurk acid)
Spell   Property spAura             Auto  ; Persistent aura (e.g. Glowing One radiation)
Explosion Property expDeathBlast    Auto  ; Death explosion (Bloatfly, exploding Radroach)
float   Property SpecialCooldown    = 12.0 Auto  ; Seconds between special uses

; ── Internal State ───────────────────────────────────────────────────────────
Actor    _self              = None
bool     _isBerserking      = False
bool     _isRetreating      = False
bool     _isLimping         = False
bool     _isStalking        = False
bool     _isFeeding         = False
float    _lastSpecialTime   = 0.0
float    _lastStateChange   = 0.0
Actor    _stalkTarget       = None
float    _initMaxHP         = 0.0
int      _woundedCount      = 0  ; How many times hit this combat

; ═══════════════════════════════════════════════════════════════════════════
; INITIALIZATION
; ═══════════════════════════════════════════════════════════════════════════
Event OnAliasInit()
    _self = GetActorReference()
    If _self == None
        Return
    EndIf

    ; Cache max HP
    ActorValue avHP = Game.GetFormFromFile(0x00000015, "Fallout4.esm") as ActorValue
    If avHP != None
        _initMaxHP = _self.GetBaseValue(avHP)
    EndIf

    ; Apply species profile
    ApplySpeciesProfile()

    ; Register events
    RegisterForRemoteEvent(_self, "OnCombatStateChanged")
    RegisterForRemoteEvent(_self, "OnHit")
    RegisterForRemoteEvent(_self, "OnDeath")
    RegisterForRemoteEvent(_self, "OnLoad")
    RegisterForUpdateGameTime(0.08)  ; ~2 hrs game time polling tick

    ; Start aura if applicable (Glowing One)
    If spAura != None
        _self.CastSpell(spAura, _self)
    EndIf

    CreatureLog("Initialized: " + _self.GetDisplayName() + " | State: " + HuntingState + " | Social: " + SocialType)
EndEvent

; ═══════════════════════════════════════════════════════════════════════════
; SPECIES PROFILE DEFAULTS
; (Modders: override individual properties in CK instead of editing here)
; ═══════════════════════════════════════════════════════════════════════════
Function ApplySpeciesProfile()
    ; ── DEATHCLAW ──────────────────────────────────────────────────────────
    If kwdDeathclaw != None && _self.HasKeyword(kwdDeathclaw)
        SmellRadius       = 1800.0   ; Incredible smell
        VibrationRadius   = 900.0    ; Feel footsteps
        SocialType        = "pair"   ; Mated pairs, sometimes solitary
        StalkDistanceMin  = 800.0
        StalkDistanceMax  = 2000.0
        AmbushTriggerDist = 450.0
        BerserkThreshold  = 0.40     ; Rage early
        RetreatThreshold  = 0.0      ; Never retreats
        CanRetreat        = False
        CanBerserk        = True
        Nocturnal         = False     ; Active all times
        DenDefenseRadius  = 1200.0   ; Very territorial
        FeedDuration      = 15.0
        RestAfterKill     = True      ; Feeds and rests

    ; ── RADSCORPION ────────────────────────────────────────────────────────
    ElseIf kwdRadscorpion != None && _self.HasKeyword(kwdRadscorpion)
        SmellRadius       = 1200.0
        VibrationRadius   = 1500.0   ; Feel vibrations excellently (like real scorpions)
        BlindCreature     = False
        SocialType        = "solitary"
        StalkDistanceMin  = 400.0
        AmbushTriggerDist = 250.0
        BerserkThreshold  = 0.20
        CanRetreat        = True
        RetreatThreshold  = 0.10
        Nocturnal         = True      ; More active at night
        DenDefenseRadius  = 600.0
        HuntingState      = 3        ; Start in ambush (burrowed)

    ; ── MIRELURK ───────────────────────────────────────────────────────────
    ElseIf kwdMirelurk != None && _self.HasKeyword(kwdMirelurk)
        SmellRadius       = 800.0
        VibrationRadius   = 600.0
        SocialType        = "pack"   ; Live in groups
        PackAlertRadius   = 1000.0
        StalkDistanceMin  = 600.0
        AmbushTriggerDist = 300.0
        BerserkThreshold  = 0.30
        CanRetreat        = True
        RetreatThreshold  = 0.10     ; Retreat into water
        DenDefenseRadius  = 900.0
        HasEggs           = True     ; Often near eggs

    ; ── MIRELURK QUEEN ─────────────────────────────────────────────────────
    ElseIf kwdMirelurkQueen != None && _self.HasKeyword(kwdMirelurkQueen)
        SmellRadius       = 2000.0
        VibrationRadius   = 1200.0
        SocialType        = "hive"   ; Commands all mirelurks in area
        IsAlphaLeader     = True
        BerserkThreshold  = 0.50     ; Berserk at half health
        CanRetreat        = False    ; Queens never flee
        DenDefenseRadius  = 2000.0
        HasEggs           = True
        FeedDuration      = 0.0      ; Doesn't feed

    ; ── YAO GUAI ───────────────────────────────────────────────────────────
    ElseIf kwdYaoGuai != None && _self.HasKeyword(kwdYaoGuai)
        SmellRadius       = 2000.0   ; Bear-like smell — best in the game
        VibrationRadius   = 400.0
        SocialType        = "solitary"
        StalkDistanceMin  = 500.0
        StalkDistanceMax  = 1500.0
        AmbushTriggerDist = 350.0
        BerserkThreshold  = 0.45     ; Rear up and charge when hurt
        CanRetreat        = True
        RetreatThreshold  = 0.08
        Nocturnal         = False
        DenDefenseRadius  = 700.0
        FeedDuration      = 12.0
        RestAfterKill     = True

    ; ── BLOODBUG ───────────────────────────────────────────────────────────
    ElseIf kwdBloodbug != None && _self.HasKeyword(kwdBloodbug)
        SmellRadius       = 1500.0   ; Smell blood from far
        SocialType        = "swarm"
        PackAlertRadius   = 800.0
        BerserkThreshold  = 0.0      ; Never berserk — too fragile
        CanRetreat        = True
        RetreatThreshold  = 0.40     ; Flee when barely damaged
        Nocturnal         = False
        DenDefenseRadius  = 0.0      ; Not territorial
        FeedDuration      = 5.0      ; Drain blood then flee
        RestAfterKill     = False

    ; ── GLOWING ONE ────────────────────────────────────────────────────────
    ElseIf kwdGlowingOne != None && _self.HasKeyword(kwdGlowingOne)
        SocialType        = "pack"   ; Leads feral ghouls
        IsAlphaLeader     = True
        PackAlertRadius   = 1500.0
        BerserkThreshold  = 0.60     ; Emits radiation pulse when hurt
        CanRetreat        = False
        DenDefenseRadius  = 500.0
        Nocturnal         = True     ; More active at night

    ; ── FOG CRAWLER (Far Harbor) ────────────────────────────────────────────
    ElseIf kwdFogCrawler != None && _self.HasKeyword(kwdFogCrawler)
        SmellRadius       = 1200.0
        EcholocationRadius = 800.0
        SocialType        = "solitary"
        StalkDistanceMin  = 700.0
        AmbushTriggerDist = 300.0
        BerserkThreshold  = 0.35
        CanRetreat        = False
        DenDefenseRadius  = 1000.0
        HuntingState      = 2        ; Start in stalk

    ; ── ANGLER (Far Harbor) ─────────────────────────────────────────────────
    ElseIf kwdAngler != None && _self.HasKeyword(kwdAngler)
        VibrationRadius   = 600.0
        SocialType        = "solitary"
        HuntingState      = 3        ; Ambush — sits still, uses lure
        StalkDistanceMin  = 0.0
        AmbushTriggerDist = 400.0    ; Lure draws prey to attack range
        BerserkThreshold  = 0.25
        CanRetreat        = True
        RetreatThreshold  = 0.10
        DenDefenseRadius  = 500.0

    ; ── HERMIT CRAB (Far Harbor) ────────────────────────────────────────────
    ElseIf kwdHermitCrab != None && _self.HasKeyword(kwdHermitCrab)
        VibrationRadius   = 800.0
        SocialType        = "solitary"
        BerserkThreshold  = 0.50     ; Shell breaks, exposed, goes berserk
        CanRetreat        = False
        DenDefenseRadius  = 300.0

    ; ── GULPER (Far Harbor) ─────────────────────────────────────────────────
    ElseIf kwdGulper != None && _self.HasKeyword(kwdGulper)
        SmellRadius       = 1000.0
        SocialType        = "pack"
        PackAlertRadius   = 900.0
        AmbushTriggerDist = 200.0    ; Gets very close before attacking
        BerserkThreshold  = 0.30
        CanRetreat        = True
        RetreatThreshold  = 0.05
        FeedDuration      = 10.0     ; Swallow and consume

    ; ── GORILLA (Institute) ─────────────────────────────────────────────────
    ElseIf kwdGorilla != None && _self.HasKeyword(kwdGorilla)
        SmellRadius       = 1400.0
        SocialType        = "pack"
        IsAlphaLeader     = False
        BerserkThreshold  = 0.45
        CanRetreat        = True
        RetreatThreshold  = 0.10
        DenDefenseRadius  = 800.0

    ; ── STINGWING ────────────────────────────────────────────────────────────
    ElseIf kwdStingwing != None && _self.HasKeyword(kwdStingwing)
        SmellRadius       = 900.0
        SocialType        = "swarm"
        PackAlertRadius   = 600.0
        BerserkThreshold  = 0.0
        CanRetreat        = True
        RetreatThreshold  = 0.50

    ; ── MOLE RAT ─────────────────────────────────────────────────────────────
    ElseIf kwdMolerat != None && _self.HasKeyword(kwdMolerat)
        SmellRadius       = 1500.0
        BlindCreature     = True     ; Mostly blind — relies on smell+vibration
        VibrationRadius   = 1200.0
        SocialType        = "pack"
        PackAlertRadius   = 800.0
        BerserkThreshold  = 0.20
        CanRetreat        = True
        RetreatThreshold  = 0.05
        HuntingState      = 3        ; Pop up from burrows (ambush)
    EndIf
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; PERIODIC TICK — State machine update
; ═══════════════════════════════════════════════════════════════════════════
Event OnUpdateGameTime()
    If _self == None || _self.IsDead()
        Return
    EndIf

    Float gameTime = Utility.GetCurrentGameTime()

    ; Day/Night behavior adjustment
    ApplyDayNightModifiers(gameTime)

    ; Stalk logic (if not already in combat)
    If HuntingState == 2 && !_self.IsInCombat()
        UpdateStalkBehavior()
    EndIf

    ; Enhanced smell/vibration detection
    If !_self.IsInCombat() && (SmellRadius > 0 || VibrationRadius > 0)
        CheckAdvancedSenses()
    EndIf

    ; Den protection check
    If DenMarker != None && !_self.IsInCombat()
        CheckDenProximity()
    EndIf

    ; Alpha pack bonus
    If IsAlphaLeader && SocialType == "pack" || SocialType == "hive"
        ApplyAlphaAura()
    EndIf

    RegisterForUpdateGameTime(0.08)
EndEvent

; ═══════════════════════════════════════════════════════════════════════════
; DAY/NIGHT MODIFIERS
; ═══════════════════════════════════════════════════════════════════════════
Function ApplyDayNightModifiers(Float gameTime)
    ; Game time: 0.0 = midnight, 0.25 = 6am, 0.5 = noon, 0.75 = 6pm
    Float hourOfDay = (gameTime - Math.Floor(gameTime)) * 24.0
    Bool isNight    = hourOfDay < 6.0 || hourOfDay > 20.0

    ActorValue avAggr = Game.GetFormFromFile(0x000002E7, "Fallout4.esm") as ActorValue
    ActorValue avConf = Game.GetFormFromFile(0x000002E8, "Fallout4.esm") as ActorValue
    If avAggr == None || avConf == None
        Return
    EndIf

    Float baseAggr = _self.GetBaseValue(avAggr)
    Float baseConf = _self.GetBaseValue(avConf)

    If Nocturnal && isNight
        ; Nocturnal: more aggressive, more confident at night
        _self.SetValue(avAggr, Math.Min(baseAggr * 1.3, 100.0))
        _self.SetValue(avConf, Math.Min(baseConf * 1.2, 100.0))
    ElseIf Nocturnal && !isNight
        ; Nocturnal in daylight: sluggish, reduced detection
        _self.SetValue(avAggr, baseAggr * 0.7)
        _self.SetValue(avConf, baseConf * 0.8)
    ElseIf Diurnal && !isNight
        ; Diurnal daytime: peak aggression
        _self.SetValue(avAggr, Math.Min(baseAggr * 1.2, 100.0))
    ElseIf Diurnal && isNight
        ; Diurnal nighttime: reduced
        _self.SetValue(avAggr, baseAggr * 0.6)
    EndIf
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; ADVANCED SENSES — Smell, Vibration, Echolocation
; ═══════════════════════════════════════════════════════════════════════════
Function CheckAdvancedSenses()
    Actor player = Game.GetPlayer()
    If player == None
        Return
    EndIf

    Float dist = _self.GetDistance(player)

    ; Smell detection (works around corners, through walls, doesn't care about LOS)
    If SmellRadius > 0 && dist <= SmellRadius
        ; Check if player is stealthed — smell ignores sneak but stacks with it
        Bool playerStealthed = player.IsSneaking()
        Float smellThreshold = SmellRadius * (playerStealthed ? 0.5 : 1.0)
        If dist <= smellThreshold && !_self.IsInCombat()
            SetHuntingState(2)  ; Begin stalk
            _stalkTarget = player
            CreatureLog("Smell detected player: " + dist + " units")
        EndIf
    EndIf

    ; Vibration detection (footsteps — only while player is moving)
    If VibrationRadius > 0 && dist <= VibrationRadius
        Bool playerMoving = player.GetVelocity().Length() > 10.0
        If playerMoving && !_self.IsInCombat()
            If dist <= VibrationRadius * 0.6
                ; Close enough — launch attack
                _self.StartCombat(player)
                CreatureLog("Vibration ambush triggered: " + dist + " units")
            Else
                SetHuntingState(2)
                _stalkTarget = player
            EndIf
        EndIf
    EndIf

    ; Echolocation (blind creatures — always on, ignores stealth)
    If EcholocationRadius > 0 && BlindCreature && dist <= EcholocationRadius
        If !_self.IsInCombat()
            _self.StartCombat(player)
            CreatureLog("Echolocation combat start: " + dist + " units")
        EndIf
    EndIf
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; HUNTING STATE MACHINE
; ═══════════════════════════════════════════════════════════════════════════
Function SetHuntingState(int newState)
    HuntingState     = newState
    _lastStateChange = Utility.GetCurrentGameTime()
    CreatureLog("State → " + newState + " (" + GetStateName(newState) + ")")
EndFunction

String Function GetStateName(int state)
    If state == 0 Return "Rest"
    ElseIf state == 1 Return "Patrol"
    ElseIf state == 2 Return "Stalk"
    ElseIf state == 3 Return "Ambush"
    ElseIf state == 4 Return "Attack"
    ElseIf state == 5 Return "Feed"
    ElseIf state == 6 Return "Retreat"
    ElseIf state == 7 Return "DenDefense"
    EndIf
    Return "Unknown"
EndFunction

Function UpdateStalkBehavior()
    If _stalkTarget == None || _stalkTarget.IsDead()
        SetHuntingState(1)  ; Back to patrol
        _stalkTarget = None
        Return
    EndIf

    Float dist = _self.GetDistance(_stalkTarget)

    If dist > StalkDistanceMax
        ; Lost them — return to patrol
        SetHuntingState(1)
        _stalkTarget = None
    ElseIf dist <= AmbushTriggerDist
        ; Close enough — launch attack
        _self.StartCombat(_stalkTarget)
        SetHuntingState(4)
    Else
        ; Keep stalking — move toward target without triggering detection
        ; The creature moves but at reduced speed to avoid detection
        _self.EvaluatePackage()
    EndIf
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; DEN PROTECTION
; ═══════════════════════════════════════════════════════════════════════════
Function CheckDenProximity()
    If DenMarker == None
        Return
    EndIf

    Actor player = Game.GetPlayer()
    Float playerToDen = player.GetDistance(DenMarker)

    If playerToDen <= DenDefenseRadius && !_self.IsInCombat()
        ; Player is in territory — defend
        Float aggrBonus = HasEggs ? 1.5 : 1.25
        ActorValue avAggr = Game.GetFormFromFile(0x000002E7, "Fallout4.esm") as ActorValue
        If avAggr != None
            _self.SetValue(avAggr, Math.Min(_self.GetBaseValue(avAggr) * aggrBonus, 100.0))
        EndIf
        _self.StartCombat(player)
        SetHuntingState(7)
        CreatureLog("Den defense triggered! Eggs: " + HasEggs)
        If HasEggs
            Debug.Notification("The " + _self.GetDisplayName() + " roars to protect its nest!")
        EndIf
    EndIf
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; ALPHA PACK AURA
; ═══════════════════════════════════════════════════════════════════════════
Function ApplyAlphaAura()
    ; Alpha leaders boost nearby pack members' confidence and aggression
    Actor[] packMembers = _self.GetActorsInRange(PackAlertRadius, 8)
    Int i = 0
    While i < packMembers.Length
        Actor member = packMembers[i]
        If member != None && member != _self && !member.IsDead()
            ActorValue avConf = Game.GetFormFromFile(0x000002E8, "Fallout4.esm") as ActorValue
            If avConf != None
                Float curConf = member.GetValue(avConf)
                If curConf < 70.0
                    member.SetValue(avConf, Math.Min(curConf + 10.0, 85.0))
                EndIf
            EndIf
        EndIf
        i += 1
    EndWhile
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; COMBAT EVENTS
; ═══════════════════════════════════════════════════════════════════════════
Event OnCombatStateChanged(Actor akSender, int aeCombatState)
    If aeCombatState == 1
        SetHuntingState(4)
        _isStalking = False
        _stalkTarget = None

        ; Pack / swarm — alert nearby members
        If SocialType == "pack" || SocialType == "swarm" || SocialType == "hive"
            AlertPackMembers(akSender.GetCombatTarget() as Actor)
        EndIf

        ; Species-specific combat entry
        HandleCombatEntry()

    ElseIf aeCombatState == 0
        ; Combat ended
        If !_self.IsDead()
            OnCombatEnded()
        EndIf
    EndIf
EndEvent

Function HandleCombatEntry()
    ; Deathclaw: roar intimidation
    If kwdDeathclaw != None && _self.HasKeyword(kwdDeathclaw)
        Debug.Notification(_self.GetDisplayName() + " roars — the ground shakes!")

    ; Glowing One: radiate
    ElseIf kwdGlowingOne != None && _self.HasKeyword(kwdGlowingOne)
        If spSpecialAbility1 != None
            _self.CastSpell(spSpecialAbility1, _self)  ; Radiation pulse
        EndIf

    ; Angler: stops glowing to prevent revealing position
    ElseIf kwdAngler != None && _self.HasKeyword(kwdAngler)
        Debug.Notification("The Angler's lure dims — it's moving!")

    ; Hermit Crab: shell up briefly before attacking
    ElseIf kwdHermitCrab != None && _self.HasKeyword(kwdHermitCrab)
        Debug.Notification("The Hermit Crab retreats into its shell!")
        Utility.Wait(1.5)
    EndIf
EndFunction

Function OnCombatEnded()
    ; Check if should return to den
    If DenMarker != None
        Float distToDen = _self.GetDistance(DenMarker)
        If distToDen > DenReturnRadius
            ; Too far from den — wander back
            SetHuntingState(1)
        EndIf
    EndIf

    ; Feeding behavior — approach nearest corpse
    If FeedDuration > 0 && !_isRetreating
        SetHuntingState(5)
        StartFeeding()
    Else
        SetHuntingState(1)
    EndIf

    _isBerserking  = False
    _isRetreating  = False
    _woundedCount  = 0
EndFunction

Event OnHit(ObjectReference akTarget, ObjectReference akAggressor, Form akSource, Projectile akProjectile, bool abPowerAttack, bool abSneakAttack, bool abBashAttack, bool abHitBlocked, string apMaterial)
    _woundedCount += 1

    ; Check HP thresholds
    ActorValue avHP = Game.GetFormFromFile(0x00000015, "Fallout4.esm") as ActorValue
    If avHP == None
        Return
    EndIf
    Float maxHP = _initMaxHP > 0 ? _initMaxHP : _self.GetBaseValue(avHP)
    Float curHP = _self.GetValue(avHP)
    Float hpPct = maxHP > 0 ? (curHP / maxHP) : 1.0

    ; Limp threshold
    If !_isLimping && hpPct <= LimpThreshold
        _isLimping = True
        ApplyLimp()
    EndIf

    ; Berserk threshold
    If CanBerserk && !_isBerserking && hpPct <= BerserkThreshold
        _isBerserking = True
        TriggerBerserk()
    EndIf

    ; Retreat threshold
    If CanRetreat && !_isRetreating && hpPct <= RetreatThreshold
        _isRetreating = True
        TriggerRetreat()
        Return
    EndIf

    ; Special ability trigger (on hit, if cooldown expired)
    Float now = Utility.GetCurrentRealTime()
    If spSpecialAbility1 != None && (now - _lastSpecialTime) >= SpecialCooldown
        _lastSpecialTime = now
        TriggerSpecialAbility(akAggressor as Actor)
    EndIf

    ; Species wound reactions
    HandleWoundReaction(hpPct, akAggressor as Actor)
EndEvent

; ═══════════════════════════════════════════════════════════════════════════
; WOUNDED STATE RESPONSES
; ═══════════════════════════════════════════════════════════════════════════
Function ApplyLimp()
    ; Reduce speed to simulate injury
    ActorValue avSpeed = Game.GetFormFromFile(0x00000036, "Fallout4.esm") as ActorValue
    If avSpeed != None
        Float baseSpeed = _self.GetBaseValue(avSpeed)
        _self.SetValue(avSpeed, baseSpeed * 0.65)
    EndIf

    ; Species-specific limp reactions
    If kwdYaoGuai != None && _self.HasKeyword(kwdYaoGuai)
        Debug.Notification("The Yao Guai snarls, wounded but still dangerous!")
    ElseIf kwdDeathclaw != None && _self.HasKeyword(kwdDeathclaw)
        Debug.Notification("The Deathclaw drags its wounded leg — it's getting more desperate!")
    EndIf
EndFunction

Function TriggerBerserk()
    ; Massive aggression/speed boost — desperate last stand
    ActorValue avAggr  = Game.GetFormFromFile(0x000002E7, "Fallout4.esm") as ActorValue
    ActorValue avSpeed = Game.GetFormFromFile(0x00000036, "Fallout4.esm") as ActorValue
    ActorValue avConf  = Game.GetFormFromFile(0x000002E8, "Fallout4.esm") as ActorValue

    If avAggr  != None  _self.SetValue(avAggr,  100.0)
    If avConf  != None  _self.SetValue(avConf,  100.0)
    If avSpeed != None
        Float baseSpeed = _self.GetBaseValue(avSpeed)
        _self.SetValue(avSpeed, baseSpeed * 1.35)  ; 35% speed burst
    EndIf

    _self.EvaluatePackage()
    SetHuntingState(4)

    ; Species berserk messages
    If kwdDeathclaw != None && _self.HasKeyword(kwdDeathclaw)
        Debug.Notification("DEATHCLAW BERSERK — It has nothing left to lose!")
    ElseIf kwdMirelurkQueen != None && _self.HasKeyword(kwdMirelurkQueen)
        Debug.Notification("The QUEEN unleashes everything — she'll defend her eggs to the death!")
    ElseIf kwdYaoGuai != None && _self.HasKeyword(kwdYaoGuai)
        Debug.Notification("The Yao Guai rears up in a final, furious charge!")
    ElseIf kwdGlowingOne != None && _self.HasKeyword(kwdGlowingOne)
        ; Glowing One death radiation pulse
        If spSpecialAbility1 != None
            _self.CastSpell(spSpecialAbility1, _self)
        EndIf
        Debug.Notification("The Glowing One pulses with lethal radiation!")
    ElseIf kwdHermitCrab != None && _self.HasKeyword(kwdHermitCrab)
        Debug.Notification("The Hermit Crab's shell CRACKS — fully exposed and enraged!")
    EndIf

    CreatureLog("BERSERK: " + _self.GetDisplayName())
EndFunction

Function TriggerRetreat()
    ; Lower confidence so the AI package can trigger flee behavior
    ActorValue avConf = Game.GetFormFromFile(0x000002E8, "Fallout4.esm") as ActorValue
    If avConf != None
        _self.SetValue(avConf, 0.0)
    EndIf
    SetHuntingState(6)
    _self.EvaluatePackage()
    CreatureLog("RETREAT: " + _self.GetDisplayName())
EndFunction

Function HandleWoundReaction(Float hpPct, Actor aggressor)
    ; Radscorpion: sting on first few hits
    If kwdRadscorpion != None && _self.HasKeyword(kwdRadscorpion)
        If _woundedCount <= 2 && spSpecialAbility1 != None && aggressor != None
            _self.CastSpell(spSpecialAbility1, aggressor)  ; Paralyzing sting
        EndIf

    ; Mirelurk: shell-up when hit from front
    ElseIf kwdMirelurk != None && _self.HasKeyword(kwdMirelurk)
        If abHitBlocked  ; Mirelurk shell blocks frontal hits
            Debug.Notification("The Mirelurk's shell deflects the attack — aim for the face!")
        EndIf

    ; Bloodbug: feeds when hits connect (heals slightly)
    ElseIf kwdBloodbug != None && _self.HasKeyword(kwdBloodbug)
        If aggressor != None && aggressor == Game.GetPlayer()
            ; When bloodbug hits player it heals itself
            ActorValue avHP = Game.GetFormFromFile(0x00000015, "Fallout4.esm") as ActorValue
            If avHP != None
                _self.RestoreValue(avHP, 8.0)
            EndIf
        EndIf

    ; Gulper: attempt swallow on close hit
    ElseIf kwdGulper != None && _self.HasKeyword(kwdGulper)
        If spSpecialAbility1 != None && aggressor != None
            Float distToAggressor = _self.GetDistance(aggressor)
            If distToAggressor < 150.0
                _self.CastSpell(spSpecialAbility1, aggressor)  ; Swallow
            EndIf
        EndIf
    EndIf
EndFunction

Function TriggerSpecialAbility(Actor akTarget)
    If akTarget == None || akTarget.IsDead()
        Return
    EndIf

    If spSpecialAbility1 != None
        _self.CastSpell(spSpecialAbility1, akTarget)

        ; Species ability messages
        If kwdRadscorpion != None && _self.HasKeyword(kwdRadscorpion)
            Debug.Notification("Radscorpion STING — paralytic venom injected!")
        ElseIf kwdMirelurk != None && _self.HasKeyword(kwdMirelurk)
            Debug.Notification("Mirelurk acid spit!")
        ElseIf kwdStingwing != None && _self.HasKeyword(kwdStingwing)
            Debug.Notification("Stingwing poison barb!")
        EndIf
    EndIf
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; FEEDING BEHAVIOR
; ═══════════════════════════════════════════════════════════════════════════
Function StartFeeding()
    _isFeeding = True
    ; In a full CK implementation: move to nearest corpse, play feed animation
    ; For now: creature stays put and "rests" with reduced detection
    ActorValue avAggr = Game.GetFormFromFile(0x000002E7, "Fallout4.esm") as ActorValue
    If avAggr != None
        _self.SetValue(avAggr, 20.0)  ; Less aggressive while feeding
    EndIf

    Utility.Wait(FeedDuration)

    _isFeeding = False
    ActorValue avAggr = Game.GetFormFromFile(0x000002E7, "Fallout4.esm") as ActorValue
    If avAggr != None
        _self.SetValue(avAggr, _self.GetBaseValue(avAggr))
    EndIf
    SetHuntingState(RestAfterKill ? 0 : 1)
    CreatureLog("Feed complete — " + (RestAfterKill ? "resting" : "returning to patrol"))
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; PACK ALERT
; ═══════════════════════════════════════════════════════════════════════════
Function AlertPackMembers(Actor akTarget)
    If akTarget == None
        Return
    EndIf
    Actor[] nearby = _self.GetActorsInRange(PackAlertRadius, 10)
    Int i = 0
    Int alerted = 0
    While i < nearby.Length
        Actor member = nearby[i]
        If member != None && member != _self && !member.IsDead() && !member.IsInCombat()
            member.StartCombat(akTarget)
            alerted += 1
        EndIf
        i += 1
    EndWhile
    If alerted > 0
        CreatureLog("Pack alerted: " + alerted + " members")
    EndIf
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; DEATH
; ═══════════════════════════════════════════════════════════════════════════
Event OnDeath(Actor akKiller)
    _isBerserking  = False
    _isRetreating  = False
    _isFeeding     = False

    ; Pack death cry
    If (SocialType == "pack" || SocialType == "hive") && akKiller != None
        AlertPackMembers(akKiller)
    EndIf

    ; Death explosion (Bloatfly, Nuka-Cola creature)
    If expDeathBlast != None
        _self.PlaceAtMe(expDeathBlast)
    EndIf

    ; Log creature death for bridge (population tracking)
    String speciesName = GetSpeciesName()
    Debug.Trace("[AAI] CREATURE_DEATH|species=" + speciesName + \
                "|location=" + _self.GetCurrentLocation().GetDisplayName() + \
                "|game_time=" + Utility.GetCurrentGameTime())
EndEvent

String Function GetSpeciesName()
    If kwdDeathclaw    != None && _self.HasKeyword(kwdDeathclaw)    Return "Deathclaw"
    ElseIf kwdRadscorpion != None && _self.HasKeyword(kwdRadscorpion) Return "Radscorpion"
    ElseIf kwdMirelurkQueen != None && _self.HasKeyword(kwdMirelurkQueen) Return "MirelurkQueen"
    ElseIf kwdMirelurk != None && _self.HasKeyword(kwdMirelurk)     Return "Mirelurk"
    ElseIf kwdYaoGuai  != None && _self.HasKeyword(kwdYaoGuai)      Return "YaoGuai"
    ElseIf kwdBloodbug != None && _self.HasKeyword(kwdBloodbug)     Return "Bloodbug"
    ElseIf kwdGlowingOne != None && _self.HasKeyword(kwdGlowingOne) Return "GlowingOne"
    ElseIf kwdFogCrawler != None && _self.HasKeyword(kwdFogCrawler) Return "FogCrawler"
    ElseIf kwdAngler   != None && _self.HasKeyword(kwdAngler)       Return "Angler"
    ElseIf kwdHermitCrab != None && _self.HasKeyword(kwdHermitCrab) Return "HermitCrab"
    ElseIf kwdGulper   != None && _self.HasKeyword(kwdGulper)       Return "Gulper"
    ElseIf kwdGorilla  != None && _self.HasKeyword(kwdGorilla)      Return "Gorilla"
    ElseIf kwdStingwing != None && _self.HasKeyword(kwdStingwing)   Return "Stingwing"
    ElseIf kwdMolerat  != None && _self.HasKeyword(kwdMolerat)      Return "Molerat"
    EndIf
    Return "Unknown"
EndFunction

; ═══════════════════════════════════════════════════════════════════════════
; LOGGING
; ═══════════════════════════════════════════════════════════════════════════
Function CreatureLog(String msg)
    Debug.Trace("[AAI-Creature] " + msg)
EndFunction
