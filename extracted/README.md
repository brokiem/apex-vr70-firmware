# extracted

Unpacked firmware lives here, one folder per image.

```
extracted/
  README.md
  dump1.bin-<sha256>/     <- stock dump, unpacked
    boot0.bin boot1.bin mbr.bin
    sys-config.bin sys-config.txt
    kernel.raw epos.img ramdisk.iso
    rootfs/           ROOTFS tree (flat). type-6 modules also have .stored.
    ramdisk/          nested MINFS tree, flat. same for .stored.
    udisk0/ udisk1/   FAT file contents (raw as udisk0.fat, udisk1.fat).
    manifest.txt      one line per file: path, size, sha256, offset.
  patched-02.bin-<sha256>/   <- same shape for a patched image
```

Container files are decoded too, output next to the source:

```
  rootfs/res/boot_ui/logo.bmp.decoded.bmp       (AZ10 -> BMP)
  rootfs/apps/bg_default0.bgd.decoded/plane-*.bmp
  rootfs/apps/lang.bin.decoded.txt              (string table)
  rootfs/apps/theme.bin.decoded/*.bmp           (645 theme resources)
  udisk0/SETTING.BIN.decoded.txt                (flat settings)
```

The name is the image file name plus its full SHA-256.
`extract.py` figures both out for you:

    python3 scripts/extract.py firmware/dump1.bin
    python3 scripts/extract.py build/patched-02.bin

Each time it runs it wipes every folder ending in that SHA first,
so a rename still replaces the old folder. Other images (different
SHA) stay. To look at a module, open its flat file in its image
folder, e.g. `dump1.bin-*/rootfs/apps/app_root.axf`.

`extract.py` also runs `scripts/decode.py` at the end: container
files (AZ10 images, `.langdat`, `.resthem`, `REG1`) are decoded in
place, next to their source. `*.decoded` output is wiped and rebuilt
on every run — see `docs/formats.md`, section 7.

Only this README is checked in. The image folders are git-ignored —
they are big. Do not hand-edit them. Patches work on the image file.
