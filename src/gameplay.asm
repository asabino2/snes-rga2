; ============================================================================
; RETROGAMERS AVENTURA 2 (RGA2) - 16-BIT SNES EDITION
; File: src/gameplay.asm
; Description: Game State Machine, Character Select, Hub & 2.5D Beat 'em Up Engine
; ============================================================================

; ============================================================================
; RunGameStateFrame: Dispatches current frame logic based on DP_STATE
; ============================================================================
RunGameStateFrame:
    SEP #$20
    .a8
    REP #$10
    .i16
    LDA DP_STATE
    CMP #STATE_TITLE
    BNE CheckStateIntro
    JMP UpdateTitleState
CheckStateIntro:
    CMP #STATE_INTRO
    BNE CheckStateSelect
    JMP UpdateIntroState
CheckStateSelect:
    CMP #STATE_SELECT
    BNE CheckStateHub
    JMP UpdateSelectState
CheckStateHub:
    CMP #STATE_HUB
    BNE CheckStateStage
    JMP UpdateHubState
CheckStateStage:
    CMP #STATE_STAGE
    BNE CheckStateEnding
    JMP UpdateStageState
CheckStateEnding:
    CMP #STATE_ENDING
    BNE CheckStateGameOver
    JMP UpdateEndingState
CheckStateGameOver:
    JMP UpdateGameOverState


; ============================================================================
; STATE 0: TITLE SCREEN (Converted from Bgs/Title.gif)
; ============================================================================
EnterTitleState:
    SEP #$20
    .a8
    REP #$10
    .i16
    LDA #STATE_TITLE
    STA DP_STATE

    JSR ClearOAMBuffer
    JSR ClearBG3Buffer

    ; Load Title Screen Package from Bank $C4
    LDA #$C4
    JSR LoadScreenPackage

    ; Draw dark text backing box at rows 21..25 (offset $0540, 160 tiles)
    LDX #$0540
    LDY #$00A0
    JSR FillBG3TilesDark

    ; Print Title Screen Strings
    LDA #$20
    STA DP_TMP0
    LDX #$0546              ; Row 21, Col 3
    LDY #StrTitleLine1
    JSR PrintBG3String

    LDA #$24
    STA DP_TMP0
    LDX #$0588              ; Row 22, Col 4
    LDY #StrTitleLine2
    JSR PrintBG3String

    LDA #$28
    STA DP_TMP0
    LDX #$0606              ; Row 24, Col 3
    LDY #StrTitleSRAM
    JSR PrintBG3String

    ; Count cleared portals in DP_PORTALS (0..8) and display at Row 24, Col 25
    LDA DP_PORTALS
    LDY #$0008
    STZ DP_TMP1
CountPortalsLoop:
    LSR
    BCC SkipPortalBit
    INC DP_TMP1
SkipPortalBit:
    DEY
    BNE CountPortalsLoop

    LDX #$0632              ; Row 24, Col 25
    LDA DP_TMP1
    CLC
    ADC #$10                ; '0' + count
    STA !BG3_MAP_BUF,X
    LDA #$20
    STA !BG3_MAP_BUF+1,X
    LDA #$0F                ; '/'
    STA !BG3_MAP_BUF+2,X
    LDA #$20
    STA !BG3_MAP_BUF+3,X
    LDA #$18                ; '8'
    STA !BG3_MAP_BUF+4,X
    LDA #$20
    STA !BG3_MAP_BUF+5,X

    LDA #$01
    STA DP_HUD_DIRTY

    ; Play Title BGM (Track 1)
    LDA #$01
    JSR PlayBGMTrack
    RTS

UpdateTitleState:
    SEP #$20
    .a8
    REP #$10
    .i16
    ; Blink "PRESS START" on Row 22
    LDA DP_FRAME
    AND #$1F
    BNE CheckTitleStart
    LDA #$01
    STA DP_HUD_DIRTY

CheckTitleStart:
    REP #$20
    .a16
    LDA DP_JOY_NEW
    AND #$D080              ; START ($1000) | B ($8000) | Y ($4000) | A ($0080)
    BEQ TitleNoPress
    SEP #$20
    .a8
    LDA #$09                ; Portal Beep SFX
    JSR PlaySFX
    JSR EnterIntroState
TitleNoPress:
    SEP #$20
    .a8
    RTS


; ============================================================================
; STATE 1: STORY INTRO SCREEN (Brasil Game Show Arcade Mystery)
; ============================================================================
EnterIntroState:
    SEP #$20
    .a8
    REP #$10
    .i16
    LDA #STATE_INTRO
    STA DP_STATE

    JSR ClearOAMBuffer
    JSR ClearBG3Buffer

    ; Load BGS Background ($C8) as visual backdrop for story intro
    LDA #$C8
    JSR LoadScreenPackage

    ; Fill rows 6..21 with dark text box
    LDX #$0180
    LDY #$0200
    JSR FillBG3TilesDark

    LDA #$20
    STA DP_TMP0
    LDX #$01C4              ; Row 7, Col 2
    LDY #StrIntro1
    JSR PrintBG3String

    LDA #$28
    STA DP_TMP0
    LDX #$0244              ; Row 9, Col 2
    LDY #StrIntro2
    JSR PrintBG3String

    LDX #$0284              ; Row 10, Col 2
    LDY #StrIntro3
    JSR PrintBG3String

    LDX #$02C4              ; Row 11, Col 2
    LDY #StrIntro4
    JSR PrintBG3String

    LDA #$24
    STA DP_TMP0
    LDX #$0344              ; Row 13, Col 2
    LDY #StrIntro5
    JSR PrintBG3String

    LDX #$0384              ; Row 14, Col 2
    LDY #StrIntro6
    JSR PrintBG3String

    LDA #$20
    STA DP_TMP0
    LDX #$0446              ; Row 17, Col 3
    LDY #StrIntro7
    JSR PrintBG3String

    LDA #$01
    STA DP_HUD_DIRTY
    RTS

UpdateIntroState:
    REP #$20
    .a16
    LDA DP_JOY_NEW
    AND #$D080              ; START | B | Y | A
    BEQ IntroNoPress
    SEP #$20
    .a8
    LDA #$08                ; Pickup/Confirm SFX
    JSR PlaySFX
    JSR EnterSelectState
IntroNoPress:
    SEP #$20
    .a8
    RTS


; ============================================================================
; STATE 2: CHARACTER SELECT SCREEN (6 Playable Retrogamers!)
; ============================================================================
EnterSelectState:
    SEP #$20
    .a8
    REP #$10
    .i16
    LDA #STATE_SELECT
    STA DP_STATE

    JSR ClearOAMBuffer
    JSR ClearBG3Buffer

    ; Load Character Select Screen Package ($C5)
    LDA #$C5
    JSR LoadScreenPackage

    ; Load currently selected character sprites & portrait
    JSR LoadPlayerSprites
    JSR DrawSelectScreenUI
    RTS

DrawSelectScreenUI:
    SEP #$20
    .a8
    REP #$10
    .i16
    JSR ClearBG3Buffer

    ; Top Banner (Rows 1..3)
    LDX #$0040
    LDY #$0060
    JSR FillBG3TilesDark

    LDA #$20
    STA DP_TMP0
    LDX #$0046              ; Row 1, Col 3
    LDY #StrSelectHeader
    JSR PrintBG3String

    ; Dynamically update character index digit in "(1/6)" .. "(6/6)" at Row 1, Col 27 ($0076)
    LDA DP_CHAR_ID
    CLC
    ADC #$11                ; '1' ($11) + DP_CHAR_ID (0..5)
    STA !BG3_MAP_BUF+$0076

    LDA #$28
    STA DP_TMP0
    LDX #$0082              ; Row 2, Col 1
    LDY #StrSelectSub
    JSR PrintBG3String

    ; Bottom Character Card Box (Rows 16..25)
    LDX #$0400
    LDY #$0140
    JSR FillBG3TilesDark

    ; Print Character Full Title (Row 17, Col 1)
    LDA #$20
    STA DP_TMP0
    LDA DP_CHAR_ID
    ASL
    TAX
    REP #$20
    .a16
    LDA !SelectCharTitleTable,X
    TAY
    SEP #$20
    .a8
    LDX #$0442
    JSR PrintBG3String

    ; Print Character Special Move Description (Row 19, Col 1)
    LDA #$24
    STA DP_TMP0
    LDA DP_CHAR_ID
    ASL
    TAX
    REP #$20
    .a16
    LDA !SelectCharSpecTable,X
    TAY
    SEP #$20
    .a8
    LDX #$04C2
    JSR PrintBG3String

    ; Print Character Stats Line (Row 21, Col 1)
    LDA #$28
    STA DP_TMP0
    LDA DP_CHAR_ID
    ASL
    TAX
    REP #$20
    .a16
    LDA !SelectCharStatTable,X
    TAY
    SEP #$20
    .a8
    LDX #$0542
    JSR PrintBG3String

    ; Print Controls Footer (Row 23, Col 1)
    LDA #$20
    STA DP_TMP0
    LDX #$05C2
    LDY #StrSelectFooter
    JSR PrintBG3String

    LDA #$01
    STA DP_HUD_DIRTY
    RTS

UpdateSelectState:
    SEP #$20
    .a8
    REP #$10
    .i16

    ; Check D-Pad LEFT ($0200)
    LDA DP_JOY_NEW_H
    BIT #$02
    BEQ CheckSelRight
    LDA DP_CHAR_ID
    BNE DecCharID
    LDA #$05
    STA DP_CHAR_ID
    BRA ChangedCharSelection
DecCharID:
    DEC DP_CHAR_ID
    BRA ChangedCharSelection

CheckSelRight:
    LDA DP_JOY_NEW_H
    BIT #$01
    BEQ CheckSelConfirm
    LDA DP_CHAR_ID
    CMP #$05
    BCC IncCharID
    STZ DP_CHAR_ID
    BRA ChangedCharSelection
IncCharID:
    INC DP_CHAR_ID

ChangedCharSelection:
    LDA #$08                ; SFX get.wav
    JSR PlaySFX
    JSR LoadPlayerSprites
    JSR DrawSelectScreenUI

CheckSelConfirm:
    ; Animate preview sprites in OAM:
    ; OAM Slot 0: Character Portrait (Slot 11) at (X=88, Y=84)
    LDX #$0000
    LDA #88
    STA DP_TMP0
    LDA #84
    STA DP_TMP1
    LDA #11                 ; Slot 11 = Portrait
    STA DP_TMP2
    STZ DP_TMP3             ; Palette 0, No flip
    JSR SetOAMSprite

    ; OAM Slot 1: Animated Character Sprite (cycles Idle/Walk/Attack) at (X=136, Y=84)
    LDX #$0004
    LDA #136
    STA DP_TMP0
    LDA #84
    STA DP_TMP1
    LDA DP_FRAME
    LSR
    LSR
    LSR
    LSR
    AND #$07
    STA DP_TMP2             ; Cycles slots 0..7!
    STZ DP_TMP3
    JSR SetOAMSprite

    ; Check SELECT button ($2000) -> Shortcut directly to Estação Central Hub!
    LDA DP_JOY_NEW_H
    BIT #$20
    BEQ CheckSelStartBGS
    JSR InitNewGameStats
    JSR EnterHubState
    RTS

CheckSelStartBGS:
    REP #$20
    .a16
    LDA DP_JOY_NEW
    AND #$D080              ; START | B | Y | A
    BEQ SelectDoneFrame
    SEP #$20
    .a8
    LDA #$07                ; Special Voice SFX!
    JSR PlaySFX
    JSR InitNewGameStats
    STZ DP_STAGE_ID         ; Stage 0 = Brasil Game Show (BGS)
    JSR EnterStageState
SelectDoneFrame:
    SEP #$20
    .a8
    RTS

InitNewGameStats:
    SEP #$20
    .a8
    REP #$10
    .i16
    LDA #$03
    STA DP_LIVES
    STA DP_CREDITS
    REP #$20
    .a16
    STZ DP_SCORE
    SEP #$20
    .a8
    ; Load character base stats from table
    LDA DP_CHAR_ID
    TAX
    LDA !CharBaseHPTable,X
    STA DP_PL_MAXHP
    STA DP_PL_HP
    LDA !CharBaseSpdTable,X
    STA DP_PL_SPD
    LDA !CharBaseAtkTable,X
    STA DP_PL_ATK
    LDA #100
    STA DP_PL_MP
    RTS


; ============================================================================
; STATE 3: ESTACAO CENTRAL HUB WORLD (Interactive 8-Portal Station!)
; ============================================================================
EnterHubState:
    SEP #$20
    .a8
    REP #$10
    .i16
    LDA #STATE_HUB
    STA DP_STATE
    LDA #$01
    STA DP_STAGE_ID         ; Stage 1 = Hub

    JSR ClearOAMBuffer
    JSR ClearBG3Buffer

    ; Load Hub Graphic Package ($C9 = stage_01_hub.bin)
    LDA #$C9
    JSR LoadScreenPackage
    JSR LoadPlayerSprites
    JSR LoadStageEnemyAndBossSprites
    JSR LoadUniversalFXSprites

    ; Position Player at entrance of Station
    REP #$20
    .a16
    LDA #$0038
    STA DP_PL_X
    STZ DP_CAM_X
    SEP #$20
    .a8
    LDA #164
    STA DP_PL_Z
    STZ DP_PL_Y_OFF
    STZ DP_PL_VY
    STZ DP_PL_DIR
    STZ DP_PL_ACT
    LDA DP_PL_MAXHP
    STA DP_PL_HP
    LDA #100
    STA DP_PL_MP
    STZ DP_BOSS_ACT
    LDA #$01
    STA DP_WAVE_LOCK
    LDA #$FF
    STA DP_NEAR_PORTAL

    ; Play Hub BGM (Track 3 = Elevador / Station Theme)
    LDA #$03
    JSR PlayBGMTrack
    JSR DrawGameplayHUD
    RTS

UpdateHubState:
    SEP #$20
    .a8
    REP #$10
    .i16

    ; Update Player movement inside Hub
    JSR UpdatePlayerMovementOnly

    ; Update Camera to follow Player across 512px wide Station (DP_CAM_X = 0..256)
    JSR UpdateCameraScroll

    ; Check proximity to the 8 Portals (X = 64, 116, 168, 220, 272, 324, 376, 428)
    LDA #$FF
    STA DP_NEAR_PORTAL
    LDY #$0000              ; Portal index 0..7
CheckHubPortalLoop:
    TYA
    ASL
    TAX
    REP #$20
    .a16
    LDA DP_PL_X
    SEC
    SBC !HubPortalXTable,X
    BPL HubDistPos
    EOR #$FFFF
    INC
HubDistPos:
    CMP #$0016              ; Within 22 pixels of portal center?
    BCS NextHubPortal
    SEP #$20
    .a8
    TYA
    STA DP_NEAR_PORTAL
    BRA FoundNearPortal
NextHubPortal:
    SEP #$20
    .a8
    INY
    CPY #$0008
    BCC CheckHubPortalLoop

FoundNearPortal:
    ; Redraw HUD if frame % 8 == 0 or near portal
    LDA DP_FRAME
    AND #$07
    BNE SkipHubHUDRefresh
    JSR DrawGameplayHUD
SkipHubHUDRefresh:

    ; Render OAM Sprites: Player + Visible Portals
    JSR ClearOAMBuffer
    JSR RenderPlayerOAM

    ; Render the 8 Portal Gates in OAM Slots 1..8 (OAM offset $04..$20)
    LDY #$0000
RenderHubPortalsLoop:
    TYA
    ASL
    TAX
    REP #$20
    .a16
    LDA !HubPortalXTable,X
    SEC
    SBC DP_CAM_X
    ; Check if on screen (0..228)
    BMI SkipRenderOnePortal
    CMP #$00E4
    BCS SkipRenderOnePortal
    SEP #$20
    .a8
    STA DP_TMP0             ; Screen X
    LDA #108
    STA DP_TMP1             ; Screen Y of Portal Arch
    LDA #28                 ; Slot 28 = Portal Gate Sprite
    STA DP_TMP2
    LDA #$06                ; OBJ Palette 3 (Universal FX/Portal Palette)
    STA DP_TMP3
    TYA
    INC
    ASL
    ASL
    TAX                     ; OAM offset = (portal_idx + 1) * 4
    JSR SetOAMSprite
SkipRenderOnePortal:
    SEP #$20
    .a8
    INY
    CPY #$0008
    BCC RenderHubPortalsLoop

    ; Check if Player presses UP ($0800), Y ($4000), or START ($1000) while near a portal
    LDA DP_NEAR_PORTAL
    CMP #$FF
    BEQ HubDoneFrame
    REP #$20
    .a16
    LDA DP_JOY_NEW
    AND #$5880              ; Y ($4000) | START ($1000) | UP ($0800) | A ($0080)
    BEQ HubDoneFrame
    SEP #$20
    .a8
    LDA #$09                ; Portal Warp SFX!
    JSR PlaySFX
    LDA DP_NEAR_PORTAL
    CLC
    ADC #$02                ; Stage ID = Portal_Index + 2 (2..9)
    STA DP_STAGE_ID
    JSR EnterStageState
HubDoneFrame:
    SEP #$20
    .a8
    RTS


; ============================================================================
; STATE 4: 2.5D BEAT 'EM UP STAGE & BOSS ENGINE (BGS + 8 Portals!)
; ============================================================================
EnterStageState:
    SEP #$20
    .a8
    REP #$10
    .i16
    LDA #STATE_STAGE
    STA DP_STATE

    JSR ClearOAMBuffer
    JSR ClearBG3Buffer

    ; Look up Stage Graphic Bank ($C8 + DP_STAGE_ID)
    LDA DP_STAGE_ID
    CLC
    ADC #$C8
    JSR LoadScreenPackage

    ; Load Player, Stage Enemy, Stage Boss & FX Sprites into OBJ VRAM
    JSR LoadPlayerSprites
    JSR LoadStageEnemyAndBossSprites
    JSR LoadUniversalFXSprites

    ; Initialize Player Stage Position & Combat State
    REP #$20
    .a16
    LDA #$0030
    STA DP_PL_X
    STZ DP_CAM_X
    SEP #$20
    .a8
    LDA #164
    STA DP_PL_Z
    STZ DP_PL_Y_OFF
    STZ DP_PL_VY
    STZ DP_PL_DIR
    STZ DP_PL_ACT
    STZ DP_PL_TIMER
    STZ DP_PL_COMBO
    STZ DP_PL_INV
    LDA DP_PL_MAXHP
    STA DP_PL_HP
    LDA #100
    STA DP_PL_MP

    STZ DP_PROJ_ACT
    STZ DP_ITEM_ACT
    STZ DP_SPARK_TMR
    STZ DP_BOSS_ACT
    STZ DP_WAVE_NUM

    ; Spawn Wave 0 of Enemies
    JSR SpawnCurrentStageWave

    ; Start Stage BGM Track (StageBGMTable[DP_STAGE_ID])
    LDA DP_STAGE_ID
    TAX
    LDA !StageBGMTable,X
    JSR PlayBGMTrack

    JSR DrawGameplayHUD
    RTS


; ============================================================================
; UpdateStageState: Main 60Hz Beat 'em Up Loop
; ============================================================================
UpdateStageState:
    SEP #$20
    .a8
    REP #$10
    .i16

    ; 1. Update Player Input, Jumps, Combos, Special & Movement
    JSR UpdatePlayerCombatAndMove

    ; 2. Update Camera Scrolling (when wave lock is 0 or advancing)
    JSR UpdateCameraScroll

    ; 3. Update Special Projectile & Item Pickups
    JSR UpdateProjectileAndItems

    ; 4. Update Enemy & Boss AI + Wave Progression
    JSR UpdateEnemiesAndWaves

    ; 5. Refresh HUD every 4 frames
    LDA DP_FRAME
    AND #$03
    BNE SkipStageHUD
    JSR DrawGameplayHUD
SkipStageHUD:

    ; 6. Build OAM Sprites for Player, Enemies/Boss, Projectile, Pickups & Hit Sparks
    JSR ClearOAMBuffer
    JSR RenderPlayerOAM
    JSR RenderStageEntitiesOAM
    RTS


; ============================================================================
; UpdatePlayerMovementOnly: Used in Hub World
; ============================================================================
UpdatePlayerMovementOnly:
    SEP #$20
    .a8
    REP #$10
    .i16
    STZ DP_TMP0             ; Moved flag = 0

    ; Check LEFT ($02) / RIGHT ($01) in DP_JOY_CUR_H
    LDA DP_JOY_CUR_H
    BIT #$02
    BEQ CheckHubMoveRight
    LDA #$01
    STA DP_PL_DIR           ; Facing Left
    STA DP_TMP0
    REP #$20
    .a16
    LDA DP_PL_X
    SEC
    SBC #$0002
    CMP #$0014
    BCS StoreHubXLeft
    LDA #$0014
StoreHubXLeft:
    STA DP_PL_X
    SEP #$20
    .a8
    BRA CheckHubMoveUpDown

CheckHubMoveRight:
    BIT #$01
    BEQ CheckHubMoveUpDown
    STZ DP_PL_DIR           ; Facing Right
    LDA #$01
    STA DP_TMP0
    REP #$20
    .a16
    LDA DP_PL_X
    CLC
    ADC #$0002
    CMP #$01D8              ; Max X = 472
    BCC StoreHubXRight
    LDA #$01D8
StoreHubXRight:
    STA DP_PL_X
    SEP #$20
    .a8

CheckHubMoveUpDown:
    LDA DP_JOY_CUR_H
    BIT #$08                ; UP
    BEQ CheckHubDown
    LDA #$01
    STA DP_TMP0
    LDA DP_PL_Z
    SEC
    SBC #$01
    CMP #128
    BCS StoreHubZUp
    LDA #128
StoreHubZUp:
    STA DP_PL_Z
    BRA UpdateHubAnim

CheckHubDown:
    BIT #$04                ; DOWN
    BEQ UpdateHubAnim
    LDA #$01
    STA DP_TMP0
    LDA DP_PL_Z
    CLC
    ADC #$01
    CMP #188
    BCC StoreHubZDown
    LDA #188
StoreHubZDown:
    STA DP_PL_Z

UpdateHubAnim:
    LDA DP_TMP0
    BEQ HubIdleAnim
    ; Walk cycle (Slots 2, 3, 4)
    LDA DP_FRAME
    LSR
    LSR
    LSR
    AND #$03
    CMP #$03
    BNE SetHubWalkSlot
    LDA #$01
SetHubWalkSlot:
    CLC
    ADC #$02
    STA DP_PL_ANIM
    RTS
HubIdleAnim:
    LDA DP_FRAME
    LSR
    LSR
    LSR
    LSR
    AND #$01
    STA DP_PL_ANIM
    RTS


; ============================================================================
; UpdatePlayerCombatAndMove: Full Beat 'em Up Player Controller
; ============================================================================
UpdatePlayerCombatAndMove:
    SEP #$20
    .a8
    REP #$10
    .i16

    ; Decrement invincibility & combo timers
    LDA DP_PL_INV
    BEQ SkipDecInv
    DEC DP_PL_INV
SkipDecInv:
    LDA DP_PL_COMBO
    BEQ SkipDecCombo
    DEC DP_PL_COMBO
SkipDecCombo:
    LDA DP_SPARK_TMR
    BEQ SkipDecSpark
    DEC DP_SPARK_TMR
SkipDecSpark:

    ; Passive MP regeneration (+1 MP every 32 frames up to 100)
    LDA DP_FRAME
    AND #$1F
    BNE SkipMPRegen
    LDA DP_PL_MP
    CMP #100
    BCS SkipMPRegen
    INC DP_PL_MP
SkipMPRegen:

    ; --- Handle Airborne Jump Physics if DP_PL_Y_OFF > 0 or DP_PL_VY != 0 ---
    LDA DP_PL_Y_OFF
    ORA DP_PL_VY
    BEQ PlayerOnGround
    ; Apply vertical velocity: DP_PL_Y_OFF += DP_PL_VY; DP_PL_VY -= 1
    LDA DP_PL_Y_OFF
    CLC
    ADC DP_PL_VY
    BMI LandedOnGround
    BEQ LandedOnGround
    STA DP_PL_Y_OFF
    DEC DP_PL_VY
    ; Allow mid-air Jump Kick on Y press!
    LDA DP_JOY_NEW_H
    BIT #$40                ; BTN_Y
    BEQ AirHorizontalMove
    LDA #$08                ; Slot 8 = Jump Attack
    STA DP_PL_ANIM
    LDA #$04                ; SFX Punch
    JSR PlaySFX
    LDA DP_PL_ATK
    CLC
    ADC #$04
    STA DP_TMP4
    JSR CheckPlayerMeleeHits
    BRA AirHorizontalMove

LandedOnGround:
    STZ DP_PL_Y_OFF
    STZ DP_PL_VY
    STZ DP_PL_ACT
    STZ DP_PL_TIMER
    BRA PlayerOnGround

AirHorizontalMove:
    LDA #$08
    STA DP_PL_ANIM
    JMP HandleEightWayWalk

PlayerOnGround:
    ; Check if currently in Hurt/Attack/Special animation timer
    LDA DP_PL_TIMER
    BEQ CheckPlayerNewActions
    DEC DP_PL_TIMER
    BNE PlayerActionBusy
    STZ DP_PL_ACT
    BRA CheckPlayerNewActions
PlayerActionBusy:
    ; Allow Special Cancel (X or A pressed) at any point during normal attacks!
    LDA DP_JOY_NEW
    AND #$C0
    BNE CheckSpecialBtn
    ; Allow chaining Attack 1 -> Attack 2 -> Attack 3 if Y pressed when timer <= 6!
    LDA DP_PL_TIMER
    CMP #$07
    BCS DonePlayerCombatUpdate
    LDA DP_JOY_NEW_H
    BIT #$40                ; BTN_Y pressed during combo window?
    BNE TriggerMeleeCombo
DonePlayerCombatUpdate:
    RTS

CheckPlayerNewActions:
    ; 1. Check L/R Shoulder Buttons for Guard / Block ($0030 in DP_JOY_CUR)
    LDA DP_JOY_CUR
    AND #$30
    BEQ CheckSpecialBtn
    LDA #$07                ; ACT_BLOCK
    STA DP_PL_ACT
    LDA #10                 ; Slot 10 = Block/Guard pose
    STA DP_PL_ANIM
    RTS

CheckSpecialBtn:
    ; 2. Check X ($40) or A ($80) in DP_JOY_NEW for Special Attack (costs 20 MP)
    LDA DP_JOY_NEW
    AND #$C0
    BEQ CheckJumpBtn
    LDA DP_PL_MP
    CMP #20
    BCC CheckJumpBtn
    SEC
    SBC #20
    STA DP_PL_MP
    LDA #$05                ; ACT_SPECIAL
    STA DP_PL_ACT
    LDA #18
    STA DP_PL_TIMER
    LDA #24
    STA DP_PL_INV           ; Invincibility frames during Special!
    LDA #9                  ; Slot 9 = Special Pose
    STA DP_PL_ANIM
    LDA #$07                ; SFX Special Voice (grito.wav)!
    JSR PlaySFX

    ; Spawn Special Projectile & deal shockwave melee hit
    JSR SpawnPlayerProjectile
    LDA DP_PL_ATK
    ASL                     ; 2x damage shockwave!
    STA DP_TMP4
    JSR CheckPlayerMeleeHits
    RTS

CheckJumpBtn:
    ; 3. Check B Button ($80 in DP_JOY_NEW_H) for Jump
    LDA DP_JOY_NEW_H
    BIT #$80
    BEQ CheckAttackBtn
    LDA #$04                ; ACT_JUMP
    STA DP_PL_ACT
    LDA #$07                ; Initial upward jump velocity
    STA DP_PL_VY
    LDA #$01
    STA DP_PL_Y_OFF
    LDA #8                  ; Slot 8 = Jump
    STA DP_PL_ANIM
    LDA #$06                ; SFX Jump (jump.wav)
    JSR PlaySFX
    RTS

CheckAttackBtn:
    ; 4. Check Y Button ($40 in DP_JOY_NEW_H) for 3-Hit Melee Combo
    LDA DP_JOY_NEW_H
    BIT #$40
    BEQ HandleEightWayWalk

TriggerMeleeCombo:
    LDA #$04                ; SFX Punch (punch2.wav)
    JSR PlaySFX

    LDA DP_PL_COMBO
    BEQ StartComboHit1
    LDA DP_PL_ACT
    CMP #$01
    BEQ StartComboHit2
    CMP #$02
    BEQ StartComboHit3

StartComboHit1:
    LDA #$01                ; Attack 1 (Jab)
    STA DP_PL_ACT
    LDA #11
    STA DP_PL_TIMER
    LDA #24
    STA DP_PL_COMBO
    LDA #5                  ; Slot 5 = Attack 1
    STA DP_PL_ANIM
    LDA DP_PL_ATK
    STA DP_TMP4
    JSR CheckPlayerMeleeHits
    RTS

StartComboHit2:
    LDA #$02                ; Attack 2 (Cross)
    STA DP_PL_ACT
    LDA #12
    STA DP_PL_TIMER
    LDA #24
    STA DP_PL_COMBO
    LDA #6                  ; Slot 6 = Attack 2
    STA DP_PL_ANIM
    LDA DP_PL_ATK
    CLC
    ADC #$03
    STA DP_TMP4
    JSR CheckPlayerMeleeHits
    RTS

StartComboHit3:
    LDA #$03                ; Attack 3 (Heavy Finisher!)
    STA DP_PL_ACT
    LDA #16
    STA DP_PL_TIMER
    STZ DP_PL_COMBO
    LDA #7                  ; Slot 7 = Attack 3 Finisher
    STA DP_PL_ANIM
    LDA DP_PL_ATK
    ASL                     ; 2x Heavy Finisher Damage!
    STA DP_TMP4
    JSR CheckPlayerMeleeHits
    RTS

HandleEightWayWalk:
    ; Use Hub movement routine for 8-way D-Pad movement & stage boundaries
    JSR UpdatePlayerMovementOnly

    ; Clamp Player X to current camera view [DP_CAM_X + 12 .. DP_CAM_X + 224]
    REP #$20
    .a16
    LDA DP_CAM_X
    CLC
    ADC #$000C
    CMP DP_PL_X
    BCC CheckRightCamBound
    STA DP_PL_X
CheckRightCamBound:
    LDA DP_CAM_X
    CLC
    ADC #$00DF
    CMP DP_PL_X
    BCS DoneClampCamX
    STA DP_PL_X
DoneClampCamX:
    SEP #$20
    .a8
    RTS


; ============================================================================
; UpdateCameraScroll: Scrolls BG1/BG2 horizontally as Player walks right/left
; ============================================================================
UpdateCameraScroll:
    SEP #$20
    .a8
    REP #$10
    .i16
    ; In Stage mode, only scroll forward if DP_WAVE_LOCK == 0 (or in Hub where scrolling is free)
    LDA DP_STATE
    CMP #STATE_HUB
    BEQ AllowCamScroll
    LDA DP_WAVE_LOCK
    BNE DoneCamScroll

AllowCamScroll:
    REP #$20
    .a16
    ; Target camera X = DP_PL_X - 112, clamped to [0 .. 256]
    LDA DP_PL_X
    SEC
    SBC #$0070
    BPL CheckCamMax
    LDA #$0000
CheckCamMax:
    CMP #$0100
    BCC StoreCamX
    LDA #$0100
StoreCamX:
    ; In Stage mode, camera only scrolls right (classic arcade beat 'em up rule)
    STA DP_TMP0             ; Save target camera X (16-bit) in DP_TMP0..DP_TMP1
    SEP #$20
    .a8
    LDA DP_STATE
    CMP #STATE_HUB
    REP #$20
    .a16
    BEQ WriteCamNow
    LDA DP_TMP0
    CMP DP_CAM_X
    BCC DoneCamScroll16
WriteCamNow:
    LDA DP_TMP0
    STA DP_CAM_X
DoneCamScroll16:
    SEP #$20
    .a8
DoneCamScroll:
    RTS


; ============================================================================
; CheckPlayerMeleeHits: Checks if Player's attack hits any active Enemy/Boss
; Input: DP_TMP4 = Attack Damage
; ============================================================================
CheckPlayerMeleeHits:
    SEP #$20
    .a8
    REP #$10
    .i16
    LDX #$0000              ; Enemy slot offset (0, 16, 32, 48)
MeleeEnemyLoop:
    LDA EN_ACT,X
    BEQ NextMeleeEnemy
    LDA EN_STATE,X
    CMP #$04                ; Already KO'd?
    BEQ NextMeleeEnemy

    ; Check Z depth distance |DP_PL_Z - EN_Z| < 18
    LDA DP_PL_Z
    SEC
    SBC EN_Z,X
    BPL MeleeZPos
    EOR #$FF
    INC
MeleeZPos:
    CMP #18
    BCS NextMeleeEnemy

    ; Check X distance in facing direction
    REP #$20
    .a16
    LDA EN_X_LO,X
    SEC
    SBC DP_PL_X
    STA DP_TMP0             ; Signed dx = EnemyX - PlayerX
    SEP #$20
    .a8
    LDA DP_PL_DIR
    BNE MeleeFacingLeft
    ; Facing Right: require -8 <= dx <= 38
    REP #$20
    .a16
    LDA DP_TMP0
    CLC
    ADC #$0008
    CMP #$002E
    SEP #$20
    .a8
    BCS NextMeleeEnemy
    BRA ApplyHitToEnemy

MeleeFacingLeft:
    ; Facing Left: require -38 <= dx <= 8
    REP #$20
    .a16
    LDA DP_TMP0
    CLC
    ADC #$0026
    CMP #$002E
    SEP #$20
    .a8
    BCS NextMeleeEnemy

ApplyHitToEnemy:
    JSR DamageEnemyInSlotX

NextMeleeEnemy:
    REP #$20
    .a16
    TXA
    CLC
    ADC #$0010
    TAX
    SEP #$20
    .a8
    CPX #$0040
    BCC MeleeEnemyLoop
    RTS


; ============================================================================
; DamageEnemyInSlotX: Applies DP_TMP4 damage to Enemy X, spawns Hit Spark & SFX
; ============================================================================
DamageEnemyInSlotX:
    SEP #$20
    .a8
    REP #$10
    .i16
    ; Spawn Hit Spark at Enemy screen coordinates
    REP #$20
    .a16
    LDA EN_X_LO,X
    SEC
    SBC DP_CAM_X
    SEP #$20
    .a8
    STA DP_SPARK_X
    LDA EN_Z,X
    SEC
    SBC #28
    STA DP_SPARK_Y
    LDA #$08
    STA DP_SPARK_TMR

    ; Play Heavy Hit SFX
    LDA EN_ACT,X
    CMP #$02
    BEQ HitBossSFX
    LDA #$05                ; sfx_hit (beat1old.wav)
    JSR PlaySFX
    BRA SubtractEnemyHP
HitBossSFX:
    LDA #$0A                ; sfx_bosshit (0corte.wav)
    JSR PlaySFX

SubtractEnemyHP:
    ; Knockback Enemy 8px away from Player
    LDA DP_PL_DIR
    BNE KnockEnemyLeft
    REP #$20
    .a16
    LDA EN_X_LO,X
    CLC
    ADC #$0008
    CMP #$01E0
    BCC StoreKnockR
    LDA #$01E0
StoreKnockR:
    STA EN_X_LO,X
    SEP #$20
    .a8
    BRA DoHPSub
KnockEnemyLeft:
    REP #$20
    .a16
    LDA EN_X_LO,X
    SEC
    SBC #$0008
    CMP #$0010
    BCS StoreKnockL
    LDA #$0010
StoreKnockL:
    STA EN_X_LO,X
    SEP #$20
    .a8

DoHPSub:
    LDA EN_HP,X
    SEC
    SBC DP_TMP4
    BEQ EnemyJustDied
    BCC EnemyJustDied
    STA EN_HP,X
    ; Update Boss HUD bar if this is the Boss
    LDA EN_ACT,X
    CMP #$02
    BNE SetEnemyHurtState
    LDA EN_HP,X
    STA DP_BOSS_HP
SetEnemyHurtState:
    LDA #$03                ; STATE_HURT
    STA EN_STATE,X
    LDA #12
    STA EN_TIMER,X
    RTS

EnemyJustDied:
    STZ EN_HP,X
    LDA EN_ACT,X
    CMP #$02
    BNE RegularEnemyKO
    STZ DP_BOSS_HP
RegularEnemyKO:
    LDA #$04                ; STATE_KO
    STA EN_STATE,X
    LDA #24
    STA EN_TIMER,X
    ; Add +5 points (+50 displayed) to Player Score
    REP #$20
    .a16
    LDA DP_SCORE
    CLC
    ADC #$0005
    STA DP_SCORE
    SEP #$20
    .a8
    RTS


; ============================================================================
; SpawnPlayerProjectile & UpdateProjectileAndItems
; ============================================================================
SpawnPlayerProjectile:
    SEP #$20
    .a8
    LDA #$01
    STA DP_PROJ_ACT
    REP #$20
    .a16
    LDA DP_PL_X
    STA DP_PROJ_X
    SEP #$20
    .a8
    LDA DP_PL_Z
    STA DP_PROJ_Z
    LDA DP_PL_DIR
    STA DP_PROJ_DIR
    RTS

UpdateProjectileAndItems:
    SEP #$20
    .a8
    REP #$10
    .i16
    ; --- 1. Update Active Special Projectile ---
    LDA DP_PROJ_ACT
    BEQ UpdatePickupItem
    LDA DP_PROJ_DIR
    BNE MoveProjLeft
    REP #$20
    .a16
    LDA DP_PROJ_X
    CLC
    ADC #$0005
    STA DP_PROJ_X
    SEC
    SBC DP_CAM_X
    CMP #$00F8
    SEP #$20
    .a8
    BCC CheckProjEnemyHits
    STZ DP_PROJ_ACT
    BRA UpdatePickupItem

MoveProjLeft:
    REP #$20
    .a16
    LDA DP_PROJ_X
    SEC
    SBC #$0005
    STA DP_PROJ_X
    SEC
    SBC DP_CAM_X
    BMI DeactProj
    SEP #$20
    .a8
    BRA CheckProjEnemyHits
DeactProj:
    SEP #$20
    .a8
    STZ DP_PROJ_ACT
    BRA UpdatePickupItem

CheckProjEnemyHits:
    LDX #$0000
ProjHitLoop:
    LDA EN_ACT,X
    BEQ NextProjEnemy
    LDA EN_STATE,X
    CMP #$03                ; Skip if already in HURT (3) or KO (4) state
    BCS NextProjEnemy
    LDA DP_PROJ_Z
    SEC
    SBC EN_Z,X
    BPL ProjZPos
    EOR #$FF
    INC
ProjZPos:
    CMP #18
    BCS NextProjEnemy
    REP #$20
    .a16
    LDA DP_PROJ_X
    SEC
    SBC EN_X_LO,X
    BPL ProjXPos
    EOR #$FFFF
    INC
ProjXPos:
    CMP #$0014
    SEP #$20
    .a8
    BCS NextProjEnemy
    ; Hit Enemy with Piercing Special Projectile!
    PHX
    LDA #24                 ; 24 damage!
    STA DP_TMP4
    JSR DamageEnemyInSlotX
    PLX

NextProjEnemy:
    REP #$20
    .a16
    TXA
    CLC
    ADC #$0010
    TAX
    SEP #$20
    .a8
    CPX #$0040
    BCC ProjHitLoop

UpdatePickupItem:
    ; --- 2. Check if Player picks up dropped Pizza (HP) or Mana (MP) ---
    LDA DP_ITEM_ACT
    BEQ DoneProjAndItems
    LDA DP_PL_Z
    SEC
    SBC DP_ITEM_Z
    BPL ItemZPos
    EOR #$FF
    INC
ItemZPos:
    CMP #18
    BCS DoneProjAndItems
    REP #$20
    .a16
    LDA DP_PL_X
    SEC
    SBC DP_ITEM_X
    BPL ItemXPos
    EOR #$FFFF
    INC
ItemXPos:
    CMP #$0014
    SEP #$20
    .a8
    BCS DoneProjAndItems

    ; Picked up item!
    STZ DP_ITEM_ACT
    LDA #$08                ; SFX get.wav
    JSR PlaySFX
    ; Restore +40 HP and +40 MP!
    LDA DP_PL_HP
    CLC
    ADC #40
    CMP DP_PL_MAXHP
    BCC StoreHealedHP
    LDA DP_PL_MAXHP
StoreHealedHP:
    STA DP_PL_HP

    LDA DP_PL_MP
    CLC
    ADC #40
    CMP #100
    BCC StoreHealedMP
    LDA #100
StoreHealedMP:
    STA DP_PL_MP
    JSR DrawGameplayHUD

DoneProjAndItems:
    RTS


; ============================================================================
; SpawnCurrentStageWave: Spawns enemies or Boss for DP_WAVE_NUM (0..3)
; ============================================================================
SpawnCurrentStageWave:
    SEP #$20
    .a8
    REP #$10
    .i16
    ; Clear all 4 enemy slots first
    LDX #$0000
ClearEnemySlotsLoop:
    STZ EN_ACT,X
    INX
    CPX #$0040
    BCC ClearEnemySlotsLoop

    LDA #$01
    STA DP_WAVE_LOCK
    STZ DP_GO_TIMER

    LDA DP_WAVE_NUM
    CMP #$03
    BEQ SpawnStageBossWave

    ; Regular Wave (0, 1, 2): Spawn 2 or 3 Enemies around camera
    ; Slot 0: Right side Enemy
    LDX #$0000
    LDA #$01
    STA EN_ACT,X
    STZ EN_STATE,X
    REP #$20
    .a16
    LDA DP_CAM_X
    CLC
    ADC #$00D8
    STA EN_X_LO,X
    SEP #$20
    .a8
    LDA #148
    STA EN_Z,X
    LDA #$01
    STA EN_DIR,X
    LDA #48
    STA EN_HP,X
    STA EN_MAXHP,X
    LDA #8
    STA EN_ATK,X

    ; Slot 1: Second Right Enemy
    LDX #$0010
    LDA #$01
    STA EN_ACT,X
    STZ EN_STATE,X
    REP #$20
    .a16
    LDA DP_CAM_X
    CLC
    ADC #$00A8
    STA EN_X_LO,X
    SEP #$20
    .a8
    LDA #176
    STA EN_Z,X
    LDA #$01
    STA EN_DIR,X
    LDA #48
    STA EN_HP,X
    STA EN_MAXHP,X
    LDA #8
    STA EN_ATK,X

    ; Wave 1 & 2 also spawn a 3rd Enemy in Slot 2!
    LDA DP_WAVE_NUM
    BEQ DoneSpawnWave
    LDX #$0020
    LDA #$01
    STA EN_ACT,X
    STZ EN_STATE,X
    REP #$20
    .a16
    LDA DP_CAM_X
    CLC
    ADC #$00EC
    STA EN_X_LO,X
    SEP #$20
    .a8
    LDA #162
    STA EN_Z,X
    LDA #$01
    STA EN_DIR,X
    LDA #56
    STA EN_HP,X
    STA EN_MAXHP,X
    LDA #10
    STA EN_ATK,X
DoneSpawnWave:
    RTS

SpawnStageBossWave:
    ; Wave 3: Spawn the Stage Boss in Slot 0 + 1 minion in Slot 1!
    LDX #$0000
    LDA #$02                ; EN_ACT = 2 (Stage Boss!)
    STA EN_ACT,X
    STZ EN_STATE,X
    REP #$20
    .a16
    LDA DP_CAM_X
    CLC
    ADC #$00C8
    STA EN_X_LO,X
    SEP #$20
    .a8
    LDA #160
    STA EN_Z,X
    LDA #$01
    STA EN_DIR,X
    LDA #128                ; Full 8-tile Boss HP Bar (128 HP)!
    STA EN_HP,X
    STA EN_MAXHP,X
    STA DP_BOSS_HP
    STA DP_BOSS_MAXHP
    LDA #14
    STA EN_ATK,X
    LDA #$01
    STA DP_BOSS_ACT
    RTS


; ============================================================================
; UpdateEnemiesAndWaves: AI State Machine for all 4 Enemy/Boss Slots
; ============================================================================
UpdateEnemiesAndWaves:
    SEP #$20
    .a8
    REP #$10
    .i16
    STZ DP_TMP3             ; Active enemy counter = 0
    LDX #$0000

EnemyAILoop:
    LDA EN_ACT,X
    BNE EnemyIsActive
    JMP NextEnemyAISlot
EnemyIsActive:
    INC DP_TMP3             ; Count active enemy

    LDA EN_STATE,X
    CMP #$03                ; STATE_HURT?
    BNE CheckEnemyKOState
    LDA #$06                ; Hurt frame
    STA EN_ANIM,X
    DEC EN_TIMER,X
    BNE DoneThisEnemyAI
    STZ EN_STATE,X
DoneThisEnemyAI:
    JMP NextEnemyAISlot

CheckEnemyKOState:
    CMP #$04                ; STATE_KO?
    BNE CheckEnemyWindup
    LDA #$07                ; Fall/KO frame
    STA EN_ANIM,X
    DEC EN_TIMER,X
    BNE DoneThisEnemyAI
    ; Enemy finished KO blink: drop Pizza pickup if none active, and deactivate slot!
    LDA DP_ITEM_ACT
    BNE DeactivateEnemySlot
    LDA #$01
    STA DP_ITEM_ACT
    REP #$20
    .a16
    LDA EN_X_LO,X
    STA DP_ITEM_X
    SEP #$20
    .a8
    LDA EN_Z,X
    STA DP_ITEM_Z
DeactivateEnemySlot:
    STZ EN_ACT,X
    JMP NextEnemyAISlot

CheckEnemyWindup:
    CMP #$01                ; STATE_WINDUP?
    BNE CheckEnemyStrike
    LDA #$04                ; Attack 1 frame
    STA EN_ANIM,X
    DEC EN_TIMER,X
    BNE DoneThisEnemyAI
    ; Transition to Strike!
    LDA #$02
    STA EN_STATE,X
    LDA #12
    STA EN_TIMER,X
    LDA #$05                ; Attack 2 Strike frame
    STA EN_ANIM,X
    JSR CheckEnemyStrikePlayer
    JMP NextEnemyAISlot

CheckEnemyStrike:
    CMP #$02                ; STATE_STRIKE?
    BNE EnemyChaseState
    LDA #$05
    STA EN_ANIM,X
    DEC EN_TIMER,X
    BNE DoneThisEnemyAI
    STZ EN_STATE,X
    JMP NextEnemyAISlot

EnemyChaseState:
    ; Chase Player every 2nd frame
    LDA DP_FRAME
    AND #$01
    BNE AnimateEnemyWalk

    ; Move horizontally toward DP_PL_X
    REP #$20
    .a16
    LDA DP_PL_X
    SEC
    SBC EN_X_LO,X
    BPL EnemyMoveRight
    ; Player is to the Left of Enemy
    EOR #$FFFF
    INC
    CMP #$0016              ; Within 22px horizontally?
    BCC EnemyReachedXL
    DEC EN_X_LO,X
EnemyReachedXL:
    SEP #$20
    .a8
    LDA #$01                ; Face Left
    STA EN_DIR,X
    BRA EnemyChaseZ

EnemyMoveRight:
    .a16
    CMP #$0016
    BCC EnemyReachedXR
    INC EN_X_LO,X
EnemyReachedXR:
    SEP #$20
    .a8
    STZ EN_DIR,X            ; Face Right

EnemyChaseZ:
    ; Move vertically in Z toward DP_PL_Z
    LDA DP_PL_Z
    CMP EN_Z,X
    BEQ CheckEnemyStartAttack
    BCC EnemyMoveZUp
    INC EN_Z,X
    BRA CheckEnemyStartAttack
EnemyMoveZUp:
    DEC EN_Z,X

CheckEnemyStartAttack:
    ; Check if close enough in X and Z to start an attack
    LDA DP_PL_Z
    SEC
    SBC EN_Z,X
    BPL EnZDistPos
    EOR #$FF
    INC
EnZDistPos:
    CMP #14
    BCS AnimateEnemyWalk

    REP #$20
    .a16
    LDA DP_PL_X
    SEC
    SBC EN_X_LO,X
    BPL EnXDistPos
    EOR #$FFFF
    INC
EnXDistPos:
    CMP #$001C              ; Within 28px?
    SEP #$20
    .a8
    BCS AnimateEnemyWalk

    ; Start Attack Windup!
    LDA #$01
    STA EN_STATE,X
    LDA #14
    STA EN_TIMER,X
    LDA #$04
    STA EN_ANIM,X
    BRA NextEnemyAISlot

AnimateEnemyWalk:
    LDA DP_FRAME
    LSR
    LSR
    LSR
    AND #$03
    STA EN_ANIM,X

NextEnemyAISlot:
    REP #$20
    .a16
    TXA
    CLC
    ADC #$0010
    TAX
    SEP #$20
    .a8
    CPX #$0040
    BCS CheckWaveCompletion
    JMP EnemyAILoop

CheckWaveCompletion:
    ; If any enemies are still active (DP_TMP3 > 0), keep wave locked
    LDA DP_TMP3
    BNE WaveStillActive

    ; All enemies in wave defeated!
    STZ DP_WAVE_LOCK
    INC DP_GO_TIMER
    LDA DP_GO_TIMER
    CMP #50                 ; Wait ~0.8s before spawning next wave or finishing stage
    BCC WaveStillActive

    STZ DP_GO_TIMER
    INC DP_WAVE_NUM
    LDA DP_WAVE_NUM
    CMP #$04                ; Was Wave 3 (Boss Wave) just cleared?
    BCS StageBossDefeated
    JSR SpawnCurrentStageWave
WaveStillActive:
    RTS

StageBossDefeated:
    ; Stage Boss Defeated! Play Victory 1UP Fanfare & Award +100 Score
    STZ DP_BOSS_ACT
    LDA #$0B                ; sfx_1up (1up.wav)
    JSR PlaySFX
    REP #$20
    .a16
    LDA DP_SCORE
    CLC
    ADC #$0064
    STA DP_SCORE
    SEP #$20
    .a8

    ; Check which stage was just cleared:
    LDA DP_STAGE_ID
    BEQ ClearedBGSStage
    CMP #$09                ; Stage 9 = Portal 8 (YouTube HQ Final Boss EI SPOILED!)
    BEQ ClearedFinalBossStage

    ; Cleared one of Portals 1..7 (DP_STAGE_ID 2..8 -> bit 0..6):
    SEC
    SBC #$02
    TAY
    LDA #$01
ShiftPortalBitLoop:
    CPY #$0000
    BEQ SetPortalClearedBit
    ASL
    DEY
    BRA ShiftPortalBitLoop
SetPortalClearedBit:
    ORA DP_PORTALS
    STA DP_PORTALS
    JSR SaveProgressToSRAM

ClearedBGSStage:
    ; Return to Estação Central Hub!
    JSR EnterHubState
    RTS

ClearedFinalBossStage:
    ; Mark bit 7 in DP_PORTALS, save to SRAM, and enter Ending & Credits!
    LDA DP_PORTALS
    ORA #$80
    STA DP_PORTALS
    JSR SaveProgressToSRAM
    JSR EnterEndingState
    RTS


; ============================================================================
; CheckEnemyStrikePlayer: Checks if Enemy X's strike hits the Player
; ============================================================================
CheckEnemyStrikePlayer:
    SEP #$20
    .a8
    REP #$10
    .i16
    ; Skip if Player is invincible or high in the air
    LDA DP_PL_INV
    BNE EnemyStrikeMissed
    LDA DP_PL_Y_OFF
    CMP #18
    BCS EnemyStrikeMissed

    ; Check Z distance < 14
    LDA DP_PL_Z
    SEC
    SBC EN_Z,X
    BPL StrikeZPos
    EOR #$FF
    INC
StrikeZPos:
    CMP #14
    BCS EnemyStrikeMissed

    ; Check X distance < 28
    REP #$20
    .a16
    LDA DP_PL_X
    SEC
    SBC EN_X_LO,X
    BPL StrikeXPos
    EOR #$FFFF
    INC
StrikeXPos:
    CMP #$001C
    SEP #$20
    .a8
    BCS EnemyStrikeMissed

    ; Player Hit! Check if Blocking (DP_PL_ACT == 7)
    LDA DP_PL_ACT
    CMP #$07
    BNE FullDamageToPlayer
    ; Blocked! Only 1 HP chip damage
    LDA #$01
    STA DP_TMP0
    BRA ApplyPlayerDamage

FullDamageToPlayer:
    LDA EN_ATK,X
    STA DP_TMP0
    LDA #$06                ; ACT_HURT
    STA DP_PL_ACT
    LDA #12
    STA DP_PL_TIMER
    LDA #10                 ; Slot 10 = Hurt/Block frame
    STA DP_PL_ANIM

ApplyPlayerDamage:
    LDA #24
    STA DP_PL_INV           ; 24 frames invincibility
    LDA #$05                ; SFX Hit
    JSR PlaySFX

    LDA DP_PL_HP
    SEC
    SBC DP_TMP0
    BEQ PlayerLostLife
    BCC PlayerLostLife
    STA DP_PL_HP
    rts

PlayerLostLife:
    DEC DP_LIVES
    BEQ TriggerGameOver
    ; Respawn Player in place with full HP & invincibility
    LDA DP_PL_MAXHP
    STA DP_PL_HP
    LDA #100
    STA DP_PL_MP
    LDA #60
    STA DP_PL_INV
    RTS

TriggerGameOver:
    JSR EnterGameOverState
EnemyStrikeMissed:
    RTS


; ============================================================================
; RenderPlayerOAM & RenderStageEntitiesOAM: Populates OAM Shadow Buffer
; ============================================================================
RenderPlayerOAM:
    SEP #$20
    .a8
    REP #$10
    .i16
    ; Blink Player sprite when invincible
    LDA DP_PL_INV
    BEQ DrawPlayerSpriteNow
    LDA DP_FRAME
    AND #$02
    BNE SkipPlayerOAM

DrawPlayerSpriteNow:
    REP #$20
    .a16
    LDA DP_PL_X
    SEC
    SBC DP_CAM_X
    SEC
    SBC #$0010              ; Center 32x32 sprite horizontally (X - 16)
    SEP #$20
    .a8
    STA DP_TMP0             ; Screen X

    LDA DP_PL_Z
    SEC
    SBC DP_PL_Y_OFF
    SEC
    SBC #30                 ; Align feet to Z
    STA DP_TMP1             ; Screen Y

    LDA DP_PL_ANIM
    STA DP_TMP2             ; Player Sprite Slot (0..10)

    STZ DP_TMP3             ; OBJ Palette 0
    LDA DP_PL_DIR
    BEQ SetPlayerOAMNow
    LDA #$40                ; H-Flip when facing Left!
    STA DP_TMP3
SetPlayerOAMNow:
    LDX #$0000              ; OAM Slot 0
    JSR SetOAMSprite
SkipPlayerOAM:
    RTS

RenderStageEntitiesOAM:
    SEP #$20
    .a8
    REP #$10
    .i16
    ; 1. Render Active Enemies & Boss in OAM Slots 1..4 (Offsets $04, $08, $0C, $10)
    LDX #$0000              ; Enemy slot offset (0, 16, 32, 48)
RenderEnemyOAMLoop:
    LDA EN_ACT,X
    BEQ NextEnemyOAM
    ; Blink when in KO state ($04)
    LDA EN_STATE,X
    CMP #$04
    BNE CalcEnemyScreenPos
    LDA DP_FRAME
    AND #$02
    BNE NextEnemyOAM

CalcEnemyScreenPos:
    REP #$20
    .a16
    LDA EN_X_LO,X
    SEC
    SBC DP_CAM_X
    SEC
    SBC #$0010
    BMI NextEnemyOAM16
    CMP #$00F0
    BCS NextEnemyOAM16
    SEP #$20
    .a8
    STA DP_TMP0             ; Screen X

    LDA EN_Z,X
    SEC
    SBC #30
    STA DP_TMP1             ; Screen Y

    ; Determine VRAM Slot & Palette:
    ;   EN_ACT == 1 (Enemy): Base Slot = 12, Palette = 1 ($02)
    ;   EN_ACT == 2 (Boss) : Base Slot = 20, Palette = 2 ($04)
    LDA EN_ACT,X
    CMP #$02
    BEQ UseBossSpriteSlots
    LDA #12
    CLC
    ADC EN_ANIM,X
    STA DP_TMP2
    LDA #$02                ; OBJ Palette 1 (Enemy)
    BRA CheckEnemyFlipOAM
UseBossSpriteSlots:
    LDA #20
    CLC
    ADC EN_ANIM,X
    STA DP_TMP2
    LDA #$04                ; OBJ Palette 2 (Boss)

CheckEnemyFlipOAM:
    STA DP_TMP3
    LDA EN_DIR,X
    BEQ WriteEnemyOAM
    LDA DP_TMP3
    ORA #$40                ; H-Flip
    STA DP_TMP3
WriteEnemyOAM:
    ; Save Enemy offset X, compute OAM byte offset = ((X >> 4) + 1) * 4
    PHX
    TXA
    LSR
    LSR
    CLC
    ADC #$04
    TAX
    JSR SetOAMSprite
    PLX
    BRA NextEnemyOAM

NextEnemyOAM16:
    SEP #$20
    .a8
NextEnemyOAM:
    REP #$20
    .a16
    TXA
    CLC
    ADC #$0010
    TAX
    SEP #$20
    .a8
    CPX #$0040
    BCC RenderEnemyOAMLoop

    ; 2. Render Special Projectile in OAM Slot 5 (Offset $14)
    LDA DP_PROJ_ACT
    BEQ CheckRenderPickup
    REP #$20
    .a16
    LDA DP_PROJ_X
    SEC
    SBC DP_CAM_X
    SEP #$20
    .a8
    STA DP_TMP0
    LDA DP_PROJ_Z
    SEC
    SBC #24
    STA DP_TMP1
    LDA #30                 ; Slot 30 = Special Projectile
    STA DP_TMP2
    LDA #$06                ; OBJ Palette 3
    STA DP_TMP3
    LDA DP_PROJ_DIR
    BEQ DrawProjOAM
    LDA #$46                ; Palette 3 + HFlip
    STA DP_TMP3
DrawProjOAM:
    LDX #$0014
    JSR SetOAMSprite

CheckRenderPickup:
    ; 3. Render Pickup Item (Pizza) in OAM Slot 6 (Offset $18)
    LDA DP_ITEM_ACT
    BEQ CheckRenderSpark
    REP #$20
    .a16
    LDA DP_ITEM_X
    SEC
    SBC DP_CAM_X
    BMI CheckRenderSpark16
    CMP #$00F0
    BCS CheckRenderSpark16
    SEP #$20
    .a8
    STA DP_TMP0
    LDA DP_ITEM_Z
    SEC
    SBC #20
    STA DP_TMP1
    LDA #31                 ; Slot 31 = Pizza Pickup
    STA DP_TMP2
    LDA #$06                ; OBJ Palette 3
    STA DP_TMP3
    LDX #$0018
    JSR SetOAMSprite
    BRA CheckRenderSpark
CheckRenderSpark16:
    SEP #$20
    .a8

CheckRenderSpark:
    ; 4. Render Hit Spark Flash in OAM Slot 7 (Offset $1C)
    LDA DP_SPARK_TMR
    BEQ DoneRenderEntities
    LDA DP_SPARK_X
    STA DP_TMP0
    LDA DP_SPARK_Y
    STA DP_TMP1
    LDA #29                 ; Slot 29 = Hit Spark Flash
    STA DP_TMP2
    LDA #$06                ; OBJ Palette 3
    STA DP_TMP3
    LDX #$001C
    JSR SetOAMSprite

DoneRenderEntities:
    RTS


; ============================================================================
; STATE 5: ENDING & CREDITS SCREEN (Converted from Bgs/complete.gif)
; ============================================================================
EnterEndingState:
    SEP #$20
    .a8
    REP #$10
    .i16
    LDA #STATE_ENDING
    STA DP_STATE

    JSR ClearOAMBuffer
    JSR ClearBG3Buffer

    ; Load Ending Graphic Package ($C7 = screen_ending.bin)
    LDA #$C7
    JSR LoadScreenPackage

    ; Fill Rows 16..25 with dark text backing
    LDX #$0400
    LDY #$0140
    JSR FillBG3TilesDark

    LDA #$20
    STA DP_TMP0
    LDX #$0444              ; Row 17, Col 2
    LDY #StrEnding1
    JSR PrintBG3String

    LDA #$24
    STA DP_TMP0
    LDX #$04C4              ; Row 19, Col 2
    LDY #StrEnding2
    JSR PrintBG3String

    LDA #$28
    STA DP_TMP0
    LDX #$0544              ; Row 21, Col 2
    LDY #StrEnding3
    JSR PrintBG3String

    LDA #$20
    STA DP_TMP0
    LDX #$05C4              ; Row 23, Col 2
    LDY #StrEnding4
    JSR PrintBG3String

    LDA #$01
    STA DP_HUD_DIRTY

    ; Play Victory Fanfare Track (Track 12)
    LDA #$0C
    JSR PlayBGMTrack
    RTS

UpdateEndingState:
    REP #$20
    .a16
    LDA DP_JOY_NEW
    AND #$D080              ; START | B | Y | A
    BEQ EndingNoPress
    SEP #$20
    .a8
    JSR EnterTitleState
EndingNoPress:
    SEP #$20
    .a8
    RTS


; ============================================================================
; STATE 6: GAME OVER / CONTINUE SCREEN (Converted from Bgs/gameover.gif)
; ============================================================================
EnterGameOverState:
    SEP #$20
    .a8
    REP #$10
    .i16
    LDA #STATE_GAMEOVER
    STA DP_STATE

    JSR ClearOAMBuffer
    JSR ClearBG3Buffer

    ; Load Game Over Graphic Package ($C6 = screen_gameover.bin)
    LDA #$C6
    JSR LoadScreenPackage

    LDX #$0480              ; Rows 18..23
    LDY #$00C0
    JSR FillBG3TilesDark

    LDA #$2C                ; Red Alert Palette
    STA DP_TMP0
    LDX #$04CC              ; Row 19, Col 6
    LDY #StrGameOver1
    JSR PrintBG3String

    LDA #$20
    STA DP_TMP0
    LDX #$0544              ; Row 21, Col 2
    LDY #StrGameOver2
    JSR PrintBG3String

    LDA #$01
    STA DP_HUD_DIRTY
    RTS

UpdateGameOverState:
    REP #$20
    .a16
    LDA DP_JOY_NEW
    AND #$D080              ; START | B | Y | A
    BEQ GameOverNoPress
    SEP #$20
    .a8
    LDA DP_CREDITS
    BEQ ReturnToTitleFromGO
    DEC DP_CREDITS
    LDA #$03
    STA DP_LIVES
    LDA #$08                ; SFX get.wav
    JSR PlaySFX
    JSR EnterHubState
    RTS
ReturnToTitleFromGO:
    JSR EnterTitleState
GameOverNoPress:
    SEP #$20
    .a8
    RTS
