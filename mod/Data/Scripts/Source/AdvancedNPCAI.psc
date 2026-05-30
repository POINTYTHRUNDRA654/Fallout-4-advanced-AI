; ═══════════════════════════════════════════════════════════════════════════
; AdvancedNPCAI.psc
; Advanced AI System — Humanoid NPC Behavior (Raiders, Settlers, BoS, etc.)
; Also handles Super Mutants and Synths
; Attach to ActorAlias or NPC ObjectReference
; ═══════════════════════════════════════════════════════════════════════════
Scriptname AdvancedNPCAI extends ReferenceAlias

; ── Properties ───────────────────────────────────────────────────────────────
Quest       Property AAIQuest           Auto
Keyword     Property kwdSquadLeader     Auto  ; AAI_SquadLeader
Keyword     Property kwdCoverUser       Auto  ; AAI_UsesCover
Keyword     Property kwdFlanker         Auto  ; AAI_Flanker
Keyword     Property kwdMedic           Auto  ; AAI_Medic (heals nearby allies)
CombatStyle Property csTactical         Auto  ; AAI_TacticalCombatStyle
CombatStyle Property csAggressive       Auto  ; AAI_AggressiveCombatStyle
Spell       Property spHealAlly         Auto  ; Healing spell for Medic NPCs

; ── Squad Properties ──────────────────────────────────────────────────────────
float Property SquadAlertRadius    = 2000.0 Auto
float Property MoraleBreakHP       = 0.20   Auto  ; Flee at this HP fraction
bool  Property CanSurrender        = False  Auto  ; Future: surrender system

; ── Drug / Stim use ───────────────────────────────────────────────────────────
bool  Property UsesCombatDrugs     = False  Auto  ; Raiders can pop Psycho
MiscObject Property itemPsycho     Auto
MiscObject Property itemMedX       Auto
MiscObject Property itemJet        Auto

; ── State ─────────────────────────────────────────────────────────────────────
bool  _moraleBroken   = False
bool  _tacticsApplied = False
Actor _self           = None
float _lastMedicCheck = 0.0

; ════════════════════════════════════════════════════════════════════════════
Event OnAliasInit()
    _self = GetActorReference()
    If _self == None
        Return
    EndIf

    ; Apply combat style override
    If kwdFlanker != None && _self.HasKeyword(kwdFlanker) && csTactical != None
        _self.SetCombatStyle(csTactical)
    ElseIf csAggressive != None
        _self.SetCombatStyle(csAggressive)
    EndIf

    RegisterForRemoteEvent(_self, "OnCombatStateChanged")
    RegisterForRemoteEvent(_self, "OnHit")
    RegisterForRemoteEvent(_self, "OnDeath")
EndEvent

; ════════════════════════════════════════════════════════════════════════════
; COMBAT
; ════════════════════════════════════════════════════════════════════════════
Event OnCombatStateChanged(Actor akSender, int aeCombatState)
    If aeCombatState == 1  ; Entering combat
        _moraleBroken   = False
        _tacticsApplied = False
        OnCombatStart(akSender.GetCombatTarget() as Actor)
    ElseIf aeCombatState == 0
        OnCombatEnd()
    EndIf
EndEvent

Function OnCombatStart(Actor akTarget)
    ; Squad leader calls backup
    If kwdSquadLeader != None && _self.HasKeyword(kwdSquadLeader)
        AlertSquad(akTarget)
    EndIf

    ; Drug usage (Raiders with Psycho etc.)
    If UsesCombatDrugs
        ConsiderDrugs()
    EndIf

    _self.EvaluatePackage()
    Debug.Trace("[AAI-NPC] Combat started: " + _self.GetDisplayName())
EndFunction

Function OnCombatEnd()
    _moraleBroken   = False
    _tacticsApplied = False
    Debug.Trace("[AAI-NPC] Combat ended: " + _self.GetDisplayName())
EndFunction

Event OnHit(ObjectReference akTarget, ObjectReference akAggressor, Form akSource, Projectile akProjectile, bool abPowerAttack, bool abSneakAttack, bool abBashAttack, bool abHitBlocked, string apMaterial)
    ; Morale check
    If !_moraleBroken
        CheckMorale()
    EndIf

    ; Medic: check if allies need healing
    If kwdMedic != None && _self.HasKeyword(kwdMedic) && spHealAlly != None
        Float gameTime = Utility.GetCurrentGameTime()
        If gameTime - _lastMedicCheck > 0.02  ; ~30 seconds game time
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

    Actor[] squad = _self.GetActorsInRange(SquadAlertRadius, 10)
    Int i = 0
    While i < squad.Length
        Actor member = squad[i]
        If member != None && member != _self && !member.IsDead()
            ; Only alert same-faction actors
            If _self.IsInFaction(member.GetFactions(1)[0] as Faction)
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
    Float maxHP = _self.GetBaseValue(avHP)
    Float curHP = _self.GetValue(avHP)
    If maxHP <= 0
        Return
    EndIf

    Float hpFraction = curHP / maxHP
    If hpFraction <= MoraleBreakHP && !CanSurrender
        _moraleBroken = True
        ; Boost flee chance by temporarily lowering confidence
        ActorValue avConf = Game.GetFormFromFile(0x000002E8, "Fallout4.esm") as ActorValue
        If avConf != None
            _self.SetValue(avConf, 0.0)
        EndIf
        _self.EvaluatePackage()
        Debug.Trace("[AAI-NPC] Morale broken: " + _self.GetDisplayName() + " fleeing")
    EndIf
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; MEDIC BEHAVIOR
; ════════════════════════════════════════════════════════════════════════════
Function HealNearbyAllies()
    Actor[] nearby = _self.GetActorsInRange(800.0, 5)
    Int i = 0
    While i < nearby.Length
        Actor ally = nearby[i]
        If ally != None && ally != _self && !ally.IsDead() && ally.IsPlayerTeammate()
            ActorValue avHP = Game.GetFormFromFile(0x00000015, "Fallout4.esm") as ActorValue
            If avHP != None
                Float maxHP = ally.GetBaseValue(avHP)
                Float curHP = ally.GetValue(avHP)
                If curHP / maxHP < 0.5 && spHealAlly != None
                    _self.CastSpell(spHealAlly, ally)
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
        If _self.GetItemCount(itemPsycho) > 0
            _self.EquipItemEx(itemPsycho as Form)
            Debug.Trace("[AAI-NPC] " + _self.GetDisplayName() + " used Psycho")
        EndIf
    EndIf
EndFunction

; ════════════════════════════════════════════════════════════════════════════
Event OnDeath(Actor akKiller)
    ; Trigger squad death response
    If kwdSquadLeader != None && _self.HasKeyword(kwdSquadLeader) && akKiller != None
        ; Leader died — demoralize squad
        Actor[] squad = _self.GetActorsInRange(SquadAlertRadius, 8)
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
