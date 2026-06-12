Scriptname Hydra:MemMap Hidden Native
;/ Compilation stub — runtime handled by Hydra's compiled .pex /;
; Reads values from a JSON file that was cached into TempMap via Hydra:IO:Json.

; asJsonPath is a JSON pointer e.g. "/directive" or "/npc_id"
Var Function GetValue(String asFilePath, String asJsonPath) Global Native
