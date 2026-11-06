# Boot flow

What happens when the board powers up. Checked by reading boot0/boot1.

1. The ROM loads boot0 from SPI NOR at `0x80000000`.
2. Boot0 checks its own eGON checksum and calls boot1.
3. Boot1 checks its own eGON checksum, then checks the MBR CRC at `0x24000`
   and the MINFS magic at `0x24400`. Those are the only partition checks.
4. Boot1 finds `epos.img` and `ramdisk.iso` in ROOTFS and decompresses
   them with LZMA. If decompression fails it prints an error and jumps
   to FEL.
5. The kernel mounts the rest of ROOTFS and loads modules. The shell
   shows `d:\res\boot_ui\logo.bmp` (that's our `logo.bmp`) before the
   desktop takes over.

Two things that make patching easier:

- Boot1 does **not** hash or CRC `epos.img`, `ramdisk.iso`, or the
  modules. We checked the load and decompress paths. It only checks
  that the sector count matches and that LZMA returned success.
- The MBR CRC is the only thing that stops a patched image at this stage.
  Changing file contents does not break it. Changing the partition table
  does, and then you run `scripts/mbr.py fix`.

If a patched image does not boot and there is no other sign, suspect
the kernel was relocated wrong or the eGON checksum is stale.
Run `scripts/verify.py` before you blame the flash.
