#!/usr/bin/env python3
"""Sanity-check a firmware image.

Usage:
    python3 scripts/verify.py firmware/dump1.bin
    python3 scripts/verify.py build/work.bin

Checks size, eGON checksums, MBR CRC, MINFS magic + record count,
and that the kernel decodes. Prints one line per check.
"""
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from egon import checksum as egon_checksum
from minfs import get_entries
from epos import decode as epos_decode

SIZE = 8 * 1024 * 1024
MINFS = 0x24400


def main():
    if len(sys.argv) != 2:
        print("usage: verify.py IMAGE")
        sys.exit(2)
    with open(sys.argv[1], "rb") as f:
        buf = f.read()
    ok = True

    def line(name, good, detail=""):
        nonlocal ok
        if not good:
            ok = False
        print(f"{'ok  ' if good else 'BAD '} {name} {detail}")

    line("size", len(buf) == SIZE, f"{len(buf)} bytes")
    if len(buf) != SIZE:
        sys.exit(1)

    for off in (0x0, 0x6000):
        want, ln = egon_checksum(buf, off)
        got = struct.unpack_from("<I", buf, off + 0xC)[0]
        line(f"egon {off:#x}", want == got, f"len={ln:#x} stored={got:#010x}")

    stored = struct.unpack_from("<I", buf, 0x24000)[0]
    want = zlib.crc32(bytes(buf[0x24004:0x24400])) & 0xFFFFFFFF
    line("mbr-crc", stored == want, f"stored={stored:#010x}")

    line("minfs-magic", buf[MINFS:MINFS + 5] == b"MINFS")
    try:
        entries = get_entries(buf)
        line("minfs-records", len(entries) == 119, f"{len(entries)} entries")
    except Exception as e:
        line("minfs-records", False, str(e))
        entries = []

    if entries:
        names = {r["name"] for _p, r in entries}
        for name in ("epos.img", "ramdisk.iso", "logo.bmp", "app_config.bin"):
            line(f"has {name}", name in names)

    try:
        kernel, _stored, _rec = epos_decode(buf)
        line("epos", kernel[4:9] == b"EPOS-" and len(kernel) == 0x58854,
             f"{len(kernel)} bytes")
    except Exception as e:
        line("epos", False, str(e))

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
