; ============================================================================
; RETROGAMERS AVENTURA 2 (RGA2) - 16-BIT SNES EDITION
; File: src/init_boot.asm
; Description: 65C816 Reset, PPU/WRAM/VRAM/OAM Init, SRAM & SPC700 IPL Loader
; ============================================================================

ResetHandler:
    SEI                     ; Disable interrupts
    CLC
    XCE                     ; Switch 65C816 to Native 16-bit Mode
    REP #$38                ; A=16-bit, X/Y=16-bit, Decimal=0
    .a16
    .i16
    LDX #$1FFF
    TXS                     ; Stack pointer = $1FFF
    LDA #$0000
    TCD                     ; Direct Page = $0000

    SEP #$20                ; A=8-bit
    .a8
    LDA #$01
    STA !MEMSEL             ; Enable 3.58MHz FastROM
    JML FastReset + $800000 ; Jump to FastROM Mirror in Bank $80

FastReset:
    LDA #$80
    PHA
    PLB                     ; Data Bank = $80 (FastROM system bank)

    ; --- Force Blank & Disable NMI/DMA during hardware init ---
    LDA #$8F
    STA !INIDISP            ; Force Blank ON
    STZ !NMITIMEN           ; Disable NMI & Joypad auto-read
    STZ !MDMAEN             ; Disable DMA
    STZ !HDMAEN             ; Disable HDMA

    ; --- Clear PPU Registers ---
    LDA #$63
    STA !OBSEL              ; OBJ: 16x16 small / 32x32 large, Base = $6000 word
    LDA #$09
    STA !BGMODE             ; Mode 1 (BG1 4bpp, BG2 4bpp, BG3 2bpp with HIGH PRIORITY)
    STZ !MOSAIC
    LDA #$39
    STA !BG1SC              ; BG1 Tilemap @ VRAM $3800, 64x32 tiles
    LDA #$40
    STA !BG2SC              ; BG2 Tilemap @ VRAM $4000, 32x32 tiles
    LDA #$44
    STA !BG3SC              ; BG3 Tilemap @ VRAM $4400, 32x32 tiles
    STZ !BG4SC
    LDA #$00
    STA !BG12NBA            ; BG1 & BG2 CHR @ VRAM $0000
    LDA #$03
    STA !BG34NBA            ; BG3 CHR @ VRAM $3000

    ; Reset Scroll Registers (Double-Write Low, High)
    STZ !BG1HOFS
    STZ !BG1HOFS
    LDA #$FF
    STA !BG1VOFS
    STZ !BG1VOFS
    STZ !BG2HOFS
    STZ !BG2HOFS
    STA !BG2VOFS
    STZ !BG2VOFS
    STZ !BG3HOFS
    STZ !BG3HOFS
    STA !BG3VOFS
    STZ !BG3VOFS

    ; Disable Window Masks & Color Math
    STZ !W12SEL
    STZ !W34SEL
    STZ !WOBJSEL
    STZ !TMW
    STZ !TSW
    STZ !CGWSEL
    STZ !CGADSUB
    LDA #$E0
    STA !COLDATA
    STZ !SETINI

    ; Enable BG1 + BG2 + BG3 + OBJ on Main Screen ($17)
    LDA #$17
    STA !TM
    STZ !TS

    ; --- Clear WRAM ($0000-$1EFF) ---
    REP #$20
    .a16
    LDX #$0000
ClearWRAMLoop:
    STZ !$0000,X
    INX
    INX
    CPX #$1F00
    BCC ClearWRAMLoop

    ; --- Clear All 64KB of VRAM ($0000-$7FFF Words) ---
    SEP #$20
    .a8
    LDA #$80
    STA !VMAIN              ; Increment VRAM word address on high byte write
    REP #$20
    .a16
    LDA #$0000
    STA !VMADDL
    LDX #$8000              ; 32,768 words = 64KB
    LDA #$0000
ClearVRAMLoop:
    STA !VMDATAL
    DEX
    BNE ClearVRAMLoop

    ; --- Clear All 512 Bytes of CGRAM (256 Colors) ---
    SEP #$20
    .a8
    STZ !CGADD
    LDX #$0100              ; 256 words
ClearCGRAMLoop:
    STZ !CGDATA
    STZ !CGDATA
    DEX
    BNE ClearCGRAMLoop

    ; --- Initialize OAM Shadow Buffer & Upload to PPU OAM ---
    JSR ClearOAMBuffer
    JSR UploadOAMNow

    ; --- Upload BG3 2bpp Arcade HUD Font ($C0:3000 -> VRAM $3000, 2048 bytes) ---
    LDA #$80
    STA !VMAIN
    REP #$20
    .a16
    LDA #$3000
    STA !VMADDL
    SEP #$20
    .a8
    LDA #$01
    STA !DMAP0              ; 2 registers write once ($2118/$2119)
    LDA #$18
    STA !BBAD0              ; VMDATAL
    LDX #$3000              ; Source $C0:3000
    STX !A1T0L
    LDA #$C0
    STA !A1B0
    LDX #$0800              ; 2,048 bytes
    STX !DAS0L
    LDA #$01
    STA !MDMAEN

    ; --- Upload BG3 2bpp HUD Palettes ($C0:3800 -> CGRAM $00, 32 bytes) ---
    STZ !CGADD
    STZ !DMAP0              ; 1 register write once ($2122)
    LDA #$22
    STA !BBAD0
    LDX #$3800
    STX !A1T0L
    LDA #$C0
    STA !A1B0
    LDX #$0020              ; 32 bytes (4 2bpp palettes)
    STX !DAS0L
    LDA #$01
    STA !MDMAEN

    ; --- Upload Universal FX / Portal / Pickup Sprites ($C1:9100 -> VRAM $7C00, 2048 bytes) ---
    JSR LoadUniversalFXSprites

    ; --- Upload SPC700 Audio Driver & BRR Sound Bank ($C0:0000 -> ARAM $0200) ---
    JSR InitSPC700Audio

    ; --- Load or Initialize Cartridge Battery SRAM ($B0:6000) ---
    JSR InitOrLoadSRAM

    ; --- Start in Title Screen State ---
    LDA #STATE_TITLE
    STA DP_STATE
    JSR EnterTitleState

    ; --- Enable VBlank NMI & Auto-Joypad Read, Turn Screen ON ---
    LDA !RDNMI              ; Clear any pending NMI flag
    LDA #$81
    STA !NMITIMEN           ; Enable NMI + Auto-Joypad
    LDA #$0F
    STA !INIDISP            ; Screen ON, Full Brightness ($0F)
    CLI

; ============================================================================
; MAIN GAME LOOP (Synchronized to 60Hz VBlank NMI)
; ============================================================================
MainGameLoop:
    STZ DP_NMI_DONE
WaitVBlankLoop:
    WAI                     ; Wait for NMI interrupt
    LDA DP_NMI_DONE
    BEQ WaitVBlankLoop

    ; Read Controller 1 and compute newly pressed buttons
    JSR ReadJoypadInput

    ; Run Current Game State Update
    JSR RunGameStateFrame

    JMP MainGameLoop


; ============================================================================
; InitOrLoadSRAM: Checks Battery SRAM at $B0:6000 for "RGA2" signature
; ============================================================================
InitOrLoadSRAM:
    SEP #$20
    .a8
    LDA @SRAM_MAGIC0
    CMP #$52                ; 'R'
    BNE FormatSRAM
    LDA @SRAM_MAGIC1
    CMP #$47                ; 'G'
    BNE FormatSRAM
    LDA @SRAM_MAGIC2
    CMP #$41                ; 'A'
    BNE FormatSRAM
    LDA @SRAM_MAGIC3
    CMP #$32                ; '2'
    BNE FormatSRAM
    ; Valid SRAM found! Load cleared portals bitmask
    LDA @SRAM_PORTALS
    STA DP_PORTALS
    RTS

FormatSRAM:
    LDA #$52
    STA @SRAM_MAGIC0
    LDA #$47
    STA @SRAM_MAGIC1
    LDA #$41
    STA @SRAM_MAGIC2
    LDA #$32
    STA @SRAM_MAGIC3
    LDA #$00
    STA @SRAM_PORTALS
    STA @SRAM_HISCORE_L
    STA @SRAM_HISCORE_H
    STZ DP_PORTALS
    RTS

SaveProgressToSRAM:
    SEP #$20
    .a8
    LDA DP_PORTALS
    STA @SRAM_PORTALS
    RTS


; ============================================================================
; InitSPC700Audio: Uploads SPC700 Driver + BRR Bank ($C0:0000, $2A4C bytes)
;                  to ARAM $0200 using Nintendo IPL Boot ROM protocol.
;                  Includes hardware timeout so warm resets never hang!
; ============================================================================
InitSPC700Audio:
    SEP #$20
    .a8
    REP #$10
    .i16

    ; Check if our custom driver is ALREADY running in SPC700 (Warm Reset case!)
    LDA !APUIO3
    CMP #$52                ; 'R' signature from running RGA2 SPC700 driver
    BNE WaitForIPLReady
    STZ !APUIO0
    STZ !APUIO1
    STZ !APUIO2
    LDA #$01
    STA DP_SPC_OK
    RTS

WaitForIPLReady:
    LDY #$8000              ; Timeout counter for real hardware / flashcart safety
WaitIPLLoop:
    LDA !APUIO0
    CMP #$AA
    BNE WaitIPLNext
    LDA !APUIO1
    CMP #$BB
    BEQ IPLHandshakeOK
WaitIPLNext:
    DEY
    BNE WaitIPLLoop
    ; Timeout reached: continue game gracefully without hanging
    STZ DP_SPC_OK
    RTS

IPLHandshakeOK:
    ; Set destination ARAM address = $0200 in APUIO2/APUIO3
    LDA #$00
    STA !APUIO2
    LDA #$02
    STA !APUIO3
    ; Write non-zero kick byte $CC to APUIO0 and $01 (transfer) to APUIO1
    LDA #$01
    STA !APUIO1
    LDA #$CC
    STA !APUIO0

    LDY #$8000
WaitIPLStartAck:
    CMP !APUIO0
    BEQ IPLTransferData
    DEY
    BNE WaitIPLStartAck
    STZ DP_SPC_OK
    RTS

IPLTransferData:
    ; Transfer $2A4C (10,828) bytes from $C0:0000 to ARAM $0200
    LDX #$0000              ; Byte index & counter (low byte sent to APUIO0)
IPLByteLoop:
    LDA @$C00000,X          ; Read byte from SPC700 image in Bank $C0
    STA !APUIO1             ; Data byte -> APUIO1
    TXA                     ; Counter -> A
    STA !APUIO0             ; Counter -> APUIO0
    LDY #$2000
WaitIPLByteAck:
    CMP !APUIO0
    BEQ IPLByteAcked
    DEY
    BNE WaitIPLByteAck
    STZ DP_SPC_OK
    RTS

IPLByteAcked:
    INX
    CPX #$2A4C              ; Total size of spc700_aram.bin (10,828 bytes)
    BCC IPLByteLoop

    ; Execute uploaded SPC700 program at $0200:
    ; Write $0200 to APUIO2/3, $00 to APUIO1, and (last_index + 2) to APUIO0
    LDA #$00
    STA !APUIO2
    LDA #$02
    STA !APUIO3
    STZ !APUIO1
    TXA
    CLC
    ADC #$02
    STA !APUIO0

    ; CRITICAL: Wait for SPC700 IPL ROM to jump to $0200 and for our driver
    ; to initialize the S-DSP and write $52 ('R') to APUIO3 ($2143) BEFORE clearing APUIO0!
    LDY #$8000
WaitSPCDriverBoot:
    LDA !APUIO3
    CMP #$52
    BEQ SPCDriverBooted
    DEY
    BNE WaitSPCDriverBoot
SPCDriverBooted:

    ; Clear CPU ports so BGM/SFX commands start clean
    STZ !APUIO0
    STZ !APUIO1
    STZ !APUIO2
    LDA #$01
    STA DP_SPC_OK
    RTS


; ============================================================================
; Audio Helper Routines: PlayBGMTrack (A = Track 1..12), PlaySFX (A = SFX 4..11)
; ============================================================================
PlayBGMTrack:
    SEP #$20
    .a8
    STA !APUIO0
    RTS

PlaySFX:
    SEP #$20
    .a8
    STA !APUIO2             ; SFX Sample ID (4..11)
    INC DP_SPC_SFX_CNT
    LDA DP_SPC_SFX_CNT
    BNE SendSFXCnt
    INC DP_SPC_SFX_CNT
    LDA DP_SPC_SFX_CNT
SendSFXCnt:
    STA !APUIO1             ; Incrementing counter triggers SFX in SPC700
    RTS
