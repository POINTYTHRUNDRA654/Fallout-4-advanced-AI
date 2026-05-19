Scriptname F4AI_PushToTalkTrigger extends ReferenceAlias

String Property InputPath = "Data/F4AI/bridge_input.json" Auto Const
Int Property ActivationKey = 56 Auto Const ; Left Alt
Actor ActiveTarget

Event OnInit()
    RegisterForKey(ActivationKey)
EndEvent

Event OnKeyDown(Int aiKeyCode)
    if (aiKeyCode == ActivationKey)
        ObjectReference lookTargetRef = F4SE_InternalRaycastUtils.GetPlayerCurrentCrosshairTarget()
        Actor lookTarget = lookTargetRef as Actor

        if (lookTarget == None)
            return
        endif

        if (lookTarget.IsDead())
            return
        endif

        Race turretRace = Game.GetForm(0x0001337B) as Race
        if (lookTarget.IsRace(turretRace))
            return
        endif

        ActiveTarget = lookTarget
        SafeFurnitureExit(lookTarget)
        RestrainMovementOnly(lookTarget)

        String jsonPayload = "{\"npc_name\": \"" + lookTarget.GetActorBase().GetName() + "\", \"location\": \"" + Game.GetPlayer().GetCurrentLocation().GetName() + "\", "
        jsonPayload += InjectRaceContext(lookTarget) + "}"
        MiscUtil.WriteToFile(InputPath, jsonPayload, append = false)
        WaitForVoiceReturn(lookTarget)
    endif
EndEvent

Function WaitForVoiceReturn(Actor targetNPC)
    Int checksCompleted = 0
    Bool fileFound = false
    While (!fileFound && checksCompleted < 20)
        if (MiscUtil.FileExists("Data/F4AI/text_out.txt"))
            fileFound = true
        else
            Utility.WaitMenuMode(0.2)
            checksCompleted += 1
        endif
    EndWhile

    if (!fileFound)
        targetNPC.SetRestrained(false)
        targetNPC.SetLookAt(None, abForce = true)
        Debug.Notification("[AI Sync Failed: Engine Latency]")
        return
    endif

    targetNPC.SetRestrained(false)
    targetNPC.SetLookAt(None, abForce = true)
    ResetFaceAnimations(targetNPC)
EndFunction

Function RestrainMovementOnly(Actor targetNPC)
    targetNPC.SetLookAt(Game.GetPlayer(), abForce = true)
    targetNPC.StopCombatAlarm()
    targetNPC.KeepOffsetFromActor(Game.GetPlayer(), 0.0, 0.0, 0.0)
EndFunction

Function SafeFurnitureExit(Actor targetNPC)
    if (targetNPC.GetSitState() != 0 || targetNPC.GetSleepState() != 0)
        targetNPC.Activate(targetNPC)
        Utility.Wait(1.5)
    endif
EndFunction

Function ResetFaceAnimations(Actor targetNPC)
    targetNPC.ClearExpressionOverride()
    targetNPC.EvaluatePackage()
EndFunction

String Function InjectRaceContext(Actor targetNPC)
    Race npcRace = targetNPC.GetRace()
    String raceTag = "Human"
    if (npcRace == Game.GetForm(0x0001D4B5) as Race)
        raceTag = "Super Mutant"
    elseif (npcRace == Game.GetForm(0x000EAFDF) as Race)
        raceTag = "Ghoul"
    elseif (npcRace == Game.GetForm(0x0002C4C6) as Race)
        raceTag = "Synth"
    endif
    return "\"npc_race\": \"" + raceTag + "\""
EndFunction

Event OnUnload()
    UnregisterForKey(ActivationKey)
    if (ActiveTarget != None)
        ActiveTarget.SetRestrained(false)
        ActiveTarget.SetLookAt(None, abForce = true)
    endif
    MiscUtil.DeleteFile("Data/F4AI/bridge_input.json")
EndEvent
