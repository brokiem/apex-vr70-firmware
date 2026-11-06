# firmware/

The original dump lives here. That is the only file, plus this README.

- `dump1.bin` — the 8 MiB stock dump. Never modify it.
- Keep its SHA-256 in `docs/status.md`.

To work, copy it:

```bash
python3 scripts/build.py --patches 00
```

Do not put backups, patched images, or readbacks here.
They belong in `build/` (and even there, keep them few).
