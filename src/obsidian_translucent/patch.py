"""The one binary patch that makes Obsidian's vault window transparent.

Stock Obsidian creates its vault window with ``backgroundColor:"#00000000"`` and no ``transparent``
flag, so the window is opaque on Linux. We replace that option with ``transparent:true`` and pad the
rest with spaces so the file keeps exactly the same length. That keeps every offset in the asar header
valid, so no repacking is needed.

If Obsidian changes this code in a future release, ``apply`` raises ``PatchError`` instead of guessing.
"""

from __future__ import annotations

from dataclasses import dataclass


class PatchError(Exception):
    pass


@dataclass(frozen=True)
class Patch:
    name: str
    old: bytes
    new: bytes

    def __post_init__(self) -> None:
        if len(self.old) != len(self.new):
            raise ValueError(f"patch {self.name!r} must keep the byte length")


# main vault window options, see docs/ARCHITECTURE.md ("Main process")
VAULT_WINDOW = Patch(
    name="vault-window-transparent",
    old=b'backgroundColor:"#00000000",trafficLightPosition',
    new=b"transparent:!0," + b" " * 13 + b"trafficLightPosition",
)

PATCHES = (VAULT_WINDOW,)


def apply(data: bytes, patches=PATCHES) -> tuple[bytes, list[str]]:
    """Return (patched data, names of patches that were applied now).

    Already-patched input is returned unchanged. Anything unexpected raises ``PatchError``.
    """
    applied: list[str] = []
    for p in patches:
        found = data.count(p.old)
        if found == 1:
            data = data.replace(p.old, p.new)
            applied.append(p.name)
        elif found == 0 and data.count(p.new) == 1:
            continue  # already patched
        else:
            raise PatchError(
                f"patch {p.name!r}: expected the original code exactly once, found it {found} times. "
                "This Obsidian version is probably not supported yet; please open an issue with "
                "the output of `obsidian-translucent doctor`."
            )
    return data, applied
