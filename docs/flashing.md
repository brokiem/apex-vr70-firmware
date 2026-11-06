# Flashing

The user flashes. The agent prepares the image and the commands.

Flashing is by USB FEL with a custom SD card (the card makes the board
enter FEL, then `sunxi-fel` on the PC talks to it).

## Before you flash, all of this must be true

1. Two reads of the flash match each other and `dump1.bin` (SHA-256).
2. A restore drill has been done: write the unmodified `dump1.bin`,
   read it back, confirm it matches. (Done once already — see `status.md`.)
3. The FEL SD card still enters FEL. A spare card exists.
4. Power is stable (charged battery or good USB).
5. The image passed `python3 scripts/verify.py` and its hash is recorded.

If any of these is false, do not flash.

## Commands (user runs them)

```bash
sunxi-fel ver
sunxi-fel spiflash-info
sunxi-fel -p spiflash-read 0 0x800000 backup1.bin
sunxi-fel -p spiflash-read 0 0x800000 backup2.bin
sha256sum backup1.bin backup2.bin firmware/dump1.bin

sunxi-fel -p spiflash-write 0 build/patched-NN.bin
sunxi-fel -p spiflash-read 0 0x800000 readback.bin
cmp readback.bin build/patched-NN.bin && echo FLASH-OK
```

Restore is the same write command with `firmware/dump1.bin`.
Remove the FEL SD card before a normal boot.

Always write the whole 8 MiB image at offset 0. Never patch on the device.

## After each test, report

Boots? Picture? Buttons? Menu? Backlight?
Write it down in `docs/status.md`.
