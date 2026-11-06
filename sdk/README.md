# SDK folder

Reference SDKs, gitignored (large; third-party vendor material).
Not part of the build; nothing here runs as-is.

| Folder | What it is |
| --- | --- |
| `C100s_PubRelease_V1.0_20170522/` | Official Allwinner public release `C100s_DEMOD_V1.0` (Melis OS, 2017). Kernel + drivers + `livedesk/beetles` app skeleton + build tools. Generic demo, no app customisation. |
| `F1C100-SDK/` | `C100A_zyac` full Melis source from a vendor (zyac) build — the only one with the app layer filled in. Closest match to the goggles firmware; see below. |

## `F1C100-SDK/C100A_zyac` highlights

- `livedesk/beetles/mod_desktop/functions/` — `theme/dsk_theme.c`,
  `langres/dsk_langres.c`, `reg/dsk_reg.c`: the app-side consumers
  behind our `theme.bin` (`.resthem`), `lang.bin` (`.langdat`) and
  SETTING.BIN problems. `dsk_reg.c` is a good REG1 candidate.
- `eMod/drv_fm_5807.c`, `eMod/drv_fm_8035.c` — tuner modules
  (relation to the 5.8 GHz receiver unknown, needs check).
- `eMod/drv_matrixkey.c`, `drv_ir.c`, `drv_rocker.c` — same driver
  family as the goggles' button matrix.
- `interinc/fwimage.h`, `interinc/romldr.h` — firmware image
  header/builder structs, matches our epos.img/eGON layout.

Caveat: this may still be a different vendor branch than the one the
goggles shipped with. Any claim needs a side-by-side check against the
dump before it is treated as verified.
