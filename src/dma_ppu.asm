; ============================================================================
; RETROGAMERS AVENTURA 2 (RGA2) - 16-BIT SNES EDITION
; File: src/dma_ppu.asm
; Description: VBlank NMI Handler, DMA Transfers, Joypad & OAM Sprite Manager
; ============================================================================

; ============================================================================
; NMIHandler: Executes every 60Hz VBlank
; ============================================================================
NMIHandler:
    REP #$30
    .a16
    .i16
    PHA
    PHX
    PHY
    PHD
    PHB

    LDA #$0000
    TCD                     ; Direct Page = $0000
    SEP #$20
    .a8
    LDA #$80
    PHA
    PLB                     ; Data Bank = $80

    LDA !RDNMI              ; Acknowledge NMI flag

    ; --- 1. Upload 544-byte OAM Shadow Buffer ($0200-$041F) to PPU OAM ---
    JSR UploadOAMNow

    ; --- 2. Upload BG3 HUD Tilemap ($1000-$17FF -> VRAM $4400) if dirty ---
    LDA DP_HUD_DIRTY
    BEQ SkipHUDDMA
    STZ DP_HUD_DIRTY
    LDA #$80
    STA !VMAIN
    REP #$20
    .a16
    LDA #$4400
    STA !VMADDL
    SEP #$20
    .a8
    LDA #$01
    STA !DMAP7
    LDA #$18
    STA !BBAD7
    LDX #BG3_MAP_BUF
    STX !A1T7L
    STZ !A1B7               ; Source Bank $00 (WRAM)
    LDX #$0800              ; 2048 bytes
    STX !DAS7L
    LDA #$80
    STA !MDMAEN
SkipHUDDMA:

    ; --- 3. Update BG1 & BG2 Parallax Scroll Registers ---
    LDA DP_CAM_X
    STA !BG1HOFS
    LDA DP_CAM_X_H
    STA !BG1HOFS

    ; BG2 Scrolls at 50% speed (DP_CAM_X >> 1) for 16-Bit Parallax depth!
    REP #$20
    .a16
    LDA DP_CAM_X
    LSR
    SEP #$20
    .a8
    STA !BG2HOFS
    XBA
    STA !BG2HOFS

    ; Increment frame counter & signal MainLoop
    INC DP_FRAME
    LDA #$01
    STA DP_NMI_DONE

    REP #$30
    .a16
    .i16
    PLB
    PLD
    PLY
    PLX
    PLA
    RTI

IRQHandler:
    RTI


; ============================================================================
; UploadOAMNow: Transfers 544 bytes from $00:0200 to OAM via DMA7
; ============================================================================
UploadOAMNow:
    SEP #$20
    .a8
    REP #$10
    .i16
    STZ !OAMADDL
    STZ !OAMADDH
    STZ !DMAP7              ; 1 register write once ($2104)
    LDA #$04
    STA !BBAD7              ; OAMDATA
    LDX #OAM_BUF
    STX !A1T7L
    STZ !A1B7               ; Bank $00
    LDX #$0220              ; 544 bytes (512 low + 32 high)
    STX !DAS7L
    LDA #$80
    STA !MDMAEN
    RTS


; ============================================================================
; ClearOAMBuffer: Hides all 128 sprites offscreen (Y = $F0) and sets 32x32 size
; ============================================================================
ClearOAMBuffer:
    SEP #$20
    .a8
    REP #$10
    .i16
    LDX #$0000
ClearOAMLowLoop:
    STZ !OAM_BUF,X          ; X = 0
    LDA #$F0
    STA !OAM_BUF+1,X        ; Y = $F0 (240 offscreen)
    STZ !OAM_BUF+2,X        ; Tile = 0
    STZ !OAM_BUF+3,X        ; Attr = 0
    INX
    INX
    INX
    INX
    CPX #$0200
    BCC ClearOAMLowLoop

    ; Set High OAM table ($0400-$041F) to $AA (All sprites = Large 32x32, X8 = 0)
    LDX #$0000
    LDA #$AA
ClearOAMHiLoop:
    STA !OAM_HI_BUF,X
    INX
    CPX #$0020
    BCC ClearOAMHiLoop
    RTS


; ============================================================================
; SetOAMSprite: Writes a 32x32 sprite to OAM_BUF slot
; Inputs:
;   X = OAM byte offset (0, 4, 8, 12 ... 508)
;   DP_TMP0 = Screen X (0..255)
;   DP_TMP1 = Screen Y (0..223)
;   DP_TMP2 = Sprite Slot in VRAM (0..31)
;   DP_TMP3 = Attribute flags (Palette << 1 | HFlip $40 | Priority $20)
; ============================================================================
SetOAMSprite:
    SEP #$20
    .a8
    REP #$10
    .i16
    LDA DP_TMP0
    STA !OAM_BUF,X          ; Sprite X
    LDA DP_TMP1
    STA !OAM_BUF+1,X        ; Sprite Y

    PHX
    LDA DP_TMP2
    AND #$1F
    TAX
    LDA !SpriteSlotTileTable,X
    STA DP_TMP4
    LDA !SpriteSlotNameTable,X
    ORA DP_TMP3
    ORA #$20                ; Priority 2 (above BG1/BG2, below BG3 HUD)
    PLX

    STA !OAM_BUF+3,X        ; Attribute byte (VHOPPPNN)
    LDA DP_TMP4
    STA !OAM_BUF+2,X        ; Tile index byte
    RTS

; Lookup tables mapping 32x32 Sprite Slot (0..31) to SNES OBJ Tile & Name Table
SpriteSlotTileTable:
    .db $00, $04, $08, $0C,  $40, $44, $48, $4C
    .db $80, $84, $88, $8C,  $C0, $C4, $C8, $CC
    .db $00, $04, $08, $0C,  $40, $44, $48, $4C
    .db $80, $84, $88, $8C,  $C0, $C4, $C8, $CC

SpriteSlotNameTable:
    .db $00, $00, $00, $00,  $00, $00, $00, $00
    .db $00, $00, $00, $00,  $00, $00, $00, $00
    .db $01, $01, $01, $01,  $01, $01, $01, $01
    .db $01, $01, $01, $01,  $01, $01, $01, $01


; ============================================================================
; ReadJoypadInput: Reads Controller 1 ($4218-$4219) after Auto-Joypad completes
; ============================================================================
ReadJoypadInput:
    SEP #$20
    .a8
    REP #$10
    .i16
    LDY #$0400
WaitAutoJoy:
    LDA !HVBJOY
    AND #$01
    BEQ AutoJoyReady
    DEY
    BNE WaitAutoJoy
AutoJoyReady:
    REP #$20
    .a16
    LDA DP_JOY_CUR
    STA DP_JOY_OLD
    LDA !JOY1L
    STA DP_JOY_CUR
    EOR DP_JOY_OLD
    AND DP_JOY_CUR
    STA DP_JOY_NEW
    SEP #$20
    .a8
    RTS


; ============================================================================
; LoadScreenPackage: Loads a full 22.7KB Screen/Stage Package from ROM Bank (A)
;   $0000-$3FFF (16KB) -> VRAM $0000 (BG1+BG2 4bpp Tiles)
;   $4000-$4FFF ( 4KB) -> VRAM $3800 (BG1 64x32 Tilemap)
;   $5000-$57FF ( 2KB) -> VRAM $4000 (BG2 32x32 Tilemap)
;   $5800-$587F (128B) -> CGRAM $20  (BG Palettes 2..5)
; Input: A = Source ROM Bank ($C4..$D1)
; ============================================================================
LoadScreenPackage:
    SEP #$20
    .a8
    REP #$10
    .i16
    STA DP_TMP0             ; Save source bank in DP_TMP0

    ; Disable NMI & Enter Forced Blank for safe VRAM bulk DMA (prevents NMI from interrupting DMA setup!)
    STZ !NMITIMEN
    LDA #$8F
    STA !INIDISP

    ; 1. DMA 16KB CHR ($0000-$3FFF) -> VRAM Word $0000
    LDA #$80
    STA !VMAIN
    REP #$20
    .a16
    LDA #$0000
    STA !VMADDL
    SEP #$20
    .a8
    LDA #$01
    STA !DMAP0
    LDA #$18
    STA !BBAD0
    LDX #$0000
    STX !A1T0L
    LDA DP_TMP0
    STA !A1B0
    LDX #$4000              ; 16,384 bytes
    STX !DAS0L
    LDA #$01
    STA !MDMAEN

    ; 2. DMA 4KB BG1 Tilemap ($4000-$4FFF) -> VRAM Word $3800
    REP #$20
    .a16
    LDA #$3800
    STA !VMADDL
    SEP #$20
    .a8
    LDX #$4000
    STX !A1T0L
    LDA DP_TMP0
    STA !A1B0
    LDX #$1000              ; 4,096 bytes
    STX !DAS0L
    LDA #$01
    STA !MDMAEN

    ; 3. DMA 2KB BG2 Tilemap ($5000-$57FF) -> VRAM Word $4000
    REP #$20
    .a16
    LDA #$4000
    STA !VMADDL
    SEP #$20
    .a8
    LDX #$5000
    STX !A1T0L
    LDA DP_TMP0
    STA !A1B0
    LDX #$0800              ; 2,048 bytes
    STX !DAS0L
    LDA #$01
    STA !MDMAEN

    ; 4. DMA 128B Palettes ($5800-$587F) -> CGRAM Word $20 (Palettes 2..5)
    LDA #$20
    STA !CGADD
    STZ !DMAP0
    LDA #$22
    STA !BBAD0
    LDX #$5800
    STX !A1T0L
    LDA DP_TMP0
    STA !A1B0
    LDX #$0080              ; 128 bytes
    STX !DAS0L
    LDA #$01
    STA !MDMAEN

    ; Re-upload BG3 HUD Palettes to CGRAM $00..$0F (ensures backdrop color 0 matches)
    STZ !CGADD
    LDX #$3800
    STX !A1T0L
    LDA #$C0
    STA !A1B0
    LDX #$0020
    STX !DAS0L
    LDA #$01
    STA !MDMAEN

    ; Reset scroll to 0
    REP #$20
    .a16
    STZ DP_CAM_X
    SEP #$20
    .a8
    STZ !BG1HOFS
    STZ !BG1HOFS
    STZ !BG2HOFS
    STZ !BG2HOFS

    ; Restore screen brightness & re-enable VBlank NMI
    LDA !RDNMI
    LDA #$81
    STA !NMITIMEN
    LDA #$0F
    STA !INIDISP
    RTS


; ============================================================================
; LoadUniversalFXSprites: Uploads FX/Portal/Pickup strip ($C1:9100 -> VRAM $7C00)
;                         and OBJ Palette 3 (CGRAM $B0)
; ============================================================================
LoadUniversalFXSprites:
    SEP #$20
    .a8
    REP #$10
    .i16
    STZ !NMITIMEN
    LDA #$8F
    STA !INIDISP
    LDA #$80
    STA !VMAIN
    REP #$20
    .a16
    LDA #$7C00              ; VRAM Word $7C00 (Strip 7 = Slots 28..31)
    STA !VMADDL
    SEP #$20
    .a8
    LDA #$01
    STA !DMAP0
    LDA #$18
    STA !BBAD0
    LDX #$9100              ; $C1:9100 = fx_items.chr
    STX !A1T0L
    LDA #$C1
    STA !A1B0
    LDX #$0800              ; 2,048 bytes
    STX !DAS0L
    LDA #$01
    STA !MDMAEN

    ; Upload FX Palette to OBJ Palette 3 (CGRAM $B0)
    LDA #$B0
    STA !CGADD
    STZ !DMAP0
    LDA #$22
    STA !BBAD0
    LDX #$9900              ; $C1:9900 = fx_items.pal
    STX !A1T0L
    LDA #$C1
    STA !A1B0
    LDX #$0020              ; 32 bytes
    STX !DAS0L
    LDA #$01
    STA !MDMAEN

    LDA !RDNMI
    LDA #$81
    STA !NMITIMEN
    LDA #$0F
    STA !INIDISP
    RTS


; ============================================================================
; LoadPlayerSprites: Loads Selected Retrogamer (DP_CHAR_ID 0..5) into
;                    VRAM $6000 (Slots 0..11, 6144 bytes) & CGRAM $80 (OBJ Pal 0)
; ============================================================================
LoadPlayerSprites:
    SEP #$20
    .a8
    REP #$10
    .i16
    STZ !NMITIMEN
    LDA #$8F
    STA !INIDISP

    ; Compute source offset in Bank $C1: char_id * $1800
    LDA DP_CHAR_ID
    ASL
    TAX
    REP #$20
    .a16
    LDA !PlayerCHROffsetTable,X
    STA DP_TMP0             ; 16-bit source offset in $C1
    LDA #$6000
    STA !VMADDL             ; VRAM $6000
    SEP #$20
    .a8
    LDA #$80
    STA !VMAIN
    LDA #$01
    STA !DMAP0
    LDA #$18
    STA !BBAD0
    LDX DP_TMP0
    STX !A1T0L
    LDA #$C1
    STA !A1B0
    LDX #$1800              ; 6,144 bytes (12 32x32 frames)
    STX !DAS0L
    LDA #$01
    STA !MDMAEN

    ; Upload Player Palette ($C1:9000 + char_id * 32) -> CGRAM $80 (OBJ Pal 0)
    LDA DP_CHAR_ID
    REP #$20
    .a16
    AND #$00FF
    ASL
    ASL
    ASL
    ASL
    ASL                     ; * 32
    CLC
    ADC #$9000
    TAX
    SEP #$20
    .a8
    LDA #$80
    STA !CGADD
    STZ !DMAP0
    LDA #$22
    STA !BBAD0
    STX !A1T0L
    LDA #$C1
    STA !A1B0
    LDX #$0020
    STX !DAS0L
    LDA #$01
    STA !MDMAEN

    LDA !RDNMI
    LDA #$81
    STA !NMITIMEN
    LDA #$0F
    STA !INIDISP
    RTS

PlayerCHROffsetTable:
    .dw $0000, $1800, $3000, $4800, $6000, $7800


; ============================================================================
; LoadStageEnemyAndBossSprites: Loads Enemy (Bank $C2) -> VRAM $6C00 (Slots 12..19)
;                               and Boss (Bank $C3) -> VRAM $7400 (Slots 20..27)
; ============================================================================
LoadStageEnemyAndBossSprites:
    SEP #$20
    .a8
    REP #$10
    .i16
    STZ !NMITIMEN
    LDA #$8F
    STA !INIDISP

    ; Compute offset = DP_STAGE_ID * $1000 (4,096 bytes per stage enemy/boss)
    LDA DP_STAGE_ID
    REP #$20
    .a16
    AND #$00FF
    XBA                     ; * $0100
    ASL
    ASL
    ASL
    ASL                     ; * $1000
    STA DP_TMP0

    ; 1. Enemy CHR ($C2:offset -> VRAM $6C00, 4096 bytes)
    LDA #$6C00
    STA !VMADDL
    SEP #$20
    .a8
    LDA #$80
    STA !VMAIN
    LDA #$01
    STA !DMAP0
    LDA #$18
    STA !BBAD0
    LDX DP_TMP0
    STX !A1T0L
    LDA #$C2
    STA !A1B0
    LDX #$1000
    STX !DAS0L
    LDA #$01
    STA !MDMAEN

    ; 2. Boss CHR ($C3:offset -> VRAM $7400, 4096 bytes)
    REP #$20
    .a16
    LDA #$7400
    STA !VMADDL
    SEP #$20
    .a8
    LDX DP_TMP0
    STX !A1T0L
    LDA #$C3
    STA !A1B0
    LDX #$1000
    STX !DAS0L
    LDA #$01
    STA !MDMAEN

    ; Compute Palette offset = $A000 + DP_STAGE_ID * 32
    LDA DP_STAGE_ID
    REP #$20
    .a16
    AND #$00FF
    ASL
    ASL
    ASL
    ASL
    ASL
    CLC
    ADC #$A000
    STA DP_TMP2
    SEP #$20
    .a8

    ; 3. Enemy Palette ($C2:$A000+ -> CGRAM $90 = OBJ Palette 1)
    LDA #$90
    STA !CGADD
    STZ !DMAP0
    LDA #$22
    STA !BBAD0
    LDX DP_TMP2
    STX !A1T0L
    LDA #$C2
    STA !A1B0
    LDX #$0020
    STX !DAS0L
    LDA #$01
    STA !MDMAEN

    ; 4. Boss Palette ($C3:$A000+ -> CGRAM $A0 = OBJ Palette 2)
    LDA #$A0
    STA !CGADD
    LDX DP_TMP2
    STX !A1T0L
    LDA #$C3
    STA !A1B0
    LDA #$20
    STA !DAS0L
    STZ !DAS0H
    LDA #$01
    STA !MDMAEN

    LDA !RDNMI
    LDA #$81
    STA !NMITIMEN
    LDA #$0F
    STA !INIDISP
    RTS
