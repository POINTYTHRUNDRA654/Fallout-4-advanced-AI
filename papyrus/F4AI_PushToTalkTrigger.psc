Scriptname F4AI:F4AI_PushToTalkTrigger extends ReferenceAlias

String Property InputPath = "Data/F4AI/bridge_input.json" Auto Const
String Property TextOutPath = "Data/F4AI/text_out.txt" Auto Const
; Keyboard fallback (Left Alt = 56). Set to -1 to disable keyboard trigger.
Int Property ActivationKey = 56 Auto Const
; Controller/game-control trigger — "Activate" = A button on Xbox, E on keyboard.
; Set UseControllerActivate = true to use the controller A button instead of / in addition to ActivationKey.
Bool Property UseControllerActivate = true Auto Const
; Assign the F4AI_Voice Sound record in CK — plays the generated WAV on the NPC
Sound Property F4AI_VoiceSound Auto
Actor ActiveTarget

Event OnInit()
    if (ActivationKey >= 0)
        RegisterForKey(ActivationKey)
    endif
    if (UseControllerActivate)
        RegisterForControl("Activate")
    endif
EndEvent

; ── Controller / remapped-key activation (A button on Xbox) ─────────────────
Event OnControlDown(String asControlName)
    if (asControlName == "Activate")
        TryTriggerAI()
    endif
EndEvent

; ── Keyboard fallback (Left Alt) ────────────────────────────────────────────
Event OnKeyDown(Int aiKeyCode)
    if (aiKeyCode == ActivationKey)
        TryTriggerAI()
    endif
EndEvent

; ── Called by CK Dialogue Fragment (Greeting Topic) ─────────────────────────
; akSpeaker is passed in directly by the dialogue system — no targeting needed.
; Conditions on the topic handle quest/scene filtering before this fires.
Function TriggerAIForSpeaker(Actor akSpeaker)
    if (akSpeaker == None || akSpeaker.IsDead())
        return
    endif
    ActiveTarget = akSpeaker
    SafeFurnitureExit(akSpeaker)
    RestrainMovementOnly(akSpeaker)

    String npcName      = akSpeaker.GetActorBase().GetName()
    String locName      = Game.GetPlayer().GetCurrentLocation().GetName()
    String raceField    = InjectRaceContext(akSpeaker)
    String weatherField = "\"weather\": \"" + GetCurrentWeatherName() + "\""
    String swimmingStr  = "false"
    if (Game.GetPlayer().IsSwimming())
        swimmingStr = "true"
    endif
    String jsonPayload = "{\"npc_name\": \"" + npcName + "\", \"location\": \"" + locName + "\", "
    jsonPayload += raceField + ", " + weatherField + ", \"is_swimming\": " + swimmingStr + ", \"player_speech\": \"\"}"
    MiscUtil.WriteToFile(InputPath, jsonPayload, false)
    WaitForVoiceReturn(akSpeaker)
EndFunction

; ── Shared trigger logic ─────────────────────────────────────────────────────
Function TryTriggerAI()
    Actor lookTarget = GetNearestNPC()

    if (lookTarget == None)
        Debug.Notification("[F4AI] No NPC in range.")
        return
    endif

    if (lookTarget.IsDead())
        return
    endif

    Race turretRace = Game.GetForm(0x0001337B) as Race
    if (lookTarget.GetRace() == turretRace)
        return
    endif
    if (lookTarget.IsInScene())
        Debug.Notification(lookTarget.GetActorBase().GetName() + " is currently busy.")
        return
    endif

    ActiveTarget = lookTarget
    SafeFurnitureExit(lookTarget)
    RestrainMovementOnly(lookTarget)

    ; Build JSON payload with full environment context
    String npcName = lookTarget.GetActorBase().GetName()
    String locName = Game.GetPlayer().GetCurrentLocation().GetName()
    String raceField = InjectRaceContext(lookTarget)
    String weatherField = "\"weather\": \"" + GetCurrentWeatherName() + "\""
    String swimmingStr = "false"
    if (Game.GetPlayer().IsSwimming())
        swimmingStr = "true"
    endif
    String swimmingField = "\"is_swimming\": " + swimmingStr
    ; player_speech is intentionally empty — bridge will run STT if enable_stt = 1
    String jsonPayload = "{\"npc_name\": \"" + npcName + "\", \"location\": \"" + locName + "\", "
    jsonPayload += raceField + ", " + weatherField + ", " + swimmingField + ", \"player_speech\": \"\"}"
    MiscUtil.WriteToFile(InputPath, jsonPayload, false)
    WaitForVoiceReturn(lookTarget)
EndFunction

Function WaitForVoiceReturn(Actor targetNPC)
    String npcName = targetNPC.GetActorBase().GetName()
    Int checksCompleted = 0
    Bool fileFound = false
    ; Wait up to 12 seconds (60 × 0.2s) — Mossy cloud AI may take a moment
    While (!fileFound && checksCompleted < 60)
        if (MiscUtil.FileExists(TextOutPath))
            fileFound = true
        else
            Utility.WaitMenuMode(0.2)
            checksCompleted += 1
        endif
    EndWhile

    if (!fileFound)
        targetNPC.SetRestrained(false)
        targetNPC.SetLookAt(None, true)
        Debug.Notification("[F4AI] No response received — is the bridge running?")
        return
    endif

    ; Read the response and clean up the file
    String responseText = MiscUtil.ReadFromFile(TextOutPath)
    MiscUtil.DeleteFile(TextOutPath)

    ; Show subtitle as an on-screen notification
    if (responseText != "")
        Debug.Notification(npcName + ": " + responseText)

        ; Play generated voice WAV through the NPC
        if (F4AI_VoiceSound != None)
            F4AI_VoiceSound.Play(targetNPC)
        endif

        ; Hold dialogue pose for reading time
        Float displayTime = 2.5 + (StringUtil.GetLength(responseText) as Float) / 13.0
        Utility.WaitMenuMode(displayTime)
    endif

    targetNPC.SetRestrained(false)
    targetNPC.SetLookAt(None, true)
    ResetFaceAnimations(targetNPC)
EndFunction

Function RestrainMovementOnly(Actor targetNPC)
    targetNPC.SetLookAt(Game.GetPlayer(), true)
    targetNPC.StopCombatAlarm()
    ; KeepOffsetFromActor is Skyrim-only — FO4 equivalent: restrain in place (still animates/talks).
    ; Released via SetRestrained(false) in the cleanup paths.
    targetNPC.SetRestrained(true)
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
    ; NOTE: Verify creature FormIDs in FO4Edit if race detection misfires.
    ; The known-good human/mutant IDs are confirmed; creature IDs are vanilla defaults.
    Race npcRace = targetNPC.GetRace()
    String raceTag = "Human"

    ; ── Human mutant variants ───────────────────────────────────────────────
    if (npcRace == Game.GetForm(0x0001D4B5) as Race)
        raceTag = "Super Mutant"
    elseif (npcRace == Game.GetForm(0x000EAFDF) as Race)
        raceTag = "Ghoul"
    elseif (npcRace == Game.GetForm(0x0002C4C6) as Race)
        raceTag = "Synth"

    ; ── Creatures ───────────────────────────────────────────────────────────
    elseif (npcRace == Game.GetForm(0x000F81ED) as Race)
        raceTag = "Deathclaw"
    elseif (npcRace == Game.GetForm(0x000B2BF2) as Race || npcRace == Game.GetForm(0x000B2BF5) as Race)
        raceTag = "Mirelurk"
    elseif (npcRace == Game.GetForm(0x0017B2A0) as Race)
        raceTag = "Radscorpion"
    elseif (npcRace == Game.GetForm(0x000B2BF4) as Race)
        raceTag = "Yao Guai"
    elseif (npcRace == Game.GetForm(0x00020198) as Race)
        raceTag = "Brahmin"
    elseif (npcRace == Game.GetForm(0x000A82AB) as Race)
        raceTag = "Dog"

    ; ── Robots ──────────────────────────────────────────────────────────────
    elseif (npcRace == Game.GetForm(0x000B2BF1) as Race)
        raceTag = "Protectron"
    elseif (npcRace == Game.GetForm(0x000B2BF0) as Race)
        raceTag = "Assaultron"
    elseif (npcRace == Game.GetForm(0x000B2BF3) as Race)
        raceTag = "Sentry Bot"
    endif

    return "\"npc_race\": \"" + raceTag + "\""
EndFunction

; ── Targeting ────────────────────────────────────────────────────────────────
; Vanilla fallback when F4SE raycast is disabled or unavailable.
; Finds the closest living, non-player NPC within 1200 game units (~22m).
Actor Function GetNearestNPC()
    Actor player = Game.GetPlayer()
    Float x = player.GetPositionX()
    Float y = player.GetPositionY()
    Float z = player.GetPositionZ()
    Actor nearest = Game.FindClosestActor(x, y, z, 1200.0)
    if (nearest == None || nearest == player || nearest.IsDead())
        return None
    endif
    return nearest
EndFunction

String Function GetCurrentWeatherName()
    Weather currentWeather = Weather.GetCurrentWeather()
    if (currentWeather == None)
        return "Clear"
    endif
    ; Radstorm — glowing green radioactive storm (0x000CC800 vanilla)
    if (currentWeather == Game.GetForm(0x000CC800) as Weather)
        return "Radstorm"
    endif
    ; Heavy Rain
    if (currentWeather == Game.GetForm(0x00034584) as Weather)
        return "Rain"
    endif
    ; Foggy
    if (currentWeather == Game.GetForm(0x00023EF0) as Weather)
        return "Fog"
    endif
    ; GetName() returns display name if the Weather form has one set in CK
    String wName = currentWeather.GetName()
    if (wName != "")
        return wName
    endif
    return "Overcast"
EndFunction

Event OnUnload()
    UnregisterForKey(ActivationKey)
    if (ActiveTarget != None)
        ActiveTarget.SetRestrained(false)
        ActiveTarget.SetLookAt(None, true)
    endif
    MiscUtil.DeleteFile("Data/F4AI/bridge_input.json")
EndEvent