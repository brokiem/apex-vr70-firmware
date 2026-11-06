#!/usr/bin/env python3
"""Check or fix eGON checksums (boot0 at 0x0, boot1 at 0x6000).

Usage:
    python3 scripts/egon.py check firmware/dump1.bin
    python3 scripts/egon.py fix build/work.bin

The checksum is the sum of all 32-bit words in the block,
with the checksum field set to 0x5F0A6C39 first.
"""
import struct
import sys

STAMP = 0x5F0A6C39
BOOT0 = 0x0
BOOT1 = 0x6000


def checksum(buf, off):
    length = struct.unpack_from("<I", buf, off + 0x10)[0]
    if length % 4 or off + length > len(buf):
        raise ValueError(f"bad length {length:#x} at {off:#x}")
    block = bytearray(buf[off:off + length])
    struct.pack_into("<I", block, 0xC, STAMP)
    total = sum(struct.unpack(f"<{length // 4}I", bytes(block))) & 0xFFFFFFFF
    return total, length


def check(buf):
    ok = True
    for off in (BOOT0, BOOT1):
        want, length = checksum(buf, off)
        got = struct.unpack_from("<I", buf, off + 0xC)[0]
        status = "ok" if want == got else "BAD"
        if want != got:
            ok = False
        print(f"  {off:#x} len={length:#x} stored={got:#010x} computed={want:#010x} {status}")
    return ok


def fix(buf):
    for off in (BOOT0, BOOT1):
        want, _ = checksum(buf, off)
        struct.pack_into("<I", buf, off + 0xC, want)


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("check", "fix"):
        print("usage: egon.py check|fix IMAGE")
        sys.exit(2)
    path = sys.argv[2]
    with open(path, "rb") as f:
        buf = bytearray(f.read())
    if sys.argv[1] == "check":
        print(f"{path}:")
        ok = check(buf)
        sys.exit(0 if ok else 1)
    fix(buf)
    with open(path, "wb") as f:
        f.write(buf)
    print(f"fixed {path}")
    check(buf)


if __name__ == "__main__":
    main()
