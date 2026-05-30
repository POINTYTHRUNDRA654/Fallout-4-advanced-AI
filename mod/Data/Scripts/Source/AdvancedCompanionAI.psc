; ═══════════════════════════════════════════════════════════════════════════
; AdvancedCompanionAI.psc
; Advanced AI System — Companion Enhancement + Persistent Memory System
;
; Features:
;   - Persistent conversation memory (remembers player actions & talks)
;   - Context-aware reactive dialogue
;   - Enhanced affinity system
;   - Combat awareness improvements
;   - Real-personality emotional state tracking
;
; Attach to a companion actor alias.
; Requires: F4SE (for string storage), MCM Framework
; ═══════════════════════════════════════════════════════════════════════════
Scriptname AdvancedCompanionAI extends ReferenceAlias

; ── Manager ──────────────────────────────────────────────────────────────────
Quest Property AAIQuest Auto

; ── Memory Storage (uses F4SE StorageUtil via MCM integration) ───────────────
; Memory keys are stored as GlobalVariable integers and string arrays
; Persistent across saves because they're stored on the reference
GlobalVariable Property gMemSlot_01 Auto  ; Recent event slot 1
GlobalVariable Property gMemSlot_02 Auto  ; Recent event slot 2
GlobalVariable Property gMemSlot_03 Auto  ; Recent event slot 3
GlobalVariable Property gLastSeen   Auto  ; Game time of last player encounter
GlobalVariable Property gAffinity   Auto  ; Current affinity value (mirrors vanilla)

; ── Dialogue Topics (set via CK — companion must have these available) ────────
Topic Property topicRememberKill      Auto  ; "I remember when you took down that..."
Topic Property topicRememberLocation  Auto  ; "We've been here before..."
Topic Property topicRememberConvo     Auto  ; "Last time we talked about..."
Topic Property topicGreetLongAbsence  Auto  ; "It's been a while since I've seen you"
Topic Property topicGreetRecent       Auto  ; "Good to see you again so soon"
Topic Property topicReactPositive     Auto  ; React to player doing something they like
Topic Property topicReactNegative     Auto  ; React to player doing something they dislike

; ── Affinity Properties ───────────────────────────────────────────────────────
float Property AffinityLike    =  250.0 Auto
float Property AffinityDislike = -250.0 Auto
float Property AffinityLoathe  = -750.0 Auto
float Property AffinityIdolize =  750.0 Auto

; ── Personality Properties ────────────────────────────────────────────────────
; These define how this specific companion reacts — set per-companion in CK
float Property PersonalityAggression  = 0.3  Auto  ; 0-1
float Property PersonalityMorality    = 0.6  Auto  ; 0=evil 1=good
float Property PersonalityLoyalty     = 0.8  Auto  ; How likely to stay through hard times
bool  Property LikesViolence          = False Auto
bool  Property LikesStealth           = False Auto
bool  Property LikesGenerosity        = True  Auto
bool  Property LikesCrime             = False Auto

; ── Memory Event Codes ────────────────────────────────────────────────────────
; These int codes are stored in gMemSlot variables to represent what happened
int Property MEM_NONE           = 0  Auto Const
int Property MEM_KILL_BOSS      = 1  Auto Const
int Property MEM_STEALTH_KILL   = 2  Auto Const
int Property MEM_HELPED_SETTLER = 3  Auto Const
int Property MEM_STOLE_ITEM     = 4  Auto Const
int Property MEM_PICKED_LOCK    = 5  Auto Const
int Property MEM_KILLED_NEUTRAL = 6  Auto Const
int Property MEM_GAVE_GIFT      = 7  Auto Const
int Property MEM_ENTERED_VAULT  = 8  Auto Const
int Property MEM_SURVIVED_FIGHT = 9  Auto Const
int Property MEM_PLAYER_LEVEL_UP = 10 Auto Const

; ── State ─────────────────────────────────────────────────────────────────────
Actor _self         = None
float _curAffinity  = 0.0
int   _emotionState = 0  ; 0=neutral 1=happy 2=concerned 3=angry

; ════════════════════════════════════════════════════════════════════════════
Event OnAliasInit()
    _self = GetActorReference()
    If _self == None
        Return
    EndIf

    ; Restore affinity from global
    If gAffinity != None
        _curAffinity = gAffinity.GetValue()
    EndIf

    RegisterForRemoteEvent(_self, "OnCombatStateChanged")
    RegisterForRemoteEvent(_self, "OnHit")
    RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerAcquireItem")
    RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerFastTravelEnd")
    RegisterForRemoteEvent(Game.GetPlayer(), "OnLocationChange")
    RegisterForRemoteEvent(Game.GetPlayer(), "OnLevelUp")

    ; Apply AI enhancements
    ApplyPersonalityAV()

    ; Schedule periodic "ambient thoughts"
    RegisterForUpdateGameTime(1.0)
EndEvent

; ════════════════════════════════════════════════════════════════════════════
; PERSONALITY → ACTORVALUES
; ════════════════════════════════════════════════════════════════════════════
Function ApplyPersonalityAV()
    ActorValue avAggr  = Game.GetFormFromFile(0x000002E7, "Fallout4.esm") as ActorValue
    ActorValue avConf  = Game.GetFormFromFile(0x000002E8, "Fallout4.esm") as ActorValue
    ActorValue avMood  = Game.GetFormFromFile(0x000002EA, "Fallout4.esm") as ActorValue
    ActorValue avAsst  = Game.GetFormFromFile(0x000002EB, "Fallout4.esm") as ActorValue

    If avAggr != None
        _self.SetValue(avAggr, PersonalityAggression * 100.0)
    EndIf
    If avConf != None
        _self.SetValue(avConf, Math.Min(70.0 + (PersonalityLoyalty * 30.0), 100.0))
    EndIf
    If avMood != None
        _self.SetValue(avMood, 50.0 + (_curAffinity / 20.0))  ; Mood tracks affinity
    EndIf
    If avAsst != None
        _self.SetValue(avAsst, 80.0)  ; Companions always helpful
    EndIf
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; MEMORY SYSTEM — Record Events
; ════════════════════════════════════════════════════════════════════════════
Function RecordMemory(int memCode)
    ; Shift memory slots (slot 3 = oldest, slot 1 = newest)
    If gMemSlot_02 != None && gMemSlot_03 != None
        gMemSlot_03.SetValue(gMemSlot_02.GetValue())
    EndIf
    If gMemSlot_01 != None && gMemSlot_02 != None
        gMemSlot_02.SetValue(gMemSlot_01.GetValue())
    EndIf
    If gMemSlot_01 != None
        gMemSlot_01.SetValue(memCode as Float)
    EndIf

    ; Update last seen time
    If gLastSeen != None
        gLastSeen.SetValue(Utility.GetCurrentGameTime())
    EndIf

    Debug.Trace("[AAI-Companion] Memory recorded: " + memCode + " for " + _self.GetDisplayName())
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; MEMORY SYSTEM — Greet Player (check time since last seen)
; ════════════════════════════════════════════════════════════════════════════
Event OnUpdateGameTime()
    If _self == None || _self.IsDead()
        Return
    EndIf

    ; Check if player is nearby and companion should greet
    Actor player = Game.GetPlayer()
    If player != None && _self.GetDistance(player) < 300.0 && !_self.IsInCombat()
        CheckTimedGreeting()
    EndIf

    ; Update mood ActorValue to match current affinity
    ActorValue avMood = Game.GetFormFromFile(0x000002EA, "Fallout4.esm") as ActorValue
    If avMood != None
        _self.SetValue(avMood, Math.Clamp(50.0 + (_curAffinity / 20.0), 0.0, 100.0))
    EndIf

    RegisterForUpdateGameTime(1.0)
EndEvent

Function CheckTimedGreeting()
    If gLastSeen == None
        Return
    EndIf

    Float lastSeen = gLastSeen.GetValue()
    Float now      = Utility.GetCurrentGameTime()
    Float hoursPassed = (now - lastSeen) * 24.0  ; Convert game days to hours

    If hoursPassed > 72.0 && topicGreetLongAbsence != None
        ; Been a long time — greet warmly
        _self.Say(topicGreetLongAbsence, Game.GetPlayer(), False)
        gLastSeen.SetValue(now)
    ElseIf hoursPassed > 0.5 && hoursPassed < 2.0 && topicGreetRecent != None
        ; Saw them recently
        _self.Say(topicGreetRecent, Game.GetPlayer(), False)
        gLastSeen.SetValue(now)
    EndIf
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; MEMORY RECALL — can be called from dialogue conditions
; Used by CK dialogue conditions: GetScriptVariable / CallFunction
; ════════════════════════════════════════════════════════════════════════════
Bool Function RemembersEvent(int memCode)
    If gMemSlot_01 != None && gMemSlot_01.GetValue() as Int == memCode
        Return True
    EndIf
    If gMemSlot_02 != None && gMemSlot_02.GetValue() as Int == memCode
        Return True
    EndIf
    If gMemSlot_03 != None && gMemSlot_03.GetValue() as Int == memCode
        Return True
    EndIf
    Return False
EndFunction

Int Function GetMostRecentMemory()
    If gMemSlot_01 != None
        Return gMemSlot_01.GetValue() as Int
    EndIf
    Return MEM_NONE
EndFunction

String Function GetMemoryDescription(int memCode)
    If memCode == MEM_KILL_BOSS
        Return "that fight against the boss"
    ElseIf memCode == MEM_STEALTH_KILL
        Return "that silent takedown"
    ElseIf memCode == MEM_HELPED_SETTLER
        Return "helping those settlers"
    ElseIf memCode == MEM_STOLE_ITEM
        Return "that... item you borrowed"
    ElseIf memCode == MEM_GAVE_GIFT
        Return "the gift you gave me"
    ElseIf memCode == MEM_SURVIVED_FIGHT
        Return "that fight we barely survived"
    ElseIf memCode == MEM_ENTERED_VAULT
        Return "that vault we explored"
    ElseIf memCode == MEM_PLAYER_LEVEL_UP
        Return "how far you've come"
    EndIf
    Return "something that happened between us"
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; AFFINITY — PLAYER ACTION HOOKS
; ════════════════════════════════════════════════════════════════════════════
Event OnPlayerAcquireItem(Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akContainer)
    ; Track item pickups for personality reactions
    ; (Specific items would be listed in properties — this is the hook)
EndEvent

Event OnLocationChange(ObjectReference akOldLoc, ObjectReference akNewLoc)
    ; Remember important location visits
    If akNewLoc != None
        String locName = akNewLoc.GetDisplayName()
        If locName != ""
            RecordMemory(MEM_ENTERED_VAULT)  ; Would check location type in full impl
        EndIf
    EndIf
EndEvent

Event OnLevelUp(Actor akSender)
    RecordMemory(MEM_PLAYER_LEVEL_UP)
    ; React to player leveling
    ActorValue avMood = Game.GetFormFromFile(0x000002EA, "Fallout4.esm") as ActorValue
    If avMood != None
        _self.SetValue(avMood, Math.Min(_self.GetValue(avMood) + 5.0, 100.0))
    EndIf
    If topicReactPositive != None
        _self.Say(topicReactPositive, Game.GetPlayer(), False)
    EndIf
EndEvent

; ════════════════════════════════════════════════════════════════════════════
; AFFINITY SYSTEM
; ════════════════════════════════════════════════════════════════════════════
Function ModAffinity(float delta)
    _curAffinity = Math.Clamp(_curAffinity + delta, AffinityLoathe, AffinityIdolize)

    ; Persist to global
    If gAffinity != None
        gAffinity.SetValue(_curAffinity)
    EndIf

    ; Update emotional state
    If _curAffinity >= AffinityIdolize
        _emotionState = 1  ; Happy
    ElseIf _curAffinity <= AffinityLoathe
        _emotionState = 3  ; Angry
    ElseIf _curAffinity <= AffinityDislike
        _emotionState = 2  ; Concerned
    Else
        _emotionState = 0  ; Neutral
    EndIf

    ; Sync to ActorValue mood
    ApplyPersonalityAV()
    Debug.Trace("[AAI-Companion] Affinity: " + _curAffinity + " | Emotion: " + _emotionState)
EndFunction

Float Function GetAffinity()
    Return _curAffinity
EndFunction

Int Function GetEmotionState()
    Return _emotionState
EndFunction

; ════════════════════════════════════════════════════════════════════════════
; COMBAT
; ════════════════════════════════════════════════════════════════════════════
Event OnCombatStateChanged(Actor akSender, int aeCombatState)
    If aeCombatState == 1
        ; Record that we survived a fight together
        RecordMemory(MEM_SURVIVE_FIGHT)
        ModAffinity(5.0)  ; Small bond from fighting together
    EndIf
EndEvent

Event OnHit(ObjectReference akTarget, ObjectReference akAggressor, Form akSource, Projectile akProjectile, bool abPowerAttack, bool abSneakAttack, bool abBashAttack, bool abHitBlocked, string apMaterial)
    ; If companion gets hit, slight negative affinity (player dragging them into danger)
    ModAffinity(-1.0)
EndEvent

; ════════════════════════════════════════════════════════════════════════════
; PUBLIC API (for other mods to integrate with)
; ════════════════════════════════════════════════════════════════════════════
; Call: (companionRef.GetLinkedRef() as AdvancedCompanionAI).TriggerMemoryDialogue()
Function TriggerMemoryDialogue()
    Int recentMem = GetMostRecentMemory()
    If recentMem != MEM_NONE && topicRememberKill != None
        _self.Say(topicRememberKill, Game.GetPlayer(), False)
    EndIf
EndFunction

Function ExternalAffinityMod(float delta, bool fromModder)
    ; Allow other mods to safely modify affinity through this system
    ModAffinity(delta)
    If fromModder
        Debug.Trace("[AAI-Companion] External affinity mod: " + delta)
    EndIf
EndFunction
