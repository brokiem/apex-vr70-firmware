#!/usr/bin/env python3
"""AZ10 container for the boot image.

Layout: "AZ10", u32 size, 5 props bytes, raw LZMA1 stream.
The BMP inside is 360x640 32-bit top-down. Props of the stock
image are 5D 00 00 01 00. Keep them when you encode.
"""
import lzma
import struct

MAGIC = b"AZ10"
DEFAULT_PROPS = bytes([0x5D, 0x00, 0x00, 0x01, 0x00])


def decode(data):
    if data[:4] != MAGIC:
        raise ValueError("not AZ10")
    size = struct.unpack_from("<I", data, 4)[0]
    props = bytes(data[8:13])
    hdr = props + struct.pack("<Q", size)
    out = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE).decompress(
        hdr + bytes(data[13:]))
    if len(out) != size:
        raise ValueError("size mismatch")
    return out


def encode(bmp, props5=DEFAULT_PROPS):
    p0 = props5[0]
    pb = p0 // 45
    rem = p0 % 45
    lp = rem // 9
    lc = rem % 9
    dict_size = struct.unpack("<L", bytes(props5[1:5]))[0]
    filt = [{
        "id": lzma.FILTER_LZMA1,
        "dict_size": max(dict_size, 1 << 12),
        "lc": lc, "lp": lp, "pb": pb,
    }]
    raw = lzma.compress(bmp, format=lzma.FORMAT_RAW, filters=filt)
    out = MAGIC + struct.pack("<I", len(bmp)) + bytes(props5) + raw
    if decode(out) != bmp:
        raise ValueError("round-trip failed")
    return out


def make_bmp(width, height, pixels):
    """Build a 32-bit top-down BMP. Pixels are BGRA bytes, top row first."""
    if len(pixels) != width * height * 4:
        raise ValueError("pixel size mismatch")
    header = struct.pack(
        "<2sIHHI", b"BM", 54 + len(pixels), 0, 0, 54)
    info = struct.pack(
        "<IiiHHIIiiII", 40, width, -height, 1, 32, 0,
        len(pixels), 2835, 2835, 0, 0)
    return header + info + pixels


def check_bmp(bmp):
    if bmp[:2] != b"BM":
        raise ValueError("not a BMP")
    w = struct.unpack_from("<i", bmp, 18)[0]
    h = struct.unpack_from("<i", bmp, 22)[0]
    bpp = struct.unpack_from("<H", bmp, 28)[0]
    return w, h, bpp
