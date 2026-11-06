# re-goggles

Reverse engineering project for the Allwinner suniv FPV goggles
firmware — 8 MiB SPI NOR, Melis OS, 480×272 panel, analogue CVBS in.

The stock image is `firmware/dump1.bin`. Scripts here parse it,
patches here make small, tested changes to it, and `build/` holds
the results. Everything documented in `docs/`.

## Layout

```
docs/        Hardware, flash layout, formats, boot flow, status.
firmware/    The stock dump. Never modify it.
scripts/     Parsing and build tools. Small, reusable, one job each.
patches/     One file per change, numbered in build order.
extracted/   Whole firmware, unpacked and committed. Read from here.
build/       Working images. Generated, never hand-edit.
```

Read `AGENTS.md` first if you are an agent. It has the rules
for where files go and how a patch is made.

## Quick start

Check the dump:

```bash
sha256sum firmware/dump1.bin
python3 scripts/verify.py firmware/dump1.bin
```

Build the baseline (byte-identical to the dump):

```bash
python3 scripts/build.py --patches 00
```

Build with the boot-logo test pattern:

```bash
python3 scripts/build.py --patches 00,01
```

Unpack the whole firmware (once, into `extracted/`; this also decodes
the container files inside — see `docs/formats.md` section 7):

```bash
python3 scripts/extract.py firmware/dump1.bin
```

Then read files directly, e.g. `extracted/rootfs/apps/app_root.axf`.
No inline unpacking needed.

`docs/status.md` says what is known and what already booted.
`docs/flashing.md` is the flash procedure — read it before any write.

## Rules (short version)

- Never modify `firmware/dump1.bin`. Work on a copy in `build/`.
- One logical change per patch file.
- Every patch prints what it changed (offset, before, after).
- Run `scripts/verify.py` after every build.
- If a check does not pass, stop and say so. Do not guess offsets.
