#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RGA2 (OpenBOR) -> Super Nintendo SPC700 6-Voice Stereo Audio Engine, BRR Synth & 14-Track Sequencer
1. Converts original OpenBOR .wav sound effects (punch, hit, jump, special, pickup, portal, boss hit, 1up)
   into authentic SNES S-DSP 9-byte Bit Rate Reduction (BRR) sample blocks (SRCN 4..11).
2. Synthesizes rich 16-bit multi-harmonic looped instrument waveforms (32-sample additive BRR):
   - SRCN 0 : Bright 16-Bit Polysynth / Brass Lead
   - SRCN 1 : Warm Stereo Chorus Pulse-Brass Harmony
   - SRCN 2 : Punchy 16-Bit FM Slap Bass
   - SRCN 3 : Lush Stereo String / Organ Chord Pad
   - SRCN 16: Overdriven 16-Bit Rock Guitar Lead
   - SRCN 17: Crisp Hollow Square / Woodwind Lead
3. Synthesizes a 4-piece 16-Bit Arcade Drum Kit in BRR (SRCN 12..15):
   - SRCN 12: Punchy Arcade Kick Drum
   - SRCN 13: Crisp Snare Drum with Gated Wire Burst
   - SRCN 14: Metallic Closed Hi-Hat
   - SRCN 15: Power Tom / Crash Fill
4. Assembles a native SPC700 machine-code Audio Engine at $0200 in ARAM featuring:
   - 5 Simultaneous BGM Voices (Lead, Stereo Detuned Harmony, Slap Bass, Chord Pad, Drum Kit)
   - Dedicated 6th Voice (Voice 5) for uninterrupted OpenBOR WAV Sound Effects
   - Hardware S-DSP 8-Tap FIR Stereo Echo / Reverb ($D000..$E7FF)
   - True Note Sustain/Tie ($FFFF), Clean Key-Off Rests ($0000), Per-Song Instruments & Tempos
   - 14 Full 64-Step Iconic 16-Bit Arrangements (Title, BGS, Hub, Mega Man X, TMNT, Golden Axe,
     Street Fighter II, Ninja Gaiden, Super Mario, Battletoads, Final Boss, Ending, Select, Stage Boss)
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

    out_len = max(16, int(len(samples) * target_rate / max(1, fr)))
    out_len = min(out_len, max_samples)
    resampled = []
    for i in range(out_len):
        src_i = int(i * len(samples) / out_len)
        src_i = min(len(samples) - 1, src_i)
        resampled.append(samples[src_i])

    peak = max(max(abs(s) for s in resampled), 1)
    gain = min(4.0, 24000.0 / peak)
    resampled = [max(-30000, min(30000, int(s * gain))) for s in resampled]

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
    """
    assert len(samples_16) % 16 == 0
    num_blocks = len(samples_16) // 16
    out = bytearray()

    for b_idx in range(num_blocks):
        blk = samples_16[b_idx * 16 : (b_idx + 1) * 16]
        is_last = (b_idx == num_blocks - 1)

        best_shift = 0
        best_err = 1 << 60
        best_nibbles = [0] * 16

        for shift in range(0, 13):
            step = max(1, 1 << shift)
            err = 0
            nibs = []
            for s in blk:
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


def synth_loop_wave_32(wave_type):
    """
    Synthesizes a warm, band-limited 32-sample loopable multi-harmonic 16-bit instrument waveform.
    At S-DSP 32kHz base rate, 32 samples = 1000 Hz @ Pitch $1000 (4096), so Pitch = freq_hz * 4.096.
    """
    samples = []
    for i in range(32):
        th = 2.0 * math.pi * i / 32.0
        if wave_type == "synth_lead":
            # Rich 16-bit Polysynth / Saw-Brass Lead
            v = (
                1.00 * math.sin(th)
                + 0.68 * math.sin(2 * th + 0.2)
                + 0.45 * math.sin(3 * th)
                + 0.30 * math.sin(4 * th + 0.4)
                + 0.20 * math.sin(5 * th)
                + 0.12 * math.sin(6 * th)
            )
        elif wave_type == "warm_brass":
            # Warm 35%-duty Pulse-Brass Harmony
            v = (
                1.00 * math.sin(th)
                + 0.75 * math.cos(2 * th)
                + 0.40 * math.sin(3 * th)
                + 0.22 * math.cos(4 * th)
                + 0.12 * math.sin(5 * th)
            )
        elif wave_type == "slap_bass":
            # Punchy 16-bit FM Slap Bass (strong fundamental + growling 2nd/3rd/4th FM harmonics)
            v = (
                1.00 * math.sin(th)
                + 0.85 * math.sin(2 * th + 0.5)
                + 0.58 * math.sin(3 * th + 0.2)
                + 0.35 * math.sin(4 * th + 0.9)
                + 0.18 * math.sin(6 * th)
            )
        elif wave_type == "string_pad":
            # Lush Warm String / Organ Ensemble Pad
            v = (
                1.00 * math.sin(th)
                + 0.50 * math.sin(2 * th + 0.7)
                + 0.33 * math.sin(3 * th)
                + 0.16 * math.sin(4 * th + 1.1)
                + 0.10 * math.sin(5 * th)
            )
        elif wave_type == "rock_guitar":
            # Overdriven 16-bit Rock Guitar Lead (tube-saturated harmonic profile)
            raw = (
                1.00 * math.sin(th)
                + 0.70 * math.sin(2 * th)
                + 0.65 * math.sin(3 * th + 0.3)
                + 0.40 * math.sin(4 * th)
                + 0.35 * math.sin(5 * th)
                + 0.22 * math.sin(7 * th)
            )
            v = math.tanh(raw * 1.35)
        elif wave_type == "flute_sq":
            # Crisp Band-Limited Hollow Square / Woodwind Lead
            v = (
                1.00 * math.sin(th)
                + 0.35 * math.sin(3 * th)
                + 0.20 * math.sin(5 * th)
                + 0.11 * math.sin(7 * th)
            )
        else:
            v = math.sin(th)
        samples.append(v)

    peak = max(max(abs(x) for x in samples), 1e-6)
    pcm16 = [int(round((x / peak) * 25000)) for x in samples]
    return encode_brr(pcm16, loop=True)


def synth_drum_brr(drum_type):
    """
    Synthesizes crisp, authentic 16-bit arcade drum samples encoded in S-DSP BRR format.
    Played on Voice 4 at fixed pitch $0800 (16,000 Hz sample rate).
    """
    sr = 16000.0
    samples = []
    if drum_type == "kick":
        # 512 samples (32ms): Punchy pitch-swept sine/triangle 190Hz -> 40Hz + beater click
        n = 512
        phase = 0.0
        for i in range(n):
            t = i / sr
            freq = 40.0 + 155.0 * math.exp(-t * 95.0)
            phase += 2.0 * math.pi * freq / sr
            env = math.exp(-t * 14.0)
            click = 0.65 * math.exp(-t * 450.0) * math.sin(2.0 * math.pi * 1400.0 * t)
            body = math.tanh(1.5 * math.sin(phase))
            v = int(max(-1.0, min(1.0, (body * env + click))) * 28000)
            samples.append(v)
    elif drum_type == "snare":
        # 640 samples (40ms): 210Hz->145Hz shell + high-energy metallic snare rattle
        n = 640
        phase = 0.0
        lfsr = 0xACE1
        for i in range(n):
            t = i / sr
            freq = 145.0 + 75.0 * math.exp(-t * 80.0)
            phase += 2.0 * math.pi * freq / sr
            shell_env = math.exp(-t * 32.0)
            noise_env = math.exp(-t * 19.0)
            # Deterministic LFSR noise for crisp snare wires
            bit = ((lfsr >> 0) ^ (lfsr >> 2) ^ (lfsr >> 3) ^ (lfsr >> 5)) & 1
            lfsr = (lfsr >> 1) | (bit << 15)
            n_val = 1.0 if (lfsr & 1) else -1.0
            v_f = 0.55 * math.sin(phase) * shell_env + 0.70 * n_val * noise_env
            samples.append(int(max(-1.0, min(1.0, v_f)) * 27000))
    elif drum_type == "hihat":
        # 256 samples (16ms): Crisp 6-oscillator metallic closed hi-hat
        n = 256
        freqs = [3120.0, 4290.0, 5410.0, 6580.0, 7230.0, 7890.0]
        for i in range(n):
            t = i / sr
            env = math.exp(-t * 68.0)
            m = sum(math.sin(2.0 * math.pi * f * t + (idx * 0.7)) for idx, f in enumerate(freqs)) / 3.2
            samples.append(int(max(-1.0, min(1.0, m * env)) * 23000))
    elif drum_type == "tom_crash":
        # 640 samples (40ms): Power Tom (165Hz->75Hz) + Cymbal Crash Shimmer
        n = 640
        phase = 0.0
        lfsr = 0x5A3C
        for i in range(n):
            t = i / sr
            freq = 75.0 + 90.0 * math.exp(-t * 42.0)
            phase += 2.0 * math.pi * freq / sr
            tom_env = math.exp(-t * 16.0)
            cym_env = math.exp(-t * 22.0)
            bit = ((lfsr >> 0) ^ (lfsr >> 2) ^ (lfsr >> 3) ^ (lfsr >> 5)) & 1
            lfsr = (lfsr >> 1) | (bit << 15)
            shimmer = (1.0 if (lfsr & 1) else -1.0) * math.sin(2.0 * math.pi * 5200.0 * t)
            v_f = 0.72 * math.sin(phase) * tom_env + 0.45 * shimmer * cym_env
            samples.append(int(max(-1.0, min(1.0, v_f)) * 27500))

    # Apply tiny fade on last 16 samples to ensure clean ending
    for i in range(16):
        idx = len(samples) - 16 + i
        samples[idx] = int(samples[idx] * (15 - i) / 15.0)
    return encode_brr(samples, loop=False)


# Note Name Parser: "C2"=1 .. "B6"=60, "."=0 (Rest), "-"=-1 (Sustain/Hold)
NOTE_SEMITONES = {
    "C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3,
    "E": 4, "F": 5, "F#": 6, "GB": 6, "G": 7, "G#": 8,
    "AB": 8, "A": 9, "A#": 10, "BB": 10, "B": 11,
}


def n_id(token):
    if isinstance(token, int):
        return token
    t = token.strip().upper()
    if t in (".", "R", "0", ""):
        return 0
    if t in ("-", "~", "S"):
        return -1
    octv = int(t[-1])
    name = t[:-1]
    semi = NOTE_SEMITONES[name]
    val = (octv - 2) * 12 + semi + 1
    return max(1, min(63, val))


def parse_seq(seq_str):
    tokens = seq_str.replace("|", " ").split()
    return [n_id(tok) for tok in tokens]


def parse_drums(drum_str):
    # K=12 (Kick), S=13 (Snare), H=14 (HiHat), T=15 (Tom/Crash), .=0
    mapping = {"K": 12, "S": 13, "H": 14, "T": 15, ".": 0, "-": 0}
    tokens = drum_str.replace("|", "").replace(" ", "")
    return [mapping[ch.upper()] for ch in tokens]


def build_all_14_songs():
    """
    Returns 14 rich 64-step 5-voice arrangements:
    Each song tuple: (name, timer0_fa, lead_srcn, harm_srcn, lead_str, harm_str, bass_str, pad_str, drum_str)
    """
    return [
        # 1. Track 1 (songs[0]): Title & Intro — RGA2 Heroic 16-Bit Main Theme (142 BPM -> $FA=169)
        (
            "01_title_anthem", 169, 0, 1,
            # Lead (64 steps)
            "A4 - E4 A4 B4 - C5 - | D5 - C5 B4 C5 - A4 - | F4 - C4 F4 G4 - A4 - | B4 - C5 D5 E5 - - . | "
            "A4 - E5 - D5 C5 B4 A4 | G4 - D5 - C5 B4 A4 G4 | F4 - G4 A4 B4 - C5 D5 | E5 - - . A5 - - .",
            # Harmony (64 steps)
            "C4 - A3 C4 D4 - E4 - | F4 - E4 D4 E4 - C4 - | A3 - F3 A3 B3 - C4 - | D4 - E4 F4 G#4 - - . | "
            "C4 - A4 - F4 E4 D4 C4 | B3 - G4 - E4 D4 C4 B3 | A3 - B3 C4 D4 - E4 F4 | G#4 - - . C5 - - .",
            # Slap Bass (64 steps)
            "A2 - A2 A3 A2 - G2 - | F2 - F2 F3 F2 - E2 - | D2 - D2 D3 D2 - C2 - | E2 - E2 E3 E2 F2 G2 G#2 | "
            "A2 - A2 A3 A2 - A2 - | G2 - G2 G3 G2 - G2 - | F2 - F2 F3 G2 - G2 G3 | A2 - E3 - A2 - - .",
            # Chord Pad (64 steps)
            "E3 - - - - - - - | C3 - - - - - - - | A2 - - - - - - - | B2 - - - E3 - - . | "
            "E3 - - - - - - - | D3 - - - - - - - | C3 - - - D3 - - - | E3 - - . A3 - - .",
            # Drums (64 steps)
            "K H S H K K S H | K H S H K K S T | K H S H K K S H | K H S K S S T T | "
            "K H S H K K S H | K H S H K K S T | K H S H K K S H | K S K S T T K .",
        ),
        # 2. Track 2 (songs[1]): Stage 0 Brasil Game Show — Streets Beat-'Em-Up Funk (135 BPM -> $FA=178)
        (
            "02_stage0_bgs", 178, 0, 1,
            # Lead
            "E4 - G4 A4 B4 - D5 - | B4 A4 G4 E4 G4 - - . | A4 - C5 D5 E5 - G5 - | F#5 - E5 D5 E5 - - . | "
            "G5 - E5 - D5 B4 A4 G4 | A4 - B4 D5 E5 - D5 B4 | C5 - B4 A4 G4 - A4 B4 | E4 - - . E5 - - .",
            # Harmony
            "B3 - D4 E4 G4 - B4 - | G4 F#4 E4 B3 D4 - - . | E4 - G4 A4 C5 - E5 - | D#5 - C#5 B4 B4 - - . | "
            "E5 - B4 - B4 G4 F#4 E4 | F#4 - G4 B4 C5 - B4 G4 | A4 - G4 F#4 E4 - F#4 G4 | B3 - - . B4 - - .",
            # Slap Bass
            "E2 . E3 E2 . G2 A2 B2 | E2 . E3 E2 . D3 B2 G2 | A2 . A3 A2 . C3 D3 E3 | B2 . B3 B2 A2 G2 F#2 D2 | "
            "E2 . E3 E2 . G2 A2 B2 | D2 . D3 D2 . F#2 A2 D3 | C2 . C3 C2 B2 . B3 B2 | E2 . B2 D3 E3 - - .",
            # Pad
            "B2 - - - - - - - | B2 - - - - - - - | E3 - - - - - - - | F#3 - - - - - - . | "
            "B2 - - - - - - - | A2 - - - - - - - | G2 - - - F#2 - - - | B2 - - . E3 - - .",
            # Drums
            "K H S H . K S H | K K S H . K S T | K H S H . K S H | K K S K S T T T | "
            "K H S H . K S H | K K S H . K S T | K H S H K H S H | K S K S T T K .",
        ),
        # 3. Track 3 (songs[2]): Stage 1 Estação Central Hub — Arcade Synthwave Groove (128 BPM -> $FA=188)
        (
            "03_stage1_hub", 188, 17, 3,
            # Lead
            "F4 - A4 C5 E5 - C5 A4 | G4 - B4 D5 F5 - D5 B4 | E4 - G4 B4 D5 - B4 G4 | A4 - C5 E5 A5 - G5 E5 | "
            "F5 - E5 C5 A4 - C5 F5 | E5 - D5 B4 G4 - B4 E5 | D5 - C5 A4 B4 - G4 B4 | C5 - - . A4 - - .",
            # Harmony
            "C4 - F4 A4 C5 - A4 F4 | D4 - G4 B4 D5 - B4 G4 | B3 - E4 G4 B4 - G4 E4 | E4 - A4 C5 E5 - E5 C5 | "
            "C5 - C5 A4 F4 - A4 C5 | B4 - B4 G4E4 - G4 B4 | A4 - A4 F4 G4 - D4 G4 | A4 - - . E4 - - .".replace("G4E4", "G4 E4"),
            # Bass
            "F2 - F2 C3 F2 - F2 C3 | G2 - G2 D3 G2 - G2 D3 | E2 - E2 B2 E2 - E2 B2 | A2 - A2 E3 A2 - G2 E2 | "
            "F2 - F2 C3 F2 - F2 C3 | G2 - G2 D3 G2 - G2 D3 | D2 - D2 A2 G2 - G2 D3 | A2 - E3 - A2 - - .",
            # Pad
            "C3 - - - - - - - | D3 - - - - - - - | B2 - - - - - - - | E3 - - - - - - - | "
            "C3 - - - - - - - | D3 - - - - - - - | A2 - - - B2 - - - | E3 - - - - - - .",
            # Drums
            "K H S H K H S H | K H S H K K S H | K H S H K H S H | K H S H K S T T | "
            "K H S H K H S H | K H S H K K S H | K H S H K H S H | K S H S T T K .",
        ),
        # 4. Track 4 (songs[3]): Portal 1 Mega Man X — Opening Stage Central Highway (156 BPM -> $FA=154)
        (
            "04_megaman_x", 154, 16, 1,
            # Lead (Mega Man X Highway Lead Motif)
            "C5 - - D5 D#5 - D5 C5 | A#4 - - C5 D5 - G4 - | G#4 - - A#4 C5 - A#4 G#4 | G4 - - . G4 A#4 B4 D5 | "
            "C5 - - D5 D#5 - F5 G5 | G#5 - G5 F5 G5 - D#5 - | F5 - D#5 D5 D#5 - C5 B4 | C5 - - . C5 - - .",
            # Harmony
            "G4 - - B4 C5 - B4 G4 | F4 - - G#4 A#4 - D4 - | D#4 - - G4 G#4 - G4 D#4 | D4 - - . D4 F4 G4 B4 | "
            "G4 - - B4 C5 - D5 D#5 | F5 - D#5 D5 D#5 - C5 - | D5 - C5 B4 C5 - G4 F4 | G4 - - . G4 - - .",
            # Driving 16th-Note Bass
            "C2 C2 C3 C2 C2 C2 C3 C2 | A#1 A#1 A#2 A#1 A#1 A#1 A#2 A#1 | G#1 G#1 G#2 G#1 G#1 G#1 G#2 G#1 | G1 G1 G2 G1 G2 F2 D2 B1 | "
            "C2 C2 C3 C2 C2 C2 C3 C2 | G#1 G#1 G#2 G#1 A#1 A#1 A#2 A#1 | F2 F2 F3 F2 G2 G2 G3 G2 | C2 - G2 - C3 - - .",
            # Pad
            "G3 - - - - - - - | F3 - - - - - - - | D#3 - - - - - - - | D3 - - - - - - - | "
            "G3 - - - - - - - | D#3 - - - F3 - - - | C3 - - - D3 - - - | G3 - - . G3 - - .",
            # Rock Drums
            "K H S H K K S H | K H S H K K S T | K H S H K K S H | K S K S T T T T | "
            "K H S H K K S H | K H S H K K S T | K H S K K S K S | K T S T K - . .",
        ),
        # 5. Track 5 (songs[4]): Portal 2 TMNT — Big Apple, 3 A.M. / Turtles Theme (154 BPM -> $FA=156)
        (
            "05_tmnt_turtles", 156, 0, 1,
            # Lead
            "G4 - A#4 C5 D5 - F5 - | D5 - C5 A#4 C5 - G4 - | F4 - G4 A#4 C5 - D5 C5 | A#4 - G4 F4 G4 - - . | "
            "G5 - F5 D5 D#5 - D5 C5 | D5 - C5 A#4 C5 - A4 - | A#4 - C5 D5 D#5 - F5 F#5 | G5 - - . G4 - - .",
            # Harmony
            "D4 - F4 G4 A#4 - C5 - | A#4 - G4 F4 G4 - D4 - | C4 - D4 F4 G4 - A#4 G4 | F4 - D4 C4 D4 - - . | "
            "D5 - C5 A#4 C5 - A#4 G#4 | A#4 - G4 F4 G4 - F#4 - | G4 - A4 A#4 C5 - D5 D4 | D5 - - . D4 - - .",
            # Funky Slap Bass
            "G2 . G3 G2 . F2 G2 A#2 | C2 . C3 C2 . G2 A#2 C3 | F2 . F3 F2 . F2 G2 A2 | G2 . G3 G2 F2 D2 C2 A#1 | "
            "D#2 . D#3 D#2 . D#2 G2 A#2 | D2 . D3 D2 . D2 F#2 A2 | C2 . C3 C2 D2 . D3 D2 | G2 - D3 - G2 - - .",
            # Pad
            "D3 - - - - - - - | G3 - - - - - - - | C3 - - - - - - - | D3 - - - - - - . | "
            "A#2 - - - - - - - | A2 - - - - - - - | G2 - - - A2 - - - | D3 - - . D3 - - .",
            # Drums
            "K H S H . K S H | K K S H . K S T | K H S H . K S H | K S K S T T K S | "
            "K H S H K K S H | K H S H K K S T | K H S K K S T T | K T S T K - . .",
        ),
        # 6. Track 6 (songs[5]): Portal 3 Golden Axe — Wilderness Epic March (128 BPM -> $FA=188)
        (
            "06_golden_axe", 188, 17, 1,
            # Lead (Golden Axe Wilderness Theme)
            "A4 - - E4 A4 - B4 C5 | B4 - G4 - E4 - - . | F4 - - C4 F4 - G4 A4 | G#4 - E4 - B4 - - . | "
            "C5 - - B4 A4 - G4 F4 | G4 - E4 - C5 - B4 A4 | F4 - G4 A4 E4 - G#4 B4 | A4 - - - A4 - - .",
            # Harmony
            "E4 - - C4 E4 - G4 A4 | G4 - D4 - B3 - - . | C4 - - A3 C4 - E4 F4 | E4 - B3 - G#4 - - . | "
            "A4 - - G4 F4 - E4 D4 | E4 - C4 - G4 - G4 E4 | D4 - E4 F4 B3 - E4 G#4 | E4 - - - E4 - - .",
            # Marching Bass
            "A2 A2 E3 A2 A2 A2 E3 A2 | G2 G2 D3 G2 E2 E2 B2 E2 | F2 F2 C3 F2 F2 F2 C3 F2 | E2 E2 B2 E2 E2 F2 G2 G#2 | "
            "A2 A2 E3 A2 F2 F2 C3 F2 | C2 C2 G2 C2 C2 C2 G2 C2 | D2 D2 A2 D2 E2 E2 B2 E2 | A2 - E2 - A2 - - .",
            # Pad
            "E3 - - - - - - - | D3 - - - B2 - - . | C3 - - - - - - - | B2 - - - - - - . | "
            "E3 - - - C3 - - - | G3 - - - - - - - | A2 - - - B2 - - - | E3 - - - E3 - - .",
            # War Drums
            "K . K S K . K S | K . K S K S T T | K . K S K . K S | K . K S T T T T | "
            "K H S H K H S H | K H S H K K S T | K . K S K . K S | K T T T K - . .",
        ),
        # 7. Track 7 (songs[6]): Portal 4 Street Fighter II — Ryu's Stage (148 BPM -> $FA=162)
        (
            "07_street_fighter", 162, 0, 1,
            # Lead (Street Fighter II Ryu's Theme)
            "B4 - E5 - F#5 G5 F#5 E5 | D5 - - B4 D5 - E5 F#5 | E5 - - . G5 - F#5 E5 | F#5 - - . B4 - - . | "
            "G5 - F#5 E5 D5 - E5 F#5 | E5 - D5 B4 A4 - B4 D5 | C5 - B4 A4 B4 - D5 F#5 | E5 - - - E5 - - .",
            # Harmony
            "G4 - B4 - D5 E5 D5 B4 | A4 - - F#4 A4 - B4 D5 | C5 - - . E5 - D5 C5 | D#5 - - . F#4 - - . | "
            "E5 - D5 C5 A4 - C5 D5 | B4 - A4 G4 F#4 - G4 A4 | G4 - F#4 E4 F#4 - B4 D#5 | B4 - - - B4 - - .",
            # Driving Octave Bass
            "E2 E3 E2 E3 E2 E3 E2 E3 | D2 D3 D2 D3 D2 D3 D2 D3 | C2 C3 C2 C3 C2 C3 C2 C3 | B1 B2 B1 B2 B1 C2 D2 D#2 | "
            "C2 C3 C2 C3 D2 D3 D2 D3 | E2 E3 E2 E3 D2 D3 D2 D3 | C2 C3 C2 C3 B1 B2 B1 B2 | E2 - B2 - E2 - - .",
            # Pad
            "B2 - - - - - - - | A2 - - - - - - - | G2 - - - - - - - | F#2 - - - - - - . | "
            "G2 - - - A2 - - - | B2 - - - A2 - - - | G2 - - - F#2 - - - | B2 - - - B2 - - .",
            # Drums
            "K H S H K K S H | K H S H K K S T | K H S H K K S H | K S K S T T T T | "
            "K H S H K K S H | K H S H K K S T | K H S H K S K S | K T S T K - . .",
        ),
        # 8. Track 8 (songs[7]): Portal 5 Ninja Gaiden — Act 4-2 Unbreakable Determination (164 BPM -> $FA=146)
        (
            "08_ninja_gaiden", 146, 16, 17,
            # Lead (Fast 16th-note Ninja Lead + Heroic Melody)
            "D5 A4 D5 F5 E5 A4 E5 G5 | F5 D5 A4 F4 G4 A4 C5 C#5 | D5 - F5 - A5 - G5 F5 | E5 - C5 - A4 - - . | "
            "A#4 - D5 - F5 - E5 D5 | C5 - E5 - G5 - F5 E5 | F5 E5 D5 C#5 D5 A4 F4 A4 | D5 - - . D5 - - .",
            # Harmony
            "A4 F4 A4 D5 C#5 E4 C#5 E5 | D5 A4 F4 D4 E4 F4 G4 A4 | A4 - D5 - F5 - E5 D5 | C5 - G4 - E4 - - . | "
            "F4 - A#4 - D5 - C5 A#4 | G4 - C5 - E5 - D5 C5 | D5 C#5 A4 G4 A4 F4 D4 E4 | A4 - - . A4 - - .",
            # Galloping Ninja Bass
            "D2 D2 D3 D2 A1 A1 A2 A1 | D2 D2 D3 D2 C2 C2 C#2 C#2 | D2 D2 D3 D2 D2 D2 D3 D2 | C2 C2 C3 C2 A1 A1 A2 A1 | "
            "A#1 A#1 A#2 A#1 A#1 A#1 A#2 A#1 | C2 C2 C3 C2 C2 C2 C3 C2 | D2 D2 D3 D2 A1 A1 A2 A1 | D2 - A2 - D2 - - .",
            # Pad
            "A2 - - - E3 - - - | A2 - - - G2 - - - | A2 - - - - - - - | G2 - - - E2 - - . | "
            "F2 - - - - - - - | G2 - - - - - - - | A2 - - - E2 - - - | A2 - - . A2 - - .",
            # Double-Time Ninja Drums
            "K S K S K S K T | K S K S K S T T | K H S H K K S H | K H S K S T T T | "
            "K H S H K K S H | K H S H K K S T | K S K S K S T T | K T S T K - . .",
        ),
        # 9. Track 9 (songs[8]): Portal 6 Super Mario — Overworld & Castle Theme (142 BPM -> $FA=169)
        (
            "09_super_mario", 169, 17, 1,
            # Lead (Exact Super Mario Bros. Intro + Main Theme)
            "E5 E5 . E5 . C5 E5 . | G5 - . . G4 - . . | C5 - . G4 . . E4 - | . A4 - B4 . A#4 A4 . | "
            "G4 E5 G5 A5 - F5 G5 . | E5 - C5 D5 B4 - . . | C5 - . G4 . . E4 - | A4 B4 C5 D5 C5 - - .",
            # Harmony (Exact 3rd/6th Harmony)
            "F#4 F#4 . F#4 . E4 F#4 . | B4 - . . B3 - . . | E4 - . C4 . . G3 - | . C4 - D4 . C#4 C4 . | "
            "C4 G4 B4 C5 - A4 B4 . | G4 - E4 F4 D4 - . . | E4 - . C4 . . G3 - | F4 G4 A4 B4 E4 - - .",
            # Bouncy Walking Bass
            "D2 D2 . D2 . D2 D2 . | G2 - . . G2 - . . |G2 - . E2 . . C2 - | . F2 - G2 . F#2 F2 . | "
            "E2 C3 E3 F3 - D3 E3 . | C3 - A2 B2 G2 - . . | G2 - . E2 . . C2 - | F2 G2 G2 G2 C2 - - .",
            # Pad
            "A2 - . A2 . A2 A2 . | D3 - . . G2 - . . | G2 - - - - - - - | C3 - - - - - - . | "
            "C3 - - - - - - - | G2 - - - - - - . | G2 - - - - - - - | F2 - G2 - G2 - - .",
            # Crisp Mario Snare/Hi-Hat Groove
            "S S . S . K S . | K T . . K - . . | K H S H . K S H | K H S H K S T T | "
            "K H S H K K S H | K H S H K S T . | K H S H . K S H | K S K S K - . .",
        ),
        # 10. Track 10 (songs[9]): Portal 7 Battletoads — Ragnarok's Canyon Heavy Rock (152 BPM -> $FA=158)
        (
            "10_battletoads", 158, 16, 0,
            # Lead
            "E4 E5 . E4 D5 - C5 - | B4 - G4 A4 B4 - E4 - | E4 E5 . E4 G5 - F#5 - | E5 - D5 B4 D5 - - . | "
            "A4 A5 . A4 G5 - E5 - | D5 - B4 D5 E5 - B4 - | C5 - B4 A4 G4 - A4 B4 | E4 E5 E4 D5 E5 - - .",
            # Harmony
            "B3 B4 . B3 A4 - G4 - | F#4 - D4 E4 F#4 - B3 - | B3 B4 . B3 D5 - D5 - | B4 - A4 F#4 A4 - - . | "
            "E4 E5 . E4 D5 - B4 - | A4 - G4 A4 B4 - F#4 - | G4 - F#4 E4 D4 - E4 F#4 | B3 B4 B3 A4 B4 - - .",
            # Heavy Rock Bass
            "E2 E2 . E2 D2 - C2 - | B1 - G1 A1 B1 - E2 - | E2 E2 . E2 G2 - D2 - | A2 - A2 G2 F#2 E2 D2 B1 | "
            "A2 A2 . A2 G2 - E2 - |G2 - G2 F#2 E2 - E2 - | C2 - C2 D2 E2 - F#2 G2 | E2 E2 E2 D2 E2 - - .",
            # Pad
            "B2 - - - A2 - G2 - | F#2 - - - B2 - - - | B2 - - - D3 - A2 - | E3 - - - A2 - - . | "
            "E3 - - - D3 - B2 - | A2 - - - B2 - - - | G2 - - - B2 - - - | B2 - - - B2 - - .",
            # Hard Rock Odd-Accent Drums
            "K K . K S - K - | S - K K S - K T | K K . K S - K - | S H S K S T T T | "
            "K H S H K K S H | K H S H K K S T | K H S K K S K S | K K K S K - . .",
        ),
        # 11. Track 11 (songs[10]): Portal 8 YouTube HQ & Final Boss (Ei Spoiled Showdown, 165 BPM -> $FA=145)
        (
            "11_final_boss_tube", 145, 16, 0,
            # Lead
            "F#4 A4 C#5 F#5 F5 C#5 G#4 C#5 | F#5 - G#5 A5 G#5 - F5 - | D5 F#5 A5 D5 E5 G#5 B5 E5 | C#5 - D5 E5 F5 - C#5 - | "
            "F#5 - E5 D5 C#5 - B4 A4 | G#4 - B4 D5 C#5 - F5 - | F#5 F5 C#5 B4 A4 G#4 F5 G#5 | F#5 - - . F#5 - - .",
            # Harmony
            "C#4 F#4 A4 C#5 C#5 G#4 F4 G#4 | C#5 - E5 F#5 E5 - C#5 - | A4 D5 F#5 A4 B4 E5 G#5 B4 | A4 - B4 C#5 C#5 - G#4 - | "
            "D5 - C#5 B4 A4 - G#4 F#4 | F4 - G#4 B4 A4 - C#5 - | C#5 C#5 G#4 F#4 F#4 F4 C#5 F5 | C#5 - - . C#5 - - .",
            # Double-Bass Metal Bassline
            "F#2 F#2 F#3 F#2 C#2 C#2 C#3 C#2 | F#2 F#2 F#3 F#2 C#2 C#2 C#3 C#2 | D2 D2 D3 D2 E2 E2 E3 E2 | C#2 C#2 C#3 C#2 C#2 D2 E2 F2 | "
            "D2 D2 D3 D2 A1 A1 A2 A1 | B1 B1 B2 B1 C#2 C#2 C#3 C#2 | F#2 F#2 E2 E2 D2 D2 C#2 C#2 | F#2 - C#3 - F#2 - - .",
            # Pad
            "C#3 - - - G#2 - - - | C#3 - - - G#2 - - - | A2 - - - B2 - - - | G#2 - - - - - - - | "
            "A2 - - - E2 - - - | F#2 - - - G#2 - - - | C#3 - - - G#2 - - - | C#3 - - . C#3 - - .",
            # Metal Double-Kick Drums
            "K K S K K K S K | K K S K K S T T | K K S K K K S K | K S K S T T T T | "
            "K H S H K K S H | K H S H K K S T | K S K S K S T T | K T S T K - . .",
        ),
        # 12. Track 12 (songs[11]): Victory / Ending & Credits Fanfare (138 BPM -> $FA=174)
        (
            "12_ending_victory", 174, 0, 1,
            # Lead
            "C5 . C5 C5 C5 - G#4 - | A#4 - C5 A#4 C5 - - . | C5 - E5 G5 C6 - B5 G5 | A5 - G5 F5 G5 - - . | "
            "F5 - G5 A5 G5 - E5 C5 | D5 - E5 F5 E5 - C5 - | D5 - E5 F5 G5 - A5 B5 | C6 - - - C6 - - .",
            # Harmony
            "G4 . G4 G4 G4 - D#4 - | F4 - G4 F4 G4 - - . | G4 - C5 E5 G5 - G5 E5 | F5 - E5 D5 E5 - - . | "
            "C5 - E5 F5 E5 - C5 G4 | B4 - C5 D5 C5 - G4 - | A4 - C5 D5 E5 - F5 G5 | E5 - - - E5 - - .",
            # Bass
            "C2 . C2 C2 C2 - G#2 - | A#2 - F2 G2 C2 - G2 - | C2 - C3 C2 E2 - E3 E2 | F2 - F3 F2 G2 - G3 G2 | "
            "F2 - F3 F2 E2 - E3 E2 | D2 - D3 D2 C2 - C3 C2 | F2 - F3 F2 G2 - G3 G2 | C2 - G2 - C2 - - .",
            # Pad
            "G2 . G2 G2 D#3 - - - | F3 - - - G3 - - . | G3 - - - E3 - - - | C3 - - - D3 - - . | "
            "C3 - - - G2 - - - |A2 - - - G2 - - - | C3 - - - D3 - - - | G3 - - - G3 - - .",
            # Drums
            "K . K K S - K - | S - K S K S T T | K H S H K K S H | K H S H K S T T | "
            "K H S H K K S H | K H S H K K S T | K H S K K S T T | K T S T K - . .",
        ),
        # 13. Track 13 (songs[12]): Character Select Screen — Choose Your Retrogamer Funk (136 BPM -> $FA=176)
        (
            "13_char_select", 176, 0, 3,
            # Lead
            "D5 - C5 A4 C5 - D5 - | F5 - E5 D5 C5 - A4 - | G4 - A4 C5 D5 - E5 - | D5 - - . A4 C5 D5 E5 | "
            "F5 - E5 D5 C5 - A4 C5 | D5 - C5 A4 G4 - F4 G4 | A4 - C5 D5 E5 - F5 E5 | D5 - - . D5 - - .",
            # Harmony
            "A4 - G4 F4 G4 - A4 - | C5 - B4 A4 G4 - F4 - | D4 - F4 G4 A4 - C5 - | A4 - - . F4 G4 A4 C5 | "
            "C5 - B4 A4 G4 - F4 G4 | A4 - G4 F4 D4 - C4 D4 | F4 - G4 A4 C#5 - D5 C#5 | A4 - - . A4 - - .",
            # Funky Select Slap Bass
            "D2 . D3 D2 . F2 G2 A2 | G2 . G3 G2 . G2 A2 C3 | C2 . C3 C2 . E2 G2 A2 | D2 . D3 D2 C2 A1 G1 A1 | "
            "A#1 . A#2 A#1 . A#1 C2 D2 | G2 . G3 G2 . G2 A2 A#2 | A2 . A3 A2 A1 . A2 A1 | D2 - A2 - D2 - - .",
            # Pad
            "A2 - - - - - - - | D3 - - - - - - - | G2 - - - - - - - | A2 - - - - - - - | "
            "F2 - - - - - - - | D3 - - - - - - - | E3 - - - - - - - | A2 - - . A2 - - .",
            # Drums
            "K H S H . K S H | K K S H . K S T | K H S H . K S H | K H S K S T T T | "
            "K H S H . K S H | K K S H . K S T | K H S H K S K S | K T S T K - . .",
        ),
        # 14. Track 14 (songs[13]): Stage Boss Battle — 16-Bit Boss Confrontation (162 BPM -> $FA=148)
        (
            "14_boss_battle", 148, 16, 0,
            # Lead
            "C#5 - D5 C#5 G4 - G#4 A4 | C#5 - E5 D5 C#5 - G#4 - | F#4 - G4 F#4 C5 - B4 A4 | G#4 - A4 B4 C5 - C#5 D5 | "
            "E5 - D#5 E5 F#5 - E5 D#5 | E5 - C#5 B4 A4 - G#4 F#4 | G4 - A4 B4 C5 - C#5 D#5 | C#5 - - . C#5 - - .",
            # Harmony
            "G#4 - A4 G#4 D#4 - E4 F#4 | G#4 - B4 A4 G#4 - E4 - | C#4 - D4 C#4 G#4 - F#4 E4 | D#4 - F#4 G#4 G#4 - A4 B4 | "
            "C#5 - B4 C#5 D#5 - C#5 B4 | C#5 - G#4 F#4 E4 - D#4 C#4 | D#4 - F#4 G#4 G#4 - A4 B4 | G#4 - - . G#4 - - .",
            # Aggressive Chromatic Boss Bass
            "C#2 C#2 C#3 C#2 G1 G1 G2 G1 | C#2 C#2 C#3 C#2 G#1 G#1 G#2 G#1 | F#1 F#1 F#2 F#1 F#1 F#1 F#2 F#1 | G#1 G#1 G#2 G#1 G#1 A1 B1 C2 | "
            "C#2 C#2 C#3 C#2 B1 B1 B2 B1 | A1 A1 A2 A1 F#1 F#1 F#2 F#1 | G#1 G#1 G#2 G#1 G#1 G#1 G#2 G#1 | C#2 - G#2 - C#2 - - .",
            # Pad
            "G#2 - - - D#2 - - - | G#2 - - - E2 - - - | C#2 - - - - - - - | D#2 - - - - - - - | "
            "G#2 - - - F#2 - - - | E2 - - - C#2 - - - | D#2 - - - - - - - | G#2 - - . G#2 - - .",
            # Boss Drums
            "K K S K K K S T | K K S K K S T T | K K S K K K S T | K S K S T T T T | "
            "K H S H K K S H | K H S H K K S T | K S K S K S T T | K T S T K - . .",
        ),
    ]


def build_spc700_driver_and_bank():
    """
    Builds the complete SPC700 ARAM image loaded to $0200 in Audio RAM:
      $0200..$04FF : SPC700 Machine Code Driver (6-Voice + Stereo Echo + Dynamic Tempo/Instruments)
      $0500..$0547 : S-DSP Sample Directory (DIR = $05 -> 18 BRR instruments, SFX, and drums)
      $0550..$057F : Per-Song Tempo ($0550), Lead SRCN ($0560), Harmony SRCN ($0570)
      $0580..$05FF : 64-Note 16-Bit S-DSP Pitch Lookup Table (used by Voice 3 Chord Pad)
      $0600..$21FF : 14 Full 64-Step Songs (14 * 512 bytes = $1C00 bytes)
      $2200..end   : 18 BRR Instruments, OpenBOR WAV Sound Effects & 16-Bit Drum Kit
    """
    # 1. Build 18 BRR Samples (0..3 Melodic, 4..11 OpenBOR WAV SFX, 12..15 Drum Kit, 16..17 Extra Leads)
    brr_samples = [
        ("inst_synth_lead", synth_loop_wave_32("synth_lead"),  True),   # 0
        ("inst_warm_brass", synth_loop_wave_32("warm_brass"),  True),   # 1
        ("inst_slap_bass",  synth_loop_wave_32("slap_bass"),   True),   # 2
        ("inst_string_pad", synth_loop_wave_32("string_pad"),  True),   # 3
        ("sfx_punch",       encode_brr(load_wav_mono_pcm16("SOUNDS/punch2.wav", 6000, 1120), False), False),       # 4
        ("sfx_hit",         encode_brr(load_wav_mono_pcm16("SOUNDS/beat1old.wav", 6000, 1440), False), False),     # 5
        ("sfx_jump",        encode_brr(load_wav_mono_pcm16("SOUNDS/jump.wav", 5000, 1280), False), False),         # 6
        ("sfx_special",     encode_brr(load_wav_mono_pcm16("CHARS/Velberan/grito.wav", 5500, 1600), False), False),# 7
        ("sfx_pickup",      encode_brr(load_wav_mono_pcm16("SOUNDS/get.wav", 6000, 1280), False), False),          # 8
        ("sfx_portal",      encode_brr(load_wav_mono_pcm16("SOUNDS/BEEP.WAV", 6000, 1280), False), False),         # 9
        ("sfx_bosshit",     encode_brr(load_wav_mono_pcm16("SOUNDS/0corte.wav", 6000, 1280), False), False),       # 10
        ("sfx_1up",         encode_brr(load_wav_mono_pcm16("SOUNDS/1up.wav", 5000, 1600), False), False),          # 11
        ("drum_kick",       synth_drum_brr("kick"),            False),  # 12
        ("drum_snare",      synth_drum_brr("snare"),           False),  # 13
        ("drum_hihat",      synth_drum_brr("hihat"),           False),  # 14
        ("drum_tom_crash",  synth_drum_brr("tom_crash"),       False),  # 15
        ("inst_rock_gtr",   synth_loop_wave_32("rock_guitar"), True),   # 16
        ("inst_flute_sq",   synth_loop_wave_32("flute_sq"),    True),   # 17
    ]

    # 2. Build 64-Note Pitch Table for 32-sample loop at S-DSP 32kHz (P = freq_hz * 4.096)
    # Note 1 = C2 (65.41 Hz -> P = $010C) .. Note 63 = D7
    note_pitches = [0]
    base_c2 = 65.4064
    for semitone in range(63):
        freq = base_c2 * (2.0 ** (semitone / 12.0))
        p_val = max(0x0104, min(0x3FFF, int(round(freq * 4.096))))
        note_pitches.append(p_val)

    # 3. Compile all 14 64-Step Songs into `song_blob` ($0600..$21FF = 7,168 bytes)
    raw_songs = build_all_14_songs()
    assert len(raw_songs) == 14

    song_tempos = bytearray(16)
    song_lead_srcn = bytearray(16)
    song_harm_srcn = bytearray(16)
    song_blob = bytearray()

    for s_idx, (s_name, tempo_fa, l_src, h_src, l_str, h_str, b_str, p_str, d_str) in enumerate(raw_songs):
        song_tempos[s_idx] = tempo_fa
        song_lead_srcn[s_idx] = l_src
        song_harm_srcn[s_idx] = h_src

        l_notes = parse_seq(l_str)
        h_notes = parse_seq(h_str)
        b_notes = parse_seq(b_str)
        p_notes = parse_seq(p_str)
        d_notes = parse_drums(d_str)

        assert len(l_notes) == 64, f"{s_name} lead len={len(l_notes)}"
        assert len(h_notes) == 64, f"{s_name} harm len={len(h_notes)}"
        assert len(b_notes) == 64, f"{s_name} bass len={len(b_notes)}"
        assert len(p_notes) == 64, f"{s_name} pad len={len(p_notes)}"
        assert len(d_notes) == 64, f"{s_name} drum len={len(d_notes)}"

        for step in range(64):
            # Voice 0 (Lead): 0=Rest ($0000), -1=Sustain ($FFFF), >0=Pitch
            nl = l_notes[step]
            w0 = 0xFFFF if nl == -1 else (0x0000 if nl == 0 else note_pitches[nl])

            # Voice 1 (Harmony): add +2 pitch units of stereo chorus detune!
            nh = h_notes[step]
            w1 = 0xFFFF if nh == -1 else (0x0000 if nh == 0 else (note_pitches[nh] + 2))

            # Voice 2 (Bass):
            nb = b_notes[step]
            w2 = 0xFFFF if nb == -1 else (0x0000 if nb == 0 else note_pitches[nb])

            # Voice 3 (Chord Pad): $FF=Sustain, $00=Rest, ($80 + note*2)=LUT index in $0580..$05FF
            np_ = p_notes[step]
            b6 = 0xFF if np_ == -1 else (0x00 if np_ == 0 else (0x80 + (np_ & 0x3F) * 2))

            # Voice 4 (Drum Kit): 0=None, 12=Kick, 13=Snare, 14=HiHat, 15=Tom/Crash
            b7 = d_notes[step]

            song_blob.extend(struct.pack("<HHHBB", w0, w1, w2, b6, b7))

        print(f"[OK] Compiled 64-Step Song #{s_idx + 1:02d} '{s_name:18s}' (Tempo $FA={tempo_fa}, Lead={l_src}, Harm={h_src})")

    assert len(song_blob) == 14 * 512  # $1C00 bytes ($0600..$21FF)

    # 4. Pack Page $0500..$05FF (Directory + Per-Song Metadata + 64-Note Pitch LUT)
    #    BRR samples start at ARAM $2200!
    page_0500 = bytearray(256)
    brr_blob = bytearray()
    cur_aram = 0x2200
    for idx, (name, data, is_loop) in enumerate(brr_samples):
        start_addr = cur_aram
        loop_addr = cur_aram if is_loop else (cur_aram + len(data) - 9)
        struct.pack_into("<HH", page_0500, idx * 4, start_addr, loop_addr)
        brr_blob.extend(data)
        cur_aram += len(data)
        print(f"[OK] SPC700 BRR #{idx:02d} '{name:15s}': {len(data):4d} bytes @ ARAM ${start_addr:04X}")

    page_0500[0x50:0x60] = song_tempos
    page_0500[0x60:0x70] = song_lead_srcn
    page_0500[0x70:0x80] = song_harm_srcn
    for n_i in range(64):
        struct.pack_into("<H", page_0500, 0x80 + n_i * 2, note_pitches[n_i])

    # 5. Assemble the SPC700 Machine Code Driver at ARAM $0200..$04FF
    code = bytearray()

    def mov_dp_imm(dp, imm):
        code.extend([0x8F, imm & 0xFF, dp & 0xFF])

    def dsp_write_imm(reg, val):
        mov_dp_imm(0xF2, reg)
        mov_dp_imm(0xF3, val)

    # --- Entry Point at $0200 ---
    code.append(0x20)  # CLRP (Direct Page = $0000)
    code.extend([0xCD, 0xEF, 0xBD])  # MOV X, #$EF ; MOV SP, X

    # Initialize S-DSP global registers & Hardware Stereo Echo ($D000..$E7FF):
    dsp_write_imm(0x6C, 0x20)  # FLG: Unmute, disable echo writes briefly while configuring ESA/EDL
    dsp_write_imm(0x4C, 0x00)  # KON = 0
    dsp_write_imm(0x5C, 0xFF)  # KOF = $FF (Key off all voices)
    dsp_write_imm(0x5D, 0x05)  # DIR = $05 ($0500 Sample Directory)
    dsp_write_imm(0x0C, 0x76)  # MVOLL: Master volume L
    dsp_write_imm(0x1C, 0x76)  # MVOLR: Master volume R
    dsp_write_imm(0x3D, 0x00)  # NON: Noise off
    dsp_write_imm(0x2D, 0x00)  # PMON: Pitch mod off

    # Configure Hardware S-DSP Stereo Reverb / Echo (Echo Buffer at ARAM $D000..$E7FF):
    dsp_write_imm(0x6D, 0xD0)  # ESA = $D0 ($D000)
    dsp_write_imm(0x7D, 0x03)  # EDL = $03 (48ms stereo reverb delay)
    dsp_write_imm(0x0D, 0x38)  # EFB = $38 (Warm echo feedback)
    dsp_write_imm(0x2C, 0x22)  # EVOLL = $22
    dsp_write_imm(0x3C, 0x22)  # EVOLR = $22
    # 8-Tap FIR Low-Pass Warm Reverb Filter:
    dsp_write_imm(0x0F, 0x58)  # FIR0
    dsp_write_imm(0x1F, 0x20)  # FIR1
    dsp_write_imm(0x2F, 0x08)  # FIR2
    dsp_write_imm(0x3F, 0x00)  # FIR3
    dsp_write_imm(0x4F, 0x00)  # FIR4
    dsp_write_imm(0x5F, 0x00)  # FIR5
    dsp_write_imm(0x6F, 0x00)  # FIR6
    dsp_write_imm(0x7F, 0x00)  # FIR7
    dsp_write_imm(0x4D, 0x0B)  # EON = $0B (Echo on Voice 0 Lead, Voice 1 Harmony, Voice 3 Pad)
    dsp_write_imm(0x6C, 0x00)  # FLG = $00 (Enable S-DSP Echo Buffer writes!)
    dsp_write_imm(0x5C, 0x00)  # KOF = $00

    # Voice 0: Lead Melody (Panned Left-Center, Natural Musical ADSR)
    dsp_write_imm(0x00, 0x62)  # V0VOLL
    dsp_write_imm(0x01, 0x4A)  # V0VOLR
    dsp_write_imm(0x04, 0x00)  # V0SRCN = 0 (Synth Lead default)
    dsp_write_imm(0x05, 0xFE)  # V0ADSR1 (ADSR on, Attack=14, Decay=7)
    dsp_write_imm(0x06, 0xCA)  # V0ADSR2 (Sustain Level=6, Sustain Decay Rate=10)

    # Voice 1: Harmony / Counter-Melody (Panned Right-Center, Stereo Chorus)
    dsp_write_imm(0x10, 0x3A)  # V1VOLL
    dsp_write_imm(0x11, 0x54)  # V1VOLR
    dsp_write_imm(0x14, 0x01)  # V1SRCN = 1 (Warm Brass default)
    dsp_write_imm(0x15, 0xFE)  # V1ADSR1
    dsp_write_imm(0x16, 0xAC)  # V1ADSR2 (SL=5, SR=12)

    # Voice 2: Punchy 16-Bit FM Slap Bass (Center, Tight Percussive Bass ADSR)
    dsp_write_imm(0x20, 0x6A)  # V2VOLL
    dsp_write_imm(0x21, 0x6A)  # V2VOLR
    dsp_write_imm(0x24, 0x02)  # V2SRCN = 2 (Slap Bass)
    dsp_write_imm(0x25, 0xFF)  # V2ADSR1 (Instant Attack=15, Decay=7)
    dsp_write_imm(0x26, 0x8E)  # V2ADSR2 (SL=4, SR=14 for tight punchy bass!)

    # Voice 3: Lush Stereo Chord Pad (Wide Stereo, Smooth Pad ADSR)
    dsp_write_imm(0x30, 0x36)  # V3VOLL
    dsp_write_imm(0x31, 0x42)  # V3VOLR
    dsp_write_imm(0x34, 0x03)  # V3SRCN = 3 (String/Organ Pad)
    dsp_write_imm(0x35, 0xFC)  # V3ADSR1 (Smooth Attack=12, Decay=7)
    dsp_write_imm(0x36, 0xC8)  # V3ADSR2 (SL=6, SR=8)

    # Voice 4: 16-Bit Arcade Drum Kit (Center, Fixed 16kHz Pitch = $0800)
    dsp_write_imm(0x40, 0x64)  # V4VOLL
    dsp_write_imm(0x41, 0x64)  # V4VOLR
    dsp_write_imm(0x42, 0x00)  # V4PITCHL = $00
    dsp_write_imm(0x43, 0x08)  # V4PITCHH = $08 ($0800 = 16kHz drum sample playback!)
    dsp_write_imm(0x44, 0x0C)  # V4SRCN = 12 (Kick default)
    dsp_write_imm(0x45, 0xFF)  # V4ADSR1
    dsp_write_imm(0x46, 0xE0)  # V4ADSR2 (Full sustain until BRR END block)

    # Voice 5: Dedicated OpenBOR WAV SFX Channel (Loud Center, Fixed 6kHz Pitch = $0600)
    dsp_write_imm(0x50, 0x7F)  # V5VOLL
    dsp_write_imm(0x51, 0x7F)  # V5VOLR
    dsp_write_imm(0x52, 0x00)  # V5PITCHL = $00
    dsp_write_imm(0x53, 0x06)  # V5PITCHH = $06 ($0600 = 6000Hz WAV SFX rate)
    dsp_write_imm(0x54, 0x04)  # V5SRCN = 4 (Punch default)
    dsp_write_imm(0x55, 0xFF)  # V5ADSR1
    dsp_write_imm(0x56, 0xE0)  # V5ADSR2

    # Initialize Zero-Page Sequencer Variables:
    #   $10 : SongPtrLo (0, 8 .. 248)
    #   $11 : SongPtrHi (current page)
    #   $12 : SongBaseHi ($06 + song_idx * 2)
    #   $13 : Last Port 0 (BGM track 1..14)
    #   $14 : Last Port 1 (SFX counter)
    #   $15 : Timer 0 tick accumulator (0..5)
    mov_dp_imm(0x10, 0x00)
    mov_dp_imm(0x11, 0x06)
    mov_dp_imm(0x12, 0x06)
    mov_dp_imm(0x13, 0x00)
    mov_dp_imm(0x14, 0x00)
    mov_dp_imm(0x15, 0x05)  # Trigger Step 0 immediately on first tick

    # Start Timer 0 ($FA = 169 default)
    mov_dp_imm(0xFA, 169)
    mov_dp_imm(0xF1, 0x01)

    # Signal CPU that RGA2 6-Voice Stereo Audio Driver is active: Port 3 ($F7) = $52 ('R')
    mov_dp_imm(0xF7, 0x52)

    # --- Main Sequencer & SFX Loop ---
    loop_addr = 0x0200 + len(code)

    # 1. Check Port 0 ($F4) for new BGM Track ID (1..14):
    bgm_update_blk = bytes([
        0xC4, 0x13,              # MOV $13, A
        0xC4, 0xF4,              # MOV $F4, A (echo ack)
        0x9C,                    # DEC A (song_idx = 0..13)
        0x5D,                    # MOV X, A
        # Load per-song Timer 0 Tempo ($0550+X -> $FA) and restart Timer 0:
        0xF5, 0x50, 0x05,        # MOV A, !$0550+X
        0xC4, 0xFA,              # MOV $FA, A
        0x8F, 0x00, 0xF1,        # MOV $F1, #$00
        0x8F, 0x01, 0xF1,        # MOV $F1, #$01
        # Load per-song Lead Instrument ($0560+X -> V0SRCN $04):
        0xF5, 0x60, 0x05,        # MOV A, !$0560+X
        0x8F, 0x04, 0xF2,        # MOV $F2, #$04
        0xC4, 0xF3,              # MOV $F3, A
        # Load per-song Harmony Instrument ($0570+X -> V1SRCN $14):
        0xF5, 0x70, 0x05,        # MOV A, !$0570+X
        0x8F, 0x14, 0xF2,        # MOV $F2, #$14
        0xC4, 0xF3,              # MOV $F3, A
        # Compute SongBaseHi = $06 + song_idx * 2:
        0x7D,                    # MOV A, X
        0x1C,                    # ASL A
        0x60,                    # CLC
        0x88, 0x06,              # ADC A, #$06
        0xC4, 0x12,              # MOV $12, A (SongBaseHi)
        0xC4, 0x11,              # MOV $11, A (CurrentPageHi)
        0x8F, 0x00, 0x10,        # MOV $10, #$00
        0x8F, 0x05, 0x15,        # MOV $15, #$05 (Play Step 0 immediately!)
    ])
    code.extend([
        0xE4, 0xF4,                        # MOV A, $F4
        0xF0, len(bgm_update_blk) + 8,     # BEQ skip_bgm (ignore 0)
        0x68, 0x0F,                        # CMP A, #$0F (15)
        0xB0, len(bgm_update_blk) + 4,     # BCS skip_bgm (ignore >= 15)
        0x64, 0x13,                        # CMP A, $13
        0xF0, len(bgm_update_blk),         # BEQ skip_bgm
    ])
    code.extend(bgm_update_blk)

    # 2. Check Port 1 ($F5) for new OpenBOR WAV SFX trigger on Voice 5 ($20):
    sfx_update_blk = bytes([
        0xC4, 0x14,        # MOV $14, A
        0xC4, 0xF5,        # MOV $F5, A
        0xE4, 0xF6,        # MOV A, $F6 (SFX Sample ID 4..11)
        0x8F, 0x54, 0xF2,  # MOV $F2, #$54 (V5SRCN)
        0xC4, 0xF3,        # MOV $F3, A
        0x8F, 0x4C, 0xF2,  # MOV $F2, #$4C (KON)
        0x8F, 0x20, 0xF3,  # MOV $F3, #$20 (Key On Voice 5!)
        0x8F, 0x5C, 0xF2,  # MOV $F2, #$5C (KOF)
        0x8F, 0x00, 0xF3,  # MOV $F3, #$00
    ])
    code.extend([
        0xE4, 0xF5,                        # MOV A, $F5
        0xF0, len(sfx_update_blk) + 4,     # BEQ skip_sfx
        0x64, 0x14,                        # CMP A, $14
        0xF0, len(sfx_update_blk),         # BEQ skip_sfx
    ])
    code.extend(sfx_update_blk)

    # 3. Poll Timer 0 ($FD) and accumulate ticks in $15 until >= 5:
    wait_check_pos = len(code)
    rel_to_loop1 = (loop_addr - (0x0200 + wait_check_pos + 4)) & 0xFF
    code.extend([
        0xE4, 0xFD,        # MOV A, $FD
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
        0x8F, 0x00, 0x15,  # MOV $15, #$00
    ])

    # 4. Execute Current 8-Byte Step on Voices 0..4:
    #    $16 = KON_MASK, $17 = KOF_MASK, $18 = PitchLo temp
    code.extend([
        0x8F, 0x00, 0x16,  # MOV $16, #$00 (KON_MASK = 0)
        0x8F, 0x00, 0x17,  # MOV $17, #$00 (KOF_MASK = 0)
        0x8D, 0x00,        # MOV Y, #$00
    ])

    # Helper for Voices 0, 1, 2 (16-bit word in step: $FFFF=Sustain, $0000=Rest, else Pitch)
    for v_idx in range(3):
        bit_mask = 1 << v_idx
        reg_pl = (v_idx << 4) | 0x02
        reg_ph = (v_idx << 4) | 0x03
        # Note branch block (16 bytes):
        note_blk = bytes([
            0x8F, reg_ph, 0xF2,  # MOV $F2, #VxPITCHH
            0xC4, 0xF3,          # MOV $F3, A
            0x8F, reg_pl, 0xF2,  # MOV $F2, #VxPITCHL
            0xE4, 0x18,          # MOV A, $18
            0xC4, 0xF3,          # MOV $F3, A
            0xE4, 0x16,          # MOV A, $16
            0x08, bit_mask,      # OR A, #bit_mask
            0xC4, 0x16,          # MOV $16, A
        ])
        # Rest branch block (8 bytes):
        rest_blk = bytes([
            0xE4, 0x17,          # MOV A, $17
            0x08, bit_mask,      # OR A, #bit_mask
            0xC4, 0x17,          # MOV $17, A
            0x2F, len(note_blk), # BRA voice_done
        ])
        code.extend([
            0xF7, 0x10,                              # MOV A, [$10]+Y (Pitch Lo)
            0xC4, 0x18,                              # MOV $18, A
            0xFC,                                    # INC Y
            0xF7, 0x10,                              # MOV A, [$10]+Y (Pitch Hi)
            0xFC,                                    # INC Y
            0x68, 0xFF,                              # CMP A, #$FF (Sustain?)
            0xF0, len(rest_blk) + len(note_blk) + 4, # BEQ voice_done
            0x68, 0x00,                              # CMP A, #$00 (Rest?)
            0xD0, len(rest_blk),                     # BNE voice_note
        ])
        code.extend(rest_blk)
        code.extend(note_blk)

    # Voice 3 (Byte 6: $FF=Sustain, $00=Rest, else $80+note*2 LUT index at $0580..$05FF):
    v3_note_blk = bytes([
        0x5D,                # MOV X, A
        0x8F, 0x32, 0xF2,    # MOV $F2, #$32 (V3PITCHL)
        0xF5, 0x00, 0x05,    # MOV A, !$0500+X
        0xC4, 0xF3,          # MOV $F3, A
        0x8F, 0x33, 0xF2,    # MOV $F2, #$33 (V3PITCHH)
        0xF5, 0x01, 0x05,    # MOV A, !$0501+X
        0xC4, 0xF3,          # MOV $F3, A
        0xE4, 0x16,          # MOV A, $16
        0x08, 0x08,          # OR A, #$08 (KON bit 3)
        0xC4, 0x16,          # MOV $16, A
    ])
    v3_rest_blk = bytes([
        0xE4, 0x17,              # MOV A, $17
        0x08, 0x08,              # OR A, #$08 (KOF bit 3)
        0xC4, 0x17,              # MOV $17, A
        0x2F, len(v3_note_blk),  # BRA v3_done
    ])
    code.extend([
        0xF7, 0x10,                                  # MOV A, [$10]+Y (Byte 6)
        0xFC,                                        # INC Y
        0x68, 0xFF,                                  # CMP A, #$FF (Sustain?)
        0xF0, len(v3_rest_blk) + len(v3_note_blk) + 4,
        0x68, 0x00,                                  # CMP A, #$00 (Rest?)
        0xD0, len(v3_rest_blk),
    ])
    code.extend(v3_rest_blk)
    code.extend(v3_note_blk)

    # Voice 4 (Byte 7: 0=None, 12..15=Drum Sample ID):
    v4_drum_blk = bytes([
        0x8F, 0x44, 0xF2,    # MOV $F2, #$44 (V4SRCN)
        0xC4, 0xF3,          # MOV $F3, A
        0xE4, 0x16,          # MOV A, $16
        0x08, 0x10,          # OR A, #$10 (KON bit 4)
        0xC4, 0x16,          # MOV $16, A
    ])
    code.extend([
        0xF7, 0x10,          # MOV A, [$10]+Y (Byte 7)
        0xF0, len(v4_drum_blk),
    ])
    code.extend(v4_drum_blk)

    # Apply KOF_MASK ($17) then KON_MASK ($16), then clear KOF:
    code.extend([
        0x8F, 0x5C, 0xF2,    # MOV $F2, #$5C (KOF)
        0xE4, 0x17,          # MOV A, $17
        0xC4, 0xF3,          # MOV $F3, A
        0x8F, 0x4C, 0xF2,    # MOV $F2, #$4C (KON)
        0xE4, 0x16,          # MOV A, $16
        0xC4, 0xF3,          # MOV $F3, A
        0x8F, 0x5C, 0xF2,    # MOV $F2, #$5C (KOF)
        0x8F, 0x00, 0xF3,    # MOV $F3, #$00
    ])

    # Advance 8-byte step across the 2 pages ($12 and $12+1) of the 64-step song:
    code.extend([
        0xE4, 0x10,          # MOV A, $10
        0x60,                # CLC
        0x88, 0x08,          # ADC A, #$08
        0xC4, 0x10,          # MOV $10, A
        0x90, 0x0D,          # BCC step_done (+13 bytes)
        0xE4, 0x11,          # MOV A, $11
        0x64, 0x12,          # CMP A, $12
        0xD0, 0x03,          # BNE wrap_page0 (+3 bytes)
        0xBC,                # INC A (second page: steps 32..63)
        0x2F, 0x02,          # BRA save_page (+2 bytes)
        0xE4, 0x12,          # wrap_page0: MOV A, $12 (first page: steps 0..31)
        0xC4, 0x11,          # save_page: MOV $11, A
        0x5F, loop_addr & 0xFF, (loop_addr >> 8) & 0xFF,  # step_done: JMP !loop_addr
    ])

    print(f"[OK] Assembled SPC700 6-Voice Stereo Driver Code: {len(code)} bytes (max 768 bytes)")
    assert len(code) <= 0x0300, f"SPC700 code exceeded $0300 bytes: {len(code)}"

    # Assemble contiguous ARAM image starting at $0200:
    #   $0200..$04FF : Code ($0300 bytes)
    #   $0500..$05FF : Sample Dir + Metadata + Pitch LUT ($0100 bytes)
    #   $0600..$21FF : 14 Songs * 512B ($1C00 bytes)
    #   $2200..end   : BRR Samples
    aram_img = bytearray()
    aram_img.extend(code)
    while len(aram_img) < 0x0300:
        aram_img.append(0)
    aram_img.extend(page_0500)
    assert len(aram_img) == 0x0400  # $0200 + $0400 = $0600
    aram_img.extend(song_blob)
    assert len(aram_img) == 0x2000  # $0200 + $2000 = $2200
    aram_img.extend(brr_blob)

    out_path = os.path.join(OUT_DIR, "spc700_aram.bin")
    with open(out_path, "wb") as f:
        f.write(aram_img)
    print(f"[OK] Complete SPC700 ARAM Image ($0200..${0x0200 + len(aram_img) - 1:04X}): {len(aram_img)} bytes (${len(aram_img):04X})")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    build_spc700_driver_and_bank()
