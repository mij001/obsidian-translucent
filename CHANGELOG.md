# Changelog

## 0.1.0 (unreleased)

* Transparent vault window via a same-length patch of a local copy of Obsidian (tested on 1.14.5).
* KDE blur region with rounded corners, kept in sync with the window size.
* Separate "Obsidian Translucent" app: own settings directory, window class, desktop entry and logo (`install-app`); the stock Obsidian is never modified.
* The look is injected by a small wrapper, so no vault or settings file is touched. Optional `translucent.json` for alpha/radius.
* Blur, shadow and the translucent CSS apply only to the transparent main window; Settings and pop-outs keep Chromium's own frame.
* Corner wedges painted with a faint tint so the shadow no longer ends in a white notch at the rounded corners.
* Blur, shadow and the translucent CSS apply only to the transparent main window; Settings and pop-outs keep Chromium's own frame
  (the follower now really skips windows that advertise `_GTK_FRAME_EXTENTS`).
* KDE drop shadow for every window (`_KDE_NET_WM_SHADOW`, drawn by KWin, hidden when maximized).
* Menus, suggestions, tooltips and dialogs are nearly solid so text underneath no longer shows through.
* Window icon set through `_NET_WM_ICON` (Electron's own `setIcon` does not reach the XWayland window).
* `compact-code` CSS snippet and `install-snippet` for vaults (optional).
* Blur follows window resizes through a direct Xlib connection instead of polling subprocesses (about 335 ms to 19 ms lag).
* `doctor`, `build` (auto-rebuild when the system package changes), `run`.
