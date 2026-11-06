#!/usr/bin/env python3
"""Dump the sys_config blob at 0x607C (script.bin format).

Usage:
    python3 scripts/sysconfig.py dump firmware/dump1.bin
    python3 scripts/sysconfig.py get firmware/dump1.bin display.lcd_x

Main entries are 40 bytes: name[32], count, offset (words from blob start).
Sub entries: name[32], offset (words), pattern. Type is pattern >> 16.
"""
import struct
import sys

BLOB = 0x607C


def cstr(raw):
    return raw.split(b"\0")[0].decode("utf-8", "replace")


def parse(buf):
    base = BLOB
    count = struct.unpack_from("<I", buf, base)[0]
    p = base + 16
    matches = []
    for _ in range(count):
        name = cstr(bytes(buf[p:p + 32]))
        n, off_words = struct.unpack_from("<II", buf, p + 32)
        sub = base + off_words * 4
        for _i in range(n):
            sname = cstr(bytes(buf[sub:sub + 32]))
            soff, pattern = struct.unpack_from("<II", buf, sub + 32)
            typ = pattern >> 16
            length = pattern & 0xFFFF
            val_at = base + soff * 4
            if typ == 1:
                val = struct.unpack_from("<I", buf, val_at)[0]
                text = f"{val} ({val:#x})"
            elif typ == 2:
                raw = bytes(buf[val_at:val_at + length])
                text = cstr(raw)
            elif typ == 5:
                text = "null"
            else:
                raw = bytes(buf[val_at:val_at + length * 4])
                text = raw.hex()
            matches.append((f"{name}.{sname}", text, typ))
            sub += 40
        p += 40
    return matches


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("dump", "get"):
        print("usage: sysconfig.py dump|get IMAGE [name]")
        sys.exit(2)
    with open(sys.argv[2], "rb") as f:
        buf = f.read()
    rows = parse(buf)
    print(f"{len(rows)} entries")
    if sys.argv[1] == "dump":
        needle = sys.argv[3] if len(sys.argv) > 3 else ""
        for key, text, _typ in rows:
            if needle and needle not in key:
                continue
            print(f"{key} = {text}")
    else:
        needle = sys.argv[3]
        hits = [(k, t) for k, t, _ in rows if k == needle or needle in k]
        for k, t in hits:
            print(f"{k} = {t}")
        if not hits:
            print("not found")
            sys.exit(1)


if __name__ == "__main__":
    main()
