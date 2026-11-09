# toporia_core/engine/png.py — write and read PNG images with NumPy alone.
#
# The core writes greyscale density images (records.py, measure.py) and the library a
# colour connectivity picture; neither needs an imaging library for that.  A PNG is a
# signature and three chunks:
#
#     IHDR  width, height, bit depth 8, colour type 0 (grey) or 2 (RGB)
#     IDAT  the zlib-compressed rows, each preceded by a filter byte (0: none)
#     IEND
#
# each chunk being length, type, data and a CRC-32 of type and data (PNG specification,
# ISO/IEC 15948).  read_png reads back exactly what write_png writes (8-bit grey or RGB,
# filter 0 or the standard filters), so a figure can be assembled from saved images
# without matplotlib's or Pillow's readers.

import struct
import zlib

import numpy as np

SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_png(path, pixels):
    """Write an (h, w) uint8 grey image or an (h, w, 3) uint8 RGB image to `path`."""
    pixels = np.ascontiguousarray(pixels, dtype=np.uint8)
    if pixels.ndim == 2:
        colour, channels = 0, 1
    elif pixels.ndim == 3 and pixels.shape[2] == 3:
        colour, channels = 2, 3
    else:
        raise ValueError(f"write_png takes (h, w) or (h, w, 3) pixels, got {pixels.shape}")
    height, width = pixels.shape[:2]
    rows = pixels.reshape(height, width * channels)
    raw = np.hstack([np.zeros((height, 1), np.uint8), rows]).tobytes()      # filter byte 0 per row
    header = struct.pack(">IIBBBBB", width, height, 8, colour, 0, 0, 0)
    with open(path, "wb") as file:
        file.write(SIGNATURE + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(raw, 6))
                   + _chunk(b"IEND", b""))


def read_png(path):
    """Read an 8-bit grey or RGB PNG as uint8 pixels, (h, w) or (h, w, 3)."""
    data = open(path, "rb").read()
    if not data.startswith(SIGNATURE):
        raise ValueError(f"{path} is not a PNG")
    position, compressed, header = len(SIGNATURE), b"", None
    while position < len(data):
        length, kind = struct.unpack(">I4s", data[position:position + 8])
        body = data[position + 8:position + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            compressed += body
        elif kind == b"IEND":
            break
        position += 12 + length
    width, height, depth, colour, _, _, interlace = header
    if depth != 8 or colour not in (0, 2) or interlace:
        raise ValueError(f"{path}: only 8-bit grey or RGB, non-interlaced PNGs are read here")
    channels = 1 if colour == 0 else 3
    stride = width * channels
    raw = np.frombuffer(zlib.decompress(compressed), np.uint8).reshape(height, stride + 1)
    out = np.zeros((height, stride), np.int32)
    for y in range(height):
        kind, line = raw[y, 0], raw[y, 1:].astype(np.int32)
        previous = out[y - 1] if y else np.zeros(stride, np.int32)
        if kind == 0:
            out[y] = line
        elif kind == 2:
            out[y] = (line + previous) % 256
        else:                                  # 1 sub, 3 average, 4 Paeth: byte by byte
            row = np.zeros(stride, np.int32)
            for x in range(stride):
                left = row[x - channels] if x >= channels else 0
                up, corner = previous[x], previous[x - channels] if x >= channels else 0
                if kind == 1:
                    guess = left
                elif kind == 3:
                    guess = (left + up) // 2
                else:
                    p = left + up - corner
                    pa, pb, pc = abs(p - left), abs(p - up), abs(p - corner)
                    guess = left if pa <= pb and pa <= pc else up if pb <= pc else corner
                row[x] = (line[x] + guess) % 256
            out[y] = row
    pixels = out.astype(np.uint8)
    return pixels if channels == 1 else pixels.reshape(height, width, 3)
