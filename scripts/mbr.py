#!/usr/bin/env python3
"""Check or fix the MBR CRC at 0x24000.

Usage:
    python3 scripts/mbr.py check firmware/dump1.bin
    python3 scripts/mbr.py fix build/work.bin

CRC is zlib crc32 of bytes 4..1023, stored little-endian at +0.
"""
import struct
import sys
import zlib

MBR = 0x24000


def crc(buf):
    return zlib.crc32(bytes(buf[MBR + 4:MBR + 0x400])) & 0xFFFFFFFF


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("check", "fix"):
        print("usage: mbr.py check|fix IMAGE")
        sys.exit(2)
    path = sys.argv[2]
    with open(path, "rb") as f:
        buf = bytearray(f.read())
    stored = struct.unpack_from("<I", buf, MBR)[0]
    want = crc(buf)
    if sys.argv[1] == "check":
        ok = stored == want
        print(f"{path}: stored={stored:#010x} computed={want:#010x} {'ok' if ok else 'BAD'}")
        sys.exit(0 if ok else 1)
    struct.pack_into("<I", buf, MBR, want)
    with open(path, "wb") as f:
        f.write(buf)
    print(f"fixed {path}: {stored:#010x} -> {want:#010x}")


if __name__ == "__main__":
    main()
