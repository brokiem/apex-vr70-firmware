#!/usr/bin/env python3
"""Unpack the whole firmware image into extracted/.

Usage:
    python3 scripts/extract.py firmware/dump1.bin
    python3 scripts/extract.py build/patched-02.bin

Each image gets its own folder: extracted/<binname>-<sha256>/.
Before writing, every folder ending in -<sha256> is wiped, so a
rename cannot leave a stale twin behind. Other images (different
sha) are left alone. The per-bin folders are git-ignored; only
extracted/README.md is tracked.

Layout (paths relative to extracted/):
    boot0.bin boot1.bin mbr.bin
    sys-config.bin sys-config.txt
    kernel.raw epos.img
    rootfs/<minfs tree>       type-6 modules stored as .flat beside them
    ramdisk.iso ramdisk/<tree>
    udisk0.fat udisk1.fat udisk0/ udisk1/
    manifest.txt

rootfs and ramdisk trees contain the decoded (flat) bytes of type-6
modules; type-0 files are stored as-is. The stored bytes of a type-6
module are kept next to it as <name>.stored so patches can rebuild.
Nothing here is edited by hand. Patches work on the firmware image,
not on these files.
"""
import hashlib
import os
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decode
import epos
import minfs
import sysconfig as syscfg


def sha(b):
    return hashlib.sha256(b).hexdigest()


def write(outdir, rel, data, manifest, src=""):
    path = os.path.join(outdir, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    manifest.append((rel, len(data), sha(data), src))
    return path


def ramdisk_entries(stored):
    # Reuse minfs at its fixed ROOT by placing the nested image there.
    pad = bytearray(minfs.ROOT + len(stored))
    pad[minfs.ROOT:] = stored
    root_size = struct.unpack_from("<I", pad, minfs.ROOT + 0x0C)[0]
    return minfs.walk(pad, minfs.TABLE, root_size, "")


def fat12_files(img):
    if len(img) < 512:
        raise ValueError("not a FAT image")
    byts_sec = struct.unpack_from("<H", img, 11)[0]
    sec_clus = img[13]
    rsvd = struct.unpack_from("<H", img, 14)[0]
    nfats = img[16]
    roots = struct.unpack_from("<H", img, 17)[0]
    fatsz = struct.unpack_from("<H", img, 22)[0]
    root_off = (rsvd + nfats * fatsz) * byts_sec
    root_sz = roots * 32
    fat_off = rsvd * byts_sec
    clus_sz = sec_clus * byts_sec
    data_off = root_off + root_sz
    entries = []
    for i in range(roots):
        ent = img[root_off + i * 32:root_off + (i + 1) * 32]
        if ent[0:1] == b"\x00":
            break
        if ent[0:1] == b"\xe5":
            continue
        attr = ent[11]
        if attr & 0x0F == 0x0F:  # LFN
            continue
        raw = ent[0:11].decode("ascii", "replace")
        name = raw[0:8].rstrip()
        ext = raw[8:11].rstrip()
        if raw[0:1] == ".":
            continue
        full = name + ("." + ext if ext else "")
        if attr & 0x10:  # directory: keep walking root only for now
            continue
        clus = struct.unpack_from("<H", ent, 26)[0]
        size = struct.unpack_from("<I", ent, 28)[0]
        data = bytearray()
        c = clus
        guard = 0
        while c >= 2 and c < 0xFF8 and guard < 1000:
            guard += 1
            off = data_off + (c - 2) * clus_sz
            data.extend(img[off:off + clus_sz])
            # next cluster from FAT12 (12-bit)
            fo = fat_off + (c * 3) // 2
            if c % 2 == 0:
                nxt = struct.unpack_from("<H", img, fo)[0] & 0x0FFF
            else:
                nxt = struct.unpack_from("<H", img, fo)[0] >> 4
            c = nxt
        entries.append((full, bytes(data[:size])))
    return entries


def wipe_same_sha(base, digest):
    suffix = "-" + digest
    if os.path.isdir(base):
        for name in os.listdir(base):
            p = os.path.join(base, name)
            if name.endswith(suffix) and os.path.isdir(p):
                shutil.rmtree(p)


def main():
    if len(sys.argv) != 2:
        print("usage: extract.py firmware/dump1.bin")
        sys.exit(2)
    src = sys.argv[1]
    with open(src, "rb") as f:
        buf = f.read()
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "extracted")
    base = os.path.normpath(base)
    digest = hashlib.sha256(buf).hexdigest()
    out = os.path.join(base, f"{os.path.basename(src)}-{digest}")
    wipe_same_sha(base, digest)
    os.makedirs(out, exist_ok=True)
    manifest = []

    write(out, "boot0.bin", bytes(buf[0x0000:0x3A00]), manifest,
          "dump @0x0")
    write(out, "boot1.bin", bytes(buf[0x6000:0x18200]), manifest,
          "dump @0x6000")
    write(out, "mbr.bin", bytes(buf[0x24000:0x24400]), manifest,
          "dump @0x24000")
    write(out, "sys-config.bin", bytes(buf[0x607C:0x9708]), manifest,
          "dump @0x607C")
    txt = "\n".join(f"{k} = {v}" for k, v, _t in syscfg.parse(buf)) + "\n"
    write(out, "sys-config.txt", txt.encode(), manifest, "decoded sys_config")

    kernel, stored, _rec = epos.decode(buf)
    write(out, "kernel.raw", kernel, manifest, "decoded epos.img")
    write(out, "epos.img", stored, manifest, "epos.img stored")

    nfiles = 0
    for path, rec in minfs.get_entries(buf):
        rel = path.lstrip("/")
        if rec["type"] == 1:
            os.makedirs(os.path.join(out, "rootfs", rel), exist_ok=True)
            continue
        if rec["type"] == 6:
            flat, s = minfs.module_flat(buf, rec)
            write(out, f"rootfs/{rel}", flat, manifest,
                  f"record {rec['record']:#x} data {rec['data']:#x} flat")
            write(out, f"rootfs/{rel}.stored", s, manifest,
                  f"record {rec['record']:#x} stored")
        else:
            write(out, f"rootfs/{rel}",
                  bytes(buf[rec["data"]:rec["data"] + rec["size_a"]]),
                  manifest, f"record {rec['record']:#x} data {rec['data']:#x}")
        nfiles += 1
    print(f"rootfs: {nfiles} files")

    ramdisk_stored = None
    for _p, rec in minfs.get_entries(buf):
        if rec["name"] == "ramdisk.iso" and rec["type"] != 1:
            ramdisk_stored = bytes(buf[rec["data"]:rec["data"] + rec["size_a"]])
    if ramdisk_stored is None:
        raise ValueError("ramdisk.iso not found")
    write(out, "ramdisk.iso", ramdisk_stored, manifest, "ramdisk stored")
    nfiles = 0
    for path, rec in ramdisk_entries(ramdisk_stored):
        rel = path.lstrip("/")
        if rec["type"] == 1:
            os.makedirs(os.path.join(out, "ramdisk", rel), exist_ok=True)
            continue
        if rec["type"] == 6:
            ram_buf = bytearray(minfs.ROOT + len(ramdisk_stored))
            ram_buf[minfs.ROOT:] = ramdisk_stored
            flat, s = minfs.module_flat(ram_buf, rec)
            write(out, f"ramdisk/{rel}", flat, manifest,
                  f"ramdisk record {rec['record']:#x} flat")
            write(out, f"ramdisk/{rel}.stored", s, manifest,
                  f"ramdisk record {rec['record']:#x} stored")
        else:
            ram_buf = bytearray(minfs.ROOT + len(ramdisk_stored))
            ram_buf[minfs.ROOT:] = ramdisk_stored
            write(out, f"ramdisk/{rel}",
                  bytes(ram_buf[rec["data"]:rec["data"] + rec["size_a"]]),
                  manifest, f"ramdisk record {rec['record']:#x}")
        nfiles += 1
    print(f"ramdisk: {nfiles} files")

    for i, off in enumerate((0x7E0000, 0x7F0000)):
        img = bytes(buf[off:off + 0x10000])
        write(out, f"udisk{i}.fat", img, manifest, f"dump @{off:#x}")
        try:
            got = fat12_files(img)
        except ValueError:
            got = []
        for name, data in got:
            write(out, f"udisk{i}/{name}", data, manifest, "fat file")
        print(f"udisk{i}: {len(got)} files")

    print("decoding containers:")
    decode.decode_folder(out, manifest)

    with open(os.path.join(out, "manifest.txt"), "w") as f:
        for rel, ln, h, s in sorted(manifest):
            f.write(f"{rel} {ln} {h} {s}\n")
    print(f"wrote {out} ({len(manifest)} files + manifest.txt)")


if __name__ == "__main__":
    main()
