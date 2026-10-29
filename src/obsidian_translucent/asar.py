"""Minimal reader and writer for Electron's asar archive format.

Only what this project needs: list/extract files, read one file, and pack a directory.
Archives with "unpacked" entries are read fine (those entries are skipped on extract).
"""

from __future__ import annotations

import json
import os
import struct
from pathlib import Path


class AsarError(Exception):
    pass


def _read_header(f) -> tuple[dict, int]:
    """Return (header json, byte offset where file data starts)."""
    head = f.read(16)
    if len(head) < 16:
        raise AsarError("file too short to be an asar archive")
    _, header_size, _, json_len = struct.unpack("<IIII", head)
    raw = f.read(json_len)
    try:
        header = json.loads(raw)
    except ValueError as exc:
        raise AsarError(f"bad asar header: {exc}") from exc
    return header, 8 + header_size


def read_file(archive: str | os.PathLike, name: str) -> bytes:
    """Return the contents of one file inside the archive, e.g. ``package.json``."""
    with open(archive, "rb") as f:
        header, base = _read_header(f)
        node = header
        for part in name.split("/"):
            try:
                node = node["files"][part]
            except KeyError as exc:
                raise AsarError(f"{name} not found in {archive}") from exc
        if "files" in node or node.get("unpacked"):
            raise AsarError(f"{name} is not a packed file")
        f.seek(base + int(node["offset"]))
        return f.read(node["size"])


def extract(archive: str | os.PathLike, out: str | os.PathLike) -> int:
    """Extract every packed file into ``out``. Returns the number of files written."""
    count = 0
    with open(archive, "rb") as f:
        header, base = _read_header(f)

        def walk(node: dict, directory: Path) -> None:
            nonlocal count
            for name, entry in node["files"].items():
                path = directory / name
                if "files" in entry:
                    path.mkdir(parents=True, exist_ok=True)
                    walk(entry, path)
                elif not entry.get("unpacked"):
                    f.seek(base + int(entry["offset"]))
                    path.write_bytes(f.read(entry["size"]))
                    count += 1

        Path(out).mkdir(parents=True, exist_ok=True)
        walk(header, Path(out))
    return count


def pack(src: str | os.PathLike, archive: str | os.PathLike) -> None:
    """Pack a directory into an asar archive (no unpacked entries, no integrity hashes)."""
    files: list[Path] = []

    def build(directory: Path) -> dict:
        node: dict = {"files": {}}
        for child in sorted(directory.iterdir()):
            if child.is_dir():
                node["files"][child.name] = build(child)
            else:
                files.append(child)
                node["files"][child.name] = {"size": child.stat().st_size, "offset": None}
        return node

    header = build(Path(src))
    offset = 0

    def assign(node: dict) -> None:
        nonlocal offset
        for entry in node["files"].values():
            if "files" in entry:
                assign(entry)
            else:
                entry["offset"] = str(offset)
                offset += entry["size"]

    assign(header)
    payload = json.dumps(header, separators=(",", ":")).encode()
    pad = (4 - len(payload) % 4) % 4
    with open(archive, "wb") as out:
        out.write(struct.pack("<IIII", 4, len(payload) + pad + 8, len(payload) + pad + 4, len(payload)))
        out.write(payload + b"\0" * pad)
        for path in files:
            out.write(path.read_bytes())
