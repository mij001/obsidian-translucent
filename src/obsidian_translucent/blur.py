"""X11 (XWayland) window helpers: KDE background blur shaped to match rounded corners, the window icon and a drop shadow.

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


# ---- drop shadow ----------------------------------------------------------------------------------
# A frameless transparent window gets no shadow from KWin by itself. KWin draws one from the
# _KDE_NET_WM_SHADOW property: eight pixmaps (top, top-right, right, bottom-right, bottom, bottom-left,
# left, top-left) plus the four padding values (top, right, bottom, left). KWin hides it when maximized.

SHADOW_SIGMA = 13.0  # blur softness in px
SHADOW_OFFSET = 7  # shadow sits this far below the window, like Breeze
SHADOW_ALPHA = 0.42
SHADOW_PAD = (24, 36, 44, 36)  # top, right, bottom, left extents in px


def _edge(distance: float) -> float:
    """Gaussian-blurred straight edge: 0.5 at the edge, falling to 0 outward. ``distance`` is outward-positive."""
    return 0.5 * (1.0 - math.erf(distance / (SHADOW_SIGMA * math.sqrt(2))))


def shadow_tiles() -> list[tuple[int, int, bytes]]:
    """The eight shadow tiles as ``(width, height, premultiplied ARGB32 little-endian bytes)``.

    Edge tiles are one pixel thick along the edge (KWin stretches them); corner tiles are pad x pad.
    The shadow shape is the window rectangle moved down by SHADOW_OFFSET and blurred, which is separable,
    so every tile is a product of two one-dimensional profiles.
    """
    top, right, bottom, left = SHADOW_PAD

    def alpha(fx: float, fy: float) -> int:
        return max(0, min(255, round(255 * SHADOW_ALPHA * fx * fy)))

    def tile(width: int, height: int, fx_of, fy_of) -> tuple[int, int, bytes]:
        out = bytearray()
        for y in range(height):
            for x in range(width):
                out += struct.pack("<I", alpha(fx_of(x), fy_of(y)) << 24)  # black shadow: premultiplied colour is zero
        return width, height, bytes(out)

    # distances measured outward from the window edge, at the centre of each pixel
    def left_d(x):  # x in [0, left): distance from the left edge going outward
        return left - x - 0.5

    def right_d(x):
        return x + 0.5

    def top_d(y):  # shadow is moved down, so the top edge of the shadow is SHADOW_OFFSET inside
        return top - y - 0.5 + SHADOW_OFFSET

    def bottom_d(y):
        return y + 0.5 - SHADOW_OFFSET

    one = lambda _v: 1.0  # noqa: E731
    return [
        tile(1, top, one, lambda y: _edge(top_d(y))),  # top
        tile(right, top, lambda x: _edge(right_d(x)), lambda y: _edge(top_d(y))),  # top-right
        tile(right, 1, lambda x: _edge(right_d(x)), one),  # right
        tile(right, bottom, lambda x: _edge(right_d(x)), lambda y: _edge(bottom_d(y))),  # bottom-right
        tile(1, bottom, one, lambda y: _edge(bottom_d(y))),  # bottom
        tile(left, bottom, lambda x: _edge(left_d(x)), lambda y: _edge(bottom_d(y))),  # bottom-left
        tile(left, 1, lambda x: _edge(left_d(x)), one),  # left
        tile(left, top, lambda x: _edge(left_d(x)), lambda y: _edge(top_d(y))),  # top-left
    ]


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

    def _create_pixmaps(self) -> list[int]:
        """Upload the shadow tiles to the X server as 32-bit pixmaps. Done once per connection."""

        class VisualInfo(ctypes.Structure):
            _fields_ = [
                ("visual", ctypes.c_void_p), ("visualid", ctypes.c_ulong), ("screen", ctypes.c_int), ("depth", ctypes.c_int),
                ("klass", ctypes.c_int), ("red_mask", ctypes.c_ulong), ("green_mask", ctypes.c_ulong),
                ("blue_mask", ctypes.c_ulong), ("colormap_size", ctypes.c_int), ("bits_per_rgb", ctypes.c_int),
            ]

        x, dpy = self.x, self.dpy
        x.XDefaultScreen.argtypes = [ctypes.c_void_p]
        x.XRootWindow.restype = ctypes.c_ulong
        x.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x.XMatchVisualInfo.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(VisualInfo)]
        x.XCreatePixmap.restype = ctypes.c_ulong
        x.XCreatePixmap.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
        x.XCreateGC.restype = ctypes.c_void_p
        x.XCreateGC.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p]
        x.XCreateImage.restype = ctypes.c_void_p
        x.XCreateImage.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
            ctypes.c_uint, ctypes.c_uint, ctypes.c_int, ctypes.c_int,
        ]
        x.XPutImage.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_uint, ctypes.c_uint,
        ]
        screen = x.XDefaultScreen(dpy)
        root = x.XRootWindow(dpy, screen)
        info = VisualInfo()
        if not x.XMatchVisualInfo(dpy, screen, 32, 4, ctypes.byref(info)):  # 4 = TrueColor
            raise RuntimeError("no 32-bit visual for the shadow")
        ids = []
        self._keep = []  # XCreateImage does not copy the data; keep it alive
        for width, height, data in shadow_tiles():
            pixmap = x.XCreatePixmap(dpy, root, width, height, 32)
            gc = x.XCreateGC(dpy, pixmap, 0, None)
            buffer = ctypes.create_string_buffer(data, len(data))
            self._keep.append(buffer)
            image = x.XCreateImage(dpy, info.visual, 32, 2, 0, buffer, width, height, 32, width * 4)  # 2 = ZPixmap
            x.XPutImage(dpy, pixmap, gc, image, 0, 0, 0, 0, width, height)
            ids.append(pixmap)
        return ids

    def set_shadow(self, window: int) -> None:
        """Give the window KWin's drop shadow (``_KDE_NET_WM_SHADOW``)."""
        if getattr(self, "_shadow_ids", None) is None:
            self._shadow_ids = self._create_pixmaps()
        values = [*self._shadow_ids, *SHADOW_PAD]
        data = (ctypes.c_long * len(values))(*values)
        atom = self.x.XInternAtom(self.dpy, b"_KDE_NET_WM_SHADOW", 0)
        self.x.XChangeProperty(self.dpy, window, atom, _XA_CARDINAL, 32, 0, data, len(values))
        self.x.XFlush(self.dpy)

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

    def frame_extents(self, window: int) -> tuple[int, int, int, int] | None:
        """``_GTK_FRAME_EXTENTS`` as (left, right, top, bottom), or None if the window does not have the property.

        Obsidian's opaque pop-out windows (Settings and detached panes) have it: Chromium draws its own rounded
        corners and shadow, with the content inset from the X window by this margin. Our transparent main window has none.
        """
        atom = self.x.XInternAtom(self.dpy, b"_GTK_FRAME_EXTENTS", 1)  # only_if_exists: 0 means it was never set
        if not atom:
            return None
        actual_type, actual_format = ctypes.c_ulong(), ctypes.c_int()
        nitems, after, prop = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.POINTER(ctypes.c_long)()
        self.x.XGetWindowProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long, ctypes.c_long, ctypes.c_int, ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_long)),
        ]
        self.x.XGetWindowProperty(self.dpy, window, atom, 0, 4, 0, 0, ctypes.byref(actual_type), ctypes.byref(actual_format),
                                  ctypes.byref(nitems), ctypes.byref(after), ctypes.byref(prop))
        result = tuple(int(prop[k]) for k in range(4)) if nitems.value >= 4 and prop else None
        if prop:
            self.x.XFree.argtypes = [ctypes.c_void_p]
            self.x.XFree(prop)
        return result

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


def follow(pid: int, radius: int, interval: float = 1.0, icon: bytes | None = None, shadow: bool = True) -> None:
    """Keep the blur region of every window of ``pid`` matched to its size until the process exits.
    If ``icon`` (``icon.wmicon`` data) is given, each new window also gets it as its window icon, and with
    ``shadow`` (default) a KDE drop shadow.

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
    blurred: set[int] = set()
    next_scan = 0.0
    while process_alive(pid):
        now = time.monotonic()
        if now >= next_scan:
            next_scan = now + interval
            for window in map(int, window_ids(pid)):
                if window in known:
                    continue
                conn.watch(window)
                size = geometry(str(window))
                if not size or size[0] <= 40:
                    continue  # helper windows
                known[window] = size
                if icon:
                    conn.set_window_icon(window, icon)
                if conn.frame_extents(window) is not None:
                    continue  # Settings and pop-outs draw their own frame and shadow: leave them alone
                conn.set_region(window, size[0], size[1], radius)
                blurred.add(window)
                if shadow:
                    conn.set_shadow(window)
        select.select([conn.fd], [], [], 0.05)
        for window, size in conn.sizes().items():
            if window in known and size[0] > 40 and known[window] != size and window in blurred:
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
