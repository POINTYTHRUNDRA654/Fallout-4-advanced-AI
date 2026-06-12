Scriptname Hydra:IO:Json Hidden Native
;/ Compilation stub — runtime handled by Hydra's compiled .pex /;

; Reads a JSON file from disk and caches it into TempMap for fast access via Hydra:MemMap.
Function Cache_TempMap(String asFilePath) Global Native

; Releases the cached JSON file from TempMap.
Function Uncache_TempMap(String asFilePath) Global Native
