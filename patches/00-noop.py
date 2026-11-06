#!/usr/bin/env python3
"""00 baseline: no change at all.

Usage:
    python3 patches/00-noop.py build/work.bin

Proves the pipeline: copying the dump and running this file
gives a byte-identical image. Every other patch starts here.
"""
import os
import sys


def main():
    if len(sys.argv) != 2:
        print("usage: 00-noop.py build/work.bin")
        sys.exit(2)
    path = sys.argv[1]
    assert os.path.getsize(path) == 8 * 1024 * 1024, "not 8 MiB"
    print(f"noop: {path} unchanged")


if __name__ == "__main__":
    main()
