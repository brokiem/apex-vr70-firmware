# Hardware

What we have. All of this comes from the dump (boot0, boot1, sys_config blob).

## The board

- SoC: Allwinner suniv (F1C100s / F1C200s family)
- CPU: ARM926EJ-S, ARMv5TE, little endian
- OS: Melis (Allwinner media SDK)
- Flash: 8 MiB SPI NOR on SPI0 (CLK PC0, CS0 PC1, MISO PC2, MOSI PC3)
- RAM: DRAM base `0x80000000`, auto size, 156 MHz, DDR, 16-bit bus.
  Do not edit DRAM values.
- Video in: analogue CVBS via TVD. INI default is NTSC (`cvbs=0`), PAL is `1`.
- Audio: amp shutdown on PC9.

## Display

- Panel is 480 x 272. That is what sys_config says, and that is what the
  panel wants.
- Interface: RGB565 on a 24-bit bus (blue, green, red on PD1-PD17, declk etc).
- Timings in sys_config: `ht=531`, `vt=576`, `hbp=43`, `vbp=12`, `dclk_div=9`.
  The backlight is on PWM, pin PE6.
- Do not change the timings and expect it to work. The UI code may
  hard-code 480x272 as well. Nobody has proved otherwise on hardware.

## Buttons, storage, misc

- Six buttons in a 2-row matrix. From `app_config`: SW4 EPG, SW5 SCAN,
  SW6 MENU, SW7 RIGHT, SW8 ENTER, SW9 PREVIEW_LIST.
- SD0 is 4-bit. Card detect on PE10.
- Debug UART1 is PA3/PA2 but it is off in the dump (`debugenable=0`).
- JTAG is off. IR receiver and TWI share PE11/PE12.

## Defaults we kept

From the INI in the firmware (`app_config.fex`):

- volume 30, language `0x410` (Simplified Chinese), backlight 12,
  keytone off, cvbs NTSC, client id `4C4E`.

These are easy to change in place. See `docs/formats.md`.
