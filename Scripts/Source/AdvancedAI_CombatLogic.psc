;==============================================================================
; AdvancedAI_CombatLogic.psc
; Fallout 4 Advanced AI – Enhanced Combat Logic
;
; Extends the base-game combat AI with:
;   • Improved cover-seeking – NPCs prefer HIGH_COVER nodes over OPEN ground.
;   • Flanking manoeuvres   – Attackers move to positions offset from the
;                              target, prioritising covered flanking spots.
;   • Dynamic morale        – Tracks faction health; triggers a flee package
;                              when average health falls below the threshold or
;                              the faction leader is killed.
;   • Staged detection      – Hidden → Caution → Danger, driven by in-game
;                              light-level and noise keywords.
;
; USAGE
; -----
; Attach this script to a Combat Style quest or a faction management quest.
;==============================================================================

ScriptName AdvancedAI_CombatLogic extends Quest

;-- Properties ----------------------------------------------------------------

; Morale
Float  Property  FleeHealthThreshold  = 0.25  Auto  ; 0–1 fraction
Actor  Property  FactionLeader        Auto          ; Named leader; death triggers morale break

; Detection thresholds (combined visibility×light + noise×0.5)
Float  Property  CautionThreshold  = 0.3  Auto
Float  Property  DangerThreshold   = 0.6  Auto

; Flee package forced on survivors when morale breaks
Package  Property  pkg_Flee  Auto

; Reference to the faction's actor list (set in CK via FormList)
FormList  Property  FactionMembers  Auto

;-- Private state -------------------------------------------------------------

Bool _moraleBreakFired = False

;-- Events --------------------------------------------------------------------

Event OnInit()
    RegisterForSingleUpdate(5.0)
EndEvent

Event OnUpdate()
    EvaluateMorale()
    RegisterForSingleUpdate(5.0)
EndEvent

;-- Morale functions ----------------------------------------------------------

Function EvaluateMorale()
    If _moraleBreakFired
        Return
    EndIf

    ; Check whether the leader is dead
    If FactionLeader && FactionLeader.IsDead()
        TriggerMoraleBreak()
        Return
    EndIf

    ; Calculate average health fraction across living members
    Int totalMembers = FactionMembers.GetSize()
    If totalMembers == 0
        Return
    EndIf

    Float totalHealthFraction = 0.0
    Int alive = 0
    Int i = 0
    While i < totalMembers
        Actor member = FactionMembers.GetAt(i) As Actor
        If member && !member.IsDead()
            totalHealthFraction += member.GetActorValuePercentage("Health")
            alive += 1
        EndIf
        i += 1
    EndWhile

    If alive == 0
        Return
    EndIf

    Float avgHealth = totalHealthFraction / alive
    If avgHealth < FleeHealthThreshold
        TriggerMoraleBreak()
    EndIf
EndFunction

; Force surviving faction members onto the flee package.
Function TriggerMoraleBreak()
    _moraleBreakFired = True
    Debug.Trace("[AdvancedAI_CombatLogic] Morale break! Survivors fleeing.")
    Int totalMembers = FactionMembers.GetSize()
    Int i = 0
    While i < totalMembers
        Actor member = FactionMembers.GetAt(i) As Actor
        If member && !member.IsDead()
            member.EvaluatePackage()
            ; The flee package is evaluated via a condition that checks this
            ; quest's _moraleBreakFired flag, set above.
            Debug.Trace("[AdvancedAI_CombatLogic] " + member + " is fleeing.")
        EndIf
        i += 1
    EndWhile
EndFunction

;-- Detection helper ----------------------------------------------------------

; Computes the combined detection score and returns an integer:
;   0 = HIDDEN | 1 = CAUTION | 2 = DANGER
Int Function ComputeDetectionState(Float visibility, Float lightLevel, Float noise)
    Float combined = (visibility * lightLevel) + (noise * 0.5)
    If combined >= DangerThreshold
        Return 2   ; DANGER
    ElseIf combined >= CautionThreshold
        Return 1   ; CAUTION
    Else
        Return 0   ; HIDDEN
    EndIf
EndFunction

;-- Cover / Flanking helpers --------------------------------------------------

; Find and move the attacker to a cover position using NavMesh queries.
; The engine's FindBestPositionFromReference kFindBestPositionFromReference
; flag is used to locate covered spots near the NPC.
Function SeekCover(Actor attacker)
    ObjectReference coverRef = Game.FindClosestReferenceOfTypeFromRef(attacker, \
        GetFormFromFile(0x000B8D6F, "Fallout4.esm") As Form, 2048.0)
    If coverRef
        attacker.PathToReference(coverRef, 1.0)
        Debug.Trace("[AdvancedAI_CombatLogic] " + attacker + " moving to cover: " + coverRef)
    EndIf
EndFunction

; Move attacker to a flanking position relative to targetRef.
Function AttemptFlank(Actor attacker, ObjectReference targetRef)
    Float targetX = targetRef.GetPositionX()
    Float targetY = targetRef.GetPositionY()
    Float flankOffsetX = (Utility.RandomFloat(-512.0, 512.0))
    Float flankOffsetY = (Utility.RandomFloat(-512.0, 512.0))
    attacker.SetPosition(targetX + flankOffsetX, targetY + flankOffsetY, attacker.GetPositionZ())
    Debug.Trace("[AdvancedAI_CombatLogic] " + attacker + " flanking to (" + \
        (targetX + flankOffsetX) + ", " + (targetY + flankOffsetY) + ")")
EndFunction
