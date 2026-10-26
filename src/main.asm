; ============================================================================
; RETROGAMERS AVENTURA 2 (RGA2) - 16-BIT SNES EDITION
; File: src/main.asm
; Description: Master 65C816 Assembly Entry Point ($00:8000 / $80:8000 / $C0:8000)
; ============================================================================

    .org $8000

    .include "hardware.inc"
    .include "init_boot.asm"
    .include "dma_ppu.asm"
    .include "hud_text.asm"
    .include "gameplay.asm"
    .include "data_tables.asm"
