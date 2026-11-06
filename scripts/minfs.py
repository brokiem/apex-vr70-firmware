#!/usr/bin/env python3
"""List, find, and extract MINFS files. Also decodes sectioned modules.

Usage:
    python3 scripts/minfs.py list firmware/dump1.bin [substr]
    python3 scripts/minfs.py find firmware/dump1.bin logo.bmp
    python3 scripts/minfs.py extract firmware/dump1.bin /epos.img extracted/
    python3 scripts/minfs.py module firmware/dump1.bin app_root.axf
    python3 scripts/minfs.py flat firmware/dump1.bin app_root.axf [--force]
    python3 scripts/minfs.py report firmware/dump1.bin app_root.axf [0xff202020]

The MINFS header is at 0x24400. Tables start at 0x24600.
Each record: off, size-a, size-b (u32), reclen (u16), type (u16),
namelen, name. File data is at 0x24400 + off. Type 1 is a directory.

Type 6 (compressed module) records carry namelen (u16) and extlen (u16)
at +0x10, then the name, then extlen bytes of extent entries. Each
extent is 32 bytes: off, rec size, unpack size, section size, 3 reserved,
flags. Flag bit 2 (value 2) means raw LZMA1. A section with rec size 0
has no stored bytes (BSS). Compressed modules are the concatenation
of their decoded sections in stored-data order.
"""
import lzma
import os
import struct
import sys

ROOT = 0x24400
TABLE = 0x24600


def read_rec(buf, p):
    off, sa, sb, rl, ty = struct.unpack_from("<IIIHH", buf, p)
    if rl < 20:
        raise ValueError(f"bad record length at {p:#x}")
    if ty == 6:
        nl, xl = struct.unpack_from("<HH", buf, p + 16)
    else:
        (nl,) = struct.unpack_from("<I", buf, p + 16)
        xl = 0
    name = bytes(buf[p + 20:p + 20 + nl]).split(b"\0")[0].decode("utf-8", "replace")
    ext_off = p + 20 + ((nl + 3) & ~3)
    extents = []
    if ty == 6:
        for i in range(xl // 32):
            vals = struct.unpack_from("<8I", buf, ext_off + i * 32)
            extents.append({
                "off": vals[0], "rec": vals[1], "unpack": vals[2],
                "size": vals[3], "flags": vals[7],
            })
    return {
        "record": p, "off": off, "size_a": sa, "size_b": sb,
        "reclen": rl, "type": ty, "namelen": nl, "extlen": xl,
        "ext_off": ext_off, "extents": extents,
        "name": name, "data": ROOT + off,
    }


def walk(buf, table_off, table_size, prefix):
    out = []
    p = table_off
    end = table_off + table_size
    while p + 20 <= end:
        r = read_rec(buf, p)
        if r["reclen"] == 0:
            break
        path = (prefix + "/" + r["name"]).replace("//", "/")
        out.append((path, r))
        if r["type"] == 1 and r["size_a"] > 0:
            out.extend(walk(buf, ROOT + r["off"], r["size_a"], path))
        p += r["reclen"]
    return out


def get_entries(buf):
    root_size = struct.unpack_from("<I", buf, ROOT + 0x0C)[0]
    return walk(buf, TABLE, root_size, "")


def find_entry(buf, name):
    for _p, r in get_entries(buf):
        if r["name"] == name:
            return r
    raise ValueError(f"{name!r} not found")


def lzma1_decode(blob, expected):
    props = blob[:5]
    pb = props[0] // 45
    rem = props[0] % 45
    lp = rem // 9
    lc = rem % 9
    dict_size = struct.unpack_from("<I", props, 1)[0]
    out = lzma.LZMADecompressor(
        format=lzma.FORMAT_RAW,
        filters=[{"id": lzma.FILTER_LZMA1,
                  "dict_size": max(dict_size, 1 << 12),
                  "lc": lc, "lp": lp, "pb": pb}],
    ).decompress(blob[5:], expected)
    if len(out) != expected:
        raise ValueError("decompressed size mismatch")
    return out


def lzma1_encode(data, props):
    pb = props[0] // 45
    rem = props[0] % 45
    lp = rem // 9
    lc = rem % 9
    dict_size = struct.unpack_from("<I", props, 1)[0]
    raw = lzma.compress(
        data, format=lzma.FORMAT_RAW,
        filters=[{"id": lzma.FILTER_LZMA1,
                  "dict_size": max(dict_size, 1 << 12),
                  "lc": lc, "lp": lp, "pb": pb}])
    return props + raw


def module_flat(buf, rec):
    """Decode a type-6 module. Returns (flat bytes, stored bytes)."""
    stored = bytes(buf[rec["data"]:rec["data"] + rec["size_a"]])
    flat = bytearray()
    for e in sorted(rec["extents"], key=lambda x: (0 if x["rec"] else 1, x["off"])):
        if not e["rec"]:
            continue
        blob = stored[e["off"]:e["off"] + e["rec"]]
        if e["flags"] & 2:
            flat.extend(lzma1_decode(blob, e["unpack"]))
        else:
            if len(blob) != e["unpack"]:
                raise ValueError("raw section size mismatch")
            flat.extend(blob)
    return bytes(flat), stored


def module_rebuild(rec, flat, stored):
    """Rebuild stored bytes for a changed flat image.

    Sections are laid out in original stored order. The new stored
    size must fit the old size_a. Returns (new_stored, new_extents)
    with new_extents in the original record order.
    """
    # Stored order defines the flat slices; keep the record index too.
    order = sorted(
        range(len(rec["extents"])),
        key=lambda i: (0 if rec["extents"][i]["rec"] else 1,
                       rec["extents"][i]["off"]))
    new_extents = [None] * len(rec["extents"])
    new_stored = bytearray()
    pos = 0
    for i in order:
        e = rec["extents"][i]
        ne = dict(e)
        if e["rec"]:
            seg = flat[pos:pos + e["unpack"]]
            if len(seg) != e["unpack"]:
                raise ValueError("flat image too short")
            pos += e["unpack"]
            if e["flags"] & 2:
                blob = lzma1_encode(bytes(seg), stored[e["off"]:e["off"] + 5])
            else:
                blob = bytes(seg)
            ne["off"] = len(new_stored)
            ne["rec"] = len(blob)
            new_stored.extend(blob)
        new_extents[i] = ne
    if pos != len(flat):
        raise ValueError("flat image not fully consumed")
    if len(new_stored) > rec["size_a"]:
        raise ValueError(
            f"rebuilt {len(new_stored)} exceeds slot {rec['size_a']}")
    return bytes(new_stored), new_extents


def flat_path(name):
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return os.path.join("extracted", stem + ".flat")


def setcolor_sites(flat):
    """Find GUI SetColor sites: LDR r1,[r0,#0x1f0] / LDR r0,[pc..] / BLX r1."""
    sites = []
    for off in range(0, len(flat) - 11, 4):
        w0 = struct.unpack_from("<I", flat, off)[0]
        w1 = struct.unpack_from("<I", flat, off + 4)[0]
        w2 = struct.unpack_from("<I", flat, off + 8)[0]
        if w0 != 0xE59011F0 or w2 != 0xE12FFF31:
            continue
        if ((w1 >> 25) & 7) != 2 or ((w1 >> 20) & 1) != 1:
            continue
        if ((w1 >> 16) & 0xF) != 0xF:
            continue
        u = (w1 >> 23) & 1
        imm = w1 & 0xFFF
        pool = off + 4 + 8 + (imm if u else -imm)
        if not 0 <= pool < len(flat) - 3:
            continue
        color = struct.unpack_from("<I", flat, pool)[0]
        sites.append({"site": off, "pool": pool, "color": color})
    return sites


def report_lines(buf, rec):
    flat, stored = module_flat(buf, rec)
    lines = []
    lines.append(f"{rec['name']}: stored {len(stored)} flat {len(flat)}")
    lines.append(f"record {rec['record']:#x} data {rec['data']:#x} "
                 f"size_a {rec['size_a']:#x} size_b {rec['size_b']:#x}")
    for i, e in enumerate(rec["extents"]):
        lines.append(f"  section {i}: off={e['off']:#x} rec={e['rec']:#x} "
                     f"unpack={e['unpack']:#x} flags={e['flags']:#x}")
    sites = setcolor_sites(flat)
    from collections import Counter
    counts = Counter(s["color"] for s in sites)
    lines.append(f"SetColor sites: {len(sites)}")
    for color, n in counts.most_common():
        lines.append(f"  {color:#010x} x{n}")
    return flat, lines, sites


def rect_look(flat, site):
    """MOV immediates just before a site, decoded from raw words."""
    out = []
    for off in range(max(0, site - 160), site, 4):
        w = struct.unpack_from("<I", flat, off)[0]
        if (w & 0x0FF00000) == 0x03A00000 and (w >> 28) == 0xE:
            imm8 = w & 0xFF
            rot = ((w >> 8) & 0xF) * 2
            imm = ((imm8 >> rot) | ((imm8 << (32 - rot)) & 0xFFFFFFFF)) & 0xFFFFFFFF if rot else imm8
            rd = (w >> 12) & 0xF
            out.append(f"  {off:#x} MOV r{rd}, #{imm:#x}")
    return "\n".join(out[-8:]) if out else "  (no mov immediates)"


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in (
            "list", "find", "extract", "module", "flat", "report"):
        print("usage: minfs.py list|find|extract|module|flat|report "
              "IMAGE [arg ...]")
        sys.exit(2)
    path = sys.argv[2]
    with open(path, "rb") as f:
        buf = f.read()
    if buf[ROOT:ROOT + 5] != b"MINFS":
        print("bad MINFS magic")
        sys.exit(1)
    entries = get_entries(buf)
    if sys.argv[1] == "list":
        needle = sys.argv[3] if len(sys.argv) > 3 else ""
        for p, r in entries:
            if needle and needle not in p:
                continue
            kind = "dir" if r["type"] == 1 else "file"
            print(f"{r['record']:#x} {kind:4} type={r['type']} "
                  f"size={r['size_a']:#x} data={r['data']:#x} {p}")
        print(f"{len(entries)} entries")
    elif sys.argv[1] == "find":
        needle = sys.argv[3]
        hits = [(p, r) for p, r in entries if needle in p or needle in r["name"]]
        for p, r in hits:
            print(f"{p} record={r['record']:#x} data={r['data']:#x} "
                  f"size_a={r['size_a']:#x} size_b={r['size_b']:#x} type={r['type']}")
        if not hits:
            print("not found")
            sys.exit(1)
    elif sys.argv[1] == "module":
        rec = find_entry(buf, sys.argv[3])
        if rec["type"] != 6:
            print("not a type-6 module")
            sys.exit(1)
        flat, stored = module_flat(buf, rec)
        print(f"{rec['name']}: stored {len(stored)} -> flat {len(flat)}")
        for i, e in enumerate(rec["extents"]):
            print(f"  section {i}: off={e['off']:#x} rec={e['rec']:#x} "
                  f"unpack={e['unpack']:#x} flags={e['flags']:#x}")
    elif sys.argv[1] == "flat":
        rec = find_entry(buf, sys.argv[3])
        if rec["type"] != 6:
            print("not a type-6 module")
            sys.exit(1)
        out = flat_path(rec["name"])
        if len(sys.argv) > 4 and sys.argv[4] != "--force":
            out = sys.argv[4]
        force = "--force" in sys.argv[4:]
        if os.path.exists(out) and not force:
            print(f"exists: {out} (use --force to overwrite)")
            sys.exit(0)
        flat, _stored = module_flat(buf, rec)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(flat)
        print(f"wrote {out} ({len(flat)} bytes)")
    elif sys.argv[1] == "report":
        rec = find_entry(buf, sys.argv[3])
        if rec["type"] != 6:
            print("not a type-6 module")
            sys.exit(1)
        want = 0xFF202020
        if len(sys.argv) > 4:
            want = int(sys.argv[4], 0)
        flat, header, sites = report_lines(buf, rec)
        for line in header:
            print(line)
        hits = [s for s in sites if s["color"] == want]
        print(f"colour {want:#010x} sites: {len(hits)}")
        for s in hits:
            print(f"  @{s['site']:#x} pool {s['pool']:#x}")
            print(rect_look(flat, s["site"]))
    else:
        target = sys.argv[3]
        outdir = sys.argv[4] if len(sys.argv) > 4 else "extracted"
        hits = [(p, r) for p, r in entries if p == target or target in r["name"]]
        if not hits:
            print("not found")
            sys.exit(1)
        os.makedirs(outdir, exist_ok=True)
        for p, r in hits:
            if r["type"] == 1:
                continue
            data = buf[r["data"]:r["data"] + r["size_a"]]
            leaf = r["name"] or "file"
            out = os.path.join(outdir, leaf)
            with open(out, "wb") as f:
                f.write(data)
            print(f"wrote {out} ({len(data)} bytes from {r['data']:#x})")


if __name__ == "__main__":
    main()
