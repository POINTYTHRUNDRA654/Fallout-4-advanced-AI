Scriptname F4AI_QueueManager extends Quest

String Property OutputPath = "Data/F4AI/bridge_output.json" Auto Const

Function ProcessAIResponsePayload()
    String rawJsonString = MiscUtil.ReadFromFile(OutputPath)
    String searchKey = "\"subtitle_text\": \""
    Int keyIndexPosition = StringUtil.Find(rawJsonString, searchKey)

    If (keyIndexPosition != -1)
        Int dialogueStartIndex = keyIndexPosition + 18
        Int dialogueEndIndex = StringUtil.Find(rawJsonString, "\"", dialogueStartIndex)

        If (dialogueEndIndex > dialogueStartIndex)
            String finalSubtitleText = StringUtil.Substring(rawJsonString, dialogueStartIndex, dialogueEndIndex - dialogueStartIndex)
            Debug.Notification(finalSubtitleText)
        EndIf
    EndIf
EndFunction

Function ReadFlatAIResponse()
    If (MiscUtil.FileExists("Data/F4AI/text_out.txt"))
        String cleanSubtitle = MiscUtil.ReadFromFile("Data/F4AI/text_out.txt")
        Debug.Notification(cleanSubtitle)
        MiscUtil.DeleteFile("Data/F4AI/text_out.txt")
    EndIf
EndFunction
