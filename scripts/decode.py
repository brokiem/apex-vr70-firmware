#!/usr/bin/env python3
"""Decode container files found in an extracted image folder.

Dispatch is on magic bytes (not extensions). Every decoded output is
written next to its source file:

    <file> starts "AZ10"     ->  <file>.decoded.bmp
        payload inside the AZ10/LZMA wrap. Stock payloads are plain
        BMPs (logo.bmp, nosignal.bmp) or an 84-byte header plus equal
        8-bit sample planes (bg_default0.bgd: 3 planes of 240x320),
        rendered as grayscale BMPs.
    <file> starts ".langdat" ->  <file>.decoded.txt
        string table: id x language records at 0x324
    <file> starts ".resthem" ->  <file>.decoded/<name>.bmp
        BMP per resource slot of the 64-byte name table; support blobs
        (palettes, raw tables) are emitted as .bin raw files
    <file> starts "REG1"     ->  <file>.decoded.txt
        flat u32 setting slots plus embedded strings

charset.bin (COMPV1.0, a loader program whose segments map to RAM
0x8000xxxx) and font20.sft (SFTT2.OO8 glyph data) carry no decoded
text or images worth the effort; they are left alone.

Nothing inside a `<file>.decoded` folder is re-read, and the folder
is wiped on every run, so output is rebuilt from the source files.

    python3 scripts/decode.py extracted/dump1.bin-<sha256>
extract.py calls decode_folder() at the end of every run.

Formats: 8-bit plane images under an 84-byte header, the .langdat
table, the .resthem slots and the REG1 layout were probed from
dump1.bin; see docs/formats.md #7 and #8. Plane semantics are
inferred from size arithmetic and are not device-tested.
"""
import os
import re
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import az10


def shahex(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


def planes_8(payload):
    """Raw-plane image: 84-byte header + N planes of w*h 8-bit samples
    (the header says bpp=16 but the plane math says one byte per pixel,
    3 equal planes; semantics unknown, rendered grayscale). Returns
    (w, h, [plane bytes]) or None if the sizes do not fit."""
    if len(payload) < 84:
        return None
    w, h = struct.unpack_from("<II", payload, 8)
    if not (0 < w < 4096 and 0 < h < 4096):
        return None
    psize = w * h
    n = len(payload) - 84
    if n == 0 or n % psize:
        return None
    planes = [payload[84 + k * psize:84 + (k + 1) * psize]
              for k in range(n // psize)]
    return w, h, planes


def plane_bmps(w, h, planes, name):
    outs = []
    for i, p in enumerate(planes):
        px = bytes(b for v in p for b in (v, v, v, 0xFF))
        outs.append((f"{name}.decoded/plane-{i}.bmp", az10.make_bmp(w, h, px)))
    return outs


def outputs_for_az10(path, rel_src):
    """AZ10 file -> ([rel, bytes], note). Payload BMP or 8-bit planes."""
    with open(path, "rb") as f:
        data = f.read()
    payload = az10.decode(data)
    if payload[:2] == b"BM":
        w, h, bpp = az10.check_bmp(payload)
        return [(rel_src + ".decoded.bmp", payload)], f"{w}x{h}x{bpp} bmp"
    got = planes_8(payload)
    if got is not None:
        w, h, planes = got
        outs = plane_bmps(w, h, planes, rel_src)
        return outs, f"{w}x{h}, {len(planes)} 8-bit plane(s)"
    return [(rel_src + ".decoded.bin", payload)], "unknown payload, raw"


def outputs_for_langdat(path, rel_src):
    with open(path, "rb") as f:
        data = f.read()
    nid = struct.unpack_from("<I", data, 0x18)[0]      # strings per language
    recs = []                                          # (lang, id, off, len)
    o = 0x324
    while o + 12 <= len(data):
        lang, sid, off, ln = struct.unpack_from("<HHII", data, o)
        if off + ln > len(data) or ln > 0x200:
            break
        recs.append((lang, sid, off, ln))
        o += 12
    langs = []
    for lang, *_x in recs:
        if lang not in langs:
            langs.append(lang)
    out = ["# .langdat: %d string ids x %d languages %s" % (
        nid, len(langs), " ".join(hex(l) for l in langs)),
        "# text is utf-8; id per line, tab-separated langcode=string"]
    byid = {}
    for lang, sid, off, ln in recs:
        s = data[off:off + ln].decode("utf-8", "replace").rstrip("\x00")
        byid.setdefault(sid, {})[lang] = s
    for sid, m in sorted(byid.items()):
        line = str(sid)
        for lang in langs:
            line += "\t%s=%s" % (hex(lang), m.get(lang, ""))
        out.append(line)
    text = ("\n".join(out) + "\n").encode()
    return [(rel_src + ".decoded.txt", text)], \
        f"{nid} ids x {len(langs)} langs, {len(recs)} records"


def _resthem_slots(data):
    """Yield (name, off, size) from the 64-byte name table."""
    count = struct.unpack_from("<I", data, 0x14)[0]
    table = struct.unpack_from("<I", data, 0x34)[0]
    for i in range(count):
        sl = data[table + i * 64:table + (i + 1) * 64]
        if len(sl) < 64:
            break
        name = sl[4:56].split(b"\x00")[0].decode("ascii", "replace")
        off, size = struct.unpack_from("<II", sl, 56)
        if not name or not name.isprintable() or off + size > len(data):
            continue
        yield name, off, size


def outputs_for_resthem(path, rel_src):
    with open(path, "rb") as f:
        data = f.read()
    outs = []
    kinds = {}
    for name, off, size in _resthem_slots(data):
        blob = data[off:off + size]
        if blob[:4] == az10.MAGIC:
            payload = az10.decode(blob)
            got = planes_8(payload)
            if got and payload[:2] != b"BM":
                w, h, planes = got
                outs.extend(plane_bmps(w, h, planes,
                                       f"{rel_src}.decoded/{name}"))
                kinds["8-bit-planes"] = kinds.get("8-bit-planes", 0) + 1
                continue
            if payload[:2] == b"BM":
                outs.append((f"{rel_src}.decoded/{name}.bmp", payload))
                kinds["az10-bmp"] = kinds.get("az10-bmp", 0) + 1
                continue
            outs.append((f"{rel_src}.decoded/{name}.bin", payload))
            kinds["other-bin"] = kinds.get("other-bin", 0) + 1
        elif blob[:2] == b"BM":
            outs.append((f"{rel_src}.decoded/{name}.bmp", blob))
            kinds["raw-bmp"] = kinds.get("raw-bmp", 0) + 1
        else:
            outs.append((f"{rel_src}.decoded/{name}.bin", blob))
            kinds["other-bin"] = kinds.get("other-bin", 0) + 1
    return outs, ", ".join(f"{k}:{v}" for k, v in sorted(kinds.items()))


def outputs_for_reg1(path, rel_src):
    with open(path, "rb") as f:
        data = f.read()
    out = ["# REG1 flat settings image: u32 slots at fixed offsets.",
           "# The app reads these by offset; udisk0 and udisk1 hold equal copies."]
    for off in range(0, len(data) - 3, 4):
        v = struct.unpack_from("<I", data, off)[0]
        if v:
            out.append("%#06x = %#010x (%d)" % (off, v, v))
    for m in re.finditer(rb"[\x20-\x7e]{4,}", data):
        out.append("# string @%#x: %r" % (m.start(), m.group()))
    text = ("\n".join(out) + "\n").encode()
    return [(rel_src + ".decoded.txt", text)], "settings dump"


def decode_folder(outdir, manifest=None):
    if manifest is None:
        manifest = []
    n = 0
    for root, dirs, files in os.walk(outdir):
        dirs[:] = sorted(d for d in dirs if not d.endswith(".decoded"))
        for name in sorted(files):
            if name == "manifest.txt":
                continue
            path = os.path.join(root, name)
            rel_src = os.path.relpath(path, outdir)
            with open(path, "rb") as f:
                head = f.read(16)
            try:
                if head[:4] == az10.MAGIC:
                    outs, note = outputs_for_az10(path, rel_src)
                elif head[:8] == b".langdat":
                    outs, note = outputs_for_langdat(path, rel_src)
                elif head[:8] == b".resthem":
                    outs, note = outputs_for_resthem(path, rel_src)
                elif head[:4] == b"REG1":
                    outs, note = outputs_for_reg1(path, rel_src)
                else:
                    continue
            except Exception as e:  # one bad file is not fatal
                print(f"  decode: FAILED {rel_src}: {e}")
                continue
            # wipe any decoded folder we regenerate
            for d in {os.path.dirname(os.path.join(outdir, r)) for r, _ in outs}:
                if d and d.endswith(".decoded") and os.path.isdir(d):
                    shutil.rmtree(d)
            for rel, blob in outs:
                p = os.path.join(outdir, rel)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "wb") as f:
                    f.write(blob)
                manifest.append((rel, len(blob), shahex(blob), "decode " + note))
            print(f"  decode: {rel_src} -> {len(outs)} file(s), {note}")
            n += 1
    return n


def main():
    if len(sys.argv) != 2:
        print("usage: decode.py extracted/dump1.bin-<sha256>")
        sys.exit(2)
    outdir = sys.argv[1]
    mpath = os.path.join(outdir, "manifest.txt")
    entries = []
    if os.path.exists(mpath):
        with open(mpath) as f:
            for line in f:
                line = line.strip()
                if not line or ".decoded" in line:
                    continue
                rel, ln, h, src = line.split(" ", 3)
                entries.append((rel, int(ln), h, src))
    n = decode_folder(outdir, entries)
    with open(mpath, "w") as f:
        for rel, ln, h, src in sorted(entries):
            f.write(f"{rel} {ln} {h} {src}\n")
    print(f"decoded {n} containers (manifest: {mpath})")


if __name__ == "__main__":
    main()
