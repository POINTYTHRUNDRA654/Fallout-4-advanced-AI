Scriptname F4AI_VisionWidgetManager extends ReferenceAlias

String Property VisionTriggerPath = "Data/F4AI/vision_trigger.json" Auto Const
Int Property HotkeyScanKey = 48 Auto Const ; 'B' by default

Event OnInit()
    RegisterForKey(HotkeyScanKey)
EndEvent

Event OnKeyDown(Int aiKeyCode)
    if (aiKeyCode == HotkeyScanKey)
        TriggerVisualScan()
    endif
EndEvent

Function TriggerVisualScan()
    ObjectReference lookTarget = F4SE_InternalRaycastUtils.GetPlayerCurrentCrosshairTarget()

    String targetClass = "Static Object"
    String targetName = "Unknown Environment Entity"

    if (lookTarget != None)
        targetName = lookTarget.GetBaseObject().GetName()
        if (lookTarget as Actor)
            targetClass = "Actor/Living Entity"
        endif
    endif

    String jsonPayload = "{"
    jsonPayload += "\"trigger_status\": \"CAPTURE_REQUESTED\","
    jsonPayload += "\"engine_target_name\": \"" + targetName + "\","
    jsonPayload += "\"engine_target_class\": \"" + targetClass + "\""
    jsonPayload += "}"

    Debug.Notification("Scanning object via AI receptors...")
    MiscUtil.WriteToFile(VisionTriggerPath, jsonPayload, append = false)
EndFunction
