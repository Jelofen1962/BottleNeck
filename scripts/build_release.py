#!/usr/bin/env python3
"""Build a clean, checksummed BottleNeck source release archive."""
from __future__ import annotations

import argparse
import hashlib
import json
import tomllib
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache",
    "data", "backups", "logs", "dist", "node_modules", "htmlcov",
}
EXCLUDED_FILES = {"uv.lock", ".coverage"}
REQUIRED_FILES = {
    "README.md", "LICENSE", "SECURITY.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
    "main.py", "bottleneck_cli.py", "schema.sql", "pyproject.toml", "start.ps1", "start.sh",
    "index.html", "static/app.js", "static/styles.css", "tests/test_release_smoke.py",
    "docs/assets/readme-hero.svg", "HANDBOOK.md", "CHANGELOG.md",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if path.name in EXCLUDED_FILES:
        return False
    if path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example"):
        return False
    if path.suffix in {".sqlite3", ".db", ".log", ".pyc"}:
        return False
    return path.is_file()


def build(output: Path) -> tuple[Path, Path]:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = metadata["project"]["version"]
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    if f'APP_VERSION = "{version}"' not in main_source:
        raise SystemExit("pyproject.toml and main.py version values do not match")

    files = sorted(path for path in ROOT.rglob("*") if included(path))
    relative_names = {path.relative_to(ROOT).as_posix() for path in files}
    missing = sorted(REQUIRED_FILES - relative_names)
    if missing:
        raise SystemExit("Release is missing required files: " + ", ".join(missing))

    manifest_files = []
    for path in files:
        raw = path.read_bytes()
        manifest_files.append({
            "path": path.relative_to(ROOT).as_posix(),
            "size": len(raw),
            "sha256": sha256_bytes(raw),
        })
    manifest = {
        "name": "BottleNeck",
        "version": version,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "archive_root": "bottleneck-mvp/",
        "files": manifest_files,
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, f"bottleneck-mvp/{path.relative_to(ROOT).as_posix()}")
        archive.writestr("bottleneck-mvp/RELEASE-MANIFEST.json", manifest_bytes)
    with zipfile.ZipFile(output, "r") as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise SystemExit(f"ZIP integrity check failed at: {bad_member}")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_suffix(output.suffix + ".sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="ascii")
    return output, checksum


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = metadata["project"]["version"]
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / f"BottleNeck-v{version}-production.zip")
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    built, checksum = build(output)
    print(f"Built: {built}")
    print(f"Size: {built.stat().st_size:,} bytes")
    print(f"SHA-256: {checksum.read_text(encoding='ascii').split()[0]}")
    print(f"Checksum file: {checksum}")


if __name__ == "__main__":
    main()
