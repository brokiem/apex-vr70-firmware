# Formats

The four formats you need to touch. Each one has a small script here.

## 1. eGON (boot0 / boot1)

Header: jump instruction, magic (`eGON.BT0` / `eGON.BT1`), checksum at
`+0x0C`, length at `+0x10`. No signature.

Checksum: sum of all 32-bit little-endian words over the whole block,
with the checksum field set to `0x5F0A6C39` first.

```bash
python3 scripts/egon.py check firmware/dump1.bin
python3 scripts/egon.py fix build/work.bin   # after editing boot0/boot1
```

Rules: fix boot0 at offset `0x0`, boot1 at `0x6000`.
Do not change the length fields.
Stored checksums in the dump: boot0 `0x8D40AB4A`, boot1 `0xEDF7CE8C`.

## 2. MBR

At `0x24000`, 1024 bytes. The first 4 bytes are a CRC-32 (zlib) of
bytes 4 to 1023, little endian.

```bash
python3 scripts/mbr.py check firmware/dump1.bin
python3 scripts/mbr.py fix build/work.bin    # only if the table changed
```

ROOTFS content edits do not touch the MBR. You only need this if you
change the partition table itself.

## 3. MINFS (ROOTFS)

Header at `0x24400`: magic `MINFS`. Then six values (sizes, counts).

Each file record is: offset, size-a, size-b, record length (u16),
type (u16), name length, name. File data lives at `0x24400 + offset`.

- Type 0: plain file. size-a equals size-b.
- Type 1: directory. The offset points to its table.
- Type 4: kernel (`epos.img`, LZMA).
- Type 6: compressed module (`.mod`, `.drv`, `.axf`). size-b is the raw size.
  Its record carries a name length and an extlen, then the name, then
  32-byte extent entries. Each extent has an offset and a stored size
  into the module data. Flag 2 means raw LZMA1. An extent with stored
  size 0 is BSS and has no data. `scripts/minfs.py module` prints them.

```bash
python3 scripts/minfs.py list firmware/dump1.bin
python3 scripts/minfs.py find firmware/dump1.bin logo.bmp
python3 scripts/extract.py firmware/dump1.bin   # full tree into extracted/
```

Nobody found a checksum over MINFS. Boot1 only checks the magic
and that the sector count matches. After you change a file size,
update its record. If you move a file, update its offset too.

## 4. epos.img (kernel) and AZ10 (boot image)

The kernel is raw LZMA1. Stored form is 5 props bytes
(`5D 00 80 00 00` for the kernel) plus the stream, with no size
field and no end marker. That is why you add the decompressed size
back in before calling Python's `FORMAT_ALONE`. The raw kernel
starts with a branch instruction (`e3 0f 00 ea`), then `EPOS-IMG`.

```bash
python3 scripts/epos.py info firmware/dump1.bin
python3 scripts/epos.py decode firmware/dump1.bin extracted/
```

Watch out: Python's LZMA writes an end marker, so a naive re-encode
of the untouched kernel comes out about 15 bytes bigger than the
original. The kernel slot has no spare room. For kernel patches,
relocate the new stream into the free area and update the record.
Do not try to squeeze it in place.

`logo.bmp` is a normal BMP wrapped in an `AZ10` container
(magic, size, 5 props bytes, then raw LZMA1). The BMP inside is
360x640, 32-bit, top-down. The code rejects anything else.
`scripts/az10.py` handles the wrap. It keeps the original props so
the loader can decode it the same way.

## 5. sys_config (script.bin)

The blob sits at `0x607C` inside boot1. It starts with a count (57)
and three version words, then main entries, each with sub-entries
(plain values, strings, GPIO pins). Full text dump:

```bash
python3 scripts/sysconfig.py dump firmware/dump1.bin
python3 scripts/sysconfig.py get firmware/dump1.bin display.lcd_x
```

Prefer in-place edits of values. A repack must fit the original slot
(ends near `0x9708`) without moving the rest of boot1.
After any edit, run `scripts/egon.py fix` for boot1.

## 6. INI files

`app_config.fex` is plain INI text (with some GBK comments).
Same-size edits are safe: keep the length, pad with spaces if needed.
`app_config.bin` is a zero-size alias at the same address, so only
the `.fex` record holds data.

## 7. App containers (decoded by `scripts/decode.py`)

Dispatch is on magic bytes, output lands next to the source file
inside `extracted/`. Everything below was probed from the dump;
plane/colour semantics are inferred from size arithmetic and not
device-tested.

### AZ10 (`logo.bmp`, `bg_default0.bgd`, `nosignal.bmp`)

`AZ10`, u32 uncompressed size, 5 LZMA props bytes, raw LZMA1 stream
(see `scripts/az10.py`). Stock payloads come in two shapes:

- BMP file (`BM` header; `logo.bmp` is 360x640 32-bit, `nosignal.bmp`
  400x200 32-bit, top-down). Written as `<file>.decoded.bmp`.
- Raw planes: 84-byte header with width/height at +8/+12, then equal
  8-bit planes of w*h bytes (`bg_default0.bgd`: header says bpp=16
  but there are exactly 3 planes of 240x320). Plane meaning
  [INFERRED]. Rendered grayscale as `plane-N.bmp`.

### .langdat (`lang.bin`)

Magic `.langdat`, then: u16 512, u16 36, u32 756 (= id table end
offset), u16 16, u16 language count (3), u16 0, u16 12 (record size),
u32 356 (string count), u32 4. Then:

- `0x2C..0x2F4`: 356 string ids as u16 (1, 2, ..., 1001.., 2001.. )
- `0x2F4..0x324`: per-language directory (3 x 16 B, language codes
  0x410, 0x420, 0x400; exact field meaning unread [UNKNOWN])
- `0x324..0x3524`: one 12-byte record per string:
  `{u16 lang, u16 id, u32 file offset, u32 len}`, text is UTF-8,
  NUL terminated (356 ids x 3 languages = 1068 records).

Decoded to `lang.bin.decoded.txt`: one line per id, tab separated
`langcode=string`. To ship changed strings you must rebuild the
record offsets and lengths; no re-enryptor exists yet [UNKNOWN].

### .resthem (`theme.bin`)

Header: magic, `u16 512, u16 32`, u32 32, u32 1, u32 count (645),
u32 16, zeros, theme name (16 B, `LiveTouch_demo`), then u32
`0x550` (name table start), u32 `0xA690` (data start), u32
`0x18C9B0` (data size = file size - data start). Then 645 u16
indices (1..645) at 0x40.

Name table: 645 slots x 64 B:
`{u16 1, u16 index, char name[52] NUL-padded, u32 blob offset,
u32 blob size}`. Blobs: most are `AZ10`-wrapped BMPs (591), 44 raw
`BM` BMPs, 10 support tables (palettes etc., written as `.bin`).

Decoded to `theme.bin.decoded/<NAME>_BMP.bmp|.bin`.

### REG1 (`udisk{0,1}/SETTING.BIN`)

Flat settings image: `REG1` magic, then u32 values at fixed offsets
(the app reads them by hardcoded offset) with a few embedded
strings (`d:\apps\`, `f:\DCIM\AW_0001.avi`). Both UDISKs hold
byte-identical copies. No table, no checksum found [UNKNOWN].
Decoded to `SETTING.BIN.decoded.txt` (all nonzero slots + strings).

### Not decoded on purpose

- `charset.bin` (`COMPV1.0 ` + trailing space): a loader program;
  header carries a target-address table of segments mapped to RAM
  (0x8000xxxx). Code, no readable payload worth the effort.
- `font20.sft` (`SFTT2.OO8`): glyph bitmap data for the font engine;
  parsing it only matters if we ever change fonts.

