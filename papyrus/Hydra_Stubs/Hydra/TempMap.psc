Scriptname Hydra:TempMap Hidden Native
;/ Compilation stub — runtime handled by Hydra's compiled .pex /;
; TempMap is session-only (cleared on load). Use SaveMap for persistent data.

Var Function GetValue(String asMapName, String asKey) Global Native
Function SetValue(String asMapName, String asKey, Var avValue) Global Native
Function DeleteValue(String asMapName, String asKey) Global Native
Function ClearMap(String asMapName) Global Native
