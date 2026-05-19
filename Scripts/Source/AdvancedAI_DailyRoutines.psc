;==============================================================================
; AdvancedAI_DailyRoutines.psc
; Fallout 4 Advanced AI – Daily Life Routines
;
; Manages the AI Package scheduling system for NPCs.  Each NPC has an ordered
; list of packages.  This script evaluates the package stack on a timed basis
; and forces the appropriate package, falling back to sandbox behaviour when
; no package is eligible.
;
; USAGE
; -----
; Attach this script to a Quest (or a Scene Actor) and configure the
; exported properties in the Creation Kit.
;==============================================================================

ScriptName AdvancedAI_DailyRoutines extends Quest

;-- Properties ----------------------------------------------------------------

Actor   Property   TargetNPC      Auto    ; The NPC controlled by this script
Float   Property   TickIntervalSeconds  = 300.0  Auto  ; Real-time seconds per game-hour tick (default 5 min)

; AI Package references assigned in the Creation Kit
Package Property   pkg_Sleep   Auto
Package Property   pkg_Eat     Auto
Package Property   pkg_Work    Auto
Package Property   pkg_Relax   Auto
Package Property   pkg_Patrol  Auto
Package Property   pkg_Sandbox Auto

;-- Private state -------------------------------------------------------------

Int _lastGameHour = -1

;-- Events --------------------------------------------------------------------

Event OnInit()
    RegisterForSingleUpdate(TickIntervalSeconds)
EndEvent

Event OnUpdate()
    Int gameHour = Utility.GetCurrentGameTime() As Int % 24
    If gameHour != _lastGameHour
        _lastGameHour = gameHour
        EvaluateSchedule(gameHour)
    EndIf
    RegisterForSingleUpdate(TickIntervalSeconds)
EndEvent

;-- Functions -----------------------------------------------------------------

; Evaluate the package stack for the current game hour and force the
; highest-priority eligible package onto the NPC.
Function EvaluateSchedule(Int currentHour)
    ; Sleep  22:00 – 06:00  (priority 0)
    If IsInWindow(currentHour, 22, 6)
        ForcePackage(pkg_Sleep)
        Return
    EndIf

    ; Eat    06:00 – 08:00  (priority 1)
    If IsInWindow(currentHour, 6, 8)
        ForcePackage(pkg_Eat)
        Return
    EndIf

    ; Work   08:00 – 18:00  (priority 2)
    If IsInWindow(currentHour, 8, 18)
        ForcePackage(pkg_Work)
        Return
    EndIf

    ; Relax  18:00 – 22:00  (priority 3)
    If IsInWindow(currentHour, 18, 22)
        ForcePackage(pkg_Relax)
        Return
    EndIf

    ; No package matched → sandbox
    ForcePackage(pkg_Sandbox)
EndFunction

; Returns True when currentHour is inside the [startHour, endHour) window,
; handling midnight-crossing windows where startHour > endHour.
Bool Function IsInWindow(Int currentHour, Int startHour, Int endHour)
    If startHour <= endHour
        Return currentHour >= startHour && currentHour < endHour
    Else
        ; Wraps midnight
        Return currentHour >= startHour || currentHour < endHour
    EndIf
EndFunction

; Force the given package onto the NPC if it differs from the current one.
Function ForcePackage(Package pkgToForce)
    If TargetNPC.GetCurrentPackage() != pkgToForce
        TargetNPC.EvaluatePackage()
        ; The Creation Kit "Force Package" function is called via the package
        ; condition flags; the script signals the engine to re-evaluate here.
        Debug.Trace("[AdvancedAI_DailyRoutines] " + TargetNPC + " → " + pkgToForce)
    EndIf
EndFunction
