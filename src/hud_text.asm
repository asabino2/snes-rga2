; ============================================================================
; RETROGAMERS AVENTURA 2 (RGA2) - 16-BIT SNES EDITION
; File: src/hud_text.asm
; Description: BG3 High-Priority Arcade HUD, Health/MP Bars & Text Renderer
; ============================================================================

; ============================================================================
; ClearBG3Buffer: Clears all 2048 bytes of WRAM BG3_MAP_BUF ($1000-$17FF)
; ============================================================================
ClearBG3Buffer:
    REP #$30
    .a16
    .i16
    LDX #$0000
    LDA #$0000
ClearBG3Loop:
    STA !BG3_MAP_BUF,X
    INX
    INX
    CPX #$0800
    BCC ClearBG3Loop
    SEP #$20
    .a8
    LDA #$01
    STA DP_HUD_DIRTY
    RTS


; ============================================================================
; FillBG3RowsDark: Fills tilemap byte range X..DP_TMP0 with dark backing ($2046)
; Inputs: X = Start byte offset, Y = Number of 16-bit tiles to fill
; ============================================================================
FillBG3TilesDark:
    REP #$30
    .a16
    .i16
    LDA #$2046              ; Priority 1 ($2000), Palette 0, Tile $46 (Dark Box)
FillBG3DarkLoop:
    STA !BG3_MAP_BUF,X
    INX
    INX
    DEY
    BNE FillBG3DarkLoop
    SEP #$20
    .a8
    RTS


; ============================================================================
; PrintBG3String: Writes a null-terminated ASCII string from Bank $80 to BG3
; Inputs:
;   X = BG3_MAP_BUF byte offset ((row * 32 + col) * 2)
;   Y = String address in Bank $80
;   DP_TMP0 = High attribute byte ($20=Gold/White, $24=Green, $28=Cyan, $2C=Red)
; ============================================================================
PrintBG3String:
    SEP #$20
    .a8
    REP #$10
    .i16
PrintBG3StrLoop:
    LDA !$0000,Y
    BEQ PrintBG3StrDone
    SEC
    SBC #$20                ; Convert ASCII ($20..$5F) to Tile Index ($00..$3F)
    BNE NotSpaceBG3Char
    LDA #$46                ; Space ' ' uses Solid Dark Backing Tile ($46) so text boxes have no holes!
    STA !BG3_MAP_BUF,X
    LDA #$20                ; Palette 0 + High Priority
    STA !BG3_MAP_BUF+1,X
    BRA NextBG3StrChar
NotSpaceBG3Char:
    STA !BG3_MAP_BUF,X
    LDA DP_TMP0
    STA !BG3_MAP_BUF+1,X
NextBG3StrChar:
    INX
    INX
    INY
    BRA PrintBG3StrLoop
PrintBG3StrDone:
    LDA #$01
    STA DP_HUD_DIRTY
    RTS


; ============================================================================
; DrawBar8Tiles: Draws an 8-tile health/MP bar (value 0..128 in A)
; Inputs:
;   A = Current value (0..128, where 16 per full tile, 8 per half tile)
;   X = BG3_MAP_BUF byte offset
;   DP_TMP0 = Palette High Byte ($24=Green HP, $28=Blue MP, $2C=Red Boss)
; ============================================================================
DrawBar8Tiles:
    SEP #$20
    .a8
    REP #$10
    .i16
    STA DP_TMP1             ; Remaining bar points
    LDY #$0008              ; 8 bar tiles wide
DrawBarTileLoop:
    LDA DP_TMP1
    CMP #$10                ; >= 16? Full tile ($42)
    BCC CheckHalfBar
    SEC
    SBC #$10
    STA DP_TMP1
    LDA #$42
    BRA WriteBarTile
CheckHalfBar:
    CMP #$06                ; >= 6? Half tile ($41)
    BCC EmptyBarTile
    STZ DP_TMP1
    LDA #$41
    BRA WriteBarTile
EmptyBarTile:
    LDA #$40                ; Empty bar tile ($40)
WriteBarTile:
    STA !BG3_MAP_BUF,X
    LDA DP_TMP0
    STA !BG3_MAP_BUF+1,X
    INX
    INX
    DEY
    BNE DrawBarTileLoop
    RTS


; ============================================================================
; PrintHex16FourDigits: Prints 16-bit value in DP_TMP2/DP_TMP3 as 4 DECIMAL digits (0000..9999)
; Inputs: X = BG3_MAP_BUF offset, DP_TMP2 (16-bit val), DP_TMP0 = High Attr
; ============================================================================
PrintHex16FourDigits:
    REP #$30
    .a16
    .i16
    LDA DP_TMP2
    CMP #9999
    BCC ScoreUnderMaxDec
    LDA #9999
    STA DP_TMP2
ScoreUnderMaxDec:
    ; --- Digit 1: Thousands (1000) ---
    LDY #$0000
Dec1000Loop:
    LDA DP_TMP2
    CMP #1000
    BCC Dec1000Done
    SEC
    SBC #1000
    STA DP_TMP2
    INY
    BRA Dec1000Loop
Dec1000Done:
    SEP #$20
    .a8
    TYA
    JSR WriteDecDigit

    ; --- Digit 2: Hundreds (100) ---
    REP #$20
    .a16
    LDY #$0000
Dec100Loop:
    LDA DP_TMP2
    CMP #100
    BCC Dec100Done
    SEC
    SBC #100
    STA DP_TMP2
    INY
    BRA Dec100Loop
Dec100Done:
    SEP #$20
    .a8
    TYA
    JSR WriteDecDigit

    ; --- Digit 3: Tens (10) ---
    REP #$20
    .a16
    LDY #$0000
Dec10Loop:
    LDA DP_TMP2
    CMP #10
    BCC Dec10Done
    SEC
    SBC #10
    STA DP_TMP2
    INY
    BRA Dec10Loop
Dec10Done:
    SEP #$20
    .a8
    TYA
    JSR WriteDecDigit

    ; --- Digit 4: Ones (0..9) ---
    LDA DP_TMP2
    JSR WriteDecDigit
    RTS

WriteDecDigit:
    CLC
    ADC #$10                ; '0' ($10) + decimal digit (0..9)
    STA !BG3_MAP_BUF,X
    LDA DP_TMP0
    STA !BG3_MAP_BUF+1,X
    INX
    INX
    RTS


; ============================================================================
; DrawGameplayHUD: Renders Top 3 Rows of Arcade Beat 'em Up HUD on BG3
; ============================================================================
DrawGameplayHUD:
    SEP #$20
    .a8
    REP #$10
    .i16

    ; Clear top 4 rows (128 tiles) with dark HUD bar on rows 1..2
    LDX #$0040              ; Row 1, Col 0
    LDY #$0040              ; 64 tiles (Rows 1 and 2)
    JSR FillBG3TilesDark

    ; Clear Row 3 & Row 4 (used for Hub portal prompts / Boss alerts)
    REP #$20
    .a16
    LDX #$00C0
    LDA #$0000
ClearHUDRow3Loop:
    STA !BG3_MAP_BUF,X
    INX
    INX
    CPX #$0140
    BCC ClearHUDRow3Loop
    SEP #$20
    .a8

    ; --- Row 1, Col 1: Selected Character Name ---
    LDA #$20
    STA DP_TMP0
    LDA DP_CHAR_ID
    ASL
    TAX
    REP #$20
    .a16
    LDA !CharNamePtrTable,X
    TAY
    SEP #$20
    .a8
    LDX #$0042              ; Row 1, Col 1
    JSR PrintBG3String

    ; --- Row 1, Col 11: "HP" + 8-tile Green Health Bar ---
    LDX #$0056              ; Row 1, Col 11
    LDA #$28                ; 'H' ($48 - $20)
    STA !BG3_MAP_BUF,X
    LDA #$20
    STA !BG3_MAP_BUF+1,X
    LDA #$30                ; 'P' ($50 - $20)
    STA !BG3_MAP_BUF+2,X
    LDA #$20
    STA !BG3_MAP_BUF+3,X

    LDA #$24                ; Palette 1 (Green Bar)
    STA DP_TMP0
    LDX #$005A              ; Row 1, Col 13
    LDA DP_PL_HP
    JSR DrawBar8Tiles

    ; --- Row 1, Col 22: Heart Icon + Lives + Score ---
    LDX #$006C              ; Row 1, Col 22
    LDA #$43                ; Heart Icon
    STA !BG3_MAP_BUF,X
    LDA #$2C                ; Red Palette
    STA !BG3_MAP_BUF+1,X
    LDA DP_LIVES
    AND #$0F
    CLC
    ADC #$10                ; '0' + lives
    STA !BG3_MAP_BUF+2,X
    LDA #$20
    STA !BG3_MAP_BUF+3,X

    ; Score at Row 1, Col 26
    LDA #$20
    STA DP_TMP0
    LDA DP_SCORE
    STA DP_TMP2
    LDA DP_SCORE+1
    STA DP_TMP3
    LDX #$0074              ; Row 1, Col 26
    JSR PrintHex16FourDigits
    ; Trailing '0' for arcade score
    LDA #$10
    STA !BG3_MAP_BUF,X
    LDA #$20
    STA !BG3_MAP_BUF+1,X

    ; --- Row 2, Col 1: Stage Name ---
    LDA #$28                ; Cyan palette for stage title
    STA DP_TMP0
    LDA DP_STAGE_ID
    ASL
    TAX
    REP #$20
    .a16
    LDA !StageNamePtrTable,X
    TAY
    SEP #$20
    .a8
    LDX #$0082              ; Row 2, Col 1
    JSR PrintBG3String

    ; --- Row 2, Col 11: "MP" + 8-tile Blue MP Bar ---
    LDX #$0096              ; Row 2, Col 11
    LDA #$2D                ; 'M'
    STA !BG3_MAP_BUF,X
    LDA #$20
    STA !BG3_MAP_BUF+1,X
    LDA #$30                ; 'P'
    STA !BG3_MAP_BUF+2,X
    LDA #$20
    STA !BG3_MAP_BUF+3,X

    LDA #$28                ; Palette 2 (Blue MP Bar)
    STA DP_TMP0
    LDX #$009A              ; Row 2, Col 13
    LDA DP_PL_MP
    JSR DrawBar8Tiles

    ; --- Row 2, Col 22: Boss HP Bar OR "GO ->" Indicator ---
    LDA DP_BOSS_ACT
    BEQ CheckHUDGoArrow
    ; Draw "B:" + 6-tile Red Boss Bar at Row 2, Col 22
    LDX #$00AC
    LDA #$22                ; 'B'
    STA !BG3_MAP_BUF,X
    LDA #$2C
    STA !BG3_MAP_BUF+1,X
    LDA #$2C                ; Red Palette 3
    STA DP_TMP0
    LDX #$00AE              ; Row 2, Col 23
    LDA DP_BOSS_HP
    JSR DrawBar8Tiles
    BRA CheckHubPrompt

CheckHUDGoArrow:
    LDA DP_WAVE_LOCK
    BNE CheckHubPrompt
    ; Flash "GO ->" on Row 2, Col 25
    LDA DP_FRAME
    AND #$10
    BEQ CheckHubPrompt
    LDX #$00B2
    LDY #StrHUDGoArrow
    LDA #$20
    STA DP_TMP0
    JSR PrintBG3String

CheckHubPrompt:
    ; If in Hub (DP_STAGE_ID == 1) and standing near a portal (DP_NEAR_PORTAL != $FF),
    ; display Portal Name & Cleared Badge on Row 3!
    LDA DP_STAGE_ID
    CMP #$01
    BNE DoneGameplayHUD
    LDA DP_NEAR_PORTAL
    CMP #$FF
    BEQ ShowHubClearedCount

    ; Fill Row 3 with dark backing
    LDX #$00C0
    LDY #$0020
    JSR FillBG3TilesDark

    ; Print Portal Name at Row 3, Col 2
    LDA #$20
    STA DP_TMP0
    LDA DP_NEAR_PORTAL
    ASL
    TAX
    REP #$20
    .a16
    LDA !PortalPromptPtrTable,X
    TAY
    SEP #$20
    .a8
    LDX #$00C4
    JSR PrintBG3String
    BRA DoneGameplayHUD

ShowHubClearedCount:
    ; Show "SELECT A PORTAL (UP/Y)" on Row 3
    LDX #$00C8
    LDY #StrHubWalkHint
    LDA #$20
    STA DP_TMP0
    JSR PrintBG3String

DoneGameplayHUD:
    LDA #$01
    STA DP_HUD_DIRTY
    RTS
