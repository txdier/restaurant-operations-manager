from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

APP_ID = "cn.restaurant.manager"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("dist/RestaurantManager"))
    parser.add_argument("--version", required=True)
    parser.add_argument("--min-version", default="1.0.0")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    output = (args.output or Path(f"release/RestaurantManager-Update-{args.version}.zip")).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = []
    for path in sorted(item for item in source.rglob("*") if item.is_file()):
        relative = path.relative_to(source).as_posix()
        files.append({"path": relative, "sha256": digest(path), "size": path.stat().st_size})
    manifest = {"appId": APP_ID, "version": args.version, "minVersion": args.min_version, "files": files}
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("update.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for entry in files:
            archive.write(source / entry["path"], f"payload/{entry['path']}")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
