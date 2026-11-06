#!/usr/bin/env python3
"""Inspect and decode epos.img (the Melis kernel).

Usage:
    python3 scripts/epos.py info firmware/dump1.bin
    python3 scripts/epos.py decode firmware/dump1.bin [outdir]

The kernel is raw LZMA1: 5 props bytes plus the stream, no size,
no end marker. Decompressed size is 0x58854 and it starts with
"EPOS-IMG". To decode, rebuild a FORMAT_ALONE header.
"""
import lzma
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minfs import get_entries

EXPECTED_SIZE = 0x58854


def kernel_bytes(buf):
    for _p, r in get_entries(buf):
        if r["name"] == "epos.img" and r["type"] != 1:
            return bytes(buf[r["data"]:r["data"] + r["size_a"]]), r
    raise ValueError("epos.img not found")


def decode(buf):
    stored, rec = kernel_bytes(buf)
    props = stored[:5]
    hdr = props + struct.pack("<Q", EXPECTED_SIZE)
    d = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
    out = d.decompress(hdr + stored[5:])
    return out, stored, rec


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("info", "decode"):
        print("usage: epos.py info|decode IMAGE [outdir]")
        sys.exit(2)
    with open(sys.argv[2], "rb") as f:
        buf = f.read()
    out, stored, rec = decode(buf)
    print(f"stored {len(stored)} bytes at {rec['data']:#x}, "
          f"decompressed {len(out)} bytes")
    # Raw starts with a branch instruction (e3 0f 00 ea), then "EPOS-IMG".
    print(f"magic: {out[4:9]!r} (want {b'EPOS-'!r})")
    if sys.argv[1] == "decode":
        outdir = sys.argv[3] if len(sys.argv) > 3 else "extracted"
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, "kernel.raw")
        with open(path, "wb") as f:
            f.write(out)
        print(f"wrote {path}")
    if out[4:9] != b"EPOS-":
        print("BAD: kernel magic mismatch")
        sys.exit(1)
    if len(out) != EXPECTED_SIZE:
        print(f"BAD: size {len(out)} != {EXPECTED_SIZE}")
        sys.exit(1)


if __name__ == "__main__":
    main()
