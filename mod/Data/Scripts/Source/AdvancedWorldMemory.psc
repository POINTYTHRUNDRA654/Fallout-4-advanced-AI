; ═══════════════════════════════════════════════════════════════════════════
; AdvancedWorldMemory.psc
; Advanced AI System — World State Tracker
;
; Monitors player actions and logs world events to the Mossy Bridge.
; Also handles personality drift, combat pattern tracking, and reputation.
;
; The bridge reads these tagged log lines and stores them in the external DB.
; Attach to the AdvancedAIManager quest.
; ═══════════════════════════════════════════════════════════════════════════
Scriptname AdvancedWorldMemory extends Quest

Quest Property AAIQuest Auto

; ── Faction References (fill in CK) ───────────────────────────────────────────
Faction Property factionMinutemen Auto
Faction Property factionBoS       Auto
Faction Property factionRailroad  Auto
Faction Property factionInstitute Auto
Faction Property factionRaiders   Auto
Faction Property factionGunners   Auto

; ── Configuration ──────────────────────────────────────────────────────────────
bool  Property TrackCombatPatterns  = True  Auto
bool  Property TrackReputation      = True  Auto
bool  Property TrackPersonalityDrift = True Auto
bool  Property GenerateLore         = True  Auto
bool  Property Debug                = False Auto

; ── Playthrough ID ─────────────────────────────────────────────────────────────
; A unique string per save. Set on first load, persists via GlobalVariable
GlobalVariable Property gPlaythroughID Auto

; ── State ─────────────────────────────────────────────────────────────────────
String _playthroughID   = ""
int    _combatCount     = 0
int    _killCount       = 0
int    _locationCount   = 0
float  _lastCombatTime  = 0.0

; Combat tracking (reset each fight)
bool   _usedStealth     = False
bool   _usedVATS        = False
bool   _usedCover       = False
String _weaponCategory  = "rifle"

; ════════════════════════════════════════════════════════════════════════════
Event OnQuestInit()
    ; Generate or restore playthrough ID
    If gPlaythroughID != None && gPlaythroughID.GetValue() > 0
        _playthroughID = "PT_" + (gPlaythroughID.GetValue() as Int)
    Else
        _playthroughID = "PT_" + (Utility.GetCurrentGameTime() as Int)
        If gPlaythroughID != None
            gPlaythroughID.SetValue(Utility.GetCurrentGameTime())
        EndIf
    EndIf

    Actor player = Game.GetPlayer()
    RegisterForRemoteEvent(player, "OnPlayerLoadGame")
    RegisterForRemoteEvent(player, "OnCombatStateChanged")
    RegisterForRemoteEvent(player, "OnLocationChange")
    RegisterForRemoteEvent(player, "OnLevelUp")
    RegisterForRemoteEvent(player, "OnItemEquipped")
    RegisterForRemoteEvent(player, "OnSneakStateBegin")
    RegisterForRemoteEvent(player, "OnVATSStart")
    RegisterForUpdateGameTime(6.0)  ; Periodic reputation decay notification

    WorldLog("World Memory initialized | playthrough=" + _playthroughID)
EndEvent

; ════════════════════════════════════════════════════════════════════════════
; PLAYER EVENTS
; ════════════════════════════════════════════════════════════════════════════
Event OnCombatStateChanged(Actor akSender, int aeCombatState)
    If aeCombatState == 1
        ; Combat started
        _usedStealth   = False
        _usedVATS      = False
        _usedCover     = False
        _lastCombatTime = Utility.GetCurrentGameTime()
    ElseIf aeCombatState == 0
        ; Combat ended — record pattern
        If TrackCombatPatterns
            RecordCombatPattern()
        EndIf
    EndIf
EndEvent

Event OnSneakStateBegin(Actor akTarget, int aiDetectionLevel)
    If akTarget == Game.GetPlayer()
        _usedStealth = True
    EndIf
EndEvent

Event OnVATSStart()
    _usedVATS = True
EndEvent

Event OnItemEquipped(Actor akSender, Form akBaseObject, ObjectReference akReference)
    If akSender == Game.GetPlayer()
        _weaponCategory = ClassifyWeapon(akBaseObject)
    EndIf
EndEvent

Event OnLocationChange(Actor akSender, ObjectReference akOldLoc, ObjectReference akNewLoc)
    If akNewLoc == None
        Return
    EndIf

    String locName = akNewLoc.GetDisplayName()
    _locationCount += 1

    ; Log world event — player entered location
    WorldLog("WORLD_EVENT|type=entered_location|subject=Player|location=" + locName + \
             "|game_time=" + Utility.GetCurrentGameTime())

    ; Check if this is a notable location worth archiving as lore
    If GenerateLore && IsNotableLocation(akNewLoc)
        WorldLog("LORE_EVENT|playthrough=" + _playthroughID + \
                 "|type=location_visit|location=" + locName + \
                 "|significance=0.4")
    EndIf
EndEvent

Event OnLevelUp(Actor akSender)
    Int level = akSender.GetLevel()
    WorldLog("WORLD_EVENT|type=player_level_up|subject=Player|level=" + level + \
             "|game_time=" + Utility.GetCurrentGameTime())

    ; Reputation boost with nearby friendly faction on level-up
    ; (Shows the player is growing in capability — factions notice)
    If TrackReputation
        LogReputationEvent("Minutemen", 10.0, "PlayerLevelUp",
                          Game.GetPlayer().GetCurrentLocation().GetDisplayName())
    EndIf
EndEvent

; ════════════════════════════════════════════════════════════════════════════
; COMBAT PATTERN RECORDING
; ════════════════════════════════════════════════════════════════════════════
Function RecordCombatPattern()
    String approach = "balanced"
    If _usedStealth
        approach = "stealth"
    ElseIf _usedVATS
        approach = "vats"
    ElseIf _usedCover
        approach = "cover"
    EndIf

    ; Classify location type
    ObjectReference curLoc = Game.GetPlayer().GetCurrentLocation() as ObjectReference
    String locType = "outdoor"
    If curLoc != None
        String locName = curLoc.GetDisplayName()
        If locName.Find("Building") >= 0 || locName.Find("Vault") >= 0 || \
           locName.Find("Factory") >= 0 || locName.Find("Station") >= 0
            locType = "indoor"
        ElseIf locName.Find("City") >= 0 || locName.Find("Settlement") >= 0
            locType = "settlement"
        EndIf
    EndIf

    WorldLog("COMBAT_PATTERN|weapon=" + _weaponCategory + \
             "|approach=" + approach + \
             "|vats=" + _usedVATS + \
             "|stealth=" + _usedStealth + \
             "|cover=" + _usedCover + \
             "|loc_type=" + locType + \
             "|game_time=" + Utility.GetCurrentGameTime())

    _combatCount += 1

    ; Reset combat flags
    _usedStealth = False
    _usedVATS    = False
    _usedCover   = False
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; REPUTATION LOGGING
; ════════════════════════════════════════════════════════════════════════════
Function LogReputationEvent(String faction, Float delta, String reason, String location)
    If !TrackReputation
        Return
    EndIf
    WorldLog("REP_EVENT|faction=" + faction + \
             "|delta=" + delta + \
             "|reason=" + reason + \
             "|location=" + location + \
             "|game_time=" + Utility.GetCurrentGameTime())
EndFunction

; Call these from other scripts when the player does faction-affecting things
Function PlayerHelpedFaction(String factionName, Float amount, String reason)
    LogReputationEvent(factionName, amount, reason,
                       Game.GetPlayer().GetCurrentLocation().GetDisplayName())
EndFunction

Function PlayerHarmedFaction(String factionName, Float amount, String reason)
    LogReputationEvent(factionName, -amount, reason,
                       Game.GetPlayer().GetCurrentLocation().GetDisplayName())
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; PERSONALITY DRIFT LOGGING
; ════════════════════════════════════════════════════════════════════════════
Function LogPersonalityDrift(String npcId, String npcName,
                              Float aggrDelta, Float moralDelta,
                              Float loyalDelta, Float trustDelta,
                              String reason)
    If !TrackPersonalityDrift
        Return
    EndIf
    WorldLog("PERSONALITY_DRIFT|npc_id=" + npcId + \
             "|npc_name=" + npcName + \
             "|aggr=" + aggrDelta + \
             "|moral=" + moralDelta + \
             "|loyal=" + loyalDelta + \
             "|trust=" + trustDelta + \
             "|reason=" + reason)
EndFunction

; Example: companion drift when player does something immoral
Function CompanionWitnessedImmoral(Actor companion, String eventDesc)
    LogPersonalityDrift(
        companion.GetActorBase().GetFormID() as String,
        companion.GetDisplayName(),
        0.02,   ; Slightly more aggressive (hardened by witnessing)
        -0.05,  ; Less moral (compromised)
        -0.03,  ; Slight loyalty loss
        -0.08,  ; Trust in player drops
        "witnessed_immoral_act: " + eventDesc
    )
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; WORLD EVENT LOGGING
; ════════════════════════════════════════════════════════════════════════════
Function LogWorldEvent(String eventType, String subject, String location, String faction)
    WorldLog("WORLD_EVENT|type=" + eventType + \
             "|subject=" + subject + \
             "|location=" + location + \
             "|faction=" + faction + \
             "|game_time=" + Utility.GetCurrentGameTime())

    ; Lore generation for significant events
    If GenerateLore && IsSignificantEvent(eventType)
        WorldLog("LORE_EVENT|playthrough=" + _playthroughID + \
                 "|type=" + eventType + \
                 "|subject=" + subject + \
                 "|location=" + location + \
                 "|significance=0.75")
    EndIf
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; PERIODIC — Reputation decay notification
; ════════════════════════════════════════════════════════════════════════════
Event OnUpdateGameTime()
    ; Tell the bridge that time has passed so it can apply rep decay
    WorldLog("TIME_TICK|game_time=" + Utility.GetCurrentGameTime())
    RegisterForUpdateGameTime(6.0)
EndEvent

; ════════════════════════════════════════════════════════════════════════════
; HELPERS
; ════════════════════════════════════════════════════════════════════════════
String Function ClassifyWeapon(Form item)
    If item == None
        Return "unarmed"
    EndIf
    String name = item.GetName()
    If name.Find("Rifle") >= 0 || name.Find("Laser") >= 0 || name.Find("Plasma") >= 0
        Return "rifle"
    ElseIf name.Find("Pistol") >= 0 || name.Find("10mm") >= 0
        Return "pistol"
    ElseIf name.Find("Shotgun") >= 0
        Return "shotgun"
    ElseIf name.Find("Sniper") >= 0 || name.Find(".50") >= 0
        Return "sniper"
    ElseIf name.Find("Pipe") >= 0 || name.Find("Minigun") >= 0
        Return "heavy"
    ElseIf name.Find("Grenade") >= 0 || name.Find("Mine") >= 0 || name.Find("Fatman") >= 0
        Return "explosives"
    ElseIf name.Find("Knife") >= 0 || name.Find("Bat") >= 0 || name.Find("Machete") >= 0
        Return "melee"
    EndIf
    Return "rifle"
EndFunction

Bool Function IsNotableLocation(ObjectReference loc)
    If loc == None
        Return False
    EndIf
    String name = loc.GetDisplayName()
    Return name.Find("Diamond City") >= 0 || name.Find("Vault") >= 0 || \
           name.Find("Prydwen") >= 0 || name.Find("Institute") >= 0 || \
           name.Find("Goodneighbor") >= 0 || name.Find("Castle") >= 0
EndFunction

Bool Function IsSignificantEvent(String eventType)
    Return eventType == "cleared_location" || eventType == "killed_boss" || \
           eventType == "joined_faction"   || eventType == "completed_quest" || \
           eventType == "found_artifact"   || eventType == "defeated_legend"
EndFunction

Function WorldLog(String msg)
    Debug.Trace("[AAI] " + msg)
    If Debug
        Debug.Notification("[AAI-World] " + msg)
    EndIf
EndFunction
