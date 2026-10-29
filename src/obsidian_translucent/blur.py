"""X11 (XWayland) window helpers: KDE background blur shaped to match rounded corners, and the window icon.

KWin reads the ``_KDE_NET_WM_BLUR_BEHIND_REGION`` property: a list of ``x y w h`` rectangles in window
coordinates. xprop accepts at most 64 values, so a rounded rectangle is approximated with one band of
rows per distinct corner inset (about 13 rectangles for radius 10). Rectangles overlap by a row so no
unblurred seam is left between them.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import math
import os
import shutil
import struct
import subprocess
import time

PROPERTY = "_KDE_NET_WM_BLUR_BEHIND_REGION"
MAX_VALUES = 64
MAX_RADIUS = 11  # largest radius whose region still fits in 64 values


def region(width: int, height: int, radius: int) -> list[int]:
    """Flat ``[x, y, w, h, ...]`` list covering a rounded rectangle."""
    radius = max(0, min(radius, width // 2, height // 2))
    insets = [round(radius - math.sqrt(max(radius * radius - (radius - i - 0.5) ** 2, 0))) for i in range(radius)]
    rects: list[int] = []
    i = 0
    while i < radius:
        j = i
        while j + 1 < radius and insets[j + 1] == insets[i]:
            j += 1
        rows = j - i + 1
        rects += [insets[i], i, width - 2 * insets[i], rows]
        rects += [insets[i], height - 1 - j, width - 2 * insets[i], rows]
        i = j + 1
    # the middle overlaps the corner bands by one row on each side
    rects += [0, max(radius - 1, 0), width, height - 2 * radius + 2]
    if len(rects) > MAX_VALUES:
        raise ValueError(f"radius {radius} needs {len(rects)} values; xprop accepts {MAX_VALUES}")
    return rects


def _run(*cmd: str) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout


def window_ids(pid: int) -> list[str]:
    return _run("xdotool", "search", "--pid", str(pid)).split()


def geometry(window: str) -> tuple[int, int] | None:
    values = dict(
        line.split("=", 1) for line in _run("xdotool", "getwindowgeometry", "--shell", window).splitlines() if "=" in line
    )
    try:
        return int(values["WIDTH"]), int(values["HEIGHT"])
    except (KeyError, ValueError):
        return None


def set_region(window: str, width: int, height: int, radius: int) -> None:
    """Set the property with xprop (slow: one process per call; kept as a fallback and for tests by hand)."""
    value = ",".join(map(str, region(width, height, radius)))
    _run("xprop", "-id", window, "-f", PROPERTY, "32c", "-set", PROPERTY, value)


def process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


# ---- event driven path: a direct Xlib connection through ctypes (no dependencies) -------------------

_STRUCTURE_NOTIFY = 1 << 17
_CONFIGURE_NOTIFY = 22
_XA_CARDINAL = 6


class _ConfigureEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int), ("serial", ctypes.c_ulong), ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p), ("event", ctypes.c_ulong), ("window", ctypes.c_ulong),
        ("x", ctypes.c_int), ("y", ctypes.c_int), ("width", ctypes.c_int), ("height", ctypes.c_int),
        ("border_width", ctypes.c_int), ("above", ctypes.c_ulong), ("override_redirect", ctypes.c_int),
    ]


class _XEvent(ctypes.Union):
    _fields_ = [("type", ctypes.c_int), ("configure", _ConfigureEvent), ("pad", ctypes.c_long * 24)]


class XConnection:
    """Just enough Xlib to watch window sizes and set one CARDINAL property."""

    def __init__(self) -> None:
        name = ctypes.util.find_library("X11")
        if not name:
            raise RuntimeError("libX11 not found")
        self.x = ctypes.CDLL(name)
        self.x.XOpenDisplay.restype = ctypes.c_void_p
        self.x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x.XInternAtom.restype = ctypes.c_ulong
        self.x.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        self.x.XSelectInput.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_long]
        self.x.XPending.argtypes = [ctypes.c_void_p]
        self.x.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.x.XFlush.argtypes = [ctypes.c_void_p]
        self.x.XConnectionNumber.argtypes = [ctypes.c_void_p]
        self.x.XChangeProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_int, ctypes.c_int,
            ctypes.c_void_p, ctypes.c_int,
        ]
        self.dpy = self.x.XOpenDisplay(None)
        if not self.dpy:
            raise RuntimeError("cannot open the X display (is DISPLAY set? XWayland running?)")
        self.atom = self.x.XInternAtom(self.dpy, PROPERTY.encode(), 0)
        self.fd = self.x.XConnectionNumber(self.dpy)

    def set_window_icon(self, window: int, icon: bytes) -> None:
        """Set ``_NET_WM_ICON`` (the icon taskbars and switchers show) and tell KDE which desktop file this is.

        ``icon`` is ``assets/icon.wmicon``: little-endian 32-bit words, ``width height ARGB...`` per size.
        Electron's own ``setIcon`` does not reach the window here, which left a generic icon in the task manager.
        """
        words = struct.unpack(f"<{len(icon) // 4}I", icon)
        data = (ctypes.c_long * len(words))(*words)
        atom = self.x.XInternAtom(self.dpy, b"_NET_WM_ICON", 0)
        self.x.XChangeProperty(self.dpy, window, atom, _XA_CARDINAL, 32, 0, data, len(words))
        desktop = self.x.XInternAtom(self.dpy, b"_KDE_NET_WM_DESKTOP_FILE", 0)
        utf8 = self.x.XInternAtom(self.dpy, b"UTF8_STRING", 0)
        name = b"obsidian-translucent"
        self.x.XChangeProperty(self.dpy, window, desktop, utf8, 8, 0, name, len(name))
        self.x.XFlush(self.dpy)

    def watch(self, window: int) -> None:
        self.x.XSelectInput(self.dpy, window, _STRUCTURE_NOTIFY)

    def set_region(self, window: int, width: int, height: int, radius: int) -> None:
        values = region(width, height, radius)
        data = (ctypes.c_long * len(values))(*values)
        self.x.XChangeProperty(self.dpy, window, self.atom, _XA_CARDINAL, 32, 0, data, len(values))
        self.x.XFlush(self.dpy)

    def sizes(self) -> dict[int, tuple[int, int]]:
        """Drain pending events; return the latest size per resized window."""
        latest: dict[int, tuple[int, int]] = {}
        event = _XEvent()
        while self.x.XPending(self.dpy):
            self.x.XNextEvent(self.dpy, ctypes.byref(event))
            if event.type == _CONFIGURE_NOTIFY:
                c = event.configure
                latest[c.window] = (c.width, c.height)
        return latest


def follow(pid: int, radius: int, interval: float = 1.0, icon: bytes | None = None) -> None:
    """Keep the blur region of every window of ``pid`` matched to its size until the process exits.
    If ``icon`` (``icon.wmicon`` data) is given, each new window also gets it as its window icon.

    Resizes are picked up the moment the X server reports them. Window discovery (new windows such as
    pop-outs) runs once per ``interval``. Falls back to slower polling if Xlib is unavailable.
    """
    if shutil.which("xdotool") is None:
        raise RuntimeError("xdotool is required to find the Obsidian window (install it with your package manager)")
    try:
        conn = XConnection()
    except (RuntimeError, OSError) as exc:
        if shutil.which("xprop") is None:
            raise RuntimeError("neither Xlib nor xprop is available for the blur") from exc
        return _follow_polling(pid, radius)

    import select

    known: dict[int, tuple[int, int]] = {}
    next_scan = 0.0
    while process_alive(pid):
        now = time.monotonic()
        if now >= next_scan:
            next_scan = now + interval
            for window in map(int, window_ids(pid)):
                if window not in known:
                    conn.watch(window)
                    size = geometry(str(window))
                    if size and size[0] > 40:
                        known[window] = size
                        conn.set_region(window, size[0], size[1], radius)
                        if icon:
                            conn.set_window_icon(window, icon)
        select.select([conn.fd], [], [], 0.05)
        for window, size in conn.sizes().items():
            if window in known and size[0] > 40 and known[window] != size:
                known[window] = size
                conn.set_region(window, size[0], size[1], radius)


def _follow_polling(pid: int, radius: int, interval: float = 0.3) -> None:
    seen: dict[str, tuple[int, int]] = {}
    while process_alive(pid):
        for window in window_ids(pid):
            size = geometry(window)
            if size and size[0] > 40 and seen.get(window) != size:
                seen[window] = size
                set_region(window, size[0], size[1], radius)
        time.sleep(interval)
