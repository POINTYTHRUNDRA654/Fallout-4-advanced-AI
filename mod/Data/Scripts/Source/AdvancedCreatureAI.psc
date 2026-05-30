; ═══════════════════════════════════════════════════════════════════════════
; AdvancedCreatureAI.psc
; Advanced AI System — Creature Behavior Enhancement
; Attach to an ActorAlias filled with creature refs, or use ObjectReference
; Requires: AdvancedAIManager quest to be running
; ═══════════════════════════════════════════════════════════════════════════
Scriptname AdvancedCreatureAI extends ReferenceAlias

; ── Manager Reference ────────────────────────────────────────────────────────
Quest        Property AAIQuest           Auto  ; The AdvancedAIManager quest
Keyword      Property kwdPackBehavior    Auto  ; Custom keyword: AAI_PackBehavior
Keyword      Property kwdAmbushReady     Auto  ; Custom keyword: AAI_AmbushReady
Keyword      Property kwdApexPredator    Auto  ; Custom keyword: AAI_ApexPredator (Deathclaw etc.)
CombatStyle  Property csBerserker        Auto  ; Override for apex predators
CombatStyle  Property csPackHunter       Auto  ; Override for pack creatures
CombatStyle  Property csAmbusher         Auto  ; Override for ambush creatures

; ── Behavior Properties ──────────────────────────────────────────────────────
float Property PackAlertRadius   = 1500.0 Auto  ; Alert pack within this radius
float Property AmbushTriggerDist = 600.0  Auto  ; Reveal ambush at this distance
bool  Property EnrageBelowHP     = True   Auto  ; Rage state at low HP
float Property EnrageThreshold   = 0.25   Auto  ; HP fraction for enrage

; ── State ─────────────────────────────────────────────────────────────────────
bool _isEnraged   = False
bool _ambushArmed = False
Actor _self       = None

; ════════════════════════════════════════════════════════════════════════════
; INIT
; ════════════════════════════════════════════════════════════════════════════
Event OnAliasInit()
    _self = GetActorReference()
    If _self == None
        Return
    EndIf

    ; Arm ambush if flagged
    If kwdAmbushReady != None && _self.HasKeyword(kwdAmbushReady)
        ArmAmbush()
    EndIf

    RegisterForRemoteEvent(_self, "OnCombatStateChanged")
    RegisterForRemoteEvent(_self, "OnHit")
    RegisterForRemoteEvent(_self, "OnDeath")
    RegisterForRemoteEvent(_self, "OnLoad")

    ; Override combat style for apex predators
    If kwdApexPredator != None && _self.HasKeyword(kwdApexPredator) && csBerserker != None
        _self.SetCombatStyle(csBerserker)
    ElseIf kwdPackBehavior != None && _self.HasKeyword(kwdPackBehavior) && csPackHunter != None
        _self.SetCombatStyle(csPackHunter)
    EndIf
EndEvent

; ════════════════════════════════════════════════════════════════════════════
; AMBUSH SYSTEM
; ════════════════════════════════════════════════════════════════════════════
Function ArmAmbush()
    _ambushArmed = True
    _self.SetRestrained(True)  ; Hold position until triggered
    RegisterForUpdateGameTime(0.05)  ; Check player distance every ~3 in-game minutes
EndEvent

Event OnUpdateGameTime()
    If _ambushArmed && _self != None && !_self.IsDead()
        Actor player = Game.GetPlayer()
        If player != None && _self.GetDistance(player) <= AmbushTriggerDist
            TriggerAmbush(player)
        EndIf
        RegisterForUpdateGameTime(0.05)
    EndIf
EndEvent

Function TriggerAmbush(Actor akTarget)
    _ambushArmed = False
    _self.SetRestrained(False)
    _self.StartCombat(akTarget)

    ; Alert nearby pack members
    If kwdPackBehavior != None && _self.HasKeyword(kwdPackBehavior)
        AlertPack(akTarget)
    EndIf

    Debug.Trace("[AAI-Creature] Ambush triggered: " + _self.GetDisplayName())
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; COMBAT EVENTS
; ════════════════════════════════════════════════════════════════════════════
Event OnCombatStateChanged(Actor akSender, int aeCombatState)
    If aeCombatState == 1  ; Combat entered
        ; Alert pack members
        If kwdPackBehavior != None && _self.HasKeyword(kwdPackBehavior)
            AlertPack(akSender.GetCombatTarget() as Actor)
        EndIf
    ElseIf aeCombatState == 0  ; Combat exited
        _isEnraged = False
    EndIf
EndEvent

Event OnHit(ObjectReference akTarget, ObjectReference akAggressor, Form akSource, Projectile akProjectile, bool abPowerAttack, bool abSneakAttack, bool abBashAttack, bool abHitBlocked, string apMaterial)
    If EnrageBelowHP && !_isEnraged && _self != None
        CheckEnrageCondition()
    EndIf
EndEvent

Function CheckEnrageCondition()
    ActorValue avHP = Game.GetFormFromFile(0x00000015, "Fallout4.esm") as ActorValue
    If avHP == None
        Return
    EndIf
    Float maxHP = _self.GetBaseValue(avHP)
    Float curHP = _self.GetValue(avHP)
    If maxHP > 0 && (curHP / maxHP) <= EnrageThreshold
        TriggerEnrage()
    EndIf
EndFunction

Function TriggerEnrage()
    _isEnraged = True

    ; Boost aggression and speed for the enrage state
    ActorValue avAggr  = Game.GetFormFromFile(0x000002E7, "Fallout4.esm") as ActorValue
    ActorValue avSpeed = Game.GetFormFromFile(0x00000036, "Fallout4.esm") as ActorValue

    If avAggr != None
        _self.SetValue(avAggr, 100.0)
    EndIf
    If avSpeed != None
        Float baseSpeed = _self.GetBaseValue(avSpeed)
        _self.SetValue(avSpeed, baseSpeed * 1.25)  ; 25% speed boost when enraged
    EndIf

    _self.EvaluatePackage()
    Debug.Trace("[AAI-Creature] ENRAGE: " + _self.GetDisplayName())

    ; If this is an apex predator, play a berserk behavior
    If kwdApexPredator != None && _self.HasKeyword(kwdApexPredator) && csBerserker != None
        _self.SetCombatStyle(csBerserker)
    EndIf

    Debug.Notification(_self.GetDisplayName() + " is ENRAGED!")
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; PACK BEHAVIOR
; ════════════════════════════════════════════════════════════════════════════
Function AlertPack(Actor akTarget)
    If akTarget == None
        Return
    EndIf

    Actor[] nearbyActors = _self.GetActorsInRange(PackAlertRadius, 15)
    Int i = 0
    Int alerted = 0
    While i < nearbyActors.Length
        Actor packMember = nearbyActors[i]
        If packMember != None && packMember != _self && !packMember.IsDead()
            If kwdPackBehavior == None || packMember.HasKeyword(kwdPackBehavior)
                If !packMember.IsInCombat()
                    packMember.StartCombat(akTarget)
                    alerted += 1
                EndIf
            EndIf
        EndIf
        i += 1
    EndWhile

    If alerted > 0
        Debug.Trace("[AAI-Creature] Pack alerted: " + alerted + " members by " + _self.GetDisplayName())
    EndIf
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; DEATH
; ════════════════════════════════════════════════════════════════════════════
Event OnDeath(Actor akKiller)
    ; Death cry — alert remaining pack
    If kwdPackBehavior != None && _self.HasKeyword(kwdPackBehavior) && akKiller != None
        AlertPack(akKiller)
    EndIf
    _isEnraged   = False
    _ambushArmed = False
EndEvent
