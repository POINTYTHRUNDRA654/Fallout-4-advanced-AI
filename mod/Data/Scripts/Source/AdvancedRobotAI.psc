; ═══════════════════════════════════════════════════════════════════════════
; AdvancedRobotAI.psc
; Advanced AI System — Robot & Synth Behavior Enhancement
; Handles: Assaultrons, Protectrons, Sentry Bots, Eyebots, Gen1/2 Synths
; ═══════════════════════════════════════════════════════════════════════════
Scriptname AdvancedRobotAI extends ReferenceAlias

Quest Property AAIQuest Auto

; ── Robot-Specific Properties ─────────────────────────────────────────────
Keyword  Property kwdAssaultron   Auto
Keyword  Property kwdSentryBot    Auto
Keyword  Property kwdProtectron   Auto
Keyword  Property kwdEyebot       Auto
Keyword  Property kwdSynthGen1    Auto
Keyword  Property kwdSynthGen2    Auto
Keyword  Property kwdSynthCourser Auto

; Abilities
Spell    Property spLaserCharge     Auto  ; Assaultron head laser
Spell    Property spEMPBlast        Auto  ; EMP burst (Protectron)
Spell    Property spRocketBarrage   Auto  ; Sentry Bot missiles
Explosion Property expSelfDestruct  Auto  ; Self-destruct explosion

CombatStyle Property csRobotPrecision  Auto
CombatStyle Property csCourserTactics  Auto

; ── Self-Repair ───────────────────────────────────────────────────────────
bool  Property CanSelfRepair      = True  Auto
float Property SelfRepairAmount   = 25.0  Auto  ; HP restored per repair trigger
float Property SelfRepairCooldown = 30.0  Auto  ; Real seconds between repairs
float Property SelfRepairThreshold = 0.40 Auto  ; Trigger at 40% HP

; ── Targeting ─────────────────────────────────────────────────────────────
bool  Property PrioritizeArmor    = False Auto  ; Aim for armor pieces
bool  Property PrioritizeStealth  = False Auto  ; Hunt stealthed targets

; ── State ─────────────────────────────────────────────────────────────────
bool  _repairOnCooldown = False
bool  _laserCharging    = False
float _lastRepairTime   = 0.0
Actor _self             = None

; ════════════════════════════════════════════════════════════════════════════
Event OnAliasInit()
    _self = GetActorReference()
    If _self == None
        Return
    EndIf

    ; Robots never flee — max confidence
    ActorValue avConf = Game.GetFormFromFile(0x000002E8, "Fallout4.esm") as ActorValue
    If avConf != None
        _self.SetValue(avConf, 100.0)
    EndIf

    ; Apply robot-specific combat style
    If kwdSynthCourser != None && _self.HasKeyword(kwdSynthCourser) && csCourserTactics != None
        _self.SetCombatStyle(csCourserTactics)
    ElseIf csRobotPrecision != None
        _self.SetCombatStyle(csRobotPrecision)
    EndIf

    RegisterForRemoteEvent(_self, "OnCombatStateChanged")
    RegisterForRemoteEvent(_self, "OnHit")
    RegisterForRemoteEvent(_self, "OnDeath")
EndEvent

; ════════════════════════════════════════════════════════════════════════════
; COMBAT
; ════════════════════════════════════════════════════════════════════════════
Event OnCombatStateChanged(Actor akSender, int aeCombatState)
    If aeCombatState == 1
        ActivateRobotProtocols()
    EndIf
EndEvent

Function ActivateRobotProtocols()
    ; Assaultron: begin laser charge cycle
    If kwdAssaultron != None && _self.HasKeyword(kwdAssaultron)
        _laserCharging = True
        RegisterForUpdateGameTime(0.01)  ; ~15s game time
    EndIf

    ; Eyebot: activate alarm — call nearby hostiles
    If kwdEyebot != None && _self.HasKeyword(kwdEyebot)
        AlertNearbyRobots()
    EndIf

    ; Courser: teleport to optimal position
    If kwdSynthCourser != None && _self.HasKeyword(kwdSynthCourser)
        RegisterForUpdateGameTime(0.03)  ; Teleport reposition
    EndIf

    _self.EvaluatePackage()
EndFunction

Event OnUpdateGameTime()
    If _self == None || _self.IsDead()
        Return
    EndIf

    ; Assaultron laser charge
    If _laserCharging && spLaserCharge != None && _self.IsInCombat()
        Actor target = _self.GetCombatTarget() as Actor
        If target != None
            _self.CastSpell(spLaserCharge, target)
            Debug.Trace("[AAI-Robot] Assaultron laser fired: " + _self.GetDisplayName())
        EndIf
        RegisterForUpdateGameTime(0.05)  ; Fire again after cooldown
    EndIf

    ; Courser reposition (teleport-like movement)
    If kwdSynthCourser != None && _self.HasKeyword(kwdSynthCourser) && _self.IsInCombat()
        Actor target = _self.GetCombatTarget() as Actor
        If target != None
            ; Move to a position flanking the target
            _self.EvaluatePackage()
        EndIf
        RegisterForUpdateGameTime(0.08)
    EndIf
EndEvent

Event OnHit(ObjectReference akTarget, ObjectReference akAggressor, Form akSource, Projectile akProjectile, bool abPowerAttack, bool abSneakAttack, bool abBashAttack, bool abHitBlocked, string apMaterial)
    ; Self-repair check
    If CanSelfRepair && !_repairOnCooldown
        CheckSelfRepair()
    EndIf

    ; Sentry Bot: if critically hit, activate missile barrage
    If kwdSentryBot != None && _self.HasKeyword(kwdSentryBot) && spRocketBarrage != None
        Actor aggressor = akAggressor as Actor
        If aggressor != None
            _self.CastSpell(spRocketBarrage, aggressor)
        EndIf
    EndIf
EndEvent

; ════════════════════════════════════════════════════════════════════════════
; SELF-REPAIR
; ════════════════════════════════════════════════════════════════════════════
Function CheckSelfRepair()
    ActorValue avHP = Game.GetFormFromFile(0x00000015, "Fallout4.esm") as ActorValue
    If avHP == None
        Return
    EndIf
    Float maxHP = _self.GetBaseValue(avHP)
    Float curHP = _self.GetValue(avHP)
    If maxHP <= 0
        Return
    EndIf

    If (curHP / maxHP) <= SelfRepairThreshold
        _self.RestoreValue(avHP, SelfRepairAmount)
        _repairOnCooldown = True
        Utility.Wait(SelfRepairCooldown)
        _repairOnCooldown = False
        Debug.Trace("[AAI-Robot] Self-repaired: " + _self.GetDisplayName() + " +" + SelfRepairAmount + "HP")
    EndIf
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; EYEBOT ALARM — Alert nearby robots
; ════════════════════════════════════════════════════════════════════════════
Function AlertNearbyRobots()
    Actor player = Game.GetPlayer()
    Actor[] nearby = _self.GetActorsInRange(3000.0, 10)
    Int i = 0
    While i < nearby.Length
        Actor bot = nearby[i]
        If bot != None && bot != _self && !bot.IsDead()
            If (kwdAssaultron != None && bot.HasKeyword(kwdAssaultron)) || \
               (kwdSentryBot  != None && bot.HasKeyword(kwdSentryBot))  || \
               (kwdSynthGen2  != None && bot.HasKeyword(kwdSynthGen2))
                If !bot.IsInCombat()
                    bot.StartCombat(player)
                EndIf
            EndIf
        EndIf
        i += 1
    EndWhile
    Debug.Trace("[AAI-Robot] Eyebot alarm triggered nearby robots")
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; DEATH — Self-Destruct
; ════════════════════════════════════════════════════════════════════════════
Event OnDeath(Actor akKiller)
    _laserCharging = False

    ; Sentry Bot: explode on death
    If kwdSentryBot != None && _self.HasKeyword(kwdSentryBot) && expSelfDestruct != None
        _self.PlaceAtMe(expSelfDestruct)
        Debug.Notification("SENTRY BOT SELF-DESTRUCT!")
    EndIf

    ; Assaultron: head laser deactivates
    If kwdAssaultron != None && _self.HasKeyword(kwdAssaultron) && expSelfDestruct != None
        _self.PlaceAtMe(expSelfDestruct)
    EndIf
EndEvent
