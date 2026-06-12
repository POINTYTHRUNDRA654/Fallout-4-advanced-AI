Scriptname Hydra:Mutex Hidden Native
;/ Compilation stub — runtime handled by Hydra's compiled .pex /;

; Acquires a named global lock. Blocks until the lock is available.
Function LockGlobal(String asNamespace, String asKey) Global Native

; Releases a named global lock.
Function UnlockGlobal(String asNamespace, String asKey) Global Native
