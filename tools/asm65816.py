#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clean Two-Pass 65C816 Cross-Assembler for Super Nintendo (SNES) Development
Supports:
  - Directives: .org, .a8, .a16, .i8, .i16, .db/.byte, .dw/.word, .dl/.long, .asc, .equ/=, .include
  - Automatic M/X flag tracking on SEP #$xx / REP #$xx AND explicit .a8/.a16/.i8/.i16 hints
  - All standard 65C816 addressing modes:
      Implied, Immediate (#), Direct Page ($xx), Direct Page Indexed ($xx,X / $xx,Y),
      Direct Page Indirect Long ([$xx], [$xx],Y),
      Absolute ($xxxx), Absolute Indexed ($xxxx,X / $xxxx,Y),
      Absolute Long ($xxxxxx / $xxxxxx,X),
      Relative 8-bit (BRA, BEQ, BNE, BCC, BCS, BPL, BMI, BVC, BVS) and 16-bit (BRL)
"""

import os
import re
import struct

IMPLIED_OPCODES = {
    "CLC": 0x18, "SEC": 0x38, "CLI": 0x58, "SEI": 0x78, "CLV": 0xB8, "CLD": 0xD8, "SED": 0xF8,
    "XCE": 0xFB, "XBA": 0xEB, "NOP": 0xEA, "WAI": 0xCB, "STP": 0xDB,
    "TAX": 0xAA, "TXA": 0x8A, "TAY": 0xA8, "TYA": 0x98, "TSX": 0xBA, "TXS": 0x9A,
    "TXY": 0x9B, "TYX": 0xBB, "TCD": 0x5B, "TDC": 0x7B, "TCS": 0x1B, "TSC": 0x3B,
    "PHA": 0x48, "PLA": 0x68, "PHX": 0xDA, "PLX": 0xFA, "PHY": 0x5A, "PLY": 0x7A,
    "PHB": 0x8B, "PLB": 0xAB, "PHD": 0x0B, "PLD": 0x2B, "PHK": 0x4B, "PHP": 0x08, "PLP": 0x28,
    "INX": 0xE8, "DEX": 0xCA, "INY": 0xC8, "DEY": 0x88,
    "INC": 0x1A, "DEC": 0x3A, "ASL": 0x0A, "LSR": 0x4A, "ROL": 0x2A, "ROR": 0x6A,
    "RTS": 0x60, "RTL": 0x6B, "RTI": 0x40,
}

BRANCH8_OPCODES = {
    "BPL": 0x10, "BMI": 0x30, "BVC": 0x50, "BVS": 0x70,
    "BCC": 0x90, "BCS": 0xB0, "BNE": 0xD0, "BEQ": 0xF0, "BRA": 0x80,
}

# Standard ALU instructions: (imm, dp, dp_x, abs, abs_x, abs_y, long, long_x, dp_ind_long_y)
ALU_TABLE = {
    "ORA": (0x09, 0x05, 0x15, 0x0D, 0x1D, 0x19, 0x0F, 0x1F, 0x17),
    "AND": (0x29, 0x25, 0x35, 0x2D, 0x3D, 0x39, 0x2F, 0x3F, 0x37),
    "EOR": (0x49, 0x45, 0x55, 0x4D, 0x5D, 0x59, 0x4F, 0x5F, 0x57),
    "ADC": (0x69, 0x65, 0x75, 0x6D, 0x7D, 0x79, 0x6F, 0x7F, 0x77),
    "STA": (None, 0x85, 0x95, 0x8D, 0x9D, 0x99, 0x8F, 0x9F, 0x97),
    "LDA": (0xA9, 0xA5, 0xB5, 0xAD, 0xBD, 0xB9, 0xAF, 0xBF, 0xB7),
    "CMP": (0xC9, 0xC5, 0xD5, 0xCD, 0xDD, 0xD9, 0xCF, 0xDF, 0xD7),
    "SBC": (0xE9, 0xE5, 0xF5, 0xED, 0xFD, 0xF9, 0xEF, 0xFF, 0xF7),
}


class Assembler65816:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.symbols = {}
        self.lines = []

    def load_source(self, filepath):
        full = os.path.join(self.base_dir, filepath)
        with open(full, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
        for lno, raw in enumerate(raw_lines, 1):
            # Strip comments (;...) unless inside quotes
            in_q = False
            clean = []
            for ch in raw:
                if ch == '"':
                    in_q = not in_q
                if ch == ';' and not in_q:
                    break
                clean.append(ch)
            line = "".join(clean).strip()
            if not line:
                continue
            if line.lower().startswith(".include"):
                inc_file = line.split(None, 1)[1].strip('"').strip("'")
                self.load_source(inc_file)
            else:
                self.lines.append((filepath, lno, line))

    def eval_expr(self, expr, pc, allow_unresolved=False):
        expr = expr.strip().lstrip("!@")
        # Replace '$' hex prefix with '0x' and '%' binary prefix with '0b'
        def repl_hex(m):
            return "0x" + m.group(1)

        def repl_bin(m):
            return "0b" + m.group(1)

        expr_py = re.sub(r"\$([0-9A-Fa-f]+)", repl_hex, expr)
        expr_py = re.sub(r"%([01]+)", repl_bin, expr_py)

        # Replace identifier tokens
        def repl_ident(m):
            ident = m.group(0)
            if ident.startswith(("0x", "0b")) or ident.isdigit():
                return ident
            if ident in self.symbols:
                return str(self.symbols[ident])
            if allow_unresolved:
                return "0x8000"
            raise ValueError(f"Undefined symbol '{ident}' in expression '{expr}'")

        expr_py = re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\b", repl_ident, expr_py)
        try:
            return int(eval(expr_py, {"__builtins__": None}, {}))
        except Exception as e:
            if allow_unresolved:
                return 0x8000
            raise ValueError(f"Cannot evaluate '{expr}' -> '{expr_py}': {e}")

    def assemble(self):
        # Two-pass assembly
        for pass_num in (1, 2):
            pc = 0x8000
            m8 = True   # True = 8-bit Accumulator, False = 16-bit Accumulator
            x8 = True   # True = 8-bit Index, False = 16-bit Index
            out = bytearray()
            org_base = 0x8000

            for filepath, lno, line in self.lines:
                try:
                    # Check for symbol = expr
                    if "=" in line and not line.startswith(".") and not ('"' in line):
                        lhs, rhs = line.split("=", 1)
                        sym = lhs.strip()
                        val = self.eval_expr(rhs, pc, allow_unresolved=(pass_num == 1))
                        self.symbols[sym] = val
                        continue

                    # Check for label:
                    while ":" in line:
                        before, after = line.split(":", 1)
                        if '"' in before:
                            break
                        lbl = before.strip()
                        if lbl:
                            self.symbols[lbl] = pc
                        line = after.strip()

                    if not line:
                        continue

                    parts = line.split(None, 1)
                    mnem = parts[0].upper()
                    arg = parts[1].strip() if len(parts) > 1 else ""

                    # Directives
                    if mnem == ".ORG":
                        new_pc = self.eval_expr(arg, pc, allow_unresolved=False)
                        if len(out) == 0:
                            org_base = new_pc
                            pc = new_pc
                        else:
                            if new_pc < pc:
                                raise ValueError(f".org ${new_pc:04X} backwards from ${pc:04X}")
                            out.extend(b"\x00" * (new_pc - pc))
                            pc = new_pc
                        continue
                    elif mnem == ".A8":
                        m8 = True
                        continue
                    elif mnem == ".A16":
                        m8 = False
                        continue
                    elif mnem == ".I8":
                        x8 = True
                        continue
                    elif mnem == ".I16":
                        x8 = False
                        continue
                    elif mnem in (".DB", ".BYTE"):
                        items = [x.strip() for x in arg.split(",") if x.strip()]
                        for it in items:
                            if it.startswith('"') and it.endswith('"'):
                                for ch in it[1:-1]:
                                    out.append(ord(ch) & 0xFF)
                                    pc += 1
                            else:
                                v = self.eval_expr(it, pc, allow_unresolved=(pass_num == 1))
                                out.append(v & 0xFF)
                                pc += 1
                        continue
                    elif mnem in (".DW", ".WORD"):
                        items = [x.strip() for x in arg.split(",") if x.strip()]
                        for it in items:
                            v = self.eval_expr(it, pc, allow_unresolved=(pass_num == 1))
                            out.extend(struct.pack("<H", v & 0xFFFF))
                            pc += 2
                        continue
                    elif mnem in (".DL", ".LONG"):
                        items = [x.strip() for x in arg.split(",") if x.strip()]
                        for it in items:
                            v = self.eval_expr(it, pc, allow_unresolved=(pass_num == 1))
                            out.extend([v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF])
                            pc += 3
                        continue
                    elif mnem == ".ASC":
                        # .asc "STRING", 0
                        m_str = re.match(r'^"([^"]*)"(?:\s*,\s*(.+))?$', arg)
                        if not m_str:
                            raise ValueError(f"Bad .asc syntax: {arg}")
                        s_val = m_str.group(1)
                        for ch in s_val:
                            out.append(ord(ch) & 0xFF)
                            pc += 1
                        if m_str.group(2):
                            v = self.eval_expr(m_str.group(2), pc, allow_unresolved=(pass_num == 1))
                            out.append(v & 0xFF)
                            pc += 1
                        continue

                    # Instructions
                    if not arg and mnem in IMPLIED_OPCODES:
                        # CRITICAL 65C816 SAFETY:
                        # When A is 8-bit (m8=True) and X/Y are 16-bit (x8=False),
                        # hardware TAX/TAY copies all 16 bits of C (including dirty high byte B) into X/Y!
                        # Automatically zero-extend A into C (REP #$20; AND #$00FF; SEP #$20) before TAX/TAY.
                        if mnem in ("TAX", "TAY") and m8 and (not x8):
                            out.extend([0xC2, 0x20, 0x29, 0xFF, 0x00, 0xE2, 0x20])
                            pc += 7
                        out.append(IMPLIED_OPCODES[mnem])
                        pc += 1
                        continue

                    if mnem in ("SEP", "REP"):
                        if not arg.startswith("#"):
                            raise ValueError(f"{mnem} requires #immediate")
                        v = self.eval_expr(arg[1:], pc, allow_unresolved=False) & 0xFF
                        out.extend([0xE2 if mnem == "SEP" else 0xC2, v])
                        pc += 2
                        if mnem == "SEP":
                            if v & 0x20:
                                m8 = True
                            if v & 0x10:
                                x8 = True
                        else:
                            if v & 0x20:
                                m8 = False
                            if v & 0x10:
                                x8 = False
                        continue

                    if mnem in BRANCH8_OPCODES:
                        target = self.eval_expr(arg, pc, allow_unresolved=(pass_num == 1))
                        disp = target - (pc + 2)
                        if pass_num == 2 and not (-128 <= disp <= 127):
                            raise ValueError(f"Branch {mnem} out of range ({disp} bytes) to {arg}")
                        out.extend([BRANCH8_OPCODES[mnem], disp & 0xFF])
                        pc += 2
                        continue

                    if mnem == "BRL":
                        target = self.eval_expr(arg, pc, allow_unresolved=(pass_num == 1))
                        disp = target - (pc + 3)
                        out.extend([0x82, disp & 0xFF, (disp >> 8) & 0xFF])
                        pc += 3
                        continue

                    if mnem in ("JMP", "JSR"):
                        v = self.eval_expr(arg, pc, allow_unresolved=(pass_num == 1))
                        out.extend([0x4C if mnem == "JMP" else 0x20, v & 0xFF, (v >> 8) & 0xFF])
                        pc += 3
                        continue

                    if mnem in ("JML", "JSL"):
                        v = self.eval_expr(arg, pc, allow_unresolved=(pass_num == 1))
                        out.extend([0x5C if mnem == "JML" else 0x22, v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF])
                        pc += 4
                        continue

                    # STZ
                    if mnem == "STZ":
                        if arg.upper().endswith(",X"):
                            base_s = arg[:-2].strip()
                            v = self.eval_expr(base_s, pc, allow_unresolved=(pass_num == 1))
                            if v <= 0xFF and not base_s.startswith("!"):
                                out.extend([0x74, v & 0xFF])
                                pc += 2
                            else:
                                out.extend([0x9E, v & 0xFF, (v >> 8) & 0xFF])
                                pc += 3
                        else:
                            v = self.eval_expr(arg, pc, allow_unresolved=(pass_num == 1))
                            if v <= 0xFF and not arg.startswith("!"):
                                out.extend([0x64, v & 0xFF])
                                pc += 2
                            else:
                                out.extend([0x9C, v & 0xFF, (v >> 8) & 0xFF])
                                pc += 3
                        continue

                    # INC / DEC / ASL / LSR / ROL / ROR with memory operand
                    if mnem in ("INC", "DEC", "ASL", "LSR", "ROL", "ROR"):
                        rmw_map = {
                            "ASL": (0x06, 0x16, 0x0E, 0x1E),
                            "ROL": (0x26, 0x36, 0x2E, 0x3E),
                            "LSR": (0x46, 0x56, 0x4E, 0x5E),
                            "ROR": (0x66, 0x76, 0x6E, 0x7E),
                            "DEC": (0xC6, 0xD6, 0xCE, 0xDE),
                            "INC": (0xE6, 0xF6, 0xEE, 0xFE),
                        }
                        dp_op, dpx_op, abs_op, absx_op = rmw_map[mnem]
                        if arg.upper().endswith(",X"):
                            base_s = arg[:-2].strip()
                            v = self.eval_expr(base_s, pc, allow_unresolved=(pass_num == 1))
                            if v <= 0xFF and not base_s.startswith("!"):
                                out.extend([dpx_op, v & 0xFF])
                                pc += 2
                            else:
                                out.extend([absx_op, v & 0xFF, (v >> 8) & 0xFF])
                                pc += 3
                        else:
                            v = self.eval_expr(arg, pc, allow_unresolved=(pass_num == 1))
                            if v <= 0xFF and not arg.startswith("!"):
                                out.extend([dp_op, v & 0xFF])
                                pc += 2
                            else:
                                out.extend([abs_op, v & 0xFF, (v >> 8) & 0xFF])
                                pc += 3
                        continue

                    # BIT
                    if mnem == "BIT":
                        if arg.startswith("#"):
                            v = self.eval_expr(arg[1:], pc, allow_unresolved=(pass_num == 1))
                            if m8:
                                out.extend([0x89, v & 0xFF])
                                pc += 2
                            else:
                                out.extend([0x89, v & 0xFF, (v >> 8) & 0xFF])
                                pc += 3
                        else:
                            v = self.eval_expr(arg, pc, allow_unresolved=(pass_num == 1))
                            if v <= 0xFF and not arg.startswith("!"):
                                out.extend([0x24, v & 0xFF])
                                pc += 2
                            else:
                                out.extend([0x2C, v & 0xFF, (v >> 8) & 0xFF])
                                pc += 3
                        continue

                    # LDX / LDY / STX / STY / CPX / CPY
                    if mnem in ("LDX", "LDY", "STX", "STY", "CPX", "CPY"):
                        idx_ops = {
                            "LDX": (0xA2, 0xA6, 0xB6, 0xAE, 0xBE, ",Y"),
                            "LDY": (0xA0, 0xA4, 0xB4, 0xAC, 0xBC, ",X"),
                            "STX": (None, 0x86, 0x96, 0x8E, None, ",Y"),
                            "STY": (None, 0x84, 0x94, 0x8C, None, ",X"),
                            "CPX": (0xE0, 0xE4, None, 0xEC, None, None),
                            "CPY": (0xC0, 0xC4, None, 0xCC, None, None),
                        }
                        imm_op, dp_op, dpi_op, abs_op, absi_op, idx_sfx = idx_ops[mnem]
                        if arg.startswith("#"):
                            v = self.eval_expr(arg[1:], pc, allow_unresolved=(pass_num == 1))
                            if x8:
                                out.extend([imm_op, v & 0xFF])
                                pc += 2
                            else:
                                out.extend([imm_op, v & 0xFF, (v >> 8) & 0xFF])
                                pc += 3
                        elif idx_sfx and arg.upper().endswith(idx_sfx):
                            base_s = arg[:-2].strip()
                            v = self.eval_expr(base_s, pc, allow_unresolved=(pass_num == 1))
                            if v <= 0xFF and dpi_op is not None and not base_s.startswith("!"):
                                out.extend([dpi_op, v & 0xFF])
                                pc += 2
                            else:
                                out.extend([absi_op, v & 0xFF, (v >> 8) & 0xFF])
                                pc += 3
                        else:
                            force_abs = arg.startswith("!")
                            clean_a = arg[1:] if force_abs else arg
                            v = self.eval_expr(clean_a, pc, allow_unresolved=(pass_num == 1))
                            if v <= 0xFF and not force_abs:
                                out.extend([dp_op, v & 0xFF])
                                pc += 2
                            else:
                                out.extend([abs_op, v & 0xFF, (v >> 8) & 0xFF])
                                pc += 3
                        continue

                    # Standard ALU (LDA, STA, ADC, SBC, CMP, AND, ORA, EOR)
                    if mnem in ALU_TABLE:
                        imm_op, dp_op, dpx_op, abs_op, absx_op, absy_op, lng_op, lngx_op, dpily_op = ALU_TABLE[mnem]
                        if arg.startswith("#"):
                            v = self.eval_expr(arg[1:], pc, allow_unresolved=(pass_num == 1))
                            if m8:
                                out.extend([imm_op, v & 0xFF])
                                pc += 2
                            else:
                                out.extend([imm_op, v & 0xFF, (v >> 8) & 0xFF])
                                pc += 3
                        elif arg.startswith("[") and arg.upper().endswith("],Y"):
                            inner = arg[1:-3].strip()
                            v = self.eval_expr(inner, pc, allow_unresolved=(pass_num == 1))
                            out.extend([dpily_op, v & 0xFF])
                            pc += 2
                        elif arg.startswith("[") and arg.endswith("]"):
                            inner = arg[1:-1].strip()
                            v = self.eval_expr(inner, pc, allow_unresolved=(pass_num == 1))
                            # Direct Page Indirect Long [$dp] is dpily_op - 0x10
                            out.extend([dpily_op - 0x10, v & 0xFF])
                            pc += 2
                        elif arg.upper().endswith(",X"):
                            base_s = arg[:-2].strip()
                            force_abs = base_s.startswith("!")
                            force_lng = base_s.startswith("@")
                            clean_s = base_s[1:] if (force_abs or force_lng) else base_s
                            v = self.eval_expr(clean_s, pc, allow_unresolved=(pass_num == 1))
                            if force_lng or v > 0xFFFF:
                                out.extend([lngx_op, v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF])
                                pc += 4
                            elif v <= 0xFF and not force_abs:
                                out.extend([dpx_op, v & 0xFF])
                                pc += 2
                            else:
                                out.extend([absx_op, v & 0xFF, (v >> 8) & 0xFF])
                                pc += 3
                        elif arg.upper().endswith(",Y"):
                            base_s = arg[:-2].strip()
                            clean_s = base_s[1:] if base_s.startswith("!") else base_s
                            v = self.eval_expr(clean_s, pc, allow_unresolved=(pass_num == 1))
                            out.extend([absy_op, v & 0xFF, (v >> 8) & 0xFF])
                            pc += 3
                        else:
                            force_abs = arg.startswith("!")
                            force_lng = arg.startswith("@")
                            clean_s = arg[1:] if (force_abs or force_lng) else arg
                            v = self.eval_expr(clean_s, pc, allow_unresolved=(pass_num == 1))
                            if force_lng or v > 0xFFFF:
                                out.extend([lng_op, v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF])
                                pc += 4
                            elif v <= 0xFF and not force_abs:
                                out.extend([dp_op, v & 0xFF])
                                pc += 2
                            else:
                                out.extend([abs_op, v & 0xFF, (v >> 8) & 0xFF])
                                pc += 3
                        continue

                    raise ValueError(f"Unknown instruction or syntax: '{line}'")

                except Exception as exc:
                    raise RuntimeError(f"[{filepath}:{lno}] {exc} (line: '{line}')") from exc

        return org_base, bytes(out), self.symbols
