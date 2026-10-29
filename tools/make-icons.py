#!/usr/bin/env python3
"""Regenerate the PNGs and the _NET_WM_ICON data from assets/icon.svg. Dev-time only.

Needs: rsvg-convert (librsvg) and Pillow. Output goes to src/obsidian_translucent/assets/.
"""
import struct
import subprocess
import sys
from pathlib import Path

from PIL import Image

assets = Path(__file__).resolve().parent.parent / "src" / "obsidian_translucent" / "assets"
svg = assets / "icon.svg"
png_sizes = (16, 32, 48, 64, 128, 256, 512)
wm_sizes = (32, 48, 128)  # sizes embedded in _NET_WM_ICON

for size in png_sizes:
    subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size), str(svg), "-o", str(assets / f"icon-{size}.png")], check=True)

# _NET_WM_ICON is a list of 32-bit values: width, height, then width*height ARGB pixels, repeated per size
data = bytearray()
for size in wm_sizes:
    img = Image.open(assets / f"icon-{size}.png").convert("RGBA")
    data += struct.pack("<II", size, size)
    for r, g, b, a in img.getdata():
        data += struct.pack("<I", (a << 24) | (r << 16) | (g << 8) | b)
(assets / "icon.wmicon").write_bytes(bytes(data))
print("wrote", len(png_sizes), "pngs and icon.wmicon", len(data), "bytes", file=sys.stderr)
