#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RGA2 (OpenBOR) -> Super Nintendo (SNES) Graphic Asset Converter
Converts OpenBOR GIF87a/GIF89a indexed graphics into:
  - SNES 15-bit BGR555 CGRAM palettes
  - SNES 4bpp planar CHR tilesets (BG1, BG2, OBJ sprites)
  - SNES 2bpp planar CHR HUD font & UI tiles (BG3)
  - SNES 16-bit BG1 (64x32) and BG2 (32x32) tilemaps
  - Pre-interleaved 32x32 SNES OBJ sprite strips for DMA transfer
"""

import os
import struct
import math

DATA_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "build", "assets"))


def resolve_data_path(rel_path):
    """Case-insensitive path resolver relative to OpenBOR data root."""
    rel_path = rel_path.replace("\\", "/").lstrip("/")
    if rel_path.lower().startswith("data/"):
        rel_path = rel_path[5:]
    parts = [p for p in rel_path.split("/") if p]
    cur = DATA_ROOT
    for part in parts:
        if not os.path.isdir(cur):
            return os.path.join(DATA_ROOT, rel_path)
        entries = os.listdir(cur)
        match = None
        for e in entries:
            if e.lower() == part.lower():
                match = e
                break
        if match is None:
            return os.path.join(cur, part)
        cur = os.path.join(cur, match)
    return cur


def decode_gif(path):
    """
    Pure-Python GIF87a/GIF89a decoder.
    Returns (width, height, palette_rgb_list_256, pixels_bytearray, transparent_index).
    In OpenBOR, palette index 0 is always transparent for sprites.
    """
    real_path = resolve_data_path(path) if not os.path.isabs(path) else path
    if not os.path.exists(real_path):
        raise FileNotFoundError(f"GIF not found: {path} -> {real_path}")
    with open(real_path, "rb") as f:
        data = f.read()
    if data[:3] != b"GIF":
        raise ValueError(f"Not a GIF file: {real_path}")

    w, h, flags, bg_idx, _ = struct.unpack("<HHBBB", data[6:13])
    pos = 13
    palette = [(0, 0, 0)] * 256
    if flags & 0x80:
        gct_len = 1 << ((flags & 7) + 1)
        for i in range(gct_len):
            r, g, b = data[pos : pos + 3]
            palette[i] = (r, g, b)
            pos += 3

    trans_idx = 0
    canvas = bytearray(w * h)

    while pos < len(data):
        block_type = data[pos]
        pos += 1
        if block_type == 0x21:  # Extension
            ext_label = data[pos]
            pos += 1
            while pos < len(data):
                sz = data[pos]
                pos += 1
                if sz == 0:
                    break
                if ext_label == 0xF9 and sz >= 4:
                    gce_flags = data[pos]
                    if gce_flags & 1:
                        trans_idx = data[pos + 3]
                pos += sz
        elif block_type == 0x2C:  # Image Descriptor
            ix, iy, iw, ih, iflags = struct.unpack("<HHHHB", data[pos : pos + 9])
            pos += 9
            if iflags & 0x80:
                lct_len = 1 << ((iflags & 7) + 1)
                for i in range(lct_len):
                    r, g, b = data[pos : pos + 3]
                    palette[i] = (r, g, b)
                    pos += 3
            interlaced = bool(iflags & 0x40)
            min_code_size = data[pos]
            pos += 1
            sub_blocks = bytearray()
            while pos < len(data):
                sz = data[pos]
                pos += 1
                if sz == 0:
                    break
                sub_blocks.extend(data[pos : pos + sz])
                pos += sz

            # LZW decompression
            clear_code = 1 << min_code_size
            end_code = clear_code + 1
            code_size = min_code_size + 1
            table = [bytes([i]) for i in range(clear_code)] + [b"", b""]
            bit_pos = 0
            total_bits = len(sub_blocks) * 8
            out = bytearray()
            prev = None
            mask = (1 << code_size) - 1

            while bit_pos + code_size <= total_bits:
                byte_idx = bit_pos >> 3
                shift = bit_pos & 7
                raw = sub_blocks[byte_idx]
                if byte_idx + 1 < len(sub_blocks):
                    raw |= sub_blocks[byte_idx + 1] << 8
                if byte_idx + 2 < len(sub_blocks):
                    raw |= sub_blocks[byte_idx + 2] << 16
                code = (raw >> shift) & mask
                bit_pos += code_size

                if code == clear_code:
                    code_size = min_code_size + 1
                    mask = (1 << code_size) - 1
                    table = [bytes([i]) for i in range(clear_code)] + [b"", b""]
                    prev = None
                    continue
                elif code == end_code:
                    break

                if code < len(table):
                    entry = table[code]
                elif code == len(table) and prev is not None:
                    entry = prev + prev[:1]
                else:
                    break

                out.extend(entry)
                if prev is not None and len(table) < 4096:
                    table.append(prev + entry[:1])
                    if len(table) == (1 << code_size) and code_size < 12:
                        code_size += 1
                        mask = (1 << code_size) - 1
                prev = entry

            # Copy frame into canvas (handle interlace if present)
            if interlaced:
                passes = [(0, 8), (4, 8), (2, 4), (1, 2)]
                src_y = 0
                for start_y, step_y in passes:
                    for y in range(start_y, ih, step_y):
                        if src_y < ih:
                            row_src = out[src_y * iw : (src_y + 1) * iw]
                            src_y += 1
                            cy = iy + y
                            if 0 <= cy < h:
                                for x in range(min(iw, len(row_src))):
                                    cx = ix + x
                                    if 0 <= cx < w:
                                        canvas[cy * w + cx] = row_src[x]
            else:
                for y in range(ih):
                    cy = iy + y
                    if 0 <= cy < h:
                        row_off = y * iw
                        for x in range(iw):
                            cx = ix + x
                            if 0 <= cx < w and row_off + x < len(out):
                                canvas[cy * w + cx] = out[row_off + x]
            break  # First frame decoded
        elif block_type == 0x3B:
            break
        else:
            break

    return w, h, palette, canvas, trans_idx


def rgb_to_bgr555(r, g, b):
    """Convert 8-bit RGB to SNES 15-bit BGR555 word."""
    r5 = (r >> 3) & 0x1F
    g5 = (g >> 3) & 0x1F
    b5 = (b >> 3) & 0x1F
    return (b5 << 10) | (g5 << 5) | r5


def quantize_palette_16(rgb_counts, reserve_zero=True):
    """
    Quantize a histogram of {(r,g,b): count} into 15 colors (+ color 0 = black/transparent).
    Uses iterative median-cut / farthest-point clustering so sprites and backgrounds retain
    both dark outlines and vibrant highlights.
    """
    if not rgb_counts:
        return [(0, 0, 0)] * 16

    target_n = 15 if reserve_zero else 16
    unique_colors = list(rgb_counts.items())
    if len(unique_colors) <= target_n:
        pal = [(0, 0, 0)] if reserve_zero else []
        for c, _ in sorted(unique_colors, key=lambda x: (x[0][0]*3 + x[0][1]*6 + x[0][2])):
            pal.append(c)
        while len(pal) < 16:
            pal.append((0, 0, 0))
        return pal[:16]

    # Sort and split boxes (Median Cut weighted by sqrt(count) so accent colors survive)
    boxes = [[(c, math.sqrt(cnt)) for c, cnt in unique_colors]]
    while len(boxes) < target_n:
        # Pick box with largest color range * weight
        best_idx = -1
        best_score = -1
        best_channel = 0
        for idx, box in enumerate(boxes):
            if len(box) <= 1:
                continue
            rs = [c[0][0] for c in box]
            gs = [c[0][1] for c in box]
            bs = [c[0][2] for c in box]
            dr = max(rs) - min(rs)
            dg = max(gs) - min(gs)
            db = max(bs) - min(bs)
            span = max(dr, dg, db)
            if span == 0:
                continue
            ch = 0 if dr >= dg and dr >= db else (1 if dg >= db else 2)
            score = span * (sum(w for _, w in box) ** 0.35)
            if score > best_score:
                best_score = score
                best_idx = idx
                best_channel = ch
        if best_idx < 0:
            break
        box = boxes.pop(best_idx)
        box.sort(key=lambda x: x[0][best_channel])
        total_w = sum(w for _, w in box)
        acc = 0.0
        split_at = len(box) // 2
        for i, (_, w) in enumerate(box):
            acc += w
            if acc >= total_w * 0.5:
                split_at = max(1, min(len(box) - 1, i))
                break
        boxes.append(box[:split_at])
        boxes.append(box[split_at:])

    pal = [(0, 0, 0)] if reserve_zero else []
    for box in boxes:
        tw = sum(w for _, w in box)
        if tw <= 0:
            pal.append(box[0][0])
        else:
            r = int(round(sum(c[0] * w for c, w in box) / tw))
            g = int(round(sum(c[1] * w for c, w in box) / tw))
            b = int(round(sum(c[2] * w for c, w in box) / tw))
            pal.append((r, g, b))

    # Sort by luminance for clean palette ordering
    if reserve_zero:
        rest = sorted(pal[1:], key=lambda c: c[0] * 3 + c[1] * 6 + c[2])
        pal = [pal[0]] + rest
    else:
        pal.sort(key=lambda c: c[0] * 3 + c[1] * 6 + c[2])

    while len(pal) < 16:
        pal.append((0, 0, 0))
    return pal[:16]


def nearest_color_idx(rgb, pal, start_idx=1):
    """Find nearest palette index >= start_idx."""
    r, g, b = rgb
    best_i = start_idx
    best_d = 1 << 30
    for i in range(start_idx, len(pal)):
        pr, pg, pb = pal[i]
        dr = r - pr
        dg = g - pg
        db = b - pb
        d = dr * dr * 3 + dg * dg * 6 + db * db * 2
        if d < best_d:
            best_d = d
            best_i = i
    return best_i


def encode_tile_4bpp(tile_pixels_64):
    """
    Encode an 8x8 tile (64 values 0..15) into 32-byte SNES 4bpp planar format:
      Bytes 0..15:  Row 0..7 Bitplane 0, Bitplane 1 interleaved per row
      Bytes 16..31: Row 0..7 Bitplane 2, Bitplane 3 interleaved per row
    """
    out = bytearray(32)
    for y in range(8):
        bp0 = 0
        bp1 = 0
        bp2 = 0
        bp3 = 0
        row_off = y * 8
        for x in range(8):
            px = tile_pixels_64[row_off + x] & 0x0F
            bit = 7 - x
            if px & 1:
                bp0 |= 1 << bit
            if px & 2:
                bp1 |= 1 << bit
            if px & 4:
                bp2 |= 1 << bit
            if px & 8:
                bp3 |= 1 << bit
        out[y * 2] = bp0
        out[y * 2 + 1] = bp1
        out[16 + y * 2] = bp2
        out[16 + y * 2 + 1] = bp3
    return bytes(out)


def encode_tile_2bpp(tile_pixels_64):
    """Encode an 8x8 tile (64 values 0..3) into 16-byte SNES 2bpp planar format."""
    out = bytearray(16)
    for y in range(8):
        bp0 = 0
        bp1 = 0
        row_off = y * 8
        for x in range(8):
            px = tile_pixels_64[row_off + x] & 0x03
            bit = 7 - x
            if px & 1:
                bp0 |= 1 << bit
            if px & 2:
                bp1 |= 1 << bit
        out[y * 2] = bp0
        out[y * 2 + 1] = bp1
    return bytes(out)


def encode_palette_bgr555(pal_16):
    """Convert 16 RGB tuples into 32 bytes of little-endian BGR555."""
    out = bytearray()
    for r, g, b in pal_16[:16]:
        out.extend(struct.pack("<H", rgb_to_bgr555(r, g, b)))
    return bytes(out)


def crop_and_scale_sprite_32x32(gif_path, pal_16=None, is_portrait=False):
    """
    Decodes a GIF sprite, finds its non-transparent bounding box,
    and scales/centers it into a 32x32 pixel grid (aligned to bottom-center for characters,
    or center-cropped for portraits).
    If pal_16 is None, returns raw RGB tuple grid + transparency mask for palette quantization.
    """
    w, h, gpal, canvas, trans_idx = decode_gif(gif_path)

    def is_trans(idx):
        return idx == 0 or idx == trans_idx

    xs = []
    ys = []
    for y in range(h):
        row = y * w
        for x in range(w):
            if not is_trans(canvas[row + x]):
                xs.append(x)
                ys.append(y)

    if not xs:
        empty_rgb = [[None] * 32 for _ in range(32)]
        return empty_rgb

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    if is_portrait:
        # In RGA2, portrait1.gif (232x73) has the square character face on the left 44x52 area
        box_w = min(max_x - min_x + 1, 44)
        box_h = min(max_y - min_y + 1, 52)
        max_x = min_x + box_w - 1
        max_y = min_y + box_h - 1
    else:
        box_w = max_x - min_x + 1
        box_h = max_y - min_y + 1

    # Scale into 30x31 max (leaving 1px margin so outlines never clip)
    max_dim = max(box_w, box_h, 1)
    scale = min(30.0 / box_w, 31.0 / box_h)
    # Don't upscale tiny objects (like pizza/projectiles) more than 1.0x
    if max_dim < 28:
        scale = min(scale, 1.0)

    dst_w = max(1, min(32, int(round(box_w * scale))))
    dst_h = max(1, min(32, int(round(box_h * scale))))

    off_x = (32 - dst_w) // 2
    if is_portrait:
        off_y = (32 - dst_h) // 2
    else:
        # Bottom-align character feet to row 31
        off_y = 32 - dst_h

    grid_rgb = [[None] * 32 for _ in range(32)]
    for dy in range(dst_h):
        sy = min_y + int((dy + 0.5) * box_h / dst_h)
        sy = max(min_y, min(max_y, sy))
        for dx in range(dst_w):
            sx = min_x + int((dx + 0.5) * box_w / dst_w)
            sx = max(min_x, min(max_x, sx))
            pidx = canvas[sy * w + sx]
            if not is_trans(pidx):
                grid_rgb[off_y + dy][off_x + dx] = gpal[pidx]

    if pal_16 is None:
        return grid_rgb

    # Map RGB grid to 0..15 indices
    color_cache = {}
    idx_grid = [0] * (32 * 32)
    for y in range(32):
        for x in range(32):
            rgb = grid_rgb[y][x]
            if rgb is not None:
                if rgb not in color_cache:
                    color_cache[rgb] = nearest_color_idx(rgb, pal_16, start_idx=1)
                idx_grid[y * 32 + x] = color_cache[rgb]
    return idx_grid


def pack_strip_4x_32x32(frames_4_idx_grids):
    """
    Packs 4 32x32 indexed grids into a single 2048-byte SNES OBJ VRAM strip!
    In SNES OBJ VRAM, a strip of 4 rows of 16 8x8 tiles (128x32 pixels) has:
      Row ty (0..3) of 8x8 tiles -> 16 tiles across:
         Tiles 0..3   belong to Sprite 0 (tx 0..3)
         Tiles 4..7   belong to Sprite 1 (tx 0..3)
         Tiles 8..11  belong to Sprite 2 (tx 0..3)
         Tiles 12..15 belong to Sprite 3 (tx 0..3)
    """
    assert len(frames_4_idx_grids) == 4
    strip_bytes = bytearray()
    for ty in range(4):  # 4 tile rows (each 8px tall -> 32px tall)
        for spr_i in range(4):  # 4 sprites across (each 4 tiles = 32px wide -> 128px wide)
            grid = frames_4_idx_grids[spr_i]
            for tx in range(4):
                tile_px = [0] * 64
                for py in range(8):
                    sy = ty * 8 + py
                    for px in range(8):
                        sx = tx * 8 + px
                        tile_px[py * 8 + px] = grid[sy * 32 + sx]
                strip_bytes.extend(encode_tile_4bpp(tile_px))
    assert len(strip_bytes) == 2048
    return bytes(strip_bytes)


def build_spritesheet(frame_specs):
    """
    Given a list of (gif_path, is_portrait) of length multiple of 4,
    computes an optimal 16-color BGR555 palette across all frames,
    quantizes each frame into 32x32, and packs them into 2048-byte strips.
    """
    raw_grids = []
    hist = {}
    for path, is_port in frame_specs:
        grid = crop_and_scale_sprite_32x32(path, pal_16=None, is_portrait=is_port)
        raw_grids.append((path, is_port, grid))
        weight = 2 if is_port else 1
        for y in range(32):
            for x in range(32):
                c = grid[y][x]
                if c is not None:
                    hist[c] = hist.get(c, 0) + weight

    pal_16 = quantize_palette_16(hist, reserve_zero=True)
    color_cache = {}
    idx_grids = []
    for _, _, grid in raw_grids:
        idx_grid = [0] * (32 * 32)
        for y in range(32):
            for x in range(32):
                rgb = grid[y][x]
                if rgb is not None:
                    if rgb not in color_cache:
                        color_cache[rgb] = nearest_color_idx(rgb, pal_16, start_idx=1)
                    idx_grid[y * 32 + x] = color_cache[rgb]
        idx_grids.append(idx_grid)

    strips = bytearray()
    for i in range(0, len(idx_grids), 4):
        strips.extend(pack_strip_4x_32x32(idx_grids[i : i + 4]))

    return bytes(strips), encode_palette_bgr555(pal_16)


def convert_background_layer(gif_path, dst_w_tiles, dst_h_tiles, max_unique_tiles, pal_idx_base, num_palettes=2, crop_mode="scroll"):
    """
    Converts an OpenBOR background/panel GIF into SNES 4bpp tiles + tilemap + BGR555 palettes.
    dst_w_tiles: 32 (256px) or 64 (512px)
    dst_h_tiles: 28 (224px visible) padded to 32 rows in SNES tilemap
    Supports multi-palette (num_palettes x 16 colors) and automatic tile deduplication
    so large scrolling panels fit cleanly within max_unique_tiles!
    """
    w, h, gpal, canvas, _ = decode_gif(gif_path)
    dst_w = dst_w_tiles * 8
    dst_h = dst_h_tiles * 8

    # Sample image onto dst_w x dst_h RGB grid
    # For wide stage panels (e.g. 1992x276), take an exciting 768px..1024px representative span
    # scaled smoothly to 512x224 so architectural details, signs, and floors are sharp and recognizable
    if crop_mode == "scroll" and w > dst_w * 2:
        sample_w = min(w, int(dst_w * 1.65))
        start_x = min(max(0, (w - sample_w) // 4), w - sample_w)
    else:
        sample_w = w
        start_x = 0

    rgb_img = [[(0, 0, 0)] * dst_w for _ in range(dst_h)]
    # Sub-divide into num_palettes vertical/regional bands or global quantization
    hist_per_pal = [{} for _ in range(num_palettes)]

    for y in range(dst_h):
        sy = min(h - 1, int(y * h / dst_h))
        row_off = sy * w
        for x in range(dst_w):
            sx = start_x + min(sample_w - 1, int(x * sample_w / dst_w))
            c = gpal[canvas[row_off + sx]]
            rgb_img[y][x] = c
            p_slot = 0 if num_palettes == 1 else min(num_palettes - 1, (y * num_palettes) // dst_h)
            hist_per_pal[p_slot][c] = hist_per_pal[p_slot].get(c, 0) + 1

    palettes = []
    for p_slot in range(num_palettes):
        pal = quantize_palette_16(hist_per_pal[p_slot], reserve_zero=True)
        # Set color 0 of BG0 palette to dark backdrop
        if p_slot == 0 and pal_idx_base == 0:
            pal[0] = (8, 8, 16)
        palettes.append(pal)

    # Extract 8x8 tiles and quantize each tile using the best-matching palette among `palettes`
    raw_tiles = []  # (pal_offset, tuple_of_64_indices)
    for ty in range(dst_h_tiles):
        for tx in range(dst_w_tiles):
            best_p = 0
            best_err = 1 << 60
            best_px = None
            for p_i, pal in enumerate(palettes):
                err = 0
                px_list = [0] * 64
                for py in range(8):
                    for px in range(8):
                        r, g, b = rgb_img[ty * 8 + py][tx * 8 + px]
                        # Find nearest color in pal (including index 1..15)
                        bi = 1
                        bd = 1 << 30
                        for ci in range(1, 16):
                            pr, pg, pb = pal[ci]
                            d = (r - pr) ** 2 * 3 + (g - pg) ** 2 * 6 + (b - pb) ** 2 * 2
                            if d < bd:
                                bd = d
                                bi = ci
                        err += bd
                        px_list[py * 8 + px] = bi
                if err < best_err:
                    best_err = err
                    best_p = p_i
                    best_px = tuple(px_list)
            raw_tiles.append((best_p, best_px))

    # Deduplicate tiles (exact match first, then merge closest tiles if count > max_unique_tiles)
    unique_map = {}
    unique_list = []
    # Always reserve tile 0 as empty (all zeros)
    empty_tile = tuple([0] * 64)
    unique_map[empty_tile] = 0
    unique_list.append(empty_tile)

    tile_assignments = []
    for best_p, px_tup in raw_tiles:
        if px_tup not in unique_map:
            unique_map[px_tup] = len(unique_list)
            unique_list.append(px_tup)
        tile_assignments.append([best_p, unique_map[px_tup], px_tup])

    # If unique_list exceeds max_unique_tiles, select tiles uniformly across the whole screen (top to bottom)
    if len(unique_list) > max_unique_tiles:
        freq = {}
        for _, tid, px_tup in tile_assignments:
            freq[px_tup] = freq.get(px_tup, 0) + 1

        kept_tiles = [empty_tile]
        kept_map = {empty_tile: 0}

        # 1. First keep the top 64 most frequently repeated background tiles
        by_freq = sorted(freq.keys(), key=lambda t: freq[t], reverse=True)
        for px_tup in by_freq[:64]:
            if px_tup not in kept_map and len(kept_tiles) < max_unique_tiles:
                kept_map[px_tup] = len(kept_tiles)
                kept_tiles.append(px_tup)

        # 2. Next, sample uniformly across unique_list (which is in top-to-bottom spatial order!)
        #    so the top, middle, and bottom of the screen all get equal tile representation!
        remaining_candidates = [t for t in unique_list if t not in kept_map]
        slots_left = max_unique_tiles - len(kept_tiles)
        if slots_left > 0 and remaining_candidates:
            n_cand = len(remaining_candidates)
            for i in range(slots_left):
                idx = min(n_cand - 1, int(i * n_cand / slots_left))
                px_tup = remaining_candidates[idx]
                if px_tup not in kept_map:
                    kept_map[px_tup] = len(kept_tiles)
                    kept_tiles.append(px_tup)

        # 3. Map remaining tiles using a 16-point (4x4 sub-block) true RGB feature vector
        tile_pal_map = {}
        for best_p, _, px_tup in tile_assignments:
            if px_tup not in tile_pal_map:
                tile_pal_map[px_tup] = best_p

        def tile_rgb_feat(p_off, t):
            pal = palettes[p_off]
            feat = []
            for by in range(4):
                for bx in range(4):
                    c0 = pal[t[(by * 2) * 8 + (bx * 2)]]
                    c1 = pal[t[(by * 2) * 8 + (bx * 2 + 1)]]
                    c2 = pal[t[(by * 2 + 1) * 8 + (bx * 2)]]
                    c3 = pal[t[(by * 2 + 1) * 8 + (bx * 2 + 1)]]
                    feat.append(c0[0] + c1[0] + c2[0] + c3[0])
                    feat.append(c0[1] + c1[1] + c2[1] + c3[1])
                    feat.append(c0[2] + c1[2] + c2[2] + c3[2])
            return tuple(feat)

        kept_features_by_pal = [[] for _ in range(num_palettes)]
        all_kept_features = []
        for tid, kt in enumerate(kept_tiles):
            kp = tile_pal_map.get(kt, 0)
            kf = tile_rgb_feat(kp, kt)
            kept_features_by_pal[kp].append((tid, kf))
            all_kept_features.append((tid, kf))

        remap_cache = {}
        for item in tile_assignments:
            p_off = item[0]
            px_tup = item[2]
            if px_tup in kept_map:
                item[1] = kept_map[px_tup]
            elif (p_off, px_tup) in remap_cache:
                item[1] = remap_cache[(p_off, px_tup)]
            else:
                f_rgb = tile_rgb_feat(p_off, px_tup)
                cand_list = kept_features_by_pal[p_off] if kept_features_by_pal[p_off] else all_kept_features
                best_tid = 0
                best_d = 1 << 30
                for tid, kf in cand_list:
                    d = sum(abs(f_rgb[k] - kf[k]) for k in range(48))
                    if d < best_d:
                        best_d = d
                        best_tid = tid
                remap_cache[(p_off, px_tup)] = best_tid
                item[1] = best_tid
        unique_list = kept_tiles

    # Encode 4bpp tileset
    chr_bytes = bytearray()
    for px_tup in unique_list:
        chr_bytes.extend(encode_tile_4bpp(px_tup))

    # Encode SNES Tilemap
    # Note: A 64x32 SNES tilemap consists of TWO contiguous 32x32 screens (2048 bytes left + 2048 bytes right)!
    num_screens_x = dst_w_tiles // 32
    tilemap_bytes = bytearray()
    for scr_x in range(num_screens_x):
        for ty in range(32):
            for tx_local in range(32):
                if ty < dst_h_tiles:
                    tx = scr_x * 32 + tx_local
                    p_off, tid, _ = tile_assignments[ty * dst_w_tiles + tx]
                    pal_num = (pal_idx_base + p_off) & 7
                    entry = (pal_num << 10) | (tid & 0x03FF)
                else:
                    entry = 0
                tilemap_bytes.extend(struct.pack("<H", entry))

    pal_bytes = bytearray()
    for pal in palettes:
        pal_bytes.extend(encode_palette_bgr555(pal))

    return bytes(chr_bytes), bytes(tilemap_bytes), bytes(pal_bytes), len(unique_list)


def build_stage_package(bg1_gif, bg2_gif=None, is_scrolling=True):
    """
    Builds a complete 32KB Stage Graphic Package:
      - Combined BG1+BG2 4bpp CHR tileset (up to 512 tiles = 16,384 bytes)
        * Tiles 0..383: BG1 tiles (palettes 0..1)
        * Tiles 384..511: BG2 parallax tiles (palette 2)
      - BG1 Tilemap: 64x32 (4,096 bytes)
      - BG2 Tilemap: 32x32 (2,048 bytes)
      - CGRAM BG Palettes 0..3 (128 bytes)
    Total fixed layout in each Stage Bank ($C4..$D0):
      $0000-$3FFF (16 KB): 4bpp CHR Tiles (512 tiles)
      $4000-$4FFF ( 4 KB): BG1 64x32 Tilemap
      $5000-$57FF ( 2 KB): BG2 32x32 Tilemap
      $5800-$587F (128 B): CGRAM Palettes 0..3 (64 colors)
    """
    w_tiles = 64 if is_scrolling else 32
    chr1, map1, pal1, n1 = convert_background_layer(
        bg1_gif,
        dst_w_tiles=w_tiles,
        dst_h_tiles=28,
        max_unique_tiles=380,
        pal_idx_base=0,
        num_palettes=2,
        crop_mode="scroll" if is_scrolling else "full",
    )
    if not is_scrolling:
        # Duplicate 32x32 screen into second half of 64x32 map
        map1 = map1 + map1

    # Pad chr1 to 384 tiles (384 * 32 = 12,288 bytes)
    chr1_padded = bytearray(chr1)
    while len(chr1_padded) < 384 * 32:
        chr1_padded.extend(b"\x00" * 32)

    if bg2_gif is not None:
        chr2, map2_raw, pal2, n2 = convert_background_layer(
            bg2_gif,
            dst_w_tiles=32,
            dst_h_tiles=28,
            max_unique_tiles=126,
            pal_idx_base=2,
            num_palettes=1,
            crop_mode="full",
        )
        # Offset non-zero tile indices in map2_raw by +384
        map2 = bytearray()
        for i in range(0, len(map2_raw), 2):
            val = struct.unpack("<H", map2_raw[i : i + 2])[0]
            tid = val & 0x03FF
            if tid != 0:
                val = (val & 0xFC00) | ((tid + 384) & 0x03FF)
            map2.extend(struct.pack("<H", val))
    else:
        chr2 = b"\x00" * (128 * 32)
        map2 = b"\x00" * 2048
        pal2 = b"\x00" * 32

    chr2_padded = bytearray(chr2)
    while len(chr2_padded) < 128 * 32:
        chr2_padded.extend(b"\x00" * 32)

    # Combine palettes 0, 1, 2, 3 (4 * 32 = 128 bytes)
    pal_all = bytearray(pal1[:64])
    pal_all.extend(pal2[:32])
    # Palette 3: Extra UI/stage accent palette
    pal3 = [(0, 0, 0), (16, 16, 24), (48, 48, 64), (96, 96, 128),
            (180, 40, 40), (240, 80, 40), (255, 200, 40), (255, 255, 255)] + [(0, 0, 0)] * 8
    pal_all.extend(encode_palette_bgr555(pal3))

    pkg = bytearray()
    pkg.extend(chr1_padded[: 384 * 32])  # $0000..$2FFF
    pkg.extend(chr2_padded[: 128 * 32])  # $3000..$3FFF
    pkg.extend(map1[:4096])              # $4000..$4FFF
    pkg.extend(map2[:2048])              # $5000..$57FF
    pkg.extend(pal_all[:128])            # $5800..$587F
    while len(pkg) < 0x5900:
        pkg.append(0)
    return bytes(pkg), n1


# 8x8 Pixel Arcade Bitmap Font (ASCII 0x20..0x5F + Custom UI Bar & Icon Tiles 0x60..0x7F)
FONT_8X8 = {
    ' ': [0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00],
    '!': [0x18,0x3C,0x3C,0x18,0x18,0x00,0x18,0x00],
    '"': [0x66,0x66,0x24,0x00,0x00,0x00,0x00,0x00],
    '#': [0x6C,0xFE,0x6C,0x6C,0xFE,0x6C,0x00,0x00],
    '$': [0x18,0x7E,0x58,0x7E,0x1A,0x7E,0x18,0x00],
    '%': [0x62,0x64,0x08,0x10,0x26,0x46,0x00,0x00],
    '&': [0x38,0x6C,0x38,0x76,0xDC,0xCC,0x76,0x00],
    "'": [0x18,0x18,0x08,0x00,0x00,0x00,0x00,0x00],
    '(': [0x0C,0x18,0x30,0x30,0x30,0x18,0x0C,0x00],
    ')': [0x30,0x18,0x0C,0x0C,0x0C,0x18,0x30,0x00],
    '*': [0x00,0x66,0x3C,0xFF,0x3C,0x66,0x00,0x00],
    '+': [0x00,0x18,0x18,0x7E,0x18,0x18,0x00,0x00],
    ',': [0x00,0x00,0x00,0x00,0x00,0x18,0x18,0x30],
    '-': [0x00,0x00,0x00,0x7E,0x00,0x00,0x00,0x00],
    '.': [0x00,0x00,0x00,0x00,0x00,0x18,0x18,0x00],
    '/': [0x06,0x0C,0x18,0x30,0x60,0xC0,0x80,0x00],
    '0': [0x3C,0x66,0x6E,0x76,0x66,0x66,0x3C,0x00],
    '1': [0x18,0x38,0x18,0x18,0x18,0x18,0x7E,0x00],
    '2': [0x3C,0x66,0x06,0x1C,0x30,0x66,0x7E,0x00],
    '3': [0x3C,0x66,0x06,0x1C,0x06,0x66,0x3C,0x00],
    '4': [0x0E,0x1E,0x36,0x66,0x7F,0x06,0x0F,0x00],
    '5': [0x7E,0x60,0x7C,0x06,0x06,0x66,0x3C,0x00],
    '6': [0x1C,0x30,0x60,0x7C,0x66,0x66,0x3C,0x00],
    '7': [0x7E,0x66,0x06,0x0C,0x18,0x18,0x18,0x00],
    '8': [0x3C,0x66,0x66,0x3C,0x66,0x66,0x3C,0x00],
    '9': [0x3C,0x66,0x66,0x3E,0x06,0x0C,0x38,0x00],
    ':': [0x00,0x18,0x18,0x00,0x18,0x18,0x00,0x00],
    ';': [0x00,0x18,0x18,0x00,0x18,0x18,0x30,0x00],
    '<': [0x0C,0x18,0x30,0x60,0x30,0x18,0x0C,0x00],
    '=': [0x00,0x00,0x7E,0x00,0x7E,0x00,0x00,0x00],
    '>': [0x30,0x18,0x0C,0x06,0x0C,0x18,0x30,0x00],
    '?': [0x3C,0x66,0x06,0x0C,0x18,0x00,0x18,0x00],
    '@': [0x3C,0x66,0x6E,0x6E,0x60,0x62,0x3C,0x00],
    'A': [0x18,0x3C,0x66,0x66,0x7E,0x66,0x66,0x00],
    'B': [0x7C,0x66,0x66,0x7C,0x66,0x66,0x7C,0x00],
    'C': [0x3C,0x66,0x60,0x60,0x60,0x66,0x3C,0x00],
    'D': [0x78,0x6C,0x66,0x66,0x66,0x6C,0x78,0x00],
    'E': [0x7E,0x60,0x60,0x7C,0x60,0x60,0x7E,0x00],
    'F': [0x7E,0x60,0x60,0x7C,0x60,0x60,0x60,0x00],
    'G': [0x3C,0x66,0x60,0x6E,0x66,0x66,0x3E,0x00],
    'H': [0x66,0x66,0x66,0x7E,0x66,0x66,0x66,0x00],
    'I': [0x3C,0x18,0x18,0x18,0x18,0x18,0x3C,0x00],
    'J': [0x1E,0x0C,0x0C,0x0C,0x6C,0x6C,0x38,0x00],
    'K': [0x66,0x6C,0x78,0x70,0x78,0x6C,0x66,0x00],
    'L': [0x60,0x60,0x60,0x60,0x60,0x66,0x7E,0x00],
    'M': [0x63,0x77,0x7F,0x6B,0x63,0x63,0x63,0x00],
    'N': [0x66,0x76,0x7E,0x7E,0x6E,0x66,0x66,0x00],
    'O': [0x3C,0x66,0x66,0x66,0x66,0x66,0x3C,0x00],
    'P': [0x7C,0x66,0x66,0x7C,0x60,0x60,0x60,0x00],
    'Q': [0x3C,0x66,0x66,0x66,0x6A,0x6C,0x36,0x00],
    'R': [0x7C,0x66,0x66,0x7C,0x6C,0x66,0x66,0x00],
    'S': [0x3C,0x66,0x60,0x3C,0x06,0x66,0x3C,0x00],
    'T': [0x7E,0x5A,0x18,0x18,0x18,0x18,0x3C,0x00],
    'U': [0x66,0x66,0x66,0x66,0x66,0x66,0x3C,0x00],
    'V': [0x66,0x66,0x66,0x66,0x66,0x3C,0x18,0x00],
    'W': [0x63,0x63,0x63,0x6B,0x7F,0x77,0x63,0x00],
    'X': [0x66,0x66,0x3C,0x18,0x3C,0x66,0x66,0x00],
    'Y': [0x66,0x66,0x66,0x3C,0x18,0x18,0x3C,0x00],
    'Z': [0x7E,0x66,0x0C,0x18,0x30,0x66,0x7E,0x00],
    '[': [0x3C,0x30,0x30,0x30,0x30,0x30,0x3C,0x00],
    '\\':[0xC0,0x60,0x30,0x18,0x0C,0x06,0x02,0x00],
    ']': [0x3C,0x0C,0x0C,0x0C,0x0C,0x0C,0x3C,0x00],
    '^': [0x10,0x38,0x6C,0xC6,0x00,0x00,0x00,0x00],
    '_': [0x00,0x00,0x00,0x00,0x00,0x00,0x7E,0x00],
}


def build_bg3_hud_font():
    """
    Generates 128 2bpp 8x8 tiles (2,048 bytes) for BG3 HUD + 4 2bpp palettes (32 bytes):
      Tile $00..$5F: ASCII characters (with 3D drop-shadow in color 1, main body in color 3, highlight in color 2!)
      Tile $60: Empty HUD Bar segment [        ]
      Tile $61: Half HUD Bar segment  [====    ]
      Tile $62: Full HUD Bar segment  [========]
      Tile $63: Heart / Life icon
      Tile $64: Star / Cleared Portal badge
      Tile $65: Right Arrow (GO ->)
      Tile $66: Solid dark HUD backdrop box tile
      Tile $67: Box Horizontal Border
    """
    tiles = bytearray()
    for code in range(0x20, 0x60):
        ch = chr(code)
        rows = FONT_8X8.get(ch, FONT_8X8[' '])
        # Tile 0x00 (' ') is 100% transparent (0); all visible glyphs have solid dark HUD backing (color 1)
        px = [0] * 64 if code == 0x20 else [1] * 64
        # Draw glyph (color 3 on top 3 rows, color 2 on bottom rows for arcade gradient!)
        for y in range(8):
            r = rows[y]
            for x in range(8):
                if r & (1 << (7 - x)):
                    px[y * 8 + x] = 3 if y < 3 else 2
        tiles.extend(encode_tile_2bpp(px))

    # Special UI tiles $40..$47 (at indices 0x40..0x47 in tile table, i.e. ASCII + 0x20 offset or direct tile index)
    # Wait: let's index BG3 tiles directly as 0x00..0x7F where:
    #   Tile 0x00 = ' ' (blank)
    #   Tile 0x01..0x3F = ASCII 0x21..0x5F (so tile_index = ascii_code - 0x20!)
    #   Tile 0x40 = Empty Bar
    #   Tile 0x41 = Half Bar
    #   Tile 0x42 = Full Bar
    #   Tile 0x43 = Heart Icon
    #   Tile 0x44 = Star / Check Icon
    #   Tile 0x45 = Right Arrow Icon
    #   Tile 0x46 = Solid Box Fill (color 1)
    #   Tile 0x47 = Box Top/Bottom Border
    ui_defs = [
        # 0x40 Empty Bar
        [1,1,1,1,1,1,1,1,
         1,0,0,0,0,0,0,1,
         1,0,0,0,0,0,0,1,
         1,0,0,0,0,0,0,1,
         1,0,0,0,0,0,0,1,
         1,0,0,0,0,0,0,1,
         1,1,1,1,1,1,1,1,
         0,0,0,0,0,0,0,0],
        # 0x41 Half Bar
        [1,1,1,1,1,1,1,1,
         1,3,3,3,0,0,0,1,
         1,3,3,3,0,0,0,1,
         1,2,2,2,0,0,0,1,
         1,2,2,2,0,0,0,1,
         1,2,2,2,0,0,0,1,
         1,1,1,1,1,1,1,1,
         0,0,0,0,0,0,0,0],
        # 0x42 Full Bar
        [1,1,1,1,1,1,1,1,
         1,3,3,3,3,3,3,1,
         1,3,3,3,3,3,3,1,
         1,2,2,2,2,2,2,1,
         1,2,2,2,2,2,2,1,
         1,2,2,2,2,2,2,1,
         1,1,1,1,1,1,1,1,
         0,0,0,0,0,0,0,0],
        # 0x43 Heart Icon
        [0,1,1,0,0,1,1,0,
         1,3,3,1,1,3,3,1,
         1,3,2,2,2,2,2,1,
         1,2,2,2,2,2,2,1,
         0,1,2,2,2,2,1,0,
         0,0,1,2,2,1,0,0,
         0,0,0,1,1,0,0,0,
         0,0,0,0,0,0,0,0],
        # 0x44 Star / Check Icon
        [0,0,0,3,3,0,0,0,
         0,0,3,3,3,3,0,0,
         3,3,3,2,2,3,3,3,
         0,3,2,2,2,2,3,0,
         0,0,3,2,2,3,0,0,
         0,3,2,1,1,2,3,0,
         3,2,1,0,0,1,2,3,
         0,0,0,0,0,0,0,0],
        # 0x45 Right Arrow
        [0,0,0,1,1,0,0,0,
         0,0,0,1,3,1,0,0,
         1,1,1,1,3,3,1,0,
         1,3,3,3,2,2,3,1,
         1,2,2,2,2,2,3,1,
         1,1,1,1,2,2,1,0,
         0,0,0,1,2,1,0,0,
         0,0,0,1,1,0,0,0],
        # 0x46 Solid Dark Backing
        [1]*64,
        # 0x47 Gold Border Line
        [1,1,1,1,1,1,1,1,
         3,3,3,3,3,3,3,3,
         2,2,2,2,2,2,2,2,
         1,1,1,1,1,1,1,1,
         0,0,0,0,0,0,0,0,
         0,0,0,0,0,0,0,0,
         0,0,0,0,0,0,0,0,
         0,0,0,0,0,0,0,0],
    ]
    for u in ui_defs:
        u_solid = [1 if v == 0 else v for v in u]
        tiles.extend(encode_tile_2bpp(u_solid))

    while len(tiles) < 128 * 16:
        tiles.extend(b"\x00" * 16)

    # 4 2bpp palettes for BG3 (located at CGRAM $00..$0F in Mode 1!)
    # Wait: in SNES Mode 1, BG3 (2bpp) uses CGRAM indices $00..$1F (4 palettes of 4 colors each)!
    # While BG1 & BG2 (4bpp) use CGRAM indices $00..$7F (8 palettes of 16 colors each)!
    # Notice that if BG1 & BG2 use 4bpp Palettes 2..5 (CGRAM $20..$5F), then CGRAM $00..$1F is 100% dedicated to BG3 2bpp HUD Palettes 0..3 with ZERO palette conflict!
    # Let's verify that!
    # In SNES Mode 1:
    #   - BG3 (2bpp) palettes 0..3 read CGRAM colors $00..$0F (or $00..$1F for palettes 0..7).
    #   - BG1 & BG2 (4bpp) palettes 0..7 read CGRAM colors $00..$7F.
    #   - If BG1 uses 4bpp Palettes 2 & 3 (CGRAM $20..$3F) and BG2 uses 4bpp Palette 4 (CGRAM $40..$4F),
    #     then CGRAM $00..$1F is completely untouched by BG1/BG2 and serves as 4 independent 4-color palettes for BG3 HUD!
    bg3_pals = [
        # BG3 Pal 0: Crisp Arcade Gold/White Text (0=backdrop, 1=black shadow, 2=gold, 3=bright white)
        [(8, 8, 16), (0, 0, 0), (255, 208, 48), (255, 255, 255)],
        # BG3 Pal 1: Player HP Green/Yellow Bar (0=trans, 1=black border, 2=green, 3=lime highlight)
        [(0, 0, 0), (8, 8, 8), (32, 208, 48), (144, 255, 112)],
        # BG3 Pal 2: Player MP Cyan/Blue Bar (0=trans, 1=black border, 2=blue, 3=cyan highlight)
        [(0, 0, 0), (8, 8, 8), (32, 128, 248), (128, 224, 255)],
        # BG3 Pal 3: Boss HP / Alert Red/Orange Bar (0=trans, 1=black border, 2=red, 3=orange/yellow)
        [(0, 0, 0), (8, 8, 8), (224, 32, 32), (255, 160, 48)],
    ]
    pal_bytes = bytearray()
    for p4 in bg3_pals:
        for r, g, b in p4:
            pal_bytes.extend(struct.pack("<H", rgb_to_bgr555(r, g, b)))

    return bytes(tiles), bytes(pal_bytes)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=== RGA2 (OpenBOR) -> SNES Graphic Converter ===")

    # 1. Build BG3 2bpp HUD Font & Palettes
    hud_chr, hud_pal = build_bg3_hud_font()
    with open(os.path.join(OUT_DIR, "hud_2bpp.chr"), "wb") as f:
        f.write(hud_chr)
    with open(os.path.join(OUT_DIR, "hud_2bpp.pal"), "wb") as f:
        f.write(hud_pal)
    print(f"[OK] BG3 HUD Font: {len(hud_chr)} bytes, Palettes: {len(hud_pal)} bytes")

    # 2. Convert the 6 Playable Retrogamers (12 32x32 frames = 6,144 bytes each + 32B palette)
    #    Frame slots:
    #      0: IDLE 1, 1: IDLE 2, 2: WALK 1, 3: WALK 2
    #      4: WALK 3, 5: ATTACK 1, 6: ATTACK 2, 7: ATTACK 3 (Finisher)
    #      8: JUMP, 9: SPECIAL, 10: HURT/FALL, 11: PORTRAIT
    players = [
        ("velberan", [
            ("CHARS/Velberan/s1.gif", False),
            ("CHARS/Velberan/s2.gif", False),
            ("CHARS/Velberan/w1.gif", False),
            ("CHARS/Velberan/w3.gif", False),
            ("CHARS/Velberan/w5.gif", False),
            ("CHARS/Velberan/a2.gif", False),
            ("CHARS/Velberan/a4.gif", False),
            ("CHARS/Velberan/b3.gif", False),
            ("CHARS/Velberan/ja1.gif", False),
            ("CHARS/Velberan/z3.gif", False),
            ("CHARS/Velberan/g1.gif", False),
            ("CHARS/Velberan/portrait1.gif", True),
        ]),
        ("srwilson", [
            ("CHARS/Colonia/s1.gif", False),
            ("CHARS/Colonia/s2.gif", False),
            ("CHARS/Colonia/w1.gif", False),
            ("CHARS/Colonia/w3.gif", False),
            ("CHARS/Colonia/w5.gif", False),
            ("CHARS/Colonia/a2.gif", False),
            ("CHARS/Colonia/a4.gif", False),
            ("CHARS/Colonia/a7.gif", False),
            ("CHARS/Colonia/ja2.gif", False),
            ("CHARS/Colonia/x3.gif", False),
            ("CHARS/Colonia/g1.gif", False),
            ("CHARS/Colonia/portrait1.gif", True),
        ]),
        ("paitroll", [
            ("CHARS/PaiTroll/s1.gif", False),
            ("CHARS/PaiTroll/s2.gif", False),
            ("CHARS/PaiTroll/w1.gif", False),
            ("CHARS/PaiTroll/w3.gif", False),
            ("CHARS/PaiTroll/w5.gif", False),
            ("CHARS/PaiTroll/a2.gif", False),
            ("CHARS/PaiTroll/a4.gif", False),
            ("CHARS/PaiTroll/a6.gif", False),
            ("CHARS/PaiTroll/ja2.gif", False),
            ("CHARS/PaiTroll/z1.gif", False),
            ("CHARS/PaiTroll/g1.gif", False),
            ("CHARS/PaiTroll/portrait1.gif", True),
        ]),
        ("snestalgia", [
            ("CHARS/Snestalgia/s1.gif", False),
            ("CHARS/Snestalgia/s2.gif", False),
            ("CHARS/Snestalgia/w1.gif", False),
            ("CHARS/Snestalgia/w3.gif", False),
            ("CHARS/Snestalgia/w5.gif", False),
            ("CHARS/Snestalgia/a2.gif", False),
            ("CHARS/Snestalgia/a4.gif", False),
            ("CHARS/Snestalgia/a6.gif", False),
            ("CHARS/Snestalgia/ja2.gif", False),
            ("CHARS/Snestalgia/z2.gif", False),
            ("CHARS/Snestalgia/g1.gif", False),
            ("CHARS/Snestalgia/portrait1.gif", True),
        ]),
        ("oldgamer", [
            ("CHARS/OldGamer/s1.gif", False),
            ("CHARS/OldGamer/s2.gif", False),
            ("CHARS/OldGamer/w1.gif", False),
            ("CHARS/OldGamer/w3.gif", False),
            ("CHARS/OldGamer/w5.gif", False),
            ("CHARS/OldGamer/a2.gif", False),
            ("CHARS/OldGamer/a4.gif", False),
            ("CHARS/OldGamer/c3.gif", False),
            ("CHARS/OldGamer/ja2.gif", False),
            ("CHARS/OldGamer/z2.gif", False),
            ("CHARS/OldGamer/g1.gif", False),
            ("CHARS/OldGamer/portrait1.gif", True),
        ]),
        ("monique", [
            ("CHARS/Monique/s1.gif", False),
            ("CHARS/Monique/s2.gif", False),
            ("CHARS/Monique/w1.gif", False),
            ("CHARS/Monique/w3.gif", False),
            ("CHARS/Monique/w5.gif", False),
            ("CHARS/Monique/a2.gif", False),
            ("CHARS/Monique/a4.gif", False),
            ("CHARS/Monique/a6.gif", False),
            ("CHARS/Monique/ja2.gif", False),
            ("CHARS/Monique/z3.gif", False),
            ("CHARS/Monique/g1.gif", False),
            ("CHARS/Monique/portrait1.gif", True),
        ]),
    ]

    all_player_chr = bytearray()
    all_player_pal = bytearray()
    select_portraits_frames = []
    for name, specs in players:
        chr_data, pal_data = build_spritesheet(specs)
        assert len(chr_data) == 6144
        assert len(pal_data) == 32
        all_player_chr.extend(chr_data)
        all_player_pal.extend(pal_data)
        select_portraits_frames.append(specs[11])  # Portrait
        select_portraits_frames.append(specs[0])   # Idle
        print(f"[OK] Player '{name:10s}': {len(chr_data)}B CHR, 32B PAL")

    # Universal FX, Portals & Pickups Strip (4 32x32 frames = 2,048 bytes + 32B palette)
    fx_specs = [
        ("Bgs/tube/p0.gif", False),                # Slot 28 ($1C0): Portal Gate
        ("CHARS/misc/spark_10020-1.gif", False),   # Slot 29 ($1C4): Hit Spark Flash
        ("CHARS/OldGamer/as1.gif", False),         # Slot 30 ($1C8): Special Projectile
        ("CHARS/misc/pizza.gif", False),           # Slot 31 ($1CC): Pizza / Health Item
    ]
    fx_chr, fx_pal = build_spritesheet(fx_specs)

    with open(os.path.join(OUT_DIR, "players.chr"), "wb") as f:
        f.write(all_player_chr)
    with open(os.path.join(OUT_DIR, "players.pal"), "wb") as f:
        f.write(all_player_pal)
    with open(os.path.join(OUT_DIR, "fx_items.chr"), "wb") as f:
        f.write(fx_chr)
    with open(os.path.join(OUT_DIR, "fx_items.pal"), "wb") as f:
        f.write(fx_pal)

    # 3. Convert Stage Enemies (8 32x32 frames = 4,096 bytes each + 32B palette)
    #    Slots: 0:IDLE, 1:WALK1, 2:WALK2, 3:WALK3, 4:ATK1, 5:ATK2, 6:HURT, 7:FALL
    enemies = [
        ("00_thug", [
            ("CHARS/Ethug1/q1.gif", False), ("CHARS/Ethug1/q2.gif", False),
            ("CHARS/Ethug1/q4.gif", False), ("CHARS/Ethug1/q6.gif", False),
            ("CHARS/Ethug1/q14.gif", False), ("CHARS/Ethug1/q15.gif", False),
            ("CHARS/Ethug1/q10.gif", False), ("CHARS/Ethug1/q12.gif", False),
        ]),
        ("01_hub_npc", [
            ("CHARS/EBGS/ara1.gif", False), ("CHARS/EBGS/ara2.gif", False),
            ("CHARS/Celso/b1.gif", False), ("CHARS/Celso/b2.gif", False),
            ("CHARS/misc/te1.gif", False), ("Bgs/tube/youtube0.gif", False),
            ("Bgs/tube/p0.gif", False), ("Bgs/tube/p1.gif", False),
        ]),
        ("02_megathug", [
            ("CHARS/EMegaman1/a5.gif", False), ("CHARS/EMegaman1/a3.gif", False),
            ("CHARS/EMegaman1/a4.gif", False), ("CHARS/EMegaman1/a5.gif", False),
            ("CHARS/EMegaman1/a3.gif", False), ("CHARS/EMegaman1/a4.gif", False),
            ("CHARS/EMegaman1/a3.gif", False), ("CHARS/EMegaman1/a4.gif", False),
        ]),
        ("03_ninja_tmnt", [
            ("CHARS/Eninja/n1.gif", False), ("CHARS/Eninja/n2.gif", False),
            ("CHARS/Eninja/n3.gif", False), ("CHARS/Eninja/n4.gif", False),
            ("CHARS/Eninja/n6.gif", False), ("CHARS/Eninja/n7.gif", False),
            ("CHARS/Eninja/n5.gif", False), ("CHARS/Eninja/n11.gif", False),
        ]),
        ("04_grunt_golden", [
            ("CHARS/Egolden/q1.gif", False), ("CHARS/Egolden/q2.gif", False),
            ("CHARS/Egolden/q3.gif", False), ("CHARS/Egolden/q4.gif", False),
            ("CHARS/Egolden/q6.gif", False), ("CHARS/Egolden/q8.gif", False),
            ("CHARS/Egolden/q11.gif", False), ("CHARS/Egolden/q13.gif", False),
        ]),
        ("05_sf_ryu", [
            ("CHARS/Estreet/r1.gif", False), ("CHARS/Estreet/r2.gif", False),
            ("CHARS/Estreet/r4.gif", False), ("CHARS/Estreet/r6.gif", False),
            ("CHARS/Estreet/r24.gif", False), ("CHARS/Estreet/r26.gif", False),
            ("CHARS/Estreet/r19.gif", False), ("CHARS/Estreet/r21.gif", False),
        ]),
        ("06_ninjag_8bit", [
            ("CHARS/E8bit/q1.gif", False), ("CHARS/E8bit/q2.gif", False),
            ("CHARS/E8bit/q4.gif", False), ("CHARS/E8bit/q6.gif", False),
            ("CHARS/E8bit/q17.gif", False), ("CHARS/E8bit/q19.gif", False),
            ("CHARS/E8bit/q12.gif", False), ("CHARS/E8bit/q14.gif", False),
        ]),
        ("07_mario_goomba", [
            ("CHARS/EMario/a1.gif", False), ("CHARS/EMario/a2.gif", False),
            ("CHARS/EMario/a3.gif", False), ("CHARS/EMario/z1.gif", False),
            ("CHARS/EMario/a4.gif", False), ("CHARS/EMario/a6.gif", False),
            ("CHARS/EMario/a8.gif", False), ("CHARS/EMario/a8.gif", False),
        ]),
        ("08_battle_pig", [
            ("CHARS/EBattle/p1.gif", False), ("CHARS/EBattle/p2.gif", False),
            ("CHARS/EBattle/p3.gif", False), ("CHARS/EBattle/r1.gif", False),
            ("CHARS/EBattle/p4.gif", False), ("CHARS/EBattle/p5.gif", False),
            ("CHARS/EBattle/p6.gif", False), ("CHARS/EBattle/p7.gif", False),
        ]),
        ("09_tube_meme", [
            ("CHARS/EMeme/q1.gif", False), ("CHARS/EMeme/q2.gif", False),
            ("CHARS/EMeme/q4.gif", False), ("CHARS/EMeme/q6.gif", False),
            ("CHARS/EMeme/q10.gif", False), ("CHARS/EMeme/q11.gif", False),
            ("CHARS/EMeme/q13.gif", False), ("CHARS/EMeme/q15.gif", False),
        ]),
    ]

    all_enemy_chr = bytearray()
    all_enemy_pal = bytearray()
    for name, specs in enemies:
        chr_data, pal_data = build_spritesheet(specs)
        assert len(chr_data) == 4096
        all_enemy_chr.extend(chr_data)
        all_enemy_pal.extend(pal_data)
        print(f"[OK] Enemy  '{name:16s}': {len(chr_data)}B CHR, 32B PAL")

    with open(os.path.join(OUT_DIR, "enemies.chr"), "wb") as f:
        f.write(all_enemy_chr)
    with open(os.path.join(OUT_DIR, "enemies.pal"), "wb") as f:
        f.write(all_enemy_pal)

    # 4. Convert Stage Bosses (8 32x32 frames = 4,096 bytes each + 32B palette)
    bosses = [
        ("00_bgsboss", [
            ("CHARS/EBGS/boss1.gif", False), ("CHARS/EBGS/boss2.gif", False),
            ("CHARS/EBGS/boss3.gif", False), ("CHARS/EBGS/boss2.gif", False),
            ("CHARS/EBGS/boss3.gif", False), ("CHARS/EBGS/boss1.gif", False),
            ("CHARS/EBGS/boss2.gif", False), ("CHARS/EBGS/boss3.gif", False),
        ]),
        ("01_hub_portal", [
            ("Bgs/tube/p0.gif", False), ("Bgs/tube/p1.gif", False),
            ("CHARS/misc/te1.gif", False), ("Bgs/tube/youtube0.gif", False),
            ("Bgs/tube/p0.gif", False), ("Bgs/tube/p1.gif", False),
            ("Bgs/tube/p0.gif", False), ("Bgs/tube/p1.gif", False),
        ]),
        ("02_nutellaman", [
            ("CHARS/EMegaman1/z1.gif", False), ("CHARS/EMegaman1/z11.gif", False),
            ("CHARS/EMegaman1/z13.gif", False), ("CHARS/EMegaman1/z15.gif", False),
            ("CHARS/EMegaman1/z23.gif", False), ("CHARS/EMegaman1/z25.gif", False),
            ("CHARS/EMegaman1/z18.gif", False), ("CHARS/EMegaman1/z20.gif", False),
        ]),
        ("03_batman", [
            ("CHARS/Eninja/b1.gif", False), ("CHARS/Eninja/b3.gif", False),
            ("CHARS/Eninja/b5.gif", False), ("CHARS/Eninja/b7.gif", False),
            ("CHARS/Eninja/b13.gif", False), ("CHARS/Eninja/b14.gif", False),
            ("CHARS/Eninja/b2.gif", False), ("CHARS/Eninja/b12.gif", False),
        ]),
        ("04_gigante", [
            ("CHARS/Egolden/aa1.gif", False), ("CHARS/Egolden/aa2.gif", False),
            ("CHARS/Egolden/aa3.gif", False), ("CHARS/Egolden/aa4.gif", False),
            ("CHARS/Egolden/aa5.gif", False), ("CHARS/Egolden/aa7.gif", False),
            ("CHARS/Egolden/aa9.gif", False), ("CHARS/Egolden/aa10.gif", False),
        ]),
        ("05_trank_akuma", [
            ("CHARS/Estreet/t1.gif", False), ("CHARS/Estreet/t2.gif", False),
            ("CHARS/Estreet/t4.gif", False), ("CHARS/Estreet/t6.gif", False),
            ("CHARS/Estreet/t8.gif", False), ("CHARS/Estreet/t9.gif", False),
            ("CHARS/Estreet/t12.gif", False), ("CHARS/Estreet/t15.gif", False),
        ]),
        ("06_zangfake", [
            ("CHARS/E8bit/c1.gif", False), ("CHARS/E8bit/c6.gif", False),
            ("CHARS/E8bit/c8.gif", False), ("CHARS/E8bit/c10.gif", False),
            ("CHARS/E8bit/c3.gif", False), ("CHARS/E8bit/c5.gif", False),
            ("CHARS/E8bit/c2.gif", False), ("CHARS/E8bit/c2.gif", False),
        ]),
        ("07_koopa", [
            ("CHARS/EMario/kond1.gif", False), ("CHARS/EMario/kond2.gif", False),
            ("CHARS/EMario/kond3.gif", False), ("CHARS/EMario/kond4.gif", False),
            ("CHARS/EMario/kond2.gif", False), ("CHARS/EMario/kond4.gif", False),
            ("CHARS/EMario/kond5.gif", False), ("CHARS/EMario/kond5.gif", False),
        ]),
        ("08_ratobig", [
            ("CHARS/EBattle/a1.gif", False), ("CHARS/EBattle/a2.gif", False),
            ("CHARS/EBattle/a3.gif", False), ("CHARS/EBattle/a2.gif", False),
            ("CHARS/EBattle/a8.gif", False), ("CHARS/EBattle/a10.gif", False),
            ("CHARS/EBattle/a12.gif", False), ("CHARS/EBattle/a14.gif", False),
        ]),
        ("09_eispoiled", [
            ("CHARS/ETube/ei01.gif", False), ("CHARS/ETube/ei03.gif", False),
            ("CHARS/ETube/ei05.gif", False), ("CHARS/ETube/ei07.gif", False),
            ("CHARS/ETube/ei09.gif", False), ("CHARS/ETube/ei11.gif", False),
            ("CHARS/ETube/ei12.gif", False), ("CHARS/ETube/ei14.gif", False),
        ]),
    ]

    all_boss_chr = bytearray()
    all_boss_pal = bytearray()
    for name, specs in bosses:
        chr_data, pal_data = build_spritesheet(specs)
        assert len(chr_data) == 4096
        all_boss_chr.extend(chr_data)
        all_boss_pal.extend(pal_data)
        print(f"[OK] Boss   '{name:16s}': {len(chr_data)}B CHR, 32B PAL")

    with open(os.path.join(OUT_DIR, "bosses.chr"), "wb") as f:
        f.write(all_boss_chr)
    with open(os.path.join(OUT_DIR, "bosses.pal"), "wb") as f:
        f.write(all_boss_pal)

    # 5. Convert Full Screens & Stage Backgrounds
    # Note: We assign BG1 to CGRAM Palettes 2 & 3, and BG2 to CGRAM Palette 4 so CGRAM $00..$1F
    # stays 100% free for BG3 2bpp HUD Palettes 0..3!
    # Let's update convert_background_layer call inside build_stage_package or shift palette bits in tilemap by +2!
    screens_and_stages = [
        ("screen_title",   "Bgs/Title.gif",               None,                        False),
        ("screen_select",  "Bgs/Select.gif",              None,                        False),
        ("screen_gameover","Bgs/gameover.gif",            None,                        False),
        ("screen_ending",  "Bgs/complete.gif",            None,                        False),
        ("stage_00_bgs",   "Bgs/bgs/bgs.gif",             "Bgs/rua1/back0.gif",        True),
        ("stage_01_hub",   "Bgs/tube/e1.gif",             "Bgs/tube/tilt0.gif",        True),
        ("stage_02_mega",  "Bgs/megaman1/mega1.gif",      "Bgs/megaman1/mega1back.gif",True),
        ("stage_03_tmnt",  "Bgs/turtle1/rua1.gif",        "Bgs/turtle1/back1.gif",     True),
        ("stage_04_gold",  "Bgs/GoldenAxe1/golden1.gif",  "Bgs/GoldenAxe1/back1.gif",  True),
        ("stage_05_sf",    "Bgs/sf/ryu.gif",              "Bgs/sf/ryuback.gif",        True),
        ("stage_06_ninja", "Bgs/8bit/rua1.gif",           "Bgs/8bit/ninja3.gif",       True),
        ("stage_07_mario", "Bgs/mario1/f2a.gif",          "Bgs/mario1/nuv.gif",        True),
        ("stage_08_toads", "Bgs/battle/sapo00.gif",       "Bgs/battle/sapoback01.gif", True),
        ("stage_09_tube",  "Bgs/tube/hal2.gif",           "Bgs/tube/tubeF.gif",        True),
    ]

    for s_name, bg1_p, bg2_p, scroll in screens_and_stages:
        pkg, n_tiles = build_stage_package_shifted(bg1_p, bg2_p, scroll)
        out_p = os.path.join(OUT_DIR, f"{s_name}.bin")
        with open(out_p, "wb") as f:
            f.write(pkg)
        print(f"[OK] Stage/Screen '{s_name:16s}': {len(pkg)} bytes ({n_tiles} unique BG1 tiles)")


def build_stage_package_shifted(bg1_gif, bg2_gif=None, is_scrolling=True):
    """
    Same as build_stage_package, but assigns:
      - BG1 to 4bpp CGRAM Palettes 2 & 3 (CGRAM $20..$3F)
      - BG2 to 4bpp CGRAM Palette 4      (CGRAM $40..$4F)
    This leaves CGRAM $00..$1F 100% dedicated to BG3 2bpp HUD Palettes 0..3!
    Layout (22,784 bytes = $5900 bytes):
      $0000-$2FFF (12 KB): BG1 4bpp CHR Tiles (384 tiles)
      $3000-$3FFF ( 4 KB): BG2 4bpp CHR Tiles (128 tiles, at tile index 384..511)
      $4000-$4FFF ( 4 KB): BG1 64x32 Tilemap (using Palettes 2 & 3)
      $5000-$57FF ( 2 KB): BG2 32x32 Tilemap (using Palette 4)
      $5800-$587F (128 B): CGRAM Palettes 2, 3, 4, 5 (to be DMA'd to CGRAM word address $20!)
    """
    w_tiles = 64 if is_scrolling else 32
    max_bg1_tiles = 380 if bg2_gif is not None else 508
    chr1, map1, pal1, n1 = convert_background_layer(
        bg1_gif,
        dst_w_tiles=w_tiles,
        dst_h_tiles=28,
        max_unique_tiles=max_bg1_tiles,
        pal_idx_base=2,
        num_palettes=2,
        crop_mode="scroll" if is_scrolling else "full",
    )
    if not is_scrolling:
        map1 = map1 + map1

    chr1_padded = bytearray(chr1)
    if bg2_gif is not None:
        while len(chr1_padded) < 384 * 32:
            chr1_padded.extend(b"\x00" * 32)
        chr2, map2_raw, pal2, n2 = convert_background_layer(
            bg2_gif,
            dst_w_tiles=32,
            dst_h_tiles=28,
            max_unique_tiles=126,
            pal_idx_base=4,
            num_palettes=1,
            crop_mode="full",
        )
        map2 = bytearray()
        for i in range(0, len(map2_raw), 2):
            val = struct.unpack("<H", map2_raw[i : i + 2])[0]
            tid = val & 0x03FF
            if tid != 0:
                val = (val & 0xFC00) | ((tid + 384) & 0x03FF)
            map2.extend(struct.pack("<H", val))
        chr2_padded = bytearray(chr2)
        while len(chr2_padded) < 128 * 32:
            chr2_padded.extend(b"\x00" * 32)
        chr_16kb = chr1_padded[: 384 * 32] + chr2_padded[: 128 * 32]
    else:
        while len(chr1_padded) < 512 * 32:
            chr1_padded.extend(b"\x00" * 32)
        chr_16kb = chr1_padded[: 512 * 32]
        map2 = b"\x00" * 2048
        pal2 = b"\x00" * 32

    pal_all = bytearray(pal1[:64])  # Palettes 2 & 3
    pal_all.extend(pal2[:32])       # Palette 4
    pal5 = [(0, 0, 0)] * 16
    pal_all.extend(encode_palette_bgr555(pal5))  # Palette 5

    pkg = bytearray()
    pkg.extend(chr_16kb[: 512 * 32])     # $0000..$3FFF
    pkg.extend(map1[:4096])              # $4000..$4FFF
    pkg.extend(map2[:2048])              # $5000..$57FF
    pkg.extend(pal_all[:128])            # $5800..$587F
    while len(pkg) < 0x5900:
        pkg.append(0)
    return bytes(pkg), n1


if __name__ == "__main__":
    main()
