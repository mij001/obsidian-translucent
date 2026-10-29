"""The separate "Obsidian Translucent" app: its own settings directory and desktop entry."""

from __future__ import annotations

import json
import shutil
import subprocess
from importlib import resources
from pathlib import Path

from . import paths

APP_ID = "obsidian-translucent"
APP_NAME = "Obsidian Translucent"
ICON_SIZES = (16, 32, 48, 64, 128, 256, 512)


def asset(name: str) -> bytes:
    return resources.files("obsidian_translucent").joinpath("assets", name).read_bytes()


def seed_user_data(source: Path, target: Path) -> bool:
    """Create our user-data directory from the stock app's, once. Returns True if it was created now.

    Copies the vault list and per-vault window state (small top-level json files), so your vaults are
    there on first start. After that the two apps are independent. In-app auto-update is switched off in
    our copy: the stock launcher would otherwise download an unpatched obsidian.asar and load it instead of ours.
    The patched copy is refreshed by rebuilding from the system package instead.
    """
    created = not (target / "obsidian.json").is_file()
    target.mkdir(parents=True, exist_ok=True)
    if created and source.is_dir():
        for f in source.glob("*.json"):
            shutil.copy2(f, target / f.name)
    cfg_file = target / "obsidian.json"
    try:
        cfg = json.loads(cfg_file.read_text()) if cfg_file.is_file() else {}
    except ValueError:
        cfg = {}
    if cfg.get("updateDisabled") is not True:
        cfg["updateDisabled"] = True
        cfg_file.write_text(json.dumps(cfg))
    return created


def desktop_entry(exec_command: str) -> str:
    return "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            f"Name={APP_NAME}",
            "Comment=Obsidian with a transparent, blurred window",
            f"Exec={exec_command} run %U",
            f"Icon={APP_ID}",
            "Terminal=false",
            "Categories=Office;Utility;TextEditor;",
            f"StartupWMClass={APP_ID}",
            "StartupNotify=true",
            "",
        ]
    )


def _data_home() -> Path:
    import os

    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def install_desktop(exec_command: str) -> list[Path]:
    """Install the menu entry and icons for the current user. Returns the files written."""
    written: list[Path] = []
    data = _data_home()
    for size in ICON_SIZES:
        target = data / "icons" / "hicolor" / f"{size}x{size}" / "apps" / f"{APP_ID}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(asset(f"icon-{size}.png"))
        written.append(target)
    svg = data / "icons" / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg"
    svg.parent.mkdir(parents=True, exist_ok=True)
    svg.write_bytes(asset("icon.svg"))
    written.append(svg)
    entry = data / "applications" / f"{APP_ID}.desktop"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(desktop_entry(exec_command))
    written.append(entry)
    _refresh_caches(data)
    return written


def uninstall_desktop() -> list[Path]:
    data = _data_home()
    removed = []
    candidates = [data / "applications" / f"{APP_ID}.desktop", data / "icons" / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg"]
    candidates += [data / "icons" / "hicolor" / f"{s}x{s}" / "apps" / f"{APP_ID}.png" for s in ICON_SIZES]
    for path in candidates:
        if path.is_file():
            path.unlink()
            removed.append(path)
    _refresh_caches(data)
    return removed


def _refresh_caches(data: Path) -> None:
    """Best effort: tell the desktop to notice the new entry. Failures are harmless."""
    for cmd in (
        ["update-desktop-database", str(data / "applications")],
        ["gtk-update-icon-cache", "-q", "-t", str(data / "icons" / "hicolor")],
        ["kbuildsycoca6", "--noincremental"],
    ):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, capture_output=True, check=False)


def user_data_dir() -> Path:
    return paths.user_data_dir()
