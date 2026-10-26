; ============================================================================
; RETROGAMERS AVENTURA 2 (RGA2) - 16-BIT SNES EDITION
; File: src/hardware.inc
; Description: SNES Hardware Registers & Direct Page / WRAM Memory Map
; ============================================================================

; --- PPU Registers ($2100-$213F) ---
INIDISP     = $2100     ; Screen Display & Brightness ($8F = Force Blank, $0F = Full ON)
OBSEL       = $2101     ; Object Size & Base ($63 = 16x16/32x32, Base $6000)
OAMADDL     = $2102     ; OAM Address Low
OAMADDH     = $2103     ; OAM Address High
OAMDATA     = $2104     ; OAM Data Write
BGMODE      = $2105     ; BG Mode ($09 = Mode 1, BG3 Priority High)
MOSAIC      = $2106     ; Mosaic Control
BG1SC       = $2107     ; BG1 Tilemap Base & Size ($39 = $3800, 64x32)
BG2SC       = $2108     ; BG2 Tilemap Base & Size ($40 = $4000, 32x32)
BG3SC       = $2109     ; BG3 Tilemap Base & Size ($44 = $4400, 32x32)
BG4SC       = $210A     ; BG4 Tilemap Base
BG12NBA     = $210B     ; BG1 & BG2 CHR Base ($00 = $0000 for both BG1 & BG2)
BG34NBA     = $210C     ; BG3 & BG4 CHR Base ($03 = $3000 for BG3)
BG1HOFS     = $210D     ; BG1 Horizontal Scroll (Write Twice)
BG1VOFS     = $210E     ; BG1 Vertical Scroll (Write Twice)
BG2HOFS     = $210F     ; BG2 Horizontal Scroll (Write Twice)
BG2VOFS     = $2110     ; BG2 Vertical Scroll (Write Twice)
BG3HOFS     = $2111     ; BG3 Horizontal Scroll (Write Twice)
BG3VOFS     = $2112     ; BG3 Vertical Scroll (Write Twice)
VMAIN       = $2115     ; VRAM Address Increment ($80 = +1 Word on High Byte Write)
VMADDL      = $2116     ; VRAM Word Address Low
VMADDH      = $2117     ; VRAM Word Address High
VMDATAL     = $2118     ; VRAM Data Write Low
VMDATAH     = $2119     ; VRAM Data Write High
M7SEL       = $211A     ; Mode 7 Settings
M7A         = $211B     ; Mode 7 Matrix A
M7B         = $211C     ; Mode 7 Matrix B
M7C         = $211D     ; Mode 7 Matrix C
M7D         = $211E     ; Mode 7 Matrix D
M7X         = $211F     ; Mode 7 Center X
M7Y         = $2120     ; Mode 7 Center Y
CGADD       = $2121     ; CGRAM Word Address
CGDATA      = $2122     ; CGRAM Data Write (Write Twice: Low, High)
W12SEL      = $2123     ; Window Mask Settings BG1/BG2
W34SEL      = $2124     ; Window Mask Settings BG3/BG4
WOBJSEL     = $2125     ; Window Mask Settings OBJ/MATH
TM          = $212C     ; Main Screen Designation ($17 = BG1+BG2+BG3+OBJ)
TS          = $212D     ; Sub Screen Designation
TMW         = $212E     ; Window Mask Main Screen
TSW         = $212F     ; Window Mask Sub Screen
CGWSEL      = $2130     ; Color Math Control A
CGADSUB     = $2131     ; Color Math Control B
COLDATA     = $2132     ; Fixed Color Data
SETINI      = $2133     ; Screen Mode/Video Select

; --- APU / SPC700 Communication Ports ($2140-$2143) ---
APUIO0      = $2140     ; BGM Track Command / IPL Handshake
APUIO1      = $2141     ; SFX Trigger Counter / IPL Handshake
APUIO2      = $2142     ; SFX Sample ID / IPL Address Low
APUIO3      = $2143     ; Driver Status ('R'=$52) / IPL Address High

; --- CPU / DMA / Joypad Registers ($4200-$437F) ---
NMITIMEN    = $4200     ; NMI & Auto-Joypad Enable ($81 = NMI + Joypad Enable)
WRIO        = $4201     ; Programmable I/O Port
MDMAEN      = $420B     ; DMA Channel Enable
HDMAEN      = $420C     ; HDMA Channel Enable
MEMSEL      = $420D     ; FastROM Select ($01 = 3.58MHz FastROM)
RDNMI       = $4210     ; NMI Flag & 5A22 Version (Read to acknowledge NMI)
TIMEUP      = $4211     ; IRQ Flag
HVBJOY      = $4212     ; VBlank/HBlank & Auto-Joypad Status ($01 = Joypad Busy)
JOY1L       = $4218     ; Controller 1 Data Low  (A=$80, X=$40, L=$20, R=$10)
JOY1H       = $4219     ; Controller 1 Data High (B=$80, Y=$40, Sel=$20, St=$10, U=$08, D=$04, L=$02, R=$01)

DMAP0       = $4300     ; DMA0 Control
BBAD0       = $4301     ; DMA0 B-Bus Register ($18=VMDATAL, $22=CGDATA, $04=OAMDATA)
A1T0L       = $4302     ; DMA0 Source Address Low
A1T0H       = $4303     ; DMA0 Source Address High
A1B0        = $4304     ; DMA0 Source Bank
DAS0L       = $4305     ; DMA0 Byte Count Low
DAS0H       = $4306     ; DMA0 Byte Count High

DMAP7       = $4370     ; DMA7 Control (Dedicated to VBlank NMI Handler!)
BBAD7       = $4371     ; DMA7 B-Bus Register
A1T7L       = $4372     ; DMA7 Source Address Low
A1T7H       = $4373     ; DMA7 Source Address High
A1B7        = $4374     ; DMA7 Source Bank
DAS7L       = $4375     ; DMA7 Byte Count Low
DAS7H       = $4376     ; DMA7 Byte Count High

; --- Joypad Button Masks (16-bit combined JOY1L/JOY1H) ---
BTN_A       = $0080
BTN_X       = $0040
BTN_L       = $0020
BTN_R       = $0010
BTN_B       = $8000
BTN_Y       = $4000
BTN_SELECT  = $2000
BTN_START   = $1000
BTN_UP      = $0800
BTN_DOWN    = $0400
BTN_LEFT    = $0200
BTN_RIGHT   = $0100

; --- Game States ---
STATE_TITLE     = 0
STATE_INTRO     = 1
STATE_SELECT    = 2
STATE_HUB       = 3
STATE_STAGE     = 4
STATE_ENDING    = 5
STATE_GAMEOVER  = 6

; --- Direct Page Variables ($00-$7F) ---
DP_FRAME        = $00
DP_NMI_DONE     = $01
DP_JOY_CUR      = $02   ; 16-bit ($02=JOY1L, $03=JOY1H)
DP_JOY_CUR_H    = $03
DP_JOY_NEW      = $04   ; 16-bit ($04=NewL,  $05=NewH)
DP_JOY_NEW_H    = $05
DP_JOY_OLD      = $06   ; 16-bit
DP_STATE        = $08
DP_CHAR_ID      = $09   ; 0..5 (Velberan, SrWilson, PaiTroll, Snestalgia, OldGamer, Monique)
DP_STAGE_ID     = $0A   ; 0=BGS, 1=Hub, 2..9=Portals 1..8
DP_PORTALS      = $0B   ; Bitmask of cleared portals (bit 0..7)
DP_CAM_X        = $0C   ; 16-bit Camera Scroll X (0..256)
DP_CAM_X_H      = $0D
DP_SCORE        = $0E   ; 16-bit Player Score
DP_LIVES        = $10   ; Player Lives
DP_CREDITS      = $11   ; Continues remaining
DP_PL_X         = $12   ; 16-bit Player World X
DP_PL_X_H       = $13
DP_PL_Z         = $14   ; Player Z Depth (128..192)
DP_PL_Y_OFF     = $15   ; Player Jump Altitude (0..64)
DP_PL_VY        = $16   ; Signed Jump Velocity
DP_PL_DIR       = $17   ; 0=Right, 1=Left
DP_PL_ANIM      = $18   ; Current Sprite Frame (0..11)
DP_PL_ACT       = $19   ; 0=Move, 1=Atk1, 2=Atk2, 3=Atk3, 4=Jump, 5=Special, 6=Hurt, 7=Block
DP_PL_TIMER     = $1A   ; Action frame timer
DP_PL_COMBO     = $1B   ; Combo chain window
DP_PL_HP        = $1C   ; Current HP
DP_PL_MAXHP     = $1D   ; Max HP
DP_PL_MP        = $1E   ; Current MP (0..100)
DP_PL_INV       = $1F   ; Invincibility frames
DP_PL_SPD       = $20   ; Walk speed
DP_PL_ATK       = $21   ; Base attack damage
DP_WAVE_NUM     = $22   ; Current wave (0..2 = Enemies, 3 = Boss, 4 = Clear)
DP_WAVE_LOCK    = $23   ; 1 = Enemies active, 0 = Advance
DP_GO_TIMER     = $24   ; Stage clear / GO timer
DP_PROJ_ACT     = $25   ; 1 = Special Projectile active
DP_PROJ_X       = $26   ; 16-bit Projectile World X
DP_PROJ_Z       = $28   ; Projectile Z
DP_PROJ_DIR     = $29   ; Projectile Direction
DP_ITEM_ACT     = $2A   ; 0=None, 1=Pizza(HP), 2=Mana(MP)
DP_ITEM_X       = $2B   ; 16-bit Item World X
DP_ITEM_Z       = $2D   ; Item Z
DP_SPARK_TMR    = $2E   ; Hit Spark timer
DP_SPARK_X      = $2F   ; Hit Spark screen X
DP_SPARK_Y      = $30   ; Hit Spark screen Y
DP_SPC_SFX_CNT  = $31   ; SPC700 SFX counter
DP_SPC_OK       = $32   ; SPC700 Ready flag
DP_HUD_DIRTY    = $33   ; 1 = Upload BG3 HUD in NMI
DP_NEAR_PORTAL  = $34   ; $FF or 0..7 in Hub
DP_BOSS_ACT     = $35   ; 1 = Boss active
DP_BOSS_HP      = $36   ; Boss current HP
DP_BOSS_MAXHP   = $37   ; Boss max HP
DP_PTR0         = $38   ; 24-bit pointer ($38,$39,$3A)
DP_PTR0_H       = $39
DP_PTR0_B       = $3A
DP_TMP0         = $3B
DP_TMP1         = $3C
DP_TMP2         = $3D
DP_TMP3         = $3E
DP_TMP4         = $3F

; --- Enemy Slots in Direct Page ($40-$7F, 4 slots * 16 bytes) ---
EN_ACT          = $40   ; 0=Off, 1=Regular Enemy, 2=Boss
EN_STATE        = $41   ; 0=Chase, 1=Windup, 2=Attack, 3=Hurt, 4=KO
EN_X_LO         = $42   ; 16-bit World X
EN_X_HI         = $43
EN_Z            = $44   ; Z depth
EN_DIR          = $45   ; 0=Right, 1=Left
EN_HP           = $46   ; Current HP
EN_MAXHP        = $47   ; Max HP
EN_TIMER        = $48   ; AI Timer
EN_ANIM         = $49   ; Animation frame (0..7)
EN_ATK          = $4A   ; Attack damage

; --- WRAM Shadow Buffers ---
OAM_BUF         = $0200 ; 512 bytes Low OAM ($0200-$03FF)
OAM_HI_BUF      = $0400 ; 32 bytes High OAM ($0400-$041F)
BG3_MAP_BUF     = $1000 ; 2048 bytes BG3 32x32 Tilemap Shadow ($1000-$17FF)

; --- Cartridge Battery SRAM ($B0:6000 in HiROM/ExHiROM) ---
SRAM_MAGIC0     = $B06000
SRAM_MAGIC1     = $B06001
SRAM_MAGIC2     = $B06002
SRAM_MAGIC3     = $B06003
SRAM_PORTALS    = $B06004
SRAM_HISCORE_L  = $B06005
SRAM_HISCORE_H  = $B06006
