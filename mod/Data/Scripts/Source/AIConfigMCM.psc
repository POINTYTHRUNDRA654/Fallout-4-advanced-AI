; ═══════════════════════════════════════════════════════════════════════════
; AIConfigMCM.psc
; Advanced AI System — MCM Configuration Script
; Requires: MCM Helper (FallUI MCM) or Mod Configuration Menu
;           https://www.nexusmods.com/fallout4/mods/21497
; ═══════════════════════════════════════════════════════════════════════════
Scriptname AIConfigMCM extends MCM:BaseScript

Quest Property AAIQuest    Auto  ; The manager quest
AdvancedAIManager Property AAIManager Auto

; ── Config page IDs (match config.json IDs) ────────────────────────────────
string Property PAGE_MAIN       = "main"       Auto Const
string Property PAGE_CREATURES  = "creatures"  Auto Const
string Property PAGE_NPCS       = "npcs"       Auto Const
string Property PAGE_COMPANIONS = "companions" Auto Const
string Property PAGE_ROBOTS     = "robots"     Auto Const
string Property PAGE_DIFFICULTY = "difficulty" Auto Const
string Property PAGE_BRIDGE     = "bridge"     Auto Const

; ════════════════════════════════════════════════════════════════════════════
Event OnConfigInit()
    Pages = new string[7]
    Pages[0] = PAGE_MAIN
    Pages[1] = PAGE_CREATURES
    Pages[2] = PAGE_NPCS
    Pages[3] = PAGE_COMPANIONS
    Pages[4] = PAGE_ROBOTS
    Pages[5] = PAGE_DIFFICULTY
    Pages[6] = PAGE_BRIDGE
EndEvent

; ════════════════════════════════════════════════════════════════════════════
Event OnPageReset(string page)
    If page == PAGE_MAIN
        SetCursorFillMode(TOP_TO_BOTTOM)

        AddHeaderOption("Advanced AI System v1.0.0")
        AddToggleOptionST("TOGGLE_MASTER", "Enable Advanced AI", AAIManager.AAI_Enabled)
        AddEmptyOption()

        AddHeaderOption("AI Modules")
        AddToggleOptionST("TOGGLE_CREATURES",  "Enhanced Creature AI",   AAIManager.AAI_CreatureAI)
        AddToggleOptionST("TOGGLE_NPCS",       "Enhanced NPC AI",        AAIManager.AAI_NPCAI)
        AddToggleOptionST("TOGGLE_COMPANIONS", "Enhanced Companion AI",  AAIManager.AAI_CompanionAI)
        AddToggleOptionST("TOGGLE_ROBOTS",     "Enhanced Robot/Synth AI",AAIManager.AAI_RobotAI)
        AddEmptyOption()

        AddHeaderOption("Systems")
        AddToggleOptionST("TOGGLE_GROUPTACTICS", "Group Tactics",          AAIManager.AAI_GroupTactics)
        AddToggleOptionST("TOGGLE_DYNDIFFICULTY","Dynamic Difficulty",     AAIManager.AAI_DynamicDifficulty)
        AddToggleOptionST("TOGGLE_DETECTION",    "Detection Overhaul",     AAIManager.AAI_DetectionOverhaul)
        AddToggleOptionST("TOGGLE_COMBAT",       "Combat Style Overrides", AAIManager.AAI_CombatStyleOverride)
        AddEmptyOption()

        AddHeaderOption("Maintenance")
        AddTextOptionST("BTN_REFRESH", "Force Refresh All AI", "Refresh Now")
        AddToggleOptionST("TOGGLE_DEBUG", "Debug Logging", AAIManager.AAI_Debug)

    ElseIf page == PAGE_DIFFICULTY
        SetCursorFillMode(TOP_TO_BOTTOM)
        AddHeaderOption("Difficulty Multipliers")
        AddTextOption("", "Higher values = more dangerous AI", OPTION_FLAG_DISABLED)
        AddEmptyOption()
        AddSliderOptionST("SLIDER_AGGR",  "Aggression Mult",  AAIManager.AAI_AggressionMult,  "{1}")
        AddSliderOptionST("SLIDER_CONF",  "Confidence Mult",  AAIManager.AAI_ConfidenceMult,  "{1}")
        AddSliderOptionST("SLIDER_DET",   "Detection Mult",   AAIManager.AAI_DetectionMult,   "{1}")
        AddSliderOptionST("SLIDER_HP",    "Health Mult",      AAIManager.AAI_HealthMult,      "{1}")

    ElseIf page == PAGE_BRIDGE
        SetCursorFillMode(TOP_TO_BOTTOM)
        AddHeaderOption("Mossy AI Bridge")
        AddTextOption("", "Connect Mossy to monitor this mod", OPTION_FLAG_DISABLED)
        AddTextOption("Bridge Port", "28485", OPTION_FLAG_DISABLED)
        AddTextOption("Log Path", "Documents\\My Games\\Fallout4\\Logs\\Script\\", OPTION_FLAG_DISABLED)
        AddEmptyOption()
        AddTextOptionST("BTN_BRIDGE_HELP", "How to connect Mossy", "View Instructions")
    EndIf
EndEvent

; ════════════════════════════════════════════════════════════════════════════
Event OnOptionSelectST()
    string state = CurrentState
    If state == "BTN_REFRESH"
        AAIManager.MCM_ForceRefresh()
    ElseIf state == "BTN_BRIDGE_HELP"
        Debug.MessageBox("To connect Mossy:\n1. Open Mossy\n2. Go to FO4 Bridge tab\n3. Click Connect\n4. The bridge reads your Papyrus log at:\nDocuments\\My Games\\Fallout4\\Logs\\Script\\Papyrus.0.log")
    EndIf
EndEvent

Event OnOptionToggleST()
    string state = CurrentState
    If state == "TOGGLE_MASTER"
        AAIManager.MCM_SetEnabled(!AAIManager.AAI_Enabled)
        SetToggleOptionValueST(AAIManager.AAI_Enabled)
    ElseIf state == "TOGGLE_CREATURES"
        AAIManager.AAI_CreatureAI = !AAIManager.AAI_CreatureAI
        SetToggleOptionValueST(AAIManager.AAI_CreatureAI)
    ElseIf state == "TOGGLE_NPCS"
        AAIManager.AAI_NPCAI = !AAIManager.AAI_NPCAI
        SetToggleOptionValueST(AAIManager.AAI_NPCAI)
    ElseIf state == "TOGGLE_COMPANIONS"
        AAIManager.AAI_CompanionAI = !AAIManager.AAI_CompanionAI
        SetToggleOptionValueST(AAIManager.AAI_CompanionAI)
    ElseIf state == "TOGGLE_ROBOTS"
        AAIManager.AAI_RobotAI = !AAIManager.AAI_RobotAI
        SetToggleOptionValueST(AAIManager.AAI_RobotAI)
    ElseIf state == "TOGGLE_GROUPTACTICS"
        AAIManager.AAI_GroupTactics = !AAIManager.AAI_GroupTactics
        SetToggleOptionValueST(AAIManager.AAI_GroupTactics)
    ElseIf state == "TOGGLE_DYNDIFFICULTY"
        AAIManager.AAI_DynamicDifficulty = !AAIManager.AAI_DynamicDifficulty
        SetToggleOptionValueST(AAIManager.AAI_DynamicDifficulty)
    ElseIf state == "TOGGLE_DETECTION"
        AAIManager.AAI_DetectionOverhaul = !AAIManager.AAI_DetectionOverhaul
        SetToggleOptionValueST(AAIManager.AAI_DetectionOverhaul)
    ElseIf state == "TOGGLE_COMBAT"
        AAIManager.AAI_CombatStyleOverride = !AAIManager.AAI_CombatStyleOverride
        SetToggleOptionValueST(AAIManager.AAI_CombatStyleOverride)
    ElseIf state == "TOGGLE_DEBUG"
        AAIManager.AAI_Debug = !AAIManager.AAI_Debug
        SetToggleOptionValueST(AAIManager.AAI_Debug)
    EndIf
EndEvent

Event OnOptionSliderAcceptST(float value)
    string state = CurrentState
    If state == "SLIDER_AGGR"
        AAIManager.AAI_AggressionMult = value
        SetSliderOptionValueST(value)
    ElseIf state == "SLIDER_CONF"
        AAIManager.AAI_ConfidenceMult = value
        SetSliderOptionValueST(value)
    ElseIf state == "SLIDER_DET"
        AAIManager.AAI_DetectionMult = value
        SetSliderOptionValueST(value)
    ElseIf state == "SLIDER_HP"
        AAIManager.AAI_HealthMult = value
        SetSliderOptionValueST(value)
    EndIf
    AAIManager.MCM_SetDifficulty(AAIManager.AAI_AggressionMult, AAIManager.AAI_ConfidenceMult, AAIManager.AAI_DetectionMult, AAIManager.AAI_HealthMult)
EndEvent

Event OnOptionSliderOpenST()
    string state = CurrentState
    If state == "SLIDER_AGGR"
        SetSliderDialogStartValue(AAIManager.AAI_AggressionMult)
        SetSliderDialogDefaultValue(1.0)
        SetSliderDialogRange(0.5, 3.0)
        SetSliderDialogInterval(0.1)
    ElseIf state == "SLIDER_CONF"
        SetSliderDialogStartValue(AAIManager.AAI_ConfidenceMult)
        SetSliderDialogDefaultValue(1.0)
        SetSliderDialogRange(0.5, 3.0)
        SetSliderDialogInterval(0.1)
    ElseIf state == "SLIDER_DET"
        SetSliderDialogStartValue(AAIManager.AAI_DetectionMult)
        SetSliderDialogDefaultValue(1.0)
        SetSliderDialogRange(0.5, 2.5)
        SetSliderDialogInterval(0.1)
    ElseIf state == "SLIDER_HP"
        SetSliderDialogStartValue(AAIManager.AAI_HealthMult)
        SetSliderDialogDefaultValue(1.0)
        SetSliderDialogRange(1.0, 4.0)
        SetSliderDialogInterval(0.1)
    EndIf
EndEvent
