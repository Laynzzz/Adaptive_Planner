"""Restore the committed exact-byte source bundle used by a frozen measurement."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def restore_release(release, *, target=None):
    archive = Path(release["archive"])
    if hashlib.sha256(archive.read_bytes()).hexdigest() != release["archive_sha256"]:
        raise ValueError("Frozen archive digest mismatch")
    destination = Path(target or release["restore_to"]).resolve()
    with zipfile.ZipFile(archive) as source:
        names = set(source.namelist())
        if names != set(release["source_hashes"]):
            raise ValueError("Frozen archive inventory mismatch")
        for name in sorted(names):
            path = (destination / name).resolve()
            if not path.is_relative_to(destination):
                raise ValueError("Archive path escapes destination")
            content = source.read(name)
            if hashlib.sha256(content).hexdigest() != release["source_hashes"][name]:
                raise ValueError("Frozen source digest mismatch")
            if path.exists() and path.read_bytes() != content:
                raise ValueError(f"Existing source differs: {path}")
        for name in sorted(names):
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source.read(name))
    return len(names)


def main():
    releases = json.loads(Path("benchmarks/manifests/source-releases.json").read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release", choices=sorted(releases))
    args = parser.parse_args()
    count = restore_release(releases[args.release])
    print(f"Restored and verified {count} exact-byte source files for {args.release}")


if __name__ == "__main__":
    main()
