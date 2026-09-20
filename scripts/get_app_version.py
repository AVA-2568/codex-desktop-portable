#!/usr/bin/env python3
"""Print the official app version stored in an Electron app.asar.

Reads "version" from package.json inside the asar index - the same number the
app reports at runtime via Electron app.getVersion() (e.g. 26.915.31945).

Note: this differs from the MSIX *container* version declared in
AppxManifest.xml <Identity Version="..."/> (e.g. 26.915.4065.0).

Usage: get_app_version.py <path-to-app.asar>
"""
import json
import struct
import sys


def read_app_version(asar_path: str) -> str:
    with open(asar_path, "rb") as f:
        # asar frame: 4 x uint32 LE -> [4, header_total, header_payload, json_len]
        _, header_total, _, json_len = struct.unpack("<IIII", f.read(16))
        index = json.loads(f.read(json_len).decode("utf-8"))["files"]
        entry = index["package.json"]
        f.seek(8 + header_total + int(entry["offset"]))
        pkg = json.loads(f.read(entry["size"]).decode("utf-8"))
    return pkg["version"]


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <path-to-app.asar>", file=sys.stderr)
        return 2
    try:
        print(read_app_version(sys.argv[1]))
    except (OSError, KeyError, ValueError) as exc:
        print(f"failed to read app version: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
