# How it works

Four independent pieces; each can be understood and fixed on its own.

## 1. A transparent window (`src/obsidian_translucent/patch.py`)

Electron can only make a window transparent when it is *created* with `transparent: true`. Obsidian creates its vault window
with `backgroundColor:"#00000000"` and no `transparent` flag (and hides its translucency setting on Linux), so the window is
opaque and no CSS can change that. The patch replaces that one option with `transparent:!0,` followed by 13 spaces. The byte
length is unchanged, so no offsets inside `obsidian.asar` move and no repacking is needed. If the original text is not found
exactly once the tool stops with a clear error rather than patching blindly. Frameless windows (Obsidian's default) are
required; Obsidian's "native frame" option is not supported.

## 2. A separate app, not a patched install (`cli.py: build`, `app.py`)

The system package stays untouched, and so do your vaults and the stock app's settings. `build` creates an app directory in
`~/.local/share/obsidian-translucent/dist`:

```
main.js             our wrapper (src/obsidian_translucent/assets/wrapper-main.js): injects the CSS, sets the window icon,
                    then requires the unmodified launcher below
package.json        name/productName ours; version = Obsidian's (the launcher compares app.getVersion() with update versions)
translucent.css     the look, injected into every Obsidian window by the wrapper (settings override it, see README)
icon.png            our logo
app.asar            copy of the stock launcher            node_modules/   the launcher's modules (see below)
obsidian.asar       copy of the stock app with the one-line patch
```

* `node_modules/` is needed because Obsidian's renderer resolves `@electron/remote` relative to the *app directory*; in the
  stock layout that is `app.asar`, in ours it is a plain folder. `build` extracts the launcher's modules and merges the unpacked
  native ones (`btime`, `get-fonts`).
* A `build.json` keeps a digest of the source asar and of everything we generate, so a system update or a new version of this tool
  triggers a rebuild on the next `run` (and a clear error if the patch no longer matches).
* Own settings directory: `run` starts Electron with `--user-data-dir=~/.config/obsidian-translucent`, `--class=obsidian-translucent`
  (so the window gets its own taskbar entry) and `--ozone-platform=x11`. On first start the vault list and window-state json files are
  copied from `~/.config/obsidian` (read only; the stock directory is never written). `updateDisabled` is set in our copy:
  Obsidian's launcher loads a newer `obsidian-<version>.asar` from its user-data directory in preference to the one beside it, which
  is how in-app updates work and would bypass the patch. Updates for the translucent app come from rebuilding after the system package updates.
  `doctor` flags a stray update asar in our directory.
* Separate directories also mean a separate single-instance lock, so both apps can run at the same time. Opening the *same vault*
  in both at once is possible but not recommended: Obsidian expects one process per vault.
* The desktop entry (`install-app`) declares no MIME types, so `obsidian://` links stay with the stock app.

## 3. KDE blur (`blur.py`)

KWin blurs what is behind a window when it sets the `_KDE_NET_WM_BLUR_BEHIND_REGION` property on it. Chromium on native Wayland
does not set it, so we run Electron with `--ozone-platform=x11` (XWayland) and set the property ourselves with `xprop`.
Details that matter:

* the value is a list of `x y w h` rectangles, and `xprop` accepts at most 64 numbers, so a rounded rectangle is approximated
  with bands of rows that share a corner inset (radius up to 11);
* rectangles overlap by a row; otherwise a dark unblurred seam appears where bands meet;
* the region is re-set the moment the window size changes. `follow` holds one Xlib connection (via `ctypes`, no dependencies),
  listens for `ConfigureNotify` events and sets the property directly, so the blur tracks a resize drag within a frame or two.
  Spawning `xdotool`/`xprop` per update (the first implementation, polling every 0.3 s) made the blur visibly trail the window
  while resizing: about 335 ms median to catch up, against about 19 ms now. New windows (pop-outs) are discovered once a second.
  If libX11 cannot be loaded it falls back to the slower polling path.

## Window icon

Electron's `BrowserWindow.setIcon` did not reach the XWayland window, so KDE's task manager showed a generic icon. The follower
therefore sets `_NET_WM_ICON` itself (and `_KDE_NET_WM_DESKTOP_FILE`) on every new window, from `assets/icon.wmicon`: little-endian
32-bit words, `width height ARGB...` for 32, 48 and 128 px, generated from `assets/icon.svg` by `tools/make-icons.py` (dev-time,
needs `rsvg-convert` and Pillow). The menu entry installs the same logo into the user's `hicolor` icon theme.

## Drop shadow

A frameless transparent window gets no shadow from KWin by itself, and CSS cannot draw one outside the window bounds. KWin draws a
shadow for X11 windows that carry `_KDE_NET_WM_SHADOW`: eight pixmaps (top, top-right, right, bottom-right, bottom, bottom-left,
left, top-left) and four padding values. `blur.shadow_tiles()` computes them (a Gaussian-blurred rectangle moved a few pixels down;
separable, so every tile is a product of two 1-D profiles), the follower uploads them once as 32-bit pixmaps and points every
window at them. KWin hides the shadow when the window is maximized. Constants: `SHADOW_SIGMA`, `SHADOW_OFFSET`, `SHADOW_ALPHA`, `SHADOW_PAD`.

## Which windows get blur and shadow

Only the transparent main window. Obsidian's opaque pop-outs (Settings, detached panes) are drawn by Chromium with its own
client-side decoration: rounded corners and a shadow, with the content inset from the X window by a margin it advertises in
`_GTK_FRAME_EXTENTS`. Blurring the whole X window there paints a flat gray box over Chromium's shadow, and our shadow would double
it, so the follower skips any window with that property (`XConnection.frame_extents`), and only gives it the icon. The CSS skips
them too (`:not(.is-popout-window)`), because rounding or alpha on an opaque window leaves a dark rectangle.

Known limit: under XWayland Chromium's own shadow on those windows shows as a flat dark strip along the right and bottom edge of
the Settings window. That is stock Chromium behaviour on this platform, not something we draw; setting an X Shape clip and
`setHasShadow(false)` were both tried and have no effect there.

## 4. The look (`snippets/translucent.css`, injected by the wrapper)

* backgrounds get an alpha through Obsidian's own variables (`--background-primary`, `--titlebar-background`, ...), so most
  themes work without edits; text stays opaque;
* the active tab's curved "feet" use a solid box-shadow that shows as dark squares on a translucent bar, so they are hidden;
* menus, suggestions, hover previews, tooltips and dialogs get a 97% opaque fill through Obsidian's `--menu-background` family of
  variables; at the window alpha they let the note text show through and overlap their entries;
* the status bar floats over scrolling text, so it gets a nearly solid fill. `backdrop-filter` is avoided there because
  Chromium does not clip it to rounded corners;
* rounded corners come from a single `clip-path` on `<body>`. A radius on `.app-container` is not enough: the window-button
  group and the status bar are outside it and keep square corners. At 1.1× display scale the page box is a pixel or two
  larger than the window on the right and bottom, so the clip is inset by `--tl-clip-right` / `--tl-clip-bottom`; with those
  values all four corners were measured identical.

## Known limits

* Pop-out windows are not patched (they are created from a different options object).
* Blur needs KDE Plasma with Background Blur enabled; other compositors get transparency without blur.
* The corner inset values were tuned at 1.1× display scale; other scales may need a different `--tl-clip-*`.
* Running under XWayland, not native Wayland.
