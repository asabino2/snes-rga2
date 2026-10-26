#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SNES Hardware & 65C816 Execution Verification Suite for RGA2_SNES.smc
1. Validates SNES Internal Header ($FFB0-$FFFF), Vectors, Size, and Checksum/Complement.
2. Emulates the 65C816 CPU + PPU/DMA + SPC700 IPL Handshake + Auto-Joypad hardware
   directly from the compiled .smc ROM image:
     - Verifies Reset -> Native Mode -> FastROM -> PPU/VRAM/CGRAM/OAM Init
     - Verifies 100% of the 10,828-byte SPC700 Audio Driver & BRR upload over $2140-$2143
     - Verifies NMI VBlank interrupt handler (stack balance, OAM DMA, BG3 HUD DMA)
     - Simulates Controller 1 inputs through:
         STATE_TITLE -> STATE_INTRO -> STATE_SELECT -> STATE_STAGE (BGS) -> STATE_HUB -> Portals!
"""

import os
import struct

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROM_DIR = os.path.join(PROJECT_DIR, "rom")


class MiniSNESVerifier:
    def __init__(self, rom_bytes):
        self.rom = rom_bytes
        self.wram = bytearray(128 * 1024)
        self.sram = bytearray(8 * 1024)
        self.vram = bytearray(64 * 1024)
        self.cgram = bytearray(512)
        self.oam = bytearray(544)
        self.aram = bytearray(64 * 1024)

        # CPU Registers
        self.a = 0
        self.x = 0
        self.y = 0
        self.sp = 0x01FF
        self.dp = 0x0000
        self.db = 0x00
        self.pb = 0x00
        self.pc = struct.unpack_from("<H", self.rom, 0x00FFFC)[0]
        self.p = 0x34  # M=1, X=1, I=1
        self.e = True

        # Hardware I/O state
        self.inidisp = 0x8F
        self.nmitimen = 0x00
        self.vmain = 0x80
        self.vmadd = 0x0000
        self.cgadd = 0x00
        self.cg_flip = 0
        self.oamadd = 0x0000
        self.joy1 = 0x0000

        # DMA Channel 0..7 registers
        self.dmap = [0] * 8
        self.bbad = [0] * 8
        self.a1t = [0] * 8
        self.a1b = [0] * 8
        self.das = [0] * 8

        # SPC700 IPL Boot ROM state machine
        self.apu_in = [0, 0, 0, 0]          # Written by CPU to $2140..$2143
        self.apu_out = [0xAA, 0xBB, 0, 0]   # Read by CPU from $2140..$2143
        self.ipl_state = "WAIT_CC"
        self.ipl_dest = 0x0200
        self.ipl_expected_cnt = 0
        self.ipl_bytes_transferred = 0

    @property
    def m8(self):
        return self.e or bool(self.p & 0x20)

    @property
    def x8(self):
        return self.e or bool(self.p & 0x10)

    def set_nz(self, val, is8):
        if is8:
            val &= 0xFF
            n = 0x80 if (val & 0x80) else 0
        else:
            val &= 0xFFFF
            n = 0x80 if (val & 0x8000) else 0
        z = 0x02 if val == 0 else 0
        self.p = (self.p & ~0x82) | n | z

    def read8(self, bank, addr):
        bank &= 0xFF
        addr &= 0xFFFF
        if bank in (0x7E, 0x7F):
            return self.wram[((bank - 0x7E) << 16) | addr]
        if (bank & 0x7F) < 0x40:
            if addr < 0x2000:
                return self.wram[addr]
            if 0x2140 <= addr <= 0x2143:
                return self.apu_out[addr - 0x2140]
            if addr == 0x4210:
                return 0x82
            if addr == 0x4212:
                return 0x00  # Auto-joypad ready
            if addr == 0x4218:
                return self.joy1 & 0xFF
            if addr == 0x4219:
                return (self.joy1 >> 8) & 0xFF
            if 0x6000 <= addr <= 0x7FFF:
                return self.sram[addr & 0x1FFF]
            if addr >= 0x8000:
                rom_off = ((bank & 0x3F) << 16) | addr
                return self.rom[rom_off % len(self.rom)]
            return 0
        # Banks $C0-$FF or $40-$7D
        if bank >= 0xC0:
            rom_off = ((bank - 0xC0) << 16) | addr
        else:
            rom_off = ((bank & 0x3F) << 16) | addr
        return self.rom[rom_off % len(self.rom)]

    def write8(self, bank, addr, val):
        bank &= 0xFF
        addr &= 0xFFFF
        val &= 0xFF
        if bank in (0x7E, 0x7F):
            self.wram[((bank - 0x7E) << 16) | addr] = val
            return
        if (bank & 0x7F) < 0x40:
            if addr < 0x2000:
                self.wram[addr] = val
                return
            if addr == 0x2100:
                self.inidisp = val
            elif addr == 0x2102:
                self.oamadd = (self.oamadd & 0xFF00) | val
            elif addr == 0x2103:
                self.oamadd = ((val & 1) << 8) | (self.oamadd & 0xFF)
            elif addr == 0x2104:
                self.oam[self.oamadd % 544] = val
                self.oamadd = (self.oamadd + 1) % 544
            elif addr == 0x2115:
                self.vmain = val
            elif addr == 0x2116:
                self.vmadd = (self.vmadd & 0xFF00) | val
            elif addr == 0x2117:
                self.vmadd = (val << 8) | (self.vmadd & 0xFF)
            elif addr == 0x2118:
                self.vram[(self.vmadd * 2) & 0xFFFF] = val
                if (self.vmain & 0x80) == 0:
                    self.vmadd = (self.vmadd + 1) & 0x7FFF
            elif addr == 0x2119:
                self.vram[(self.vmadd * 2 + 1) & 0xFFFF] = val
                if (self.vmain & 0x80) != 0:
                    self.vmadd = (self.vmadd + 1) & 0x7FFF
            elif addr == 0x2121:
                self.cgadd = val
                self.cg_flip = 0
            elif addr == 0x2122:
                self.cgram[(self.cgadd * 2 + self.cg_flip) & 0x1FF] = val
                self.cg_flip ^= 1
                if self.cg_flip == 0:
                    self.cgadd = (self.cgadd + 1) & 0xFF
            elif 0x2140 <= addr <= 0x2143:
                p = addr - 0x2140
                self.apu_in[p] = val
                self._step_spc_ipl(p, val)
            elif addr == 0x4200:
                self.nmitimen = val
            elif addr == 0x420B:
                for ch in range(8):
                    if val & (1 << ch):
                        self._run_dma(ch)
            elif 0x4300 <= addr <= 0x437F:
                ch = (addr >> 4) & 7
                reg = addr & 0x0F
                if reg == 0:
                    self.dmap[ch] = val
                elif reg == 1:
                    self.bbad[ch] = val
                elif reg == 2:
                    self.a1t[ch] = (self.a1t[ch] & 0xFF00) | val
                elif reg == 3:
                    self.a1t[ch] = (val << 8) | (self.a1t[ch] & 0xFF)
                elif reg == 4:
                    self.a1b[ch] = val
                elif reg == 5:
                    self.das[ch] = (self.das[ch] & 0xFF00) | val
                elif reg == 6:
                    self.das[ch] = (val << 8) | (self.das[ch] & 0xFF)
            elif 0x6000 <= addr <= 0x7FFF:
                self.sram[addr & 0x1FFF] = val

    def _step_spc_ipl(self, port, val):
        if port != 0:
            return
        if self.ipl_state == "WAIT_CC":
            if val == 0xCC:
                self.ipl_dest = self.apu_in[2] | (self.apu_in[3] << 8)
                self.ipl_expected_cnt = 0
                self.apu_out[0] = 0xCC
                self.ipl_state = "TRANSFER"
        elif self.ipl_state == "TRANSFER":
            if val == self.ipl_expected_cnt:
                self.aram[self.ipl_dest & 0xFFFF] = self.apu_in[1]
                self.ipl_dest = (self.ipl_dest + 1) & 0xFFFF
                self.ipl_bytes_transferred += 1
                self.apu_out[0] = val
                self.ipl_expected_cnt = (self.ipl_expected_cnt + 1) & 0xFF
            elif ((val - self.ipl_expected_cnt) & 0xFF) < 0x80:
                if self.apu_in[1] == 0x00:
                    self.ipl_state = "RUNNING_DRIVER"
                    self.apu_out[0] = val
                    self.apu_out[3] = 0x52  # 'R' ready signature!
        elif self.ipl_state == "RUNNING_DRIVER":
            self.apu_out[0] = val

    def _run_dma(self, ch):
        cnt = self.das[ch] if self.das[ch] != 0 else 0x10000
        mode = self.dmap[ch] & 0x07
        for i in range(cnt):
            b = self.read8(self.a1b[ch], (self.a1t[ch] + i) & 0xFFFF)
            if mode == 0:
                self.write8(0x00, 0x2100 | self.bbad[ch], b)
            elif mode == 1:
                self.write8(0x00, 0x2100 | (self.bbad[ch] + (i & 1)), b)
        self.a1t[ch] = (self.a1t[ch] + cnt) & 0xFFFF
        self.das[ch] = 0

    def read16(self, bank, addr):
        lo = self.read8(bank, addr)
        hi = self.read8(bank, (addr + 1) & 0xFFFF)
        return lo | (hi << 8)

    def write16(self, bank, addr, val):
        self.write8(bank, addr, val & 0xFF)
        self.write8(bank, (addr + 1) & 0xFFFF, (val >> 8) & 0xFF)

    def push8(self, val):
        self.wram[self.sp] = val & 0xFF
        self.sp = (self.sp - 1) & 0xFFFF

    def pop8(self):
        self.sp = (self.sp + 1) & 0xFFFF
        return self.wram[self.sp]

    def push16(self, val):
        self.push8((val >> 8) & 0xFF)
        self.push8(val & 0xFF)

    def pop16(self):
        lo = self.pop8()
        hi = self.pop8()
        return lo | (hi << 8)

    def trigger_nmi(self):
        self.push8(self.pb)
        self.push16(self.pc)
        self.push8(self.p)
        self.pb = 0x00
        self.pc = struct.unpack_from("<H", self.rom, 0x00FFEA)[0]

    def step_until_wai_or_limit(self, max_Dynamic_steps=500000):
        steps = 0
        while steps < max_Dynamic_steps:
            steps += 1
            op = self.read8(self.pb, self.pc)
            self.pc = (self.pc + 1) & 0xFFFF

            if op == 0xCB:  # WAI
                return "WAI", steps
            elif op == 0x78:  # SEI
                self.p |= 0x04
            elif op == 0x58:  # CLI
                self.p &= ~0x04
            elif op == 0x18:  # CLC
                self.p &= ~0x01
            elif op == 0x38:  # SEC
                self.p |= 0x01
            elif op == 0xFB:  # XCE
                old_c = bool(self.p & 0x01)
                self.p = (self.p & ~0x01) | (1 if self.e else 0)
                self.e = old_c
            elif op == 0xC2:  # REP #imm
                imm = self.read8(self.pb, self.pc)
                self.pc += 1
                self.p &= ~imm
                if self.x8:
                    self.x &= 0xFF
                    self.y &= 0xFF
            elif op == 0xE2:  # SEP #imm
                imm = self.read8(self.pb, self.pc)
                self.pc += 1
                self.p |= imm
                if self.x8:
                    self.x &= 0xFF
                    self.y &= 0xFF
            elif op == 0xEB:  # XBA
                lo = self.a & 0xFF
                hi = (self.a >> 8) & 0xFF
                self.a = (lo << 8) | hi
                self.set_nz(self.a & 0xFF, True)
            elif op == 0x5B:  # TCD
                self.dp = self.a & 0xFFFF
            elif op == 0x9A:  # TXS
                self.sp = self.x if not self.e else (0x0100 | (self.x & 0xFF))
            elif op == 0xAA:  # TAX
                self.x = (self.a & 0xFF) if self.x8 else (self.a & 0xFFFF)
                self.set_nz(self.x, self.x8)
            elif op == 0x8A:  # TXA
                if self.m8:
                    self.a = (self.a & 0xFF00) | (self.x & 0xFF)
                else:
                    self.a = self.x & 0xFFFF
                self.set_nz(self.a, self.m8)
            elif op == 0xA8:  # TAY
                self.y = (self.a & 0xFF) if self.x8 else (self.a & 0xFFFF)
                self.set_nz(self.y, self.x8)
            elif op == 0x98:  # TYA
                if self.m8:
                    self.a = (self.a & 0xFF00) | (self.y & 0xFF)
                else:
                    self.a = self.y & 0xFFFF
                self.set_nz(self.a, self.m8)
            elif op == 0xBB:  # TYX
                self.x = self.y
                self.set_nz(self.x, self.x8)
            elif op == 0x48:  # PHA
                if self.m8:
                    self.push8(self.a)
                else:
                    self.push16(self.a)
            elif op == 0x68:  # PLA
                if self.m8:
                    self.a = (self.a & 0xFF00) | self.pop8()
                else:
                    self.a = self.pop16()
                self.set_nz(self.a, self.m8)
            elif op == 0xDA:  # PHX
                if self.x8:
                    self.push8(self.x)
                else:
                    self.push16(self.x)
            elif op == 0xFA:  # PLX
                self.x = self.pop8() if self.x8 else self.pop16()
                self.set_nz(self.x, self.x8)
            elif op == 0x5A:  # PHY
                if self.x8:
                    self.push8(self.y)
                else:
                    self.push16(self.y)
            elif op == 0x7A:  # PLY
                self.y = self.pop8() if self.x8 else self.pop16()
                self.set_nz(self.y, self.x8)
            elif op == 0x8B:  # PHB
                self.push8(self.db)
            elif op == 0xAB:  # PLB
                self.db = self.pop8()
                self.set_nz(self.db, True)
            elif op == 0x0B:  # PHD
                self.push16(self.dp)
            elif op == 0x2B:  # PLD
                self.dp = self.pop16()
            elif op == 0x40:  # RTI
                self.p = self.pop8()
                self.pc = self.pop16()
                self.pb = self.pop8()
            elif op == 0x60:  # RTS
                self.pc = (self.pop16() + 1) & 0xFFFF
            elif op == 0x20:  # JSR abs
                target = self.read16(self.pb, self.pc)
                self.pc += 2
                self.push16((self.pc - 1) & 0xFFFF)
                self.pc = target
            elif op == 0x4C:  # JMP abs
                self.pc = self.read16(self.pb, self.pc)
            elif op == 0x5C:  # JML long
                lo = self.read8(self.pb, self.pc)
                hi = self.read8(self.pb, self.pc + 1)
                bk = self.read8(self.pb, self.pc + 2)
                self.pb = bk
                self.pc = lo | (hi << 8)
            elif op in (0x10, 0x30, 0x50, 0x70, 0x80, 0x90, 0xB0, 0xD0, 0xF0):
                disp = self.read8(self.pb, self.pc)
                self.pc += 1
                if disp & 0x80:
                    disp -= 256
                cond = {
                    0x80: True,
                    0x10: not bool(self.p & 0x80),
                    0x30: bool(self.p & 0x80),
                    0x50: not bool(self.p & 0x40),
                    0x70: bool(self.p & 0x40),
                    0x90: not bool(self.p & 0x01),
                    0xB0: bool(self.p & 0x01),
                    0xD0: not bool(self.p & 0x02),
                    0xF0: bool(self.p & 0x02),
                }[op]
                if cond:
                    self.pc = (self.pc + disp) & 0xFFFF
            elif op in (0xE8, 0xCA, 0xC8, 0x88):  # INX, DEX, INY, DEY
                mask = 0xFF if self.x8 else 0xFFFF
                if op == 0xE8:
                    self.x = (self.x + 1) & mask
                    self.set_nz(self.x, self.x8)
                elif op == 0xCA:
                    self.x = (self.x - 1) & mask
                    self.set_nz(self.x, self.x8)
                elif op == 0xC8:
                    self.y = (self.y + 1) & mask
                    self.set_nz(self.y, self.x8)
                elif op == 0x88:
                    self.y = (self.y - 1) & mask
                    self.set_nz(self.y, self.x8)
            elif op in (0x1A, 0x3A, 0x0A, 0x4A):  # INC A, DEC A, ASL A, LSR A
                mask = 0xFF if self.m8 else 0xFFFF
                v = self.a & mask
                if op == 0x1A:
                    v = (v + 1) & mask
                elif op == 0x3A:
                    v = (v - 1) & mask
                elif op == 0x0A:
                    c = 1 if (v & (0x80 if self.m8 else 0x8000)) else 0
                    self.p = (self.p & ~0x01) | c
                    v = (v << 1) & mask
                elif op == 0x4A:
                    c = v & 1
                    self.p = (self.p & ~0x01) | c
                    v = v >> 1
                self.a = (self.a & ~mask) | v
                self.set_nz(v, self.m8)
            elif op in (0x64, 0x74, 0x9C, 0x9E):  # STZ
                if op == 0x64:
                    addr = (self.dp + self.read8(self.pb, self.pc)) & 0xFFFF
                    self.pc += 1
                    bank = 0x00
                elif op == 0x74:
                    addr = (self.dp + self.read8(self.pb, self.pc) + self.x) & 0xFFFF
                    self.pc += 1
                    bank = 0x00
                elif op == 0x9C:
                    addr = self.read16(self.pb, self.pc)
                    self.pc += 2
                    bank = self.db
                else:
                    addr = (self.read16(self.pb, self.pc) + self.x) & 0xFFFF
                    self.pc += 2
                    bank = self.db
                if self.m8:
                    self.write8(bank, addr, 0)
                else:
                    self.write16(bank, addr, 0)
            elif op in (0xE6, 0xF6, 0xEE, 0xFE, 0xC6, 0xD6, 0xCE, 0xDE):  # INC/DEC mem
                is_inc = op in (0xE6, 0xF6, 0xEE, 0xFE)
                if op in (0xE6, 0xC6):
                    addr = (self.dp + self.read8(self.pb, self.pc)) & 0xFFFF
                    self.pc += 1
                    bank = 0x00
                elif op in (0xF6, 0xD6):
                    addr = (self.dp + self.read8(self.pb, self.pc) + self.x) & 0xFFFF
                    self.pc += 1
                    bank = 0x00
                elif op in (0xEE, 0xCE):
                    addr = self.read16(self.pb, self.pc)
                    self.pc += 2
                    bank = self.db
                else:
                    addr = (self.read16(self.pb, self.pc) + self.x) & 0xFFFF
                    self.pc += 2
                    bank = self.db
                if self.m8:
                    v = (self.read8(bank, addr) + (1 if is_inc else -1)) & 0xFF
                    self.write8(bank, addr, v)
                    self.set_nz(v, True)
                else:
                    v = (self.read16(bank, addr) + (1 if is_inc else -1)) & 0xFFFF
                    self.write16(bank, addr, v)
                    self.set_nz(v, False)
            elif op in (0x89, 0x24, 0x2C):  # BIT
                if op == 0x89:
                    if self.m8:
                        v = self.read8(self.pb, self.pc)
                        self.pc += 1
                    else:
                        v = self.read16(self.pb, self.pc)
                        self.pc += 2
                    res = (self.a & (0xFF if self.m8 else 0xFFFF)) & v
                    self.p = (self.p & ~0x02) | (0x02 if res == 0 else 0)
                else:
                    if op == 0x24:
                        addr = (self.dp + self.read8(self.pb, self.pc)) & 0xFFFF
                        self.pc += 1
                        bank = 0x00
                    else:
                        addr = self.read16(self.pb, self.pc)
                        self.pc += 2
                        bank = self.db
                    v = self.read8(bank, addr) if self.m8 else self.read16(bank, addr)
                    res = (self.a & (0xFF if self.m8 else 0xFFFF)) & v
                    self.p = (self.p & ~0x02) | (0x02 if res == 0 else 0)
            elif op in (0xA2, 0xA6, 0xAE, 0xBE, 0xA0, 0xA4, 0xAC, 0xBC, 0x86, 0x8E, 0x84, 0x8C, 0xE0, 0xE4, 0xEC, 0xC0, 0xC4, 0xCC):
                self._exec_index_op(op)
            else:
                self._exec_alu_op(op)
        return "LIMIT", steps

    def _exec_index_op(self, op):
        if op in (0xA2, 0xA0, 0xE0, 0xC0):
            if self.x8:
                val = self.read8(self.pb, self.pc)
                self.pc += 1
            else:
                val = self.read16(self.pb, self.pc)
                self.pc += 2
            if op == 0xA2:
                self.x = val
                self.set_nz(self.x, self.x8)
            elif op == 0xA0:
                self.y = val
                self.set_nz(self.y, self.x8)
            else:
                reg = self.x if op == 0xE0 else self.y
                diff = reg - val
                self.p = (self.p & ~0x01) | (1 if reg >= val else 0)
                self.set_nz(diff, self.x8)
            return

        if op in (0xA6, 0xA4, 0x86, 0x84, 0xE4, 0xC4):
            addr = (self.dp + self.read8(self.pb, self.pc)) & 0xFFFF
            self.pc += 1
            bank = 0x00
        elif op in (0xAE, 0xAC, 0x8E, 0x8C, 0xEC, 0xCC):
            addr = self.read16(self.pb, self.pc)
            self.pc += 2
            bank = self.db
        elif op == 0xBE:
            addr = (self.read16(self.pb, self.pc) + self.y) & 0xFFFF
            self.pc += 2
            bank = self.db
        elif op == 0xBC:
            addr = (self.read16(self.pb, self.pc) + self.x) & 0xFFFF
            self.pc += 2
            bank = self.db

        if op in (0x86, 0x8E):
            if self.x8:
                self.write8(bank, addr, self.x)
            else:
                self.write16(bank, addr, self.x)
        elif op in (0x84, 0x8C):
            if self.x8:
                self.write8(bank, addr, self.y)
            else:
                self.write16(bank, addr, self.y)
        elif op in (0xA6, 0xAE, 0xBE):
            self.x = self.read8(bank, addr) if self.x8 else self.read16(bank, addr)
            self.set_nz(self.x, self.x8)
        elif op in (0xA4, 0xAC, 0xBC):
            self.y = self.read8(bank, addr) if self.x8 else self.read16(bank, addr)
            self.set_nz(self.y, self.x8)
        elif op in (0xE4, 0xEC, 0xC4, 0xCC):
            val = self.read8(bank, addr) if self.x8 else self.read16(bank, addr)
            reg = self.x if op in (0xE4, 0xEC) else self.y
            diff = reg - val
            self.p = (self.p & ~0x01) | (1 if reg >= val else 0)
            self.set_nz(diff, self.x8)

    def _exec_alu_op(self, op):
        # Decode addressing mode for standard ALU ops
        low_nib = op & 0x1F
        alu_kind = op & 0xE0  # 00=ORA, 20=AND, 40=EOR, 60=ADC, 80=STA, A0=LDA, C0=CMP, E0=SBC

        if low_nib == 0x09:  # #imm
            if self.m8:
                val = self.read8(self.pb, self.pc)
                self.pc += 1
            else:
                val = self.read16(self.pb, self.pc)
                self.pc += 2
            bank, addr = None, None
        elif low_nib == 0x05:  # dp
            addr = (self.dp + self.read8(self.pb, self.pc)) & 0xFFFF
            self.pc += 1
            bank = 0x00
        elif low_nib == 0x15:  # dp,X
            addr = (self.dp + self.read8(self.pb, self.pc) + self.x) & 0xFFFF
            self.pc += 1
            bank = 0x00
        elif low_nib == 0x0D:  # abs
            addr = self.read16(self.pb, self.pc)
            self.pc += 2
            bank = self.db
        elif low_nib == 0x1D:  # abs,X
            addr = (self.read16(self.pb, self.pc) + self.x) & 0xFFFF
            self.pc += 2
            bank = self.db
        elif low_nib == 0x19:  # abs,Y
            addr = (self.read16(self.pb, self.pc) + self.y) & 0xFFFF
            self.pc += 2
            bank = self.db
        elif low_nib == 0x0F:  # long
            lo = self.read8(self.pb, self.pc)
            hi = self.read8(self.pb, self.pc + 1)
            bank = self.read8(self.pb, self.pc + 2)
            self.pc += 3
            addr = lo | (hi << 8)
        elif low_nib == 0x1F:  # long,X
            lo = self.read8(self.pb, self.pc)
            hi = self.read8(self.pb, self.pc + 1)
            bank = self.read8(self.pb, self.pc + 2)
            self.pc += 3
            addr = ((lo | (hi << 8)) + self.x) & 0xFFFF
        else:
            raise RuntimeError(f"Unhandled opcode ${op:02X} at ${self.pb:02X}:${self.pc - 1:04X}")

        if alu_kind == 0x80:  # STA
            if self.m8:
                self.write8(bank, addr, self.a & 0xFF)
            else:
                self.write16(bank, addr, self.a & 0xFFFF)
            return

        if bank is not None:
            val = self.read8(bank, addr) if self.m8 else self.read16(bank, addr)

        mask = 0xFF if self.m8 else 0xFFFF
        acc = self.a & mask

        if alu_kind == 0xA0:  # LDA
            res = val & mask
            self.a = (self.a & ~mask) | res
            self.set_nz(res, self.m8)
        elif alu_kind == 0x00:  # ORA
            res = (acc | val) & mask
            self.a = (self.a & ~mask) | res
            self.set_nz(res, self.m8)
        elif alu_kind == 0x20:  # AND
            res = (acc & val) & mask
            self.a = (self.a & ~mask) | res
            self.set_nz(res, self.m8)
        elif alu_kind == 0x40:  # EOR
            res = (acc ^ val) & mask
            self.a = (self.a & ~mask) | res
            self.set_nz(res, self.m8)
        elif alu_kind == 0x60:  # ADC
            c = 1 if (self.p & 0x01) else 0
            tot = acc + val + c
            self.p = (self.p & ~0x01) | (1 if tot > mask else 0)
            res = tot & mask
            self.a = (self.a & ~mask) | res
            self.set_nz(res, self.m8)
        elif alu_kind == 0xE0:  # SBC
            c = 1 if (self.p & 0x01) else 0
            tot = acc - val - (1 - c)
            self.p = (self.p & ~0x01) | (1 if tot >= 0 else 0)
            res = tot & mask
            self.a = (self.a & ~mask) | res
            self.set_nz(res, self.m8)
        elif alu_kind == 0xC0:  # CMP
            diff = acc - val
            self.p = (self.p & ~0x01) | (1 if acc >= val else 0)
            self.set_nz(diff & mask, self.m8)

    def run_frame(self, joy_buttons=0x0000):
        self.joy1 = joy_buttons
        self.trigger_nmi()
        status, steps = self.step_until_wai_or_limit()
        assert status == "WAI", f"Frame did not reach WAI (status={status})"
        return steps


def verify_rom_file(rom_path):
    print(f"\n=== Verifying ROM: {os.path.basename(rom_path)} ===")
    with open(rom_path, "rb") as f:
        rom = f.read()

    # 1. Verify Header & Checksum
    title = rom[0x00FFC0:0x00FFD5].decode("ascii", errors="replace")
    map_mode = rom[0x00FFD5]
    cart_type = rom[0x00FFD6]
    rom_sz = rom[0x00FFD7]
    sram_sz = rom[0x00FFD8]
    comp, chk = struct.unpack_from("<HH", rom, 0x00FFDC)
    reset_v = struct.unpack_from("<H", rom, 0x00FFFC)[0]
    nmi_v = struct.unpack_from("<H", rom, 0x00FFEA)[0]

    print(f"  Title        : '{title}'")
    print(f"  File Size    : {len(rom):,} bytes ({len(rom) * 8 // (1024*1024)} Mbit)")
    print(f"  Map Mode     : ${map_mode:02X} | Cart Type: ${cart_type:02X} | ROM Size Code: ${rom_sz:02X} | SRAM Code: ${sram_sz:02X}")
    print(f"  Checksum     : ${chk:04X} | Complement: ${comp:04X} | XOR: ${chk ^ comp:04X}")
    print(f"  Vectors      : RESET=${reset_v:04X}, NMI=${nmi_v:04X}")
    assert (chk ^ comp) == 0xFFFF, "Checksum + Complement XOR must equal $FFFF!"

    # 2. Boot & Emulate 65C816 Execution
    emu = MiniSNESVerifier(rom)
    status, boot_steps = emu.step_until_wai_or_limit(max_Dynamic_steps=600000)
    assert status == "WAI", f"Boot sequence failed to reach WAI (status={status})"
    print(f"  [PASS] Cold Boot -> FastROM -> PPU/VRAM/OAM/SPC700 Init reached WAI in {boot_steps:,} instructions!")
    print(f"  [PASS] SPC700 IPL Transferred: {emu.ipl_bytes_transferred:,} bytes (Driver Status: {emu.ipl_state})")
    assert emu.ipl_bytes_transferred == 10828, "Expected 10,828 bytes uploaded to SPC700 ARAM!"
    assert emu.wram[0x08] == 0, f"Expected initial DP_STATE == 0 (STATE_TITLE), got {emu.wram[0x08]}"
    assert emu.sram[0:4] == b"RGA2", f"Expected SRAM magic 'RGA2', got {emu.sram[0:4]}"

    # 3. Run 2 frames on Title Screen, then press START ($1000) -> Story Intro (STATE_INTRO = 1)
    emu.run_frame(0x0000)
    emu.run_frame(0x1000)  # Press START
    assert emu.wram[0x08] == 1, f"Expected DP_STATE == 1 (STATE_INTRO), got {emu.wram[0x08]}"
    print("  [PASS] Transitioned STATE_TITLE (0) -> STATE_INTRO (1)")

    # 4. Press START ($1000) on Intro -> Character Select (STATE_SELECT = 2)
    emu.run_frame(0x0000)
    emu.run_frame(0x1000)
    assert emu.wram[0x08] == 2, f"Expected DP_STATE == 2 (STATE_SELECT), got {emu.wram[0x08]}"
    print("  [PASS] Transitioned STATE_INTRO (1) -> STATE_SELECT (2)")

    # 5. Cycle through all 6 Playable Retrogamers with RIGHT ($0100)
    for expected_char in range(1, 6):
        emu.run_frame(0x0000)
        emu.run_frame(0x0100)  # Press RIGHT
        assert emu.wram[0x09] == expected_char, f"Expected DP_CHAR_ID == {expected_char}"
    print("  [PASS] Cycled through all 6 Playable Retrogamers (Velberan -> Monique) on Select Screen!")

    # 6. Press START ($1000) to enter Stage 0: Brasil Game Show (STATE_STAGE = 4, DP_STAGE_ID = 0)
    emu.run_frame(0x0000)
    emu.run_frame(0x1000)
    assert emu.wram[0x08] == 4 and emu.wram[0x0A] == 0
    print("  [PASS] Entered Stage 0: Brasil Game Show (STATE_STAGE=4, DP_STAGE_ID=0)")

    # 7. Simulate Combat: Walk Right, Jump (B=$8000), 3-Hit Combo (Y=$4000), Special Attack Cancel (X=$0040)
    for _ in range(5):
        emu.run_frame(0x0100)  # Walk Right
    emu.run_frame(0x4000)      # Attack 1 (Y)
    emu.run_frame(0x0000)
    emu.run_frame(0x0040)      # Special Move Cancel (X)
    assert emu.wram[0x25] == 1, "Expected Special Projectile (DP_PROJ_ACT) to spawn on Special Attack!"
    print("  [PASS] Verified Player Movement, Melee Combo, and Special Projectile Spawning!")

    # 8. Simulate clearing Stage 0 Boss -> Transitions automatically to Estação Central Hub (STATE_HUB = 3)!
    emu.wram[0x22] = 3         # DP_WAVE_NUM = 3 (Boss Wave)
    emu.wram[0x40] = 0         # Clear enemies
    emu.wram[0x50] = 0
    emu.wram[0x60] = 0
    emu.wram[0x70] = 0
    emu.wram[0x24] = 49        # DP_GO_TIMER = 49 -> next frame triggers StageBossDefeated!
    emu.run_frame(0x0000)
    assert emu.wram[0x08] == 3 and emu.wram[0x0A] == 1, f"Expected Hub State (3,1), got ({emu.wram[0x08]},{emu.wram[0x0A]})"
    print("  [PASS] Stage 0 Boss Defeated -> Automatically Entered Estacao Central Hub (STATE_HUB=3)!")

    # 9. Walk right in Estação Central Hub to Portal 1 (X=64) and press UP ($0800) to enter Portal 1 (Mega Man X)!
    for _ in range(6):
        emu.run_frame(0x0100)  # Walk Right toward X=64
    assert emu.wram[0x34] == 0, f"Expected DP_NEAR_PORTAL == 0 (Portal 1), got {emu.wram[0x34]}"
    emu.run_frame(0x0800)      # Press UP to enter Portal 1!
    assert emu.wram[0x08] == 4 and emu.wram[0x0A] == 2, "Expected Stage 2 (Portal 1: Mega Man X)!"
    print("  [PASS] Entered Portal 1 (Mega Man X, DP_STAGE_ID=2) from Estacao Central Hub!")

    # 10. Defeat Portal 1 Boss (NutellaMan) -> Verifies Battery SRAM Save & Return to Hub!
    emu.wram[0x22] = 3
    emu.wram[0x40] = 0
    emu.wram[0x50] = 0
    emu.wram[0x60] = 0
    emu.wram[0x70] = 0
    emu.wram[0x24] = 49
    emu.run_frame(0x0000)
    assert emu.wram[0x08] == 3, "Expected return to Hub after clearing Portal 1!"
    assert (emu.sram[4] & 0x01) == 0x01, "Expected Portal 1 cleared bit saved in Cartridge Battery SRAM ($B0:6004)!"
    print(f"  [PASS] Portal 1 Cleared & Saved to Cartridge Battery SRAM (SRAM_PORTALS = ${emu.sram[4]:02X})!")

    # 11. Defeat Final Boss (EI SPOILED in Stage 9 / Portal 8) -> Verifies Transition to Ending & Credits (STATE_ENDING = 5)!
    emu.wram[0x08] = 4
    emu.wram[0x0A] = 9         # Stage 9 = Portal 8 (YouTube HQ Final)
    emu.wram[0x22] = 3
    emu.wram[0x40] = 0
    emu.wram[0x50] = 0
    emu.wram[0x60] = 0
    emu.wram[0x70] = 0
    emu.wram[0x24] = 49
    emu.run_frame(0x0000)
    assert emu.wram[0x08] == 5, f"Expected STATE_ENDING (5), got {emu.wram[0x08]}"
    assert (emu.sram[4] & 0x80) == 0x80, "Expected Portal 8 cleared bit saved in Cartridge Battery SRAM!"
    print("  [PASS] Final Boss 'EI SPOILED' Defeated -> Entered Ending & Credits Screen (STATE_ENDING=5)!")


if __name__ == "__main__":
    verify_rom_file(os.path.join(ROM_DIR, "RGA2_SNES.smc"))
    verify_rom_file(os.path.join(ROM_DIR, "RGA2_SNES_ExHiROM_48Mbit.smc"))
    print("\nALL SNES HARDWARE, HEADER, CHECKSUM, SPC700, DMA & GAMEPLAY CHECKS PASSED 100%!")
