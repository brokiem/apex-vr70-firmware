# Flash layout

The dump is 8 MiB (8,388,608 bytes).
Its SHA-256 is:

```
89d93d85408884c53a83e8ccb564b6c4ddfb1bed38c076950a1e477b78f6a128
```

Layout, low to high:

| Range | What |
| --- | --- |
| `0x000000` - `0x003A00` | boot0 (`eGON.BT0`), 0x3A00 bytes, checksum at `+0x0C` |
| `0x003A00` - `0x006000` | Not examined. Probably padding. |
| `0x006000` - `0x018200` | boot1 (`eGON.BT1`), 0x12200 bytes. Holds the sys_config blob at `0x607C`. |
| `0x018200` - `0x024000` | `0xFF` (erased). |
| `0x024000` | MBR, 1024 bytes. CRC-32 at `+0`. |
| `0x024400` | ROOTFS, MINFS filesystem. 0x7BBC00 bytes. |
| `0x7E0000` | UDISK volume 0, FAT12, 63 KiB. Holds registry data (`SETTING.BIN`). |
| `0x7F0000` | UDISK volume 1, FAT12, 63 KiB. Holds movie info (`MOVIEINF.FDB`). |

How to check this yourself:

```bash
python3 scripts/minfs.py list firmware/dump1.bin
python3 scripts/sysconfig.py dump firmware/dump1.bin display
```

Free space in ROOTFS is `0x670540` to `0x7E0000` (about 1.4 MiB, all zeros).
That is where you put bigger replacement files (see `docs/formats.md`).

Key files in ROOTFS:

- `epos.img` at `0x2844C` — the Melis kernel, LZMA compressed.
- `ramdisk.iso` at `0x492A8` — a small nested MINFS with drivers.
- `app_config.fex` at `0x28200` — INI text. `app_config.bin` is a
  zero-size alias at the same address.
- `logo.bmp` at `0x53D9C4` — the shell boot image.
- `pwm_cfg.ini`, `font20.sft`, `chord.wav`, `start_movie2.mp4`.

MINFS has 119 records in total (files plus directories).
That count is in the MINFS header and matches what `minfs.py` finds.
