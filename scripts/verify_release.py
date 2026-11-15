#!/usr/bin/env python3
"""Verify a BottleNeck release ZIP against its embedded manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    archive_path = args.archive.expanduser().resolve()
    with zipfile.ZipFile(archive_path) as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise SystemExit(f"Corrupt ZIP member: {corrupt}")
        manifest_path = "bottleneck-mvp/RELEASE-MANIFEST.json"
        try:
            manifest = json.loads(archive.read(manifest_path))
        except KeyError as exc:
            raise SystemExit("Release manifest is missing") from exc
        checked = 0
        for entry in manifest["files"]:
            member = f"bottleneck-mvp/{entry['path']}"
            raw = archive.read(member)
            if len(raw) != entry["size"]:
                raise SystemExit(f"Size mismatch: {member}")
            actual = hashlib.sha256(raw).hexdigest()
            if actual != entry["sha256"]:
                raise SystemExit(f"SHA-256 mismatch: {member}")
            checked += 1
    sidecar = archive_path.with_suffix(archive_path.suffix + ".sha256")
    if sidecar.exists():
        expected = sidecar.read_text(encoding="ascii").split()[0]
        actual = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit("Archive checksum does not match sidecar")
    print(f"Verified BottleNeck v{manifest['version']}: {checked} files, ZIP integrity OK")


if __name__ == "__main__":
    main()
