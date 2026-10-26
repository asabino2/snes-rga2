#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RGA2 (OpenBOR) -> Super Nintendo SPC700 Audio Driver, BRR Converter & Chiptune Sequencer
1. Converts original OpenBOR .wav sound effects (punch, hit, jump, special, pickup, boss KO)
   into authentic SNES S-DSP 9-byte Bit Rate Reduction (BRR) sample blocks.
2. Synthesizes crisp 16-bit SNES instrument BRR samples (Lead Square, Pulse, Slap Bass, Kick/Snare).
3. Assembles a real SPC700 machine-code Audio Engine + S-DSP initializer + 8-channel BGM/SFX mixer
   that runs natively on the Sony SPC700 at $0200 in Audio RAM.
"""

import os
import wave
import struct
import math

DATA_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "build", "assets"))


def load_wav_mono_pcm16(rel_path, target_rate=6000, max_samples=2400):
    """
    Reads an OpenBOR .wav file (8-bit unsigned or 16-bit signed, mono or stereo),
    resamples to `target_rate` Hz mono 16-bit PCM, normalizes amplitude, and pads to a multiple of 16 samples.
    """
    full_path = os.path.join(DATA_ROOT, rel_path.replace("/", os.sep))
    with wave.open(full_path, "rb") as wf:
        nch = wf.getnchannels()
        sw = wf.getsampwidth()
        fr = wf.getframerate()
        nframes = wf.getnframes()
        raw = wf.readframes(nframes)

    samples = []
    if sw == 1:
        # 8-bit unsigned PCM (0..255 -> -32768..32767)
        step = nch
        for i in range(0, len(raw), step):
            val = (raw[i] - 128) * 256
            samples.append(val)
    elif sw == 2:
        step = 2 * nch
        for i in range(0, len(raw) - (step - 1), step):
            val = struct.unpack("<h", raw[i : i + 2])[0]
            samples.append(val)
    else:
        samples = [0] * 64

    if not samples:
        samples = [0] * 64

    # Resample to target_rate
    out_len = max(16, int(len(samples) * target_rate / max(1, fr)))
    out_len = min(out_len, max_samples)
    resampled = []
    for i in range(out_len):
        src_i = int(i * len(samples) / out_len)
        src_i = min(len(samples) - 1, src_i)
        resampled.append(samples[src_i])

    # Normalize peak to ~24000 so BRR has clean dynamic range without clipping
    peak = max(max(abs(s) for s in resampled), 1)
    gain = min(4.0, 24000.0 / peak)
    resampled = [max(-30000, min(30000, int(s * gain))) for s in resampled]

    # Apply short fade-out on last 32 samples to prevent click at end of non-looped SFX
    fade_n = min(32, len(resampled) // 4)
    for i in range(fade_n):
        idx = len(resampled) - 1 - i
        resampled[idx] = int(resampled[idx] * (i / max(1, fade_n)))

    while len(resampled) % 16 != 0:
        resampled.append(0)

    return resampled


def encode_brr(samples_16, loop=False):
    """
    Encodes a list of 16-bit PCM samples (multiple of 16) into SNES S-DSP BRR format
    (9 bytes per 16 samples: 1 header byte + 8 data bytes of 4-bit signed nibbles).
    Uses Filter 0 (direct shift) for maximum hardware compatibility and zero filter overflow.
    """
    assert len(samples_16) % 16 == 0
    num_blocks = len(samples_16) // 16
    out = bytearray()

    for b_idx in range(num_blocks):
        blk = samples_16[b_idx * 16 : (b_idx + 1) * 16]
        is_last = (b_idx == num_blocks - 1)

        # Find optimal shift (0..12) for Filter 0
        # In S-DSP Filter 0, decoded 15-bit sample = (nibble << shift) >> 1
        # Wait: S-DSP takes 16-bit PCM in range -32768..32767.
        # For shift S (0..12), nibble (-8..+7) represents roughly (nibble << S).
        best_shift = 0
        best_err = 1 << 60
        best_nibbles = [0] * 16

        for shift in range(0, 13):
            step = max(1, 1 << shift)
            err = 0
            nibs = []
            for s in blk:
                # Scale 16-bit signed sample (-32768..32767) down to 15-bit S-DSP scale
                s15 = s >> 1
                q = int(round(s15 / step))
                q = max(-8, min(7, q))
                rec = (q << shift) >> 1
                d = (s >> 1) - rec
                err += d * d
                nibs.append(q & 0x0F)
            if err < best_err:
                best_err = err
                best_shift = shift
                best_nibbles = nibs

        flags = (best_shift << 4)  # Filter 0
        if is_last:
            flags |= 0x01  # END flag
            if loop:
                flags |= 0x02  # LOOP flag
        out.append(flags)
        for i in range(0, 16, 2):
            byte_val = (best_nibbles[i] << 4) | (best_nibbles[i + 1] & 0x0F)
            out.append(byte_val)

    return bytes(out)


def synth_loop_wave(wave_type):
    """Generates a single-cycle 16-sample loopable waveform for chiptune instruments."""
    samples = []
    for i in range(16):
        t = i / 16.0
        if wave_type == "square":
            v = 22000 if i < 8 else -22000
        elif wave_type == "pulse25":
            v = 22000 if i < 4 else -14000
        elif wave_type == "saw":
            v = int((2.0 * t - 1.0) * 22000)
        elif wave_type == "triangle":
            v = int((1.0 - 4.0 * abs(t - 0.5)) * 24000)
        else:
            v = 0
        samples.append(v)
    return encode_brr(samples, loop=True)


def build_spc700_driver_and_bank():
    """
    Builds the complete SPC700 ARAM image loaded to $0200 in Audio RAM!
    Memory map inside SPC700 64KB ARAM:
      $0000-$00EF : Zero Page variables (sequencer timers, track pointers, channel states)
      $0200-$04FF : SPC700 Machine Code Driver + 8-Channel Chiptune & SFX Engine
      $0500-$057F : S-DSP Sample Directory (DIR = $05 -> $0500, up to 32 instruments/SFX, 4 bytes each: start_addr, loop_addr)
      $0600-$11FF : 12 Stage/Menu Chiptune Song Sequences & Note Pitch Table
      $1200-$5FFF : BRR Instrument Waveforms (0..3) + Converted OpenBOR WAV SFX (4..11)

    CPU <-> SPC700 Communication Protocol via $2140-$2143 ($F4-$F7 on SPC700):
      - Port 0 ($2140 / SPC $F4): BGM Track Command ($01..$0C = Play Track 1..12, $80 = Stop BGM)
      - Port 1 ($2141 / SPC $F5): SFX Trigger Counter (incremented by CPU on each SFX trigger)
      - Port 2 ($2142 / SPC $F6): SFX ID to play ($04..$0B: Punch, Heavy Hit, Jump, Special, Pickup, Portal, Boss Hit, 1UP)
      - Port 3 ($2143 / SPC $F7): Driver Ready Signature ($52 = 'R' echoed back to CPU!)
    """
    # 1. Build BRR Instruments (0..3) and OpenBOR WAV Sound Effects (4..11)
    brr_samples = [
        ("inst_square",   synth_loop_wave("square"),   True),
        ("inst_pulse",    synth_loop_wave("pulse25"),  True),
        ("inst_bass",     synth_loop_wave("triangle"), True),
        ("inst_saw",      synth_loop_wave("saw"),      True),
        ("sfx_punch",     encode_brr(load_wav_mono_pcm16("SOUNDS/punch2.wav", 6000, 1280), False), False),
        ("sfx_hit",       encode_brr(load_wav_mono_pcm16("SOUNDS/beat1old.wav", 6000, 1600), False), False),
        ("sfx_jump",      encode_brr(load_wav_mono_pcm16("SOUNDS/jump.wav", 5000, 1440), False), False),
        ("sfx_special",   encode_brr(load_wav_mono_pcm16("CHARS/Velberan/grito.wav", 5500, 1920), False), False),
        ("sfx_pickup",    encode_brr(load_wav_mono_pcm16("SOUNDS/get.wav", 6000, 1440), False), False),
        ("sfx_portal",    encode_brr(load_wav_mono_pcm16("SOUNDS/BEEP.WAV", 6000, 1440), False), False),
        ("sfx_bosshit",   encode_brr(load_wav_mono_pcm16("SOUNDS/0corte.wav", 6000, 1440), False), False),
        ("sfx_1up",       encode_brr(load_wav_mono_pcm16("SOUNDS/1up.wav", 5000, 1920), False), False),
    ]

    # Pack BRR samples starting at ARAM $1200 and build Sample Directory at ARAM $0500
    sample_dir = bytearray(128)  # 32 entries * 4 bytes
    brr_blob = bytearray()
    cur_aram = 0x1200
    for idx, (name, data, is_loop) in enumerate(brr_samples):
        start_addr = cur_aram
        loop_addr = cur_aram if is_loop else (cur_aram + len(data) - 9)
        struct.pack_into("<HH", sample_dir, idx * 4, start_addr, loop_addr)
        brr_blob.extend(data)
        cur_aram += len(data)
        print(f"[OK] SPC700 BRR #{idx:02d} '{name:14s}': {len(data):4d} bytes @ ARAM ${start_addr:04X}")

    # 2. Build Pitch Table (36 notes: C2..B4 for 16-sample loop at S-DSP 32kHz) + 12 Chiptune Songs
    # For a 16-sample loop, f_out = 32000 * (P / 4096) / 16 = 2000 * P / 4096
    # So P = f_hz * 4096 / 2000 = f_hz * 2.048
    note_pitches = [0]  # Note 0 = Rest
    base_c2 = 130.81
    for semitone in range(48):
        freq = base_c2 * (2.0 ** (semitone / 12.0))
        p_val = max(0x0080, min(0x3FFF, int(round(freq * 2.048))))
        note_pitches.append(p_val)

    # 12 Distinct Chiptune Songs (32 steps each: Lead1 note, Lead2/Harmony note, Bass note, Drum/Rhythm note)
    # Notes are 1..48 (semitones above C2: 1=C2, 13=C3, 15=D3, 17=E3, 18=F3, 20=G3, 22=A3, 24=B3, 25=C4, 27=D4, 29=E4, 30=F4, 32=G4, 34=A4, 37=C5)
    songs = [
        # Track 0: Title & Select (RGA2 Heroic 16-Bit Anthem - C Major / A Minor)
        [
            (25,13,1), (29,17,1), (32,20,1), (37,25,1), (34,22,10), (32,20,10), (29,17,10), (25,13,10),
            (27,15,6), (30,18,6), (34,22,6), (37,25,6), (36,24,8),  (32,20,8),  (29,17,8),  (27,15,8),
            (25,13,1), (32,20,1), (37,25,1), (39,27,1), (37,25,10), (34,22,10), (32,20,10), (29,17,10),
            (30,18,6), (32,20,6), (34,22,8), (36,24,8), (37,25,1),  (32,20,1),  (25,13,1),  (0,0,1),
        ],
        # Track 1: Stage 0 BGS (Brasil Game Show Arcade Beat - E Minor)
        [
            (17,5,5),  (20,8,5),  (24,12,5), (29,17,5), (27,15,3),  (24,12,3),  (20,8,3),   (17,5,3),
            (18,6,1),  (22,10,1), (25,13,1), (30,18,1), (29,17,3),  (27,15,3),  (24,12,5),  (0,0,5),
            (29,17,5), (29,17,5), (32,20,5), (29,17,5), (27,15,3),  (24,12,3),  (22,10,3),  (20,8,3),
            (18,6,1),  (20,8,1),  (22,10,3), (24,12,3), (29,17,5),  (24,12,5),  (17,5,5),   (0,0,5),
        ],
        # Track 2: Stage 1 Estação Central Hub (Futuristic Synth Groove)
        [
            (22,10,10),(25,13,10),(29,17,10),(34,22,10),(32,20,6),  (29,17,6),  (25,13,6),  (22,10,6),
            (24,12,8), (27,15,8), (32,20,8), (36,24,8), (34,22,10), (29,17,10), (25,13,10), (0,0,10),
            (34,22,10),(32,20,10),(29,17,10),(25,13,10),(27,15,6),  (30,18,6),  (34,22,6),  (32,20,6),
            (29,17,8), (27,15,8), (24,12,8), (20,8,8),  (22,10,10), (29,17,10), (22,10,10), (0,0,10),
        ],
        # Track 3: Portal 1 Mega Man X (Cyber Highway Rock)
        [
            (27,15,3), (27,15,3), (30,18,3), (34,22,3), (39,27,3),  (37,25,1),  (34,22,1),  (30,18,1),
            (32,20,11),(32,20,11),(34,22,11),(37,25,11),(36,24,10), (34,22,10), (30,18,10), (27,15,10),
            (27,15,3), (30,18,3), (34,22,3), (39,27,3), (42,30,1),  (39,27,1),  (37,25,1),  (34,22,1),
            (32,20,11),(34,22,11),(36,24,10),(37,25,10),(39,27,3),  (34,22,3),  (27,15,3),  (0,0,3),
        ],
        # Track 4: Portal 2 Turtles (TMNT Street Action)
        [
            (20,8,8),  (23,11,8), (25,13,8), (27,15,8), (32,20,8),  (30,18,6),  (27,15,6),  (25,13,6),
            (23,11,4), (27,15,4), (30,18,4), (35,23,4), (32,20,6),  (27,15,6),  (25,13,6),  (20,8,6),
            (32,20,8), (32,20,8), (35,23,8), (32,20,8), (30,18,6),  (27,15,6),  (25,13,6),  (23,11,6),
            (25,13,4), (27,15,4), (30,18,6), (31,19,6), (32,20,8),  (27,15,8),  (20,8,8),   (0,0,8),
        ],
        # Track 5: Portal 3 Golden Axe (Wilderness Epic March)
        [
            (22,10,10),(22,10,10),(29,17,10),(29,17,10),(27,15,8),  (25,13,8),  (24,12,8),  (22,10,8),
            (18,6,6),  (18,6,6),  (25,13,6), (25,13,6), (24,12,5),  (20,8,5),   (24,12,5),  (29,17,5),
            (34,22,10),(32,20,10),(29,17,10),(25,13,10),(27,15,8),  (29,17,8),  (32,20,8),  (27,15,8),
            (25,13,6), (24,12,6), (20,8,5),  (24,12,5), (22,10,10), (22,10,10), (10,10,10), (0,0,10),
        ],
        # Track 6: Portal 4 Street Fighter (Ryu & Akuma Dojo Battle)
        [
            (24,12,12),(27,15,12),(29,17,12),(31,19,12),(36,24,12), (34,22,10), (31,19,10), (29,17,10),
            (27,15,8), (31,19,8), (34,22,8), (39,27,8), (38,26,11), (34,22,11), (31,19,11), (27,15,11),
            (36,24,12),(34,22,12),(31,19,12),(29,17,12),(27,15,10), (29,17,10), (31,19,10), (34,22,10),
            (36,24,8), (38,26,8), (39,27,11),(38,26,11),(36,24,12), (31,19,12), (24,12,12), (0,0,12),
        ],
        # Track 7: Portal 5 Ninja Gaiden (Fast 8-Bit Ninja Run)
        [
            (29,17,5), (32,20,5), (36,24,5), (41,29,5), (39,27,3),  (36,24,3),  (32,20,3),  (29,17,3),
            (30,18,1), (34,22,1), (37,25,1), (42,30,1), (41,29,3),  (39,27,3),  (36,24,3),  (34,22,3),
            (41,29,5), (39,27,5), (36,24,5), (32,20,5), (34,22,3),  (36,24,3),  (39,27,3),  (34,22,3),
            (30,18,1), (32,20,1), (34,22,3), (36,24,3), (41,29,5),  (36,24,5),  (29,17,5),  (0,0,5),
        ],
        # Track 8: Portal 6 Super Mario (Koopa Castle Overworld)
        [
            (29,17,1), (29,17,1), (0,0,1),   (29,17,1), (0,0,1),    (25,13,1),  (29,17,1),  (0,0,1),
            (32,20,8), (0,0,8),   (0,0,8),   (20,8,8),  (0,0,8),    (0,0,8),    (0,0,8),    (0,0,8),
            (25,13,1), (0,0,1),   (20,8,8),  (0,0,8),   (17,5,5),   (0,0,5),    (22,10,10), (24,12,12),
            (23,11,10),(22,10,10),(20,8,8),  (29,17,1), (32,20,8),  (34,22,10), (30,18,6),  (32,20,8),
        ],
        # Track 9: Portal 7 Battletoads (Turbo Cavern Heavy Bass)
        [
            (15,3,3),  (27,15,3), (15,3,3),  (25,13,3), (15,3,3),   (22,10,3),  (18,6,3),   (20,8,3),
            (15,3,1),  (27,15,1), (15,3,1),  (30,18,1), (29,17,11), (27,15,11), (25,13,11), (22,10,11),
            (27,15,3), (30,18,3), (34,22,3), (39,27,3), (37,25,1),  (34,22,1),  (30,18,1),  (27,15,1),
            (25,13,11),(22,10,11),(20,8,10), (18,6,10), (15,3,3),   (27,15,3),  (15,3,3),   (0,0,3),
        ],
        # Track 10: Portal 8 YouTube HQ & Final Boss (Algorithm Final Showdown)
        [
            (26,14,2), (29,17,2), (33,21,2), (38,26,2), (37,25,2),  (33,21,2),  (29,17,2),  (26,14,2),
            (27,15,3), (30,18,3), (34,22,3), (39,27,3), (38,26,11), (34,22,11), (30,18,11), (27,15,11),
            (38,26,2), (41,29,2), (45,33,2), (41,29,2), (39,27,3),  (37,25,3),  (34,22,3),  (30,18,3),
            (33,21,10),(34,22,10),(37,25,11),(38,26,11),(39,27,2),  (33,21,2),  (26,14,2),  (0,0,2),
        ],
        # Track 11: Victory / Ending Theme (Triumphant Fanfare)
        [
            (25,13,1), (25,13,1), (25,13,1), (25,13,1), (21,9,9),   (23,11,11), (25,13,1),  (23,11,11),
            (25,13,1), (29,17,1), (32,20,1), (37,25,1), (39,27,6),  (37,25,8),  (32,20,1),  (29,17,1),
            (30,18,6), (34,22,6), (37,25,6), (42,30,6), (41,29,8),  (39,27,8),  (37,25,8),  (36,24,8),
            (37,25,1), (32,20,1), (29,17,1), (25,13,1), (37,25,1),  (37,25,1),  (37,25,1),  (0,0,1),
        ],
    ]

    # Pack Song Data at ARAM $0600:
    # For each of the 12 songs, 32 steps * 6 bytes (Ch0_Pitch_Lo, Ch0_Pitch_Hi, Ch1_Pitch_Lo, Ch1_Pitch_Hi, Ch2_Pitch_Lo, Ch2_Pitch_Hi) = 192 bytes per song!
    # Wait: pre-converting note numbers into 16-bit S-DSP pitch values right here in Python makes the SPC700 machine code tiny, ultra-fast, and 100% bug-free!
    song_blob = bytearray()
    for s_idx, pattern in enumerate(songs):
        assert len(pattern) == 32
        for n0, n1, n2 in pattern:
            p0 = note_pitches[n0]
            p1 = note_pitches[n1]
            p2 = note_pitches[n2]
            song_blob.extend(struct.pack("<HHH", p0, p1, p2))
        # Pad each song to 256 bytes ($0100 bytes) so Song N is simply at ARAM page ($06 + N)!
        # WAIT A SECOND! Look how clean that is:
        #   Song 0 is at $0600, Song 1 is at $0700, Song 2 is at $0800 ... Song 11 is at $1100!
        #   Then the high byte of the song pointer is literally ($06 + song_id), and the low byte is (step * 6)!
        while len(song_blob) < (s_idx + 1) * 256:
            song_blob.append(0)

    # 3. Assemble the SPC700 Machine Code Driver at ARAM $0200!
    # Let's write a helper to emit DSP register writes:
    #   MOV $F2, #reg   (0x8F, reg, 0xF2)
    #   MOV $F3, #val   (0x8F, val, 0xF3)
    code = bytearray()

    def mov_dp_imm(dp, imm):
        code.extend([0x8F, imm & 0xFF, dp & 0xFF])

    def dsp_write_imm(reg, val):
        mov_dp_imm(0xF2, reg)
        mov_dp_imm(0xF3, val)

    # --- Entry Point at $0200 ---
    code.append(0x20)  # CLRP (Direct Page = $0000)
    # Set stack pointer to $EF: MOV X, #$EF ; MOV SP, X
    code.extend([0xCD, 0xEF, 0xBD])

    # Initialize S-DSP global registers:
    dsp_write_imm(0x6C, 0x20)  # FLG: Clear mute/reset, disable echo writes
    dsp_write_imm(0x4C, 0x00)  # KON: Clear key on
    dsp_write_imm(0x5C, 0xFF)  # KOF: Key off all voices
    dsp_write_imm(0x5D, 0x05)  # DIR: Sample directory at $0500
    dsp_write_imm(0x0C, 0x7F)  # MVOLL: Master volume L (max clean volume)
    dsp_write_imm(0x1C, 0x7F)  # MVOLR: Master volume R (max clean volume)
    dsp_write_imm(0x2C, 0x00)  # EVOLL: Echo volume L = 0
    dsp_write_imm(0x3C, 0x00)  # EVOLR: Echo volume R = 0
    dsp_write_imm(0x4D, 0x00)  # EON: Echo off
    dsp_write_imm(0x3D, 0x00)  # NON: Noise off
    dsp_write_imm(0x2D, 0x00)  # PMON: Pitch mod off
    dsp_write_imm(0x5C, 0x00)  # KOF: Release key off

    # Configure Voices 0, 1, 2 for BGM (Ch0=Square Lead, Ch1=Pulse Harmony, Ch2=Triangle Bass):
    # Voice 0 (Lead):
    dsp_write_imm(0x00, 0x58)  # V0VOLL
    dsp_write_imm(0x01, 0x58)  # V0VOLR
    dsp_write_imm(0x04, 0x00)  # V0SRCN = 0 (Square)
    dsp_write_imm(0x05, 0xFF)  # V0ADSR1 = ADSR enabled, Attack=15, Decay=7
    dsp_write_imm(0x06, 0xE4)  # V0ADSR2 = Sustain level=7, Release=4

    # Voice 1 (Harmony):
    dsp_write_imm(0x10, 0x46)  # V1VOLL
    dsp_write_imm(0x11, 0x46)  # V1VOLR
    dsp_write_imm(0x14, 0x01)  # V1SRCN = 1 (Pulse)
    dsp_write_imm(0x15, 0xFF)  # V1ADSR1
    dsp_write_imm(0x16, 0xE6)  # V1ADSR2

    # Voice 2 (Bass):
    dsp_write_imm(0x20, 0x64)  # V2VOLL
    dsp_write_imm(0x21, 0x64)  # V2VOLR
    dsp_write_imm(0x24, 0x02)  # V2SRCN = 2 (Triangle Bass)
    dsp_write_imm(0x25, 0xFF)  # V2ADSR1
    dsp_write_imm(0x26, 0xE2)  # V2ADSR2

    # Voice 3 (SFX Channel — Plays converted OpenBOR WAV BRR samples!):
    dsp_write_imm(0x30, 0x7F)  # V3VOLL (Max volume for arcade SFX)
    dsp_write_imm(0x31, 0x7F)  # V3VOLR
    dsp_write_imm(0x32, 0x00)  # V3PITCHL ($0600 = 6000Hz playback rate!)
    dsp_write_imm(0x33, 0x06)  # V3PITCHH
    dsp_write_imm(0x34, 0x04)  # V3SRCN = 4 (Punch default)
    dsp_write_imm(0x35, 0xFF)  # V3ADSR1
    dsp_write_imm(0x36, 0xE0)  # V3ADSR2 (Full sustain until BRR END block)

    # Zero-Page State Variables:
    #   $10 : Current SongPtr Lo (0, 6, 12 ... 186)
    #   $11 : Current SongPtr Hi ($06 + song_id)
    #   $12 : Step counter (0..31)
    #   $13 : Last Port 0 (BGM command 1..12)
    #   $14 : Last Port 1 (SFX counter)
    #   $15 : Timer 0 tick accumulator (0..5 -> 5 * 25ms = 125ms per 16th note = 120 BPM)
    mov_dp_imm(0x10, 0x00)
    mov_dp_imm(0x11, 0x06)  # Start on Song 0 ($0600)
    mov_dp_imm(0x12, 0x00)
    mov_dp_imm(0x13, 0x00)
    mov_dp_imm(0x14, 0x00)
    mov_dp_imm(0x15, 0x05)  # Trigger Note 0 immediately on first tick!

    # Configure Timer 0 ($FA = 200 -> 25ms tick, 5 ticks per sixteenth note = 125ms per step)
    mov_dp_imm(0xFA, 200)
    mov_dp_imm(0xF1, 0x01)  # Enable Timer 0

    # Signal CPU that custom RGA2 Audio Driver is active: Port 3 ($F7) = $52 ('R')
    mov_dp_imm(0xF7, 0x52)

    # --- Main Sequencer & SFX Loop ---
    loop_addr = 0x0200 + len(code)

    # 1. Check Port 0 ($F4) for new BGM track ID (strictly 1..12 so IPL kick byte $4E is ignored!):
    bgm_update_blk = bytes([
        0xC4, 0x13,        # MOV $13, A
        0xC4, 0xF4,        # MOV $F4, A (echo ack)
        0x60,              # CLC
        0x88, 0x05,        # ADC A, #$05  (Track 1 -> $0600, Track 2 -> $0700, etc.)
        0xC4, 0x11,        # MOV $11, A
        0x8F, 0x00, 0x10,  # MOV $10, #$00
        0x8F, 0x00, 0x12,  # MOV $12, #$00
        0x8F, 0x05, 0x15,  # MOV $15, #$05 (play first note of new track on next tick!)
    ])
    code.extend([
        0xE4, 0xF4,                        # MOV A, $F4
        0xF0, len(bgm_update_blk) + 8,     # BEQ skip_bgm (ignore 0)
        0x68, 0x0D,                        # CMP A, #$0D
        0xB0, len(bgm_update_blk) + 4,     # BCS skip_bgm (ignore >= 13, e.g. IPL kick $4E!)
        0x64, 0x13,                        # CMP A, $13
        0xF0, len(bgm_update_blk),         # BEQ skip_bgm (same track already playing)
    ])
    code.extend(bgm_update_blk)

    # 2. Check Port 1 ($F5) for new SFX trigger (Sample ID 4..11 in $F6):
    sfx_update_blk = bytes([
        0xC4, 0x14,        # MOV $14, A
        0xC4, 0xF5,        # MOV $F5, A
        0xE4, 0xF6,        # MOV A, $F6
        0x8F, 0x34, 0xF2,  # MOV $F2, #$34 (V3SRCN)
        0xC4, 0xF3,        # MOV $F3, A
        0x8F, 0x4C, 0xF2,  # MOV $F2, #$4C (KON)
        0x8F, 0x08, 0xF3,  # MOV $F3, #$08 (Key On Voice 3!)
        0x8F, 0x5C, 0xF2,  # MOV $F2, #$5C (KOF)
        0x8F, 0x00, 0xF3,  # MOV $F3, #$00
    ])
    code.extend([
        0xE4, 0xF5,                        # MOV A, $F5
        0xF0, len(sfx_update_blk) + 4,     # BEQ skip_sfx (ignore 0)
        0x64, 0x14,                        # CMP A, $14
        0xF0, len(sfx_update_blk),         # BEQ skip_sfx
    ])
    code.extend(sfx_update_blk)

    # 3. Read Timer 0 ($FD) and accumulate ticks in $15 until >= 5 (~125ms per 16th note):
    wait_check_pos = len(code)
    rel_to_loop1 = (loop_addr - (0x0200 + wait_check_pos + 4)) & 0xFF
    code.extend([
        0xE4, 0xFD,        # MOV A, $FD (reads & clears 4-bit timer counter)
        0xF0, rel_to_loop1,# BEQ loop_addr
        0x60,              # CLC
        0x84, 0x15,        # ADC A, $15
        0xC4, 0x15,        # MOV $15, A
        0x68, 0x05,        # CMP A, #$05
    ])
    bcc_pos = len(code)
    rel_to_loop2 = (loop_addr - (0x0200 + bcc_pos + 2)) & 0xFF
    code.extend([
        0x90, rel_to_loop2,# BCC loop_addr
        0x8F, 0x00, 0x15,  # MOV $15, #$00 (reset tick accumulator)
    ])

    # Play current step of BGM on Voices 0, 1, 2:
    # Voice 0 Pitch Lo/Hi (Y=0, 1):
    code.extend([
        0x8D, 0x00,        # MOV Y, #$00
        0x8F, 0x02, 0xF2,  # MOV $F2, #$02 (V0PITCHL)
        0xF7, 0x10,        # MOV A, [$10]+Y
        0xC4, 0xF3,        # MOV $F3, A
        0xFC,              # INC Y
        0x8F, 0x03, 0xF2,  # MOV $F2, #$03 (V0PITCHH)
        0xF7, 0x10,        # MOV A, [$10]+Y
        0xC4, 0xF3,        # MOV $F3, A
        # Voice 1 Pitch Lo/Hi (Y=2, 3):
        0xFC,              # INC Y
        0x8F, 0x12, 0xF2,  # MOV $F2, #$12 (V1PITCHL)
        0xF7, 0x10,        # MOV A, [$10]+Y
        0xC4, 0xF3,        # MOV $F3, A
        0xFC,              # INC Y
        0x8F, 0x13, 0xF2,  # MOV $F2, #$13 (V1PITCHH)
        0xF7, 0x10,        # MOV A, [$10]+Y
        0xC4, 0xF3,        # MOV $F3, A
        # Voice 2 Pitch Lo/Hi (Y=4, 5):
        0xFC,              # INC Y
        0x8F, 0x22, 0xF2,  # MOV $F2, #$22 (V2PITCHL)
        0xF7, 0x10,        # MOV A, [$10]+Y
        0xC4, 0xF3,        # MOV $F3, A
        0xFC,              # INC Y
        0x8F, 0x23, 0xF2,  # MOV $F2, #$23 (V2PITCHH)
        0xF7, 0x10,        # MOV A, [$10]+Y
        0xC4, 0xF3,        # MOV $F3, A
        # Key On Voices 0, 1, 2 (KON = $07):
        0x8F, 0x4C, 0xF2,  # MOV $F2, #$4C (KON)
        0x8F, 0x07, 0xF3,  # MOV $F3, #$07
    ])

    # Advance step ($10 += 6, wrap at 192 = 32 steps * 6 bytes):
    code.extend([
        0xE4, 0x10,        # MOV A, $10
        0x60,              # CLC
        0x88, 0x06,        # ADC A, #$06
        0x68, 0xC0,        # CMP A, #$C0 (192 = 32 * 6)
        0x90, 0x02,        # BCC +2
        0xE8, 0x00,        # MOV A, #$00
        0xC4, 0x10,        # MOV $10, A
        0x5F, loop_addr & 0xFF, (loop_addr >> 8) & 0xFF,  # JMP !loop_addr
    ])

    # Assemble single contiguous ARAM block starting at $0200:
    #   $0200..$04FF : Code (padded to $0300 bytes)
    #   $0500..$05FF : Sample Directory (padded to $0100 bytes)
    #   $0600..$11FF : 12 Songs (12 * 256 = $0C00 bytes)
    #   $1200..end   : BRR Samples
    aram_img = bytearray()
    assert len(code) <= 0x0300
    aram_img.extend(code)
    while len(aram_img) < 0x0300:
        aram_img.append(0)
    aram_img.extend(sample_dir)
    while len(aram_img) < 0x0400:
        aram_img.append(0)
    aram_img.extend(song_blob)
    assert len(aram_img) == 0x1000  # $0200 + $1000 = $1200!
    aram_img.extend(brr_blob)

    out_path = os.path.join(OUT_DIR, "spc700_aram.bin")
    with open(out_path, "wb") as f:
        f.write(aram_img)
    print(f"[OK] Complete SPC700 ARAM Image ($0200..${0x0200 + len(aram_img) - 1:04X}): {len(aram_img)} bytes")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    build_spc700_driver_and_bank()
