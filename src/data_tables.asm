; ============================================================================
; RETROGAMERS AVENTURA 2 (RGA2) - 16-BIT SNES EDITION
; File: src/data_tables.asm
; Description: Character Stats, Stage Metadata, Portal Coordinates & Strings
; ============================================================================

; --- Playable Character Base Stats (6 Retrogamers) ---
; 0: Velberan, 1: SrWilson, 2: PaiTroll, 3: Snestalgia, 4: OldGamer, 5: Monique
CharBaseHPTable:
    .db 128, 116, 116, 120, 128, 120

CharBaseSpdTable:
    .db 2, 3, 3, 3, 2, 3

CharBaseAtkTable:
    .db 12, 10, 10, 11, 15, 11

; --- Stage BGM Track IDs (1..12) ---
StageBGMTable:
    .db 2, 3, 4, 5, 6, 7, 8, 9, 10, 11

; --- Hub Portal World X Coordinates (16-bit, aligned to the 8 OpenBOR doors in e1.gif) ---
HubPortalXTable:
    .dw 28, 93, 158, 223, 288, 354, 419, 484

; --- HUD Short Character Names (9 chars max) ---
CharNamePtrTable:
    .dw StrCharShort0, StrCharShort1, StrCharShort2, StrCharShort3, StrCharShort4, StrCharShort5

StrCharShort0: .asc "VELBERAN", 0
StrCharShort1: .asc "SRWILSON", 0
StrCharShort2: .asc "PAITROLL", 0
StrCharShort3: .asc "SNESTALG", 0
StrCharShort4: .asc "OLDGAMER", 0
StrCharShort5: .asc "MONIQUE ", 0

; --- HUD Short Stage Names (9 chars max) ---
StageNamePtrTable:
    .dw StrStg0, StrStg1, StrStg2, StrStg3, StrStg4, StrStg5, StrStg6, StrStg7, StrStg8, StrStg9

StrStg0: .asc "BGS SHOW", 0
StrStg1: .asc "ESTACAO ", 0
StrStg2: .asc "MEGAMAN ", 0
StrStg3: .asc "TURTLES ", 0
StrStg4: .asc "GOLDENAX", 0
StrStg5: .asc "S.FIGHTR", 0
StrStg6: .asc "N.GAIDEN", 0
StrStg7: .asc "S.MARIO ", 0
StrStg8: .asc "B.TOADS ", 0
StrStg9: .asc "YOUTUBE!", 0

; --- Hub Portal Prompt Strings ---
PortalPromptPtrTable:
    .dw StrPort0, StrPort1, StrPort2, StrPort3, StrPort4, StrPort5, StrPort6, StrPort7

StrPort0: .asc "P1: MEGA MAN X (UP/Y)", 0
StrPort1: .asc "P2: TURTLES NY (UP/Y)", 0
StrPort2: .asc "P3: GOLDEN AXE (UP/Y)", 0
StrPort3: .asc "P4: STREET FIGHT (UP/Y)", 0
StrPort4: .asc "P5: NINJA GAIDEN (UP/Y)", 0
StrPort5: .asc "P6: SUPER MARIO (UP/Y)", 0
StrPort6: .asc "P7: BATTLETOADS (UP/Y)", 0
StrPort7: .asc "P8: YOUTUBE BOSS (UP/Y)", 0

StrHUDGoArrow:  .asc "GO ->", 0
StrHubWalkHint: .asc "ESCOLHA UM PORTAL (UP/Y)", 0

; --- Title Screen Strings ---
StrTitleLine1:  .asc "RETROGAMERS AVENTURA 2 - SNES", 0
StrTitleLine2:  .asc "APERTE START - 16-BIT EDITION", 0
StrTitleSRAM:   .asc "PORTAIS SALVOS SRAM: ", 0

; --- Story Intro Strings ---
StrIntro1: .asc "=== BRASIL GAME SHOW (BGS) ===", 0
StrIntro2: .asc "UM FLIPERAMA MISTERIOSO SURGE", 0
StrIntro3: .asc "NO EVENTO E SUGA OS YOUTUBERS", 0
StrIntro4: .asc "PARA O MULTIVERSO DOS GAMES!", 0
StrIntro5: .asc "DERROTE OS CHEFES DOS 8 PORTAIS", 0
StrIntro6: .asc "E DETENHA O ALGORITMO DO TUBE!", 0
StrIntro7: .asc ">> APERTE START PARA JOGAR <<", 0

; --- Character Select Screen Strings ---
StrSelectHeader: .asc "ESCOLHA SEU RETROGAMER (1/6)", 0
StrSelectSub:    .asc "< ESQ/DIR TROCA - START JOGA >", 0
StrSelectFooter: .asc "START/Y: BGS - SELECT: ESTACAO", 0

SelectCharTitleTable:
    .dw StrSelName0, StrSelName1, StrSelName2, StrSelName3, StrSelName4, StrSelName5

StrSelName0: .asc "< 1. VELBERAN (EQUILIBRADO) >", 0
StrSelName1: .asc "< 2. SR WILSON (COLONIA CCA) >", 0
StrSelName2: .asc "< 3. PAI TROLL (MESTRE COMBO)>", 0
StrSelName3: .asc "< 4. SNESTALGIA (16-BIT HERO)>", 0
StrSelName4: .asc "< 5. BAU DO OLD GAMER (FORTE)>", 0
StrSelName5: .asc "< 6. MONIQUE (AGIL E TECNICA)>", 0

SelectCharSpecTable:
    .dw StrSelSpec0, StrSelSpec1, StrSelSpec2, StrSelSpec3, StrSelSpec4, StrSelSpec5

StrSelSpec0: .asc "ESP(X/A): FANTASMA COMILAO", 0
StrSelSpec1: .asc "ESP(X/A): FREAK SONIC DASH", 0
StrSelSpec2: .asc "ESP(X/A): PAI HYPER TROLL", 0
StrSelSpec3: .asc "ESP(X/A): SUPER BAZUCA 16-BIT", 0
StrSelSpec4: .asc "ESP(X/A): CALENDARIO MORTAL", 0
StrSelSpec5: .asc "ESP(X/A): DISPARO VENENOSO", 0

SelectCharStatTable:
    .dw StrSelStat0, StrSelStat1, StrSelStat2, StrSelStat3, StrSelStat4, StrSelStat5

StrSelStat0: .asc "HP: ****   VEL: ***   FOR: ***", 0
StrSelStat1: .asc "HP: ***    VEL: ****  FOR: ***", 0
StrSelStat2: .asc "HP: ***    VEL: ****  FOR: ***", 0
StrSelStat3: .asc "HP: ***    VEL: ****  FOR: ***", 0
StrSelStat4: .asc "HP: ****   VEL: **   FOR: ****", 0
StrSelStat5: .asc "HP: ***    VEL: ****  FOR: ***", 0

; --- Ending & Credits Strings ---
StrEnding1: .asc "PARABENS! VOCE ZEROU RGA2 SNES!", 0
StrEnding2: .asc "EI SPOILED E O ALGORITMO FORAM", 0
StrEnding3: .asc "DERROTADOS PELOS RETROGAMERS!", 0
StrEnding4: .asc "OBRIGADO POR JOGAR! (START)", 0

; --- Game Over Strings ---
StrGameOver1: .asc "=== GAME OVER ===", 0
StrGameOver2: .asc "APERTE START PARA CONTINUAR!", 0
