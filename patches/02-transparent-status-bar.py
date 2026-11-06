#!/usr/bin/env python3
"""02 transparent status bar: the grey background becomes see-through.

Usage:
    python3 patches/02-transparent-status-bar.py build/work.bin

The FPV top bar is drawn by /apps/app_root.axf. Its background and
the small boxes it erases before redrawing an indicator all use one
colour, 0xFF202020. This patch changes those three words to
0x00000000 (transparent black). The bar still draws, so the frequency,
battery, signal and recording indicators keep working; only the
grey fill disappears and the video underneath shows through.

The module is a sectioned MINFS type-6 entry. The patch decodes it
through scripts/minfs.py, applies the three word changes, then
re-encodes the sections the same way. Only the stored data, the
section extents, and the stored-size field change.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from minfs import find_entry, get_entries, module_flat, module_rebuild

TARGET = "app_root.axf"
BEFORE = 0xFF202020
AFTER = 0x00000000


def main():
    if len(sys.argv) != 2:
        print("usage: 02-transparent-status-bar.py build/work.bin")
        sys.exit(2)
    path = sys.argv[1]
    with open(path, "rb") as f:
        buf = bytearray(f.read())
    assert len(buf) == 8 * 1024 * 1024, "not 8 MiB"

    rec = find_entry(buf, TARGET)
    assert rec["type"] == 6, f"{TARGET} is not type 6"
    flat, stored = module_flat(buf, rec)
    print(f"{TARGET}: stored {len(stored)} flat {len(flat)}")

    flat = bytearray(flat)
    n = 0
    for i in range(0, len(flat) - 3, 4):
        if struct.unpack_from("<I", flat, i)[0] == BEFORE:
            n += 1
    if n != 3:
        print(f"refusing: found {n} background words, want 3")
        sys.exit(1)
    for i in range(0, len(flat) - 3, 4):
        if struct.unpack_from("<I", flat, i)[0] == BEFORE:
            print(f"flat {i:#x}: {BEFORE:#010x} -> {AFTER:#010x}")
            struct.pack_into("<I", flat, i, AFTER)
            if n == 0:
                break
            n -= 1

    new_stored, new_extents = module_rebuild(rec, bytes(flat), stored)
    print(f"stored size {len(stored)} -> {len(new_stored)} "
          f"(slot {rec['size_a']})")

    buf[rec["data"]:rec["data"] + len(new_stored)] = new_stored
    for i, ne in enumerate(new_extents):
        words = list(struct.unpack_from("<8I", buf, rec["ext_off"] + i * 32))
        if rec["extents"][i]["rec"]:
            words[0] = ne["off"]
            words[1] = ne["rec"]
            struct.pack_into("<8I", buf, rec["ext_off"] + i * 32, *words)
    struct.pack_into("<I", buf, rec["record"] + 4, len(new_stored))

    with open(path, "wb") as f:
        f.write(buf)

    # Read back and check.
    buf2 = open(path, "rb").read()
    rec2 = find_entry(buf2, TARGET)
    assert rec2["size_a"] == len(new_stored), "stored size mismatch"
    assert rec2["size_b"] == rec["size_b"], "unpacked size changed"
    flat2, _ = module_flat(buf2, rec2)
    assert bytes(flat2) == bytes(flat), "flat image mismatch"
    assert struct.pack("<I", BEFORE) not in flat2, "old colour still present"
    assert flat2.count(struct.pack("<I", AFTER)) >= 3, "new colour missing"
    assert len(get_entries(buf2)) == 119, "record count changed"
    print("status-bar: read-back ok")


if __name__ == "__main__":
    main()
