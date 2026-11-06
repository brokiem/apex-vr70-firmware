# Status

Where we are. Kept short on purpose. Update it when you learn something.

## The dump

- File: `firmware/dump1.bin`
- Size: 8,388,608 bytes (8 MiB)
- SHA-256: `89d93d85…a1e477b78f6a128` (full hash in the file)
- Never modified. All work happens on copies in `build/`.

## What is checked (run these yourself)

```bash
python3 scripts/verify.py firmware/dump1.bin
```

- boot0 and boot1 eGON checksums match their stored values.
- MBR CRC matches.
- MINFS magic is good, and the 119 records parse cleanly.
- `epos.img` decompresses to 0x58854 bytes and has `EPOS-IMG` at offset 4.
- sys_config parses (57 main entries, display is 480x272).

## Builds and device tests

- `build/patched-00.bin` — the baseline (no change at all). Boots on
  the device. Built and verified in this repo: `sha256` matches
  `firmware/dump1.bin` byte for byte.
- `build/patched-01.bin` — `logo.bmp` replaced with seven analog
  color bars (white, yellow, cyan, green, magenta, red, blue) in the
  existing 360x640x32 BMP. The AZ10 payload is 278 bytes, fits the
  3326-byte slot, and round-trips exactly; `scripts/verify.py` passes.
  SHA-256: `95e9b30018677e92e2f8bc9794695fe9f410a39cfe402272007a3540b3173d4c`.
  This changes the boot logo only, not the live no-signal screen. Device
  testing of this updated pattern is outstanding.
- `build/patched-02.bin` — combined build from the original dump using
  patches `00,01,02`. It includes the boot-logo bars and status-bar changes.
  In `app_root.axf`, the shared clear colors at flat offsets `0x00DC38`,
  `0x00F620`, and `0x0114B4` are now transparent. The SD and APEX draw
  entries at `0x010D34` and `0x010F7C` return immediately. The theme's five
  `DV_RF_SIGNAL_*` resources and six `DV_SIGNAL_LEVEL_*` resources have zero
  pixel alpha; the adjacent unchanged theme resource was relocated within
  `theme.bin+0x191690..0x192271` to keep the theme file size fixed. The
  patch verifies all target BMPs and confirms other resource payloads remain
  byte-identical.
  The band-text path at `0x00EBEC`, battery resources, and recording draw
  code are not patched. `verify.py` passes; SHA-256 is
  `2314495e5c12af1ca67bb393d529a272333cc4b66a176595fc81c47c4622562a`.
  The user reports that this combined image was flashed successfully.
  Detailed boot, display, control, and status-indicator results were not
  specified. It replaces the previously generated standalone patch-02 image
  at this output path.

Patch 01 and patch 02 were also each rebuilt and verified independently
before the combined build. The combined build was also verified before
flashing; see the user-reported result above.

Write and restore work: the whole image can be written at offset 0
and read back byte-identical. That is the restore drill, already done once.

These are facts, not promises. If you change one thing at a time and
run `verify.py`, you can trust the result.

## What we do not know yet

- The 84-byte plane format behind `bg_default0.bgd` (AZ10 payload):
  8-bit planes of 240x320 are sure from size arithmetic, what the
  3 planes mean (channels?states?) is not. Rendered grayscale.
- `theme.bin` slots named `*_WKM_BMP` / `*_PAL_BMP` are 0x400 support
  tables (weighted masks / palettes); their consumers are untraced.
- `.langdat` rebuild: changing UI strings means rewriting record
  offsets/lengths; no re-encryptor written yet.

- Which module owns display scaling end to end. Sys_config says 480x272,
  but nobody traced how the desktop uses it. Do not claim a resolution
  change works until it is traced and tested.
- The 5.8 GHz receiver is on SPI with an auto-search loop.
  The strings and the loop are there, but the exact register protocol
  was not finished.
- The area at `0x3A00-0x6000` between boot0 and boot1 was never examined.

## Next steps (pick one)

1. Resolution work: find who reads `lcd_x` / `lcd_y` and where 480/272
   are hard-coded as literals in the display path.
2. Receiver work: finish the SPI register map for band/channel search.
3. Record detailed device results for the combined image: boots, picture,
   buttons, menu, backlight, and whether battery, band, and recording
   statuses update while video shows through the bar.
