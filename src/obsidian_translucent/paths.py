"""Where things live. Everything can be overridden with environment variables."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

DEFAULT_SOURCE = "/usr/lib/obsidian"


def source_dir() -> Path:
    """The system Obsidian install (contains app.asar and obsidian.asar)."""
    return Path(os.environ.get("OBSIDIAN_TRANSLUCENT_SOURCE", DEFAULT_SOURCE))


def data_dir() -> Path:
    """Where the patched copy is built. Never inside the repository."""
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(os.environ.get("OBSIDIAN_TRANSLUCENT_DATA", Path(base) / "obsidian-translucent"))


def dist_dir() -> Path:
    return data_dir() / "dist"


def user_data_dir() -> Path:
    """Our own Electron user-data directory, separate from the stock app's ``~/.config/obsidian``.

    Keeping it separate means the two apps never share an update asar or a single-instance lock, so the
    stock Obsidian keeps updating normally and both can run at once.
    """
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(os.environ.get("OBSIDIAN_TRANSLUCENT_USER_DATA", Path(base) / "obsidian-translucent"))


def config_dir() -> Path:
    """The stock Obsidian's configuration directory (read only, used to seed ours)."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "obsidian"


def user_flags() -> list[str]:
    """Extra Electron flags from Obsidian's own ``user-flags.conf`` (same file the stock launcher reads)."""
    path = config_dir() / "user-flags.conf"
    if not path.is_file():
        return []
    flags: list[str] = []
    for line in path.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            flags += line.split()
    return flags


def electron_command() -> str:
    """The Electron binary the distro's launcher uses (``electron43`` on Arch), else plain ``electron``."""
    override = os.environ.get("OBSIDIAN_TRANSLUCENT_ELECTRON")
    if override:
        return override
    launcher = Path("/usr/bin/obsidian")
    if launcher.is_file():
        match = re.search(r"^exec\s+(\S*electron\S*)\s", launcher.read_text(errors="ignore"), re.MULTILINE)
        if match and shutil.which(match.group(1)):
            return match.group(1)
    return shutil.which("electron") or "electron"
