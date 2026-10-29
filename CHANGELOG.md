# Changelog

## 0.1.0 (unreleased)

* Transparent vault window via a same-length patch of a local copy of Obsidian (tested on 1.14.5).
* KDE blur region with rounded corners, kept in sync with the window size.
* Separate "Obsidian Translucent" app: own settings directory, window class, desktop entry and logo (`install-app`); the stock Obsidian is never modified.
* The look is injected by a small wrapper, so no vault or settings file is touched. Optional `translucent.json` for alpha/radius.
* Window icon set through `_NET_WM_ICON` (Electron's own `setIcon` does not reach the XWayland window).
* `compact-code` CSS snippet and `install-snippet` for vaults (optional).
* Blur follows window resizes through a direct Xlib connection instead of polling subprocesses (about 335 ms to 19 ms lag).
* `doctor`, `build` (auto-rebuild when the system package changes), `run`.
