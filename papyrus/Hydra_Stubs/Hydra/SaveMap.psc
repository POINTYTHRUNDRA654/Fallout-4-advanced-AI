Scriptname Hydra:SaveMap Hidden Native
;/ Compilation stub — runtime handled by Hydra's compiled .pex /;
; SaveMap persists values across save/load. Use TempMap for session-only data.

Var Function GetValue(String asMapName, String asKey) Global Native
Function SetValue(String asMapName, String asKey, Var avValue) Global Native
Function DeleteValue(String asMapName, String asKey) Global Native
Function ClearMap(String asMapName) Global Native
