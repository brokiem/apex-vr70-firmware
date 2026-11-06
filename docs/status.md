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
- `build/patched-01.bin` — `logo.bmp` replaced with a 360x640x32 test
  pattern (AZ10, fits the 3326-byte slot). The device shows the pattern
  with this change. Rebuild it with `00,01` before flashing.
- `build/patched-02.bin` — `patches/02-transparent-status-bar.py`. The
  grey FPV status-bar background is made transparent so the video
  underneath shows through. The indicators still draw and update.
  The current `e872a528…` binary is built and passes `verify.py`,
  but has not been flashed yet. Flash it with `docs/flashing.md` and
  report back boots / picture / buttons / menu / backlight.

Each change was tested as a single change. Combine into one image
(`00,01,02`) and that combined image still needs its own device
test before anyone calls it proven.

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
3. Flash `build/patched-02.bin` and check the bar (see `docs/flashing.md`).
   One logical change per build. Combined images need their own test.
