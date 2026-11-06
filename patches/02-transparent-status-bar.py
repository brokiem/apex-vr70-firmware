#!/usr/bin/env python3
"""Rebuild the FPV status-bar patch from the dumped application and theme.

The three shared app_root.axf colors clear the full bar and redraw regions.
They become transparent black, preserving clean dynamic updates. The APEX
and SD draw routines return immediately. Both signal-only resource families
in theme.bin are made transparent; unrelated theme assets are preserved.

The app is a sectioned MINFS type-6 module. The theme is a .resthem type-0
file whose 64-byte resource table stores each AZ10 payload's offset and size.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import az10
from minfs import find_entry, get_entries, module_flat, module_rebuild, setcolor_sites

APP = "app_root.axf"
THEME = "theme.bin"
COLOR_PATCHES = {
    0x00DC38: 0x00000000,
    0x00F620: 0x00000000,
    0x0114B4: 0x00000000,
}
RETURN_PATCHES = {
    0x010D34: 0xE12FFF1E,
    0x010F7C: 0xE12FFF1E,
}
EXPECTED_PROLOGUES = {
    0x010D34: 0xE92D407C,
    0x010F7C: 0xE92D407C,
}
SIGNAL_RESOURCES = {
    "DV_RF_SIGNAL_0_BMP": 614,
    "DV_RF_SIGNAL_1_BMP": 615,
    "DV_RF_SIGNAL_2_BMP": 616,
    "DV_RF_SIGNAL_3_BMP": 617,
    "DV_RF_SIGNAL_FULL_BMP": 618,
    "DV_SIGNAL_LEVEL_FIVE_BMP": 620,
    "DV_SIGNAL_LEVEL_FOUR_BMP": 621,
    "DV_SIGNAL_LEVEL_NONE_BMP": 622,
    "DV_SIGNAL_LEVEL_ONE_BMP": 623,
    "DV_SIGNAL_LEVEL_THREE_BMP": 624,
    "DV_SIGNAL_LEVEL_TWO_BMP": 625,
}


def patch_app(buf):
    rec = find_entry(buf, APP)
    if rec["type"] != 6:
        raise ValueError(f"{APP} is not a type-6 module")
    flat, stored = module_flat(buf, rec)
    flat = bytearray(flat)

    color_refs = {
        site["pool"]: site["color"]
        for site in setcolor_sites(flat)
    }
    for offset, after in COLOR_PATCHES.items():
        before = 0xFF202020
        observed = struct.unpack_from("<I", flat, offset)[0]
        if observed != before or color_refs.get(offset) != before:
            raise ValueError(
                f"unexpected status-bar color at {offset:#x}: "
                f"{observed:#010x}"
            )
        new = struct.pack("<I", after)
        print(
            f"{APP} flat {offset:#08x}: "
            f"{flat[offset:offset + 4].hex(' ')} -> {new.hex(' ')}"
        )
        flat[offset:offset + 4] = new

    for offset, after in RETURN_PATCHES.items():
        before = EXPECTED_PROLOGUES[offset]
        observed = struct.unpack_from("<I", flat, offset)[0]
        if observed != before:
            raise ValueError(
                f"unexpected renderer entry at {offset:#x}: "
                f"{observed:#010x}, expected {before:#010x}"
            )
        new = struct.pack("<I", after)
        print(
            f"{APP} flat {offset:#08x}: "
            f"{flat[offset:offset + 4].hex(' ')} -> {new.hex(' ')}"
        )
        flat[offset:offset + 4] = new

    rebuilt, extents = module_rebuild(rec, bytes(flat), stored)
    if len(rebuilt) > rec["size_a"]:
        raise ValueError(
            f"rebuilt {APP} size {len(rebuilt)} exceeds slot {rec['size_a']}"
        )
    buf[rec["data"]:rec["data"] + len(rebuilt)] = rebuilt
    for index, extent in enumerate(extents):
        struct.pack_into(
            "<II", buf, rec["ext_off"] + index * 32,
            extent["off"], extent["rec"],
        )
    struct.pack_into("<I", buf, rec["record"] + 4, len(rebuilt))

    check_rec = find_entry(buf, APP)
    check_flat, _ = module_flat(buf, check_rec)
    if check_flat != bytes(flat):
        raise ValueError(f"{APP} sectioned-module read-back mismatch")
    if check_rec["size_b"] != rec["size_b"]:
        raise ValueError(f"{APP} unpacked-size field changed")
    print(f"{APP}: stored size {len(stored)} -> {len(rebuilt)}; read-back ok")


def parse_theme(data):
    if data[:8] != b".resthem":
        raise ValueError(f"{THEME} has unexpected magic")
    count = struct.unpack_from("<I", data, 0x14)[0]
    table = struct.unpack_from("<I", data, 0x34)[0]
    if count != 645 or table + count * 64 > len(data):
        raise ValueError(
            f"unexpected .resthem table: {count} entries at {table:#x}"
        )

    entries = []
    for index in range(count):
        record = table + index * 64
        resource_id = struct.unpack_from("<H", data, record + 2)[0]
        raw_name = data[record + 4:record + 56].split(b"\0", 1)[0]
        name = raw_name.decode("ascii")
        offset, size = struct.unpack_from("<II", data, record + 56)
        if not name or not size or offset + size > len(data):
            raise ValueError(f"invalid .resthem entry {index}: {name!r}")
        entries.append({
            "record": record,
            "id": resource_id,
            "name": name,
            "offset": offset,
            "size": size,
        })

    ordered = sorted(entries, key=lambda entry: entry["offset"])
    for left, right in zip(ordered, ordered[1:]):
        if left["offset"] + left["size"] > right["offset"]:
            raise ValueError(
                f"overlapping theme resources: {left['name']} and {right['name']}"
            )
    return count, entries, ordered


def transparent_bmp(data, name, require_visible=True):
    if data[:2] != b"BM":
        raise ValueError(f"{name} is not a BMP")
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    width, height = struct.unpack_from("<ii", data, 18)
    planes, bpp, compression = struct.unpack_from("<HHI", data, 26)
    if width <= 0 or height == 0 or (planes, bpp, compression) != (1, 32, 0):
        raise ValueError(f"{name} is not an uncompressed 32-bpp BMP")
    pixel_end = pixel_offset + width * abs(height) * 4
    if pixel_end > len(data):
        raise ValueError(f"{name} pixel data exceeds its BMP")

    result = bytearray(data)
    visible_pixels = 0
    for pixel in range(pixel_offset + 3, pixel_end, 4):
        visible_pixels += result[pixel] != 0
        result[pixel] = 0
    if require_visible and not visible_pixels:
        raise ValueError(f"{name} already has no visible pixels")
    return bytes(result), visible_pixels


def patch_theme(buf):
    rec = find_entry(buf, THEME)
    if rec["type"] != 0:
        raise ValueError(f"{THEME} is not a type-0 file")
    original = bytes(buf[rec["data"]:rec["data"] + rec["size_a"]])
    count, entries, ordered = parse_theme(original)

    by_name = {entry["name"]: entry for entry in entries}
    if len(by_name) != count:
        raise ValueError("duplicate resource names in .resthem table")
    for name, resource_id in SIGNAL_RESOURCES.items():
        entry = by_name.get(name)
        if entry is None or entry["id"] != resource_id:
            raise ValueError(
                f"unexpected resource mapping for {name}: "
                f"{None if entry is None else entry['id']}"
            )

    target_names = set(SIGNAL_RESOURCES)
    target_indices = [
        index for index, entry in enumerate(ordered)
        if entry["name"] in target_names
    ]
    first, last = min(target_indices), max(target_indices)
    block = ordered[first:last + 1]
    block_start = block[0]["offset"]
    block_end = max(entry["offset"] + entry["size"] for entry in block)
    if any(entry["offset"] < block_start or
           entry["offset"] + entry["size"] > block_end
           for entry in block):
        raise ValueError("invalid signal-resource packing range")

    old_blobs = {
        entry["name"]: original[entry["offset"]:entry["offset"] + entry["size"]]
        for entry in entries
    }
    replacements = {}
    expected_bmps = {}
    for entry in block:
        name = entry["name"]
        blob = old_blobs[name]
        if name in target_names:
            bmp = az10.decode(blob)
            changed, visible_pixels = transparent_bmp(bmp, name)
            replacements[name] = az10.encode(changed, blob[8:13])
            expected_bmps[name] = changed
            print(
                f"{THEME} {name}: nonzero alpha {visible_pixels} pixels -> 0; "
                f"AZ10 {len(blob)} -> {len(replacements[name])} bytes"
            )
        else:
            replacements[name] = blob

    cursor = block_start
    placements = {}
    for entry in block:
        cursor = (cursor + 3) & ~3
        blob = replacements[entry["name"]]
        placements[entry["name"]] = (cursor, blob)
        cursor += len(blob)
    if cursor > block_end:
        raise ValueError(
            f"signal-resource repack needs {cursor - block_start} bytes, "
            f"but its original span is {block_end - block_start}"
        )

    updated = bytearray(original)
    for entry in block:
        offset, blob = placements[entry["name"]]
        updated[offset:offset + len(blob)] = blob
        struct.pack_into(
            "<II", updated, entry["record"] + 56, offset, len(blob)
        )
        if entry["name"] in target_names:
            print(
                f"{THEME} resource {entry['id']} {entry['name']}: "
                f"offset {entry['offset']:#x} -> {offset:#x}, "
                f"size {entry['size']} -> {len(blob)}"
            )

    new_count, new_entries, _ = parse_theme(updated)
    if new_count != count:
        raise ValueError(".resthem resource count changed")
    new_by_name = {entry["name"]: entry for entry in new_entries}
    for entry in entries:
        new_entry = new_by_name.get(entry["name"])
        if new_entry is None or new_entry["id"] != entry["id"]:
            raise ValueError(f"resource table changed unexpectedly: {entry['name']}")
        blob = updated[
            new_entry["offset"]:new_entry["offset"] + new_entry["size"]
        ]
        if entry["name"] in target_names:
            if az10.decode(blob) != expected_bmps[entry["name"]]:
                raise ValueError(f"{entry['name']} AZ10 read-back mismatch")
            decoded = az10.decode(blob)
            if transparent_bmp(
                decoded, entry["name"], require_visible=False
            )[0] != decoded:
                raise ValueError(f"{entry['name']} has nonzero pixel alpha")
        elif blob != old_blobs[entry["name"]]:
            raise ValueError(f"unmodified theme resource changed: {entry['name']}")

    buf[rec["data"]:rec["data"] + len(updated)] = updated
    print(
        f"{THEME}: repacked {len(block)} adjacent resources within "
        f"{block_end - block_start} bytes; read-back ok"
    )


def main():
    if len(sys.argv) != 2:
        print("usage: 02-transparent-status-bar.py build/work.bin")
        sys.exit(2)
    path = sys.argv[1]
    with open(path, "rb") as f:
        buf = bytearray(f.read())
    if len(buf) != 8 * 1024 * 1024:
        raise ValueError("image must be exactly 8 MiB")

    patch_app(buf)
    patch_theme(buf)
    if len(get_entries(buf)) != 119:
        raise ValueError("MINFS record count changed")

    with open(path, "wb") as f:
        f.write(buf)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
