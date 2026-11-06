#!/usr/bin/env python3
"""01 boot logo: replace logo.bmp with an analog TV color-bar test card.

Usage:
    python3 patches/01-boot-logo.py build/work.bin

The replacement is a 360x640 32-bit BMP, AZ10-wrapped the same way
as the stock image. It must fit the 3326-byte slot. The MINFS record
sizes are updated. Nothing else changes.

This patch is self-contained: it builds the BMP itself.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from az10 import DEFAULT_PROPS, encode, decode, make_bmp, check_bmp
from minfs import get_entries

W, H = 360, 640


def test_pattern():
    px = bytearray(W * H * 4)
    bars = [
        (255, 255, 255),
        (255, 255, 0),
        (0, 255, 255),
        (0, 255, 0),
        (255, 0, 255),
        (255, 0, 0),
        (0, 0, 255),
    ]
    for y in range(H):
        bar = min(y * len(bars) // H, len(bars) - 1)
        r, g, b = bars[bar]
        for x in range(W):
            i = (y * W + x) * 4
            px[i:i + 4] = bytes([b, g, r, 255])
    return make_bmp(W, H, px)


def main():
    if len(sys.argv) != 2:
        print("usage: 01-boot-logo.py build/work.bin")
        sys.exit(2)
    path = sys.argv[1]
    bmp = test_pattern()
    assert check_bmp(bmp) == (W, -H, 32), "BMP geometry wrong"
    new = encode(bmp, DEFAULT_PROPS)
    print(f"pattern BMP {len(bmp)} bytes, AZ10 {len(new)} bytes")

    with open(path, "rb") as f:
        buf = bytearray(f.read())
    assert len(buf) == 8 * 1024 * 1024, "not 8 MiB"

    logo = [r for _p, r in get_entries(buf) if r["name"] == "logo.bmp"][0]
    old = bytes(buf[logo["data"]:logo["data"] + logo["size_a"]])
    assert old[:4] == b"AZ10", "stock logo not AZ10"
    if len(new) > logo["size_a"]:
        print(f"refusing: {len(new)} exceeds slot {logo['size_a']}")
        sys.exit(1)

    print(f"record {logo['record']:#x} data {logo['data']:#x} "
          f"old size {logo['size_a']} -> new {len(new)}")
    buf[logo["data"]:logo["data"] + len(new)] = new
    struct.pack_into("<I", buf, logo["record"] + 4, len(new))
    struct.pack_into("<I", buf, logo["record"] + 8, len(new))

    with open(path, "wb") as f:
        f.write(buf)

    # Read back and check.
    buf2 = open(path, "rb").read()
    out = [r for _p, r in get_entries(buf2) if r["name"] == "logo.bmp"][0]
    assert out["size_a"] == len(new)
    assert decode(buf2[out["data"]:out["data"] + out["size_a"]]) == bmp
    assert len(get_entries(buf2)) == 119
    print("boot-logo: read-back ok")


if __name__ == "__main__":
    main()
