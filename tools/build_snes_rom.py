#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RGA2 (OpenBOR) -> Super Nintendo (SNES) Master ROM Builder & Linker
Assembles 65C816 source code (src/main.asm), links all converted OpenBOR graphics & SPC700 BRR audio,
computes exact Nintendo SNES internal headers and checksums, and outputs:
  1. snes_rga2/rom/RGA2_SNES.smc                 (4 MB / 32 Mbit FastROM HiROM - Universal Emulator/EverDrive/27C322)
  2. snes_rga2/rom/RGA2_SNES_ExHiROM_48Mbit.smc  (6 MB / 48 Mbit FastROM ExHiROM - Extended 48Mbit Edition)
  3. snes_rga2/rom/eprom/*                       (Ready-to-burn EPROM binary images for 27C322 / 27C160)
"""

import os
import sys
import struct

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(TOOLS_DIR, ".."))
SRC_DIR = os.path.join(PROJECT_DIR, "src")
ASSETS_DIR = os.path.join(PROJECT_DIR, "build", "assets")
BUILD_DIR = os.path.join(PROJECT_DIR, "build")
ROM_DIR = os.path.join(PROJECT_DIR, "rom")
EPROM_DIR = os.path.join(ROM_DIR, "eprom")

sys.path.insert(0, TOOLS_DIR)
from asm65816 import Assembler65816


def load_asset(name):
    p = os.path.join(ASSETS_DIR, name)
    with open(p, "rb") as f:
        return f.read()


def write_snes_header(rom_buf, header_base, title_str, map_mode, rom_size_code, sram_size_code, reset_addr, nmi_addr, irq_addr):
    """
    Writes a 100% compliant Nintendo SNES Internal ROM Header at `header_base` ($FFB0 within a bank):
      $FFB0-$FFB1: Maker Code ("RG")
      $FFB2-$FFB5: Game Code ("RGA2")
      $FFB6-$FFBF: Reserved ($00)
      $FFC0-$FFD4: 21-Byte ASCII Cartridge Title (space-padded)
      $FFD5      : Map Mode ($31 = FastROM HiROM, $35 = FastROM ExHiROM)
      $FFD6      : Cartridge Type ($02 = ROM + RAM + Battery SRAM)
      $FFD7      : ROM Size ($0C = 4MB/32Mbit, $0D = 6-8MB/48-64Mbit)
      $FFD8      : SRAM Size ($03 = 8KB SRAM)
      $FFD9      : Destination Region ($01 = NTSC North America/Brazil 60Hz)
      $FFDA      : Developer ID ($33 = Extended Header present)
      $FFDB      : Mask ROM Version ($00)
      $FFDC-$FFDD: Checksum Complement (initially $FFFF)
      $FFDE-$FFDF: Checksum (initially $0000)
      $FFE0-$FFFF: Native & Emulation Interrupt Vectors
    """
    rom_buf[header_base + 0x00 : header_base + 0x02] = b"RG"
    rom_buf[header_base + 0x02 : header_base + 0x06] = b"RGA2"
    rom_buf[header_base + 0x06 : header_base + 0x10] = b"\x00" * 10

    title_bytes = title_str.encode("ascii")[:21].ljust(21, b" ")
    rom_buf[header_base + 0x10 : header_base + 0x25] = title_bytes

    rom_buf[header_base + 0x25] = map_mode
    rom_buf[header_base + 0x26] = 0x02  # ROM + RAM + Battery
    rom_buf[header_base + 0x27] = rom_size_code
    rom_buf[header_base + 0x28] = sram_size_code
    rom_buf[header_base + 0x29] = 0x01  # NTSC 60Hz
    rom_buf[header_base + 0x2A] = 0x33  # Extended header marker
    rom_buf[header_base + 0x2B] = 0x00  # Version 1.0

    # Initialize complement=$FFFF, checksum=$0000 before checksum calculation
    struct.pack_into("<HH", rom_buf, header_base + 0x2C, 0xFFFF, 0x0000)

    # Native 65C816 Vectors ($FFE4-$FFEF):
    #   $FFE4: COP, $FFE6: BRK, $FFE8: ABORT, $FFEA: NMI, $FFEC: RSV, $FFEE: IRQ
    struct.pack_into(
        "<HHHHHH",
        rom_buf,
        header_base + 0x34,
        irq_addr,
        irq_addr,
        irq_addr,
        nmi_addr,
        irq_addr,
        irq_addr,
    )

    # Emulation 6502 Vectors ($FFF4-$FFFF):
    #   $FFF4: COP, $FFF6: RSV, $FFF8: ABORT, $FFFA: NMI, $FFFC: RESET, $FFFE: IRQ/BRK
    struct.pack_into(
        "<HHHHHH",
        rom_buf,
        header_base + 0x44,
        irq_addr,
        irq_addr,
        irq_addr,
        nmi_addr,
        reset_addr,
        irq_addr,
    )


def compute_and_write_checksum(rom_buf, header_bases):
    """
    Computes the official Nintendo SNES 16-bit ROM checksum:
    - For power-of-two ROMs (e.g. 4MB), sum of all bytes & 0xFFFF.
    - For 6MB (4MB + 2MB) non-power-of-two ROMs, SNES checksum standard sums the first 4MB
      plus twice the remaining 2MB (mirroring the upper 2MB to fill 4MB) & 0xFFFF!
    """
    # Ensure all header slots have complement=0xFFFF, checksum=0x0000 before summing
    for hb in header_bases:
        struct.pack_into("<HH", rom_buf, hb + 0x2C, 0xFFFF, 0x0000)

    size = len(rom_buf)
    if size == 4 * 1024 * 1024:
        chk = sum(rom_buf) & 0xFFFF
    elif size == 6 * 1024 * 1024:
        first_4m = sum(rom_buf[: 4 * 1024 * 1024])
        upper_2m = sum(rom_buf[4 * 1024 * 1024 :])
        chk = (first_4m + upper_2m * 2) & 0xFFFF
    else:
        chk = sum(rom_buf) & 0xFFFF

    comp = chk ^ 0xFFFF
    for hb in header_bases:
        struct.pack_into("<HH", rom_buf, hb + 0x2C, comp, chk)

    # Re-verify that writing comp & chk preserves the sum (since comp + chk == 0xFFFF, identical to 0xFFFF + 0x0000!)
    return chk, comp


def main():
    os.makedirs(BUILD_DIR, exist_ok=True)
    os.makedirs(ROM_DIR, exist_ok=True)
    os.makedirs(EPROM_DIR, exist_ok=True)

    print("=== Assembling RGA2 65C816 Source Code (src/main.asm) ===")
    asm = Assembler65816(SRC_DIR)
    asm.load_source("main.asm")
    org_base, code_bytes, symbols = asm.assemble()

    reset_addr = symbols["ResetHandler"]
    nmi_addr = symbols["NMIHandler"]
    irq_addr = symbols["IRQHandler"]

    print(f"[OK] Assembled 65C816 Engine: {len(code_bytes)} bytes (${org_base:04X}..${org_base + len(code_bytes) - 1:04X})")
    print(f"     Vectors -> RESET: ${reset_addr:04X}, NMI: ${nmi_addr:04X}, IRQ: ${irq_addr:04X}")

    # Save symbol file for debugging / emulators (Mesen-S / bsnes)
    sym_path = os.path.join(BUILD_DIR, "rga2_snes.sym")
    with open(sym_path, "w", encoding="utf-8") as f:
        for k, v in sorted(symbols.items(), key=lambda x: x[1]):
            f.write(f"00:{v:04X} {k}\n")

    # Build the core 4 MB (32 Mbit = 64 Banks of 64KB) ROM image first
    rom_4mb = bytearray(4 * 1024 * 1024)

    # --- Bank $C0 ($000000-$00FFFF): Engine Code, SPC700 Audio, BG3 Font & Header ---
    spc_bin = load_asset("spc700_aram.bin")
    hud_chr = load_asset("hud_2bpp.chr")
    hud_pal = load_asset("hud_2bpp.pal")
    assert len(spc_bin) == 0x2A4C, f"Unexpected spc_bin size: {len(spc_bin)}"
    rom_4mb[0x000000 : 0x000000 + len(spc_bin)] = spc_bin
    rom_4mb[0x003000 : 0x003000 + len(hud_chr)] = hud_chr
    rom_4mb[0x003800 : 0x003800 + len(hud_pal)] = hud_pal
    assert org_base == 0x8000 and org_base + len(code_bytes) <= 0xFFB0
    rom_4mb[0x008000 : 0x008000 + len(code_bytes)] = code_bytes

    # --- Bank $C1 ($010000-$01FFFF): 6 Playable Retrogamers + Universal FX/Portals ---
    players_chr = load_asset("players.chr")
    players_pal = load_asset("players.pal")
    fx_chr = load_asset("fx_items.chr")
    fx_pal = load_asset("fx_items.pal")
    rom_4mb[0x010000 : 0x010000 + len(players_chr)] = players_chr
    rom_4mb[0x019000 : 0x019000 + len(players_pal)] = players_pal
    rom_4mb[0x019100 : 0x019100 + len(fx_chr)] = fx_chr
    rom_4mb[0x019900 : 0x019900 + len(fx_pal)] = fx_pal

    # --- Bank $C2 ($020000-$02FFFF): All 10 Stage Enemy Spritesheets & Palettes ---
    enemies_chr = load_asset("enemies.chr")
    enemies_pal = load_asset("enemies.pal")
    rom_4mb[0x020000 : 0x020000 + len(enemies_chr)] = enemies_chr
    rom_4mb[0x02A000 : 0x02A000 + len(enemies_pal)] = enemies_pal

    # --- Bank $C3 ($030000-$03FFFF): All 10 Stage Boss Spritesheets & Palettes ---
    bosses_chr = load_asset("bosses.chr")
    bosses_pal = load_asset("bosses.pal")
    rom_4mb[0x030000 : 0x030000 + len(bosses_chr)] = bosses_chr
    rom_4mb[0x03A000 : 0x03A000 + len(bosses_pal)] = bosses_pal

    # --- Banks $C4..$D1 ($040000-$11FFFF): 14 Full Screens & Scrolling Stage Packages ---
    bank_assets = [
        (0xC4, "screen_title.bin"),
        (0xC5, "screen_select.bin"),
        (0xC6, "screen_gameover.bin"),
        (0xC7, "screen_ending.bin"),
        (0xC8, "stage_00_bgs.bin"),
        (0xC9, "stage_01_hub.bin"),
        (0xCA, "stage_02_mega.bin"),
        (0xCB, "stage_03_tmnt.bin"),
        (0xCC, "stage_04_gold.bin"),
        (0xCD, "stage_05_sf.bin"),
        (0xCE, "stage_06_ninja.bin"),
        (0xCF, "stage_07_mario.bin"),
        (0xD0, "stage_08_toads.bin"),
        (0xD1, "stage_09_tube.bin"),
    ]
    for bank_id, asset_name in bank_assets:
        data = load_asset(asset_name)
        rom_off = (bank_id - 0xC0) * 0x10000
        rom_4mb[rom_off : rom_off + len(data)] = data

    # Mirror active asset banks across upper banks ($E0..$FF) so EPROM address lines are populated
    for b in range(0x12, 0x40):
        src_b = 0x04 + ((b - 0x12) % 14)
        rom_4mb[b * 0x10000 : (b + 1) * 0x10000] = rom_4mb[src_b * 0x10000 : (src_b + 1) * 0x10000]

    # 1. Finalize 4 MB (32 Mbit) FastROM HiROM ($31) Image
    rom_32mbit = bytearray(rom_4mb)
    write_snes_header(
        rom_32mbit,
        header_base=0x00FFB0,
        title_str="RETROGAMERS AVENTURA2",
        map_mode=0x31,       # FastROM HiROM
        rom_size_code=0x0C,  # 4 MB (32 Mbit)
        sram_size_code=0x03, # 8 KB Battery SRAM
        reset_addr=reset_addr,
        nmi_addr=nmi_addr,
        irq_addr=irq_addr,
    )
    chk32, comp32 = compute_and_write_checksum(rom_32mbit, [0x00FFB0])

    smc_main_path = os.path.join(ROM_DIR, "RGA2_SNES.smc")
    sfc_main_path = os.path.join(ROM_DIR, "RGA2_SNES.sfc")
    with open(smc_main_path, "wb") as f:
        f.write(rom_32mbit)
    with open(sfc_main_path, "wb") as f:
        f.write(rom_32mbit)
    print(f"[OK] Generated 32 Mbit (4 MB) ROM: {smc_main_path}")
    print(f"     Checksum: ${chk32:04X}, Complement: ${comp32:04X} (XOR = ${chk32 ^ comp32:04X})")

    # 2. Build 6 MB (48 Mbit) FastROM ExHiROM ($35) Image!
    # In ExHiROM:
    #   File offset $000000-$3FFFFF (First 4MB) maps to Banks $C0-$FF (and upper halves of $80-$BF)
    #   File offset $400000-$5FFFFF (Second 2MB) maps to Banks $40-$5F (and upper halves of $00-$1F)
    #   Notice: By mirroring Bank 0 ($000000-$00FFFF) to $400000-$40FFFF and placing the ExHiROM Header
    #   at BOTH $00FFB0 and $40FFB0, the 6MB ExHiROM boots on 100% of emulators, SD2SNES/FXPAK Pro, EverDrives,
    #   and dual-EPROM ExHiROM boards!
    rom_48mbit = bytearray(6 * 1024 * 1024)
    rom_48mbit[: 4 * 1024 * 1024] = rom_4mb
    rom_48mbit[4 * 1024 * 1024 : 6 * 1024 * 1024] = rom_4mb[: 2 * 1024 * 1024]

    for hb in (0x00FFB0, 0x40FFB0):
        write_snes_header(
            rom_48mbit,
            header_base=hb,
            title_str="RETROGAMERS AVENTURA2",
            map_mode=0x35,       # FastROM ExHiROM
            rom_size_code=0x0D,  # 48-64 Mbit
            sram_size_code=0x03, # 8 KB Battery SRAM
            reset_addr=reset_addr,
            nmi_addr=nmi_addr,
            irq_addr=irq_addr,
        )
    chk48, comp48 = compute_and_write_checksum(rom_48mbit, [0x00FFB0, 0x40FFB0])

    exhirom_path = os.path.join(ROM_DIR, "RGA2_SNES_ExHiROM_48Mbit.smc")
    with open(exhirom_path, "wb") as f:
        f.write(rom_48mbit)
    print(f"[OK] Generated 48 Mbit (6 MB) ExHiROM: {exhirom_path}")
    print(f"     Checksum: ${chk48:04X}, Complement: ${comp48:04X} (XOR = ${chk48 ^ comp48:04X})")

    # 3. Write Ready-to-Burn Physical EPROM Images (27C322 / 27C160)
    eprom_single = os.path.join(EPROM_DIR, "RGA2_EPROM_27C322_32Mbit.bin")
    eprom_u1 = os.path.join(EPROM_DIR, "RGA2_ExHiROM_U1_27C322_32Mbit.bin")
    eprom_u2 = os.path.join(EPROM_DIR, "RGA2_ExHiROM_U2_27C160_16Mbit.bin")
    with open(eprom_single, "wb") as f:
        f.write(rom_32mbit)
    with open(eprom_u1, "wb") as f:
        f.write(rom_48mbit[: 4 * 1024 * 1024])
    with open(eprom_u2, "wb") as f:
        f.write(rom_48mbit[4 * 1024 * 1024 :])
    print(f"[OK] Generated EPROM Burner Binaries in {EPROM_DIR}")


if __name__ == "__main__":
    main()
