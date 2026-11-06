# build/

Generated images. Nothing here is edited by hand.

- `work.bin` — the working copy that patches modify.
- `patched-NN.bin` — a finished, verified image, ready to flash.
- `patched-NN.bin.sha256` — its hash.

`scripts/build.py` creates these. This folder is git-ignored.
