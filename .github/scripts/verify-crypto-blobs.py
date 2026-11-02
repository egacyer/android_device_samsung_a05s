#!/usr/bin/env python3
"""Verify the firmware ELF files staged for the manual HAL test."""

import hashlib
import json
from pathlib import Path
import sys

tree = Path(sys.argv[1])
root = Path(sys.argv[2])
manifest = json.loads((tree / "docs/crypto-blobs.json").read_text())
for entry in manifest["files"]:
    relative = Path(entry["destination"].lstrip("/"))
    if ".." in relative.parts:
        raise SystemExit(f"Invalid blob path: {relative}")
    path = root / relative
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise SystemExit(f"Firmware checksum mismatch: {path}")
    if data[:6] != b"\x7fELF\x02\x01" or data[18:20] != b"\xb7\x00":
        raise SystemExit(f"Expected an arm64 ELF file: {path}")
    print(f"PASS: {relative}")
print(f"Verified {len(manifest['files'])} firmware ELF files")
