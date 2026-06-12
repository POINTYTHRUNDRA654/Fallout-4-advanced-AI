Scriptname Hydra:Timer Hidden Native
;/ Compilation stub — runtime handled by Hydra's compiled .pex /;

; Starts a repeating timer that fires akCallback every afInterval game-mode seconds.
Function StartRepeatingGameMode(Var akCallback, Float afInterval) Global Native

; Stops a previously started repeating timer.
Function StopRepeatingGameMode(Var akCallback) Global Native
