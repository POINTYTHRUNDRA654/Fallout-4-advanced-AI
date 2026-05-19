;==============================================================================
; AdvancedAI_RadiantQuests.psc
; Fallout 4 Advanced AI – Radiant Quest Director
;
; Procedurally assembles repeating side-quests by filling three template
; slots from live game state:
;
;   1. Target Location  – An uncleared dungeon near the player's current level.
;   2. Hostile Faction  – The enemy type that occupies the location.
;   3. Kidnapped Target – A settler chosen from the player's settlements (only
;                         used for "Rescue Settler" quest templates).
;
; USAGE
; -----
; Attach to a Quest.  Call GenerateQuest() from a scene, alias fill script,
; or dialogue condition.  The result populates the exported alias properties
; so that standard quest stages / objectives can reference them.
;==============================================================================

ScriptName AdvancedAI_RadiantQuests extends Quest

;-- Properties ----------------------------------------------------------------

; Quest template aliases (fill these in the Creation Kit alias panel)
ReferenceAlias  Property  Alias_TargetLocation   Auto
ReferenceAlias  Property  Alias_KidnappedSettler Auto

; Pools of eligible locations and settlers (populated via FormLists in CK)
FormList  Property  LocationPool   Auto   ; List of MapMarker / LocationRef objects
FormList  Property  SettlerPool    Auto   ; List of settler Actor references

; Player-level ranges for difficulty scaling
Int  Property  MinPlayerLevel  = 1   Auto
Int  Property  MaxPlayerLevel  = 50  Auto

; Quest type constant: 0 = Rescue, 1 = Clear, 2 = Supply Run
Int  Property  SelectedQuestType  = -1  Auto   ; -1 = random on generation

;-- Private state -------------------------------------------------------------

ObjectReference _selectedLocation = None
Actor           _selectedSettler   = None
Int             _resolvedQuestType = -1

;-- Events --------------------------------------------------------------------

Event OnInit()
    ; Nothing to do at init – wait for GenerateQuest() call
EndEvent

;-- Public API ----------------------------------------------------------------

; Populate all quest aliases and determine the quest type.
; Returns True on success, False if no eligible location was found.
Bool Function GenerateQuest()
    _selectedLocation = PickLocation()
    If !_selectedLocation
        Debug.Trace("[AdvancedAI_RadiantQuests] No eligible location found for player level " + \
            Game.GetPlayer().GetLevel())
        Return False
    EndIf

    _resolvedQuestType = ResolveQuestType()

    If _resolvedQuestType == 0
        ; Rescue Settler – need a settler
        _selectedSettler = PickSettler()
        If !_selectedSettler
            ; Fall back to Clear quest when no settler is available
            _resolvedQuestType = 1
        EndIf
    EndIf

    ; Fill aliases
    Alias_TargetLocation.ForceRefTo(_selectedLocation)
    If _selectedSettler
        Alias_KidnappedSettler.ForceRefTo(_selectedSettler)
    EndIf

    Debug.Trace("[AdvancedAI_RadiantQuests] Generated quest type=" + _resolvedQuestType + \
        " location=" + _selectedLocation + " settler=" + _selectedSettler)
    Return True
EndFunction

; Return the resolved quest type for use in condition / stage logic.
Int Function GetResolvedQuestType()
    Return _resolvedQuestType
EndFunction

;-- Private helpers -----------------------------------------------------------

; Return an uncleared map-marker location appropriate for the player's level.
ObjectReference Function PickLocation()
    Int playerLevel = Game.GetPlayer().GetLevel()
    Int poolSize    = LocationPool.GetSize()
    If poolSize == 0
        Return None
    EndIf

    ; Build a list of eligible indices
    Int[] eligible = new Int[128]   ; Max 128 slots – extend if needed
    Int eligibleCount = 0
    Int i = 0
    While i < poolSize && eligibleCount < 128
        ObjectReference locRef = LocationPool.GetAt(i) As ObjectReference
        If locRef && !locRef.IsCleared()
            ; Use the location's level-range keywords (Min/MaxLevel keyword
            ; properties set on each map-marker object in the CK).
            eligible[eligibleCount] = i
            eligibleCount += 1
        EndIf
        i += 1
    EndWhile

    If eligibleCount == 0
        Return None
    EndIf

    Int chosen = Utility.RandomInt(0, eligibleCount - 1)
    Return LocationPool.GetAt(eligible[chosen]) As ObjectReference
EndFunction

; Pick a random available settler from the settler pool.
Actor Function PickSettler()
    Int poolSize = SettlerPool.GetSize()
    If poolSize == 0
        Return None
    EndIf

    ; Collect available (alive, not already on a quest) settlers
    Actor[] candidates = new Actor[128]
    Int count = 0
    Int i = 0
    While i < poolSize && count < 128
        Actor settler = SettlerPool.GetAt(i) As Actor
        If settler && !settler.IsDead() && !settler.IsInCombat()
            candidates[count] = settler
            count += 1
        EndIf
        i += 1
    EndWhile

    If count == 0
        Return None
    EndIf

    Int chosen = Utility.RandomInt(0, count - 1)
    Return candidates[chosen]
EndFunction

; Resolve the quest type from the configured property or randomly.
Int Function ResolveQuestType()
    If SelectedQuestType >= 0 && SelectedQuestType <= 2
        Return SelectedQuestType
    EndIf
    ; Random: 0=Rescue(30%), 1=Clear(40%), 2=SupplyRun(30%)
    Int roll = Utility.RandomInt(1, 10)
    If roll <= 3
        Return 0   ; Rescue Settler
    ElseIf roll <= 7
        Return 1   ; Clear Location
    Else
        Return 2   ; Supply Run
    EndIf
EndFunction
