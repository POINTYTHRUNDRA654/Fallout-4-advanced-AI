; ═══════════════════════════════════════════════════════════════════════════
; AdvancedNPCAI.psc
; Advanced AI System — Humanoid NPC Behavior (Raiders, Settlers, BoS, etc.)
; Also handles Super Mutants and Synths
; Attach to ActorAlias or NPC ObjectReference
; ═══════════════════════════════════════════════════════════════════════════
Scriptname AdvancedNPCAI extends ReferenceAlias

; ── Properties ───────────────────────────────────────────────────────────────
Quest       Property AAIQuest           Auto
Keyword     Property kwdSquadLeader     Auto; AAI_SquadLeader; AAI_SquadLeader; AAI_SquadLeader; AAI_SquadLeader
Keyword     Property kwdCoverUser       Auto; AAI_UsesCover; AAI_UsesCover; AAI_UsesCover; AAI_UsesCover
Keyword     Property kwdFlanker         Auto; AAI_Flanker; AAI_Flanker; AAI_Flanker; AAI_Flanker
Keyword     Property kwdMedic           Auto; AAI_Medic (heals nearby allies); AAI_Medic (heals nearby allies); AAI_Medic (heals nearby allies); AAI_Medic (heals nearby allies)
CombatStyle Property csTactical         Auto; AAI_TacticalCombatStyle; AAI_TacticalCombatStyle; AAI_TacticalCombatStyle; AAI_TacticalCombatStyle
CombatStyle Property csAggressive       Auto; AAI_AggressiveCombatStyle; AAI_AggressiveCombatStyle; AAI_AggressiveCombatStyle; AAI_AggressiveCombatStyle
Spell       Property spHealAlly         Auto; Healing spell for Medic NPCs; Healing spell for Medic NPCs; Healing spell for Medic NPCs; Healing spell for Medic NPCs

; ── Squad Properties ──────────────────────────────────────────────────────────
float Property SquadAlertRadius    = 2000.0 Auto
float Property MoraleBreakHP       = 0.20   Auto; Flee at this HP fraction; Flee at this HP fraction; Flee at this HP fraction; Flee at this HP fraction
bool  Property CanSurrender        = False  Auto; Future: surrender system; Future: surrender system; Future: surrender system; Future: surrender system

; ── Drug / Stim use ───────────────────────────────────────────────────────────
bool  Property UsesCombatDrugs     = False  Auto; Raiders can pop Psycho; Raiders can pop Psycho; Raiders can pop Psycho; Raiders can pop Psycho
MiscObject Property itemPsycho     Auto
MiscObject Property itemMedX       Auto
MiscObject Property itemJet        Auto

; ── State ─────────────────────────────────────────────────────────────────────
bool  _moraleBroken   = False
bool  _tacticsApplied = False
Actor _actor           = None
float _lastMedicCheck = 0.0

; ════════════════════════════════════════════════════════════════════════════
Event OnAliasInit()
    _actor = GetActorReference() as Actor
    If _actor == None
        Return
    EndIf

    ; Apply combat style override
    If kwdFlanker != None && _actor.HasKeyword(kwdFlanker) && csTactical != None
        _actor.SetCombatStyle(csTactical)
    ElseIf csAggressive != None
        _actor.SetCombatStyle(csAggressive)
    EndIf

    RegisterForRemoteEvent(_actor, "OnCombatStateChanged")
    RegisterForHitEvent(_actor)
    RegisterForRemoteEvent(_actor, "OnDeath")
EndEvent

; ════════════════════════════════════════════════════════════════════════════
; COMBAT
; ════════════════════════════════════════════════════════════════════════════
Event Actor.OnCombatStateChanged(Actor akSender, Actor akTarget, Int aeCombatState)
    If aeCombatState == 1; Entering combat; Entering combat; Entering combat; Entering combat
        _moraleBroken   = False
        _tacticsApplied = False
        OnCombatStart(akSender.GetCombatTarget() as Actor)
    ElseIf aeCombatState == 0
        OnCombatEnd()
    EndIf
EndEvent

Function OnCombatStart(Actor akTarget)
    ; Squad leader calls backup
    If kwdSquadLeader != None && _actor.HasKeyword(kwdSquadLeader)
        AlertSquad(akTarget)
    EndIf

    ; Drug usage (Raiders with Psycho etc.)
    If UsesCombatDrugs
        ConsiderDrugs()
    EndIf

    _actor.EvaluatePackage()
    Debug.Trace("[AAI-NPC] Combat started: " + _actor.GetDisplayName())
EndFunction

Function OnCombatEnd()
    _moraleBroken   = False
    _tacticsApplied = False
    Debug.Trace("[AAI-NPC] Combat ended: " + _actor.GetDisplayName())
EndFunction

Event OnHit(ObjectReference akTarget, ObjectReference akAggressor, Form akSource, Projectile akProjectile, Bool abPowerAttack, Bool abSneakAttack, Bool abBashAttack, Bool abHitBlocked, String apMaterial)
    RegisterForHitEvent(_actor); hit events are single-shot in FO4 — re-arm immediately
    ; Morale check
    If !_moraleBroken
        CheckMorale()
    EndIf

    ; Medic: check if allies need healing
    If kwdMedic != None && _actor.HasKeyword(kwdMedic) && spHealAlly != None
        Float gameTime = Utility.GetCurrentGameTime()
        If gameTime - _lastMedicCheck > 0.02; ~30 seconds game time; ~30 seconds game time; ~30 seconds game time; ~30 seconds game time
            _lastMedicCheck = gameTime
            HealNearbyAllies()
        EndIf
    EndIf
EndEvent

; ════════════════════════════════════════════════════════════════════════════
; SQUAD TACTICS
; ════════════════════════════════════════════════════════════════════════════
Function AlertSquad(Actor akTarget)
    If akTarget == None
        Return
    EndIf

    Actor[] squad = MiscUtil.ScanActors(_actor, SquadAlertRadius, 10)
    Int i = 0
    While i < squad.Length
        Actor member = squad[i]
        If member != None && member != _actor && !member.IsDead()
            ; Only alert allied/friendly actors (FO4 has no GetFactions — use faction reaction)
            Int reaction = member.GetFactionReaction(_actor)
            If reaction == 2 || reaction == 3; 2 = Ally, 3 = Friend
                If !member.IsInCombat()
                    member.StartCombat(akTarget)
                EndIf
            EndIf
        EndIf
        i += 1
    EndWhile
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; MORALE SYSTEM
; ════════════════════════════════════════════════════════════════════════════
Function CheckMorale()
    ActorValue avHP = Game.GetFormFromFile(0x00000015, "Fallout4.esm") as ActorValue
    If avHP == None
        Return
    EndIf
    Float maxHP = _actor.GetBaseValue(avHP)
    Float curHP = _actor.GetValue(avHP)
    If maxHP <= 0
        Return
    EndIf

    Float hpFraction = curHP / maxHP
    If hpFraction <= MoraleBreakHP && !CanSurrender
        _moraleBroken = True
        ; Boost flee chance by temporarily lowering confidence
        ActorValue avConf = Game.GetFormFromFile(0x000002E8, "Fallout4.esm") as ActorValue
        If avConf != None
            _actor.SetValue(avConf, 0.0)
        EndIf
        _actor.EvaluatePackage()
        Debug.Trace("[AAI-NPC] Morale broken: " + _actor.GetDisplayName() + " fleeing")
    EndIf
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; MEDIC BEHAVIOR
; ════════════════════════════════════════════════════════════════════════════
Function HealNearbyAllies()
    Actor[] nearby = MiscUtil.ScanActors(_actor, 800.0, 5)
    Int i = 0
    While i < nearby.Length
        Actor ally = nearby[i]
        If ally != None && ally != _actor && !ally.IsDead() && ally.IsPlayerTeammate()
            ActorValue avHP = Game.GetFormFromFile(0x00000015, "Fallout4.esm") as ActorValue
            If avHP != None
                Float maxHP = ally.GetBaseValue(avHP)
                Float curHP = ally.GetValue(avHP)
                If curHP / maxHP < 0.5 && spHealAlly != None
                    spHealAlly.Cast(_actor, ally)
                    Debug.Trace("[AAI-NPC] Medic healed: " + ally.GetDisplayName())
                EndIf
            EndIf
        EndIf
        i += 1
    EndWhile
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; DRUG USAGE (Raiders / Gunners)
; ════════════════════════════════════════════════════════════════════════════
Function ConsiderDrugs()
    ; Randomly use a combat stim at the start of combat
    Int roll = Utility.RandomInt(1, 100)
    If roll <= 30 && itemPsycho != None
        If _actor.GetItemCount(itemPsycho) > 0
            _actor.EquipItem(itemPsycho as Form, false, true)
            Debug.Trace("[AAI-NPC] " + _actor.GetDisplayName() + " used Psycho")
        EndIf
    EndIf
EndFunction

; ════════════════════════════════════════════════════════════════════════════
Event Actor.OnDeath(Actor akSender, Actor akKiller)
    ; Trigger squad death response
    If kwdSquadLeader != None && _actor.HasKeyword(kwdSquadLeader) && akKiller != None
        ; Leader died — demoralize squad
        Actor[] squad = MiscUtil.ScanActors(_actor, SquadAlertRadius, 8)
        Int i = 0
        While i < squad.Length
            Actor member = squad[i]
            If member != None && !member.IsDead() && member.IsInCombat()
                ActorValue avConf = Game.GetFormFromFile(0x000002E8, "Fallout4.esm") as ActorValue
                If avConf != None
                    Float curConf = member.GetValue(avConf)
                    member.SetValue(avConf, Math.Max(curConf - 30.0, 0.0))
                EndIf
                member.EvaluatePackage()
            EndIf
            i += 1
        EndWhile
        Debug.Trace("[AAI-NPC] Squad leader died — squad demoralized")
    EndIf
EndEvent
