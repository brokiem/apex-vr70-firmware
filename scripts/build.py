#!/usr/bin/env python3
"""Build a patched image.

Usage:
    python3 scripts/build.py --patches 00
    python3 scripts/build.py --patches 00,01

Copies firmware/dump1.bin to build/work.bin, runs the patch files
in order, verifies the result, then saves build/patched-NN.bin.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(args):
    print("+ " + " ".join(args))
    r = subprocess.run(args, cwd=ROOT)
    if r.returncode != 0:
        print("failed")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patches", required=True, help="comma list, e.g. 00 or 00,01")
    args = ap.parse_args()
    nums = [n.strip() for n in args.patches.split(",") if n.strip()]
    work = os.path.join(ROOT, "build", "work.bin")
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    shutil.copyfile(os.path.join(ROOT, "firmware", "dump1.bin"), work)
    print(f"copied dump to {work}")
    for n in nums:
        patch_dir = os.path.join(ROOT, "patches")
        match = [f for f in os.listdir(patch_dir) if f.startswith(n + "-")]
        if len(match) != 1:
            print(f"want exactly one patch starting with {n}-, got {match}")
            sys.exit(1)
        run([sys.executable, os.path.join(patch_dir, match[0]), work])
    run([sys.executable, "scripts/verify.py", work])
    with open(work, "rb") as f:
        h = hashlib.sha256(f.read()).hexdigest()
    out = os.path.join(ROOT, "build", f"patched-{nums[-1]}.bin")
    shutil.copyfile(work, out)
    with open(out + ".sha256", "w") as f:
        f.write(f"{h}  {os.path.basename(out)}\n")
    print(f"saved {out} sha256={h}")


if __name__ == "__main__":
    main()
