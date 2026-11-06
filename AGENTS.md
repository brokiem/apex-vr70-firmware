# AGENTS.md — rules for this project

If you are working in this repo, follow these rules.
They are here so the folder stays small and findable.

## 1. Where things go

Only these top-level folders. Do not add new ones without asking.

| Folder | What belongs there |
| --- | --- |
| `docs/` | Notes about the hardware, formats, findings. |
| `firmware/` | The original dump only. `dump1.bin` + its `README.md`. |
| `scripts/` | Reusable tools. Small, standalone. |
| `patches/` | One file per change. Numbered, in order. |
| `extracted/` | Whole firmware, unpacked and committed. Read from here; never hand-edit. Regenerate with `scripts/extract.py`. |
| `build/` | Generated images. Never edit by hand. |

At the root, only `AGENTS.md`, `README.md`, and `.gitignore`.

- No `.bin` files in the root. No backups with names like `dump-final2.bin`.
- No new folder for every experiment. Put experiments in `/tmp`, not in `extracted/`.
- Throwaway scripts go in `/tmp`, not in `scripts/`.

## 2. Naming

- Scripts: `kebab-case.py`, for example `minfs.py`, `sysconfig.py`.
- Patches: `NN-kebab-case.py`, `00` is the baseline. Next is `01`, then `02`.
  No gaps. No `v2`, no `final`, no dates in names.
- Docs: `kebab-case.md`, for example `flash-layout.md`.
- Build output: `build/patched-NN.bin` plus `build/patched-NN.bin.sha256`.
- Lowercase only. No spaces. No uppercase.

## 3. Firmware rules

- Never modify `firmware/dump1.bin`. It is the reference.
  Make a copy with `scripts/build.py` (it writes to `build/work.bin`).
- Record the hash in `docs/status.md` if you touch it. You should not.
- Do not edit DRAM, clock, or voltage values. Those brick the board.
- A patch must not grow a file in place if it would overwrite the next file.
  If the new data is bigger, relocate it into the free area and update
  the MINFS record instead (see `docs/formats.md`).

## 4. How to make a change

1. Copy the dump to `build/work.bin` (`scripts/build.py` does this).
2. Add a patch file in `patches/`. One change only.
3. The patch takes the work file as an argument, prints offset and
   before/after bytes, and fails if the base looks different than expected.
4. Run it, then run `python3 scripts/verify.py build/work.bin`.
5. Save the result as `build/patched-NN.bin` with its `.sha256`.
6. Write what changed in `docs/status.md`. Short entry: what, why, test result.

One change per build until a baseline boots. Do not stack patches.

## 5. Evidence

- Do not invent offsets, addresses, or behaviour.
- Every claim in `docs/` should say how it was checked
  (a script, an offset + bytes, or a disassembly address).
- Read `extracted/` first. To inspect a module, open its flat file there
  (`extracted/rootfs/apps/app_root.axf`). Do not re-unpack the dump inline.
  Rebuild `extracted/` with `scripts/extract.py` — it also decodes the
  container files (`*.decoded*` next to each source). One-off inspection code
  belongs in `/tmp`, not in `scripts/`.
- Keep hex dumps in files. In chat or logs, print at most 128 bytes.
- If you cannot reproduce a fact, mark it as unknown in `docs/status.md`.

## 6. Scripts

- Scripts must run with plain `python3`. No extra installs without asking.
- Each script has one job. It should print a short summary and exit 0 on success.
- Keep scripts small and single-purpose. Say where each format came from
  in the script's header comment.

## 7. Flashing

- Only the user flashes. You prepare the image and the commands.
- Tell the user to run `sunxi-fel` only if they ask in this session.
- Before any flash: two reads must match, a restore drill must have been
  done once, the image must have passed `verify.py`, and the hash recorded.
- After each test, ask the user: boots? picture? buttons? menu? backlight?

## 8. SDK source

The `sdk/` folder holds the Melis SDK source for this SoC (see
`sdk/README.md`). If it exists, read it before guessing how a
file format or driver works. Cross-check anything you find there
against the dump in `extracted/` before trusting it: the goggles
may run a different vendor branch.

## 9. When stuck

If the same problem happens twice, or you have used about five tool calls
without progress, stop. Tell the user:

1. What you were trying to do (one line).
2. What you tried, and what came back.
3. Why you think you are stuck (evidence, not a guess).
4. The exact thing you need (a test result, a log, a photo, a decision).

Do not loop. Do not guess your way forward.
