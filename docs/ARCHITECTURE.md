# Obsidian internals relevant to this project (1.14.5, Linux, Arch `obsidian` package)

Notes on *how Obsidian is put together*, written in our own words so the patch can be maintained when Obsidian changes.
Nothing here is Obsidian's source; see [LEGAL.md](LEGAL.md). Line numbers refer to the beautified copy that
`make re` generates locally in `.local/study/pretty/` and will drift between versions; the *strings* are the stable landmarks.

## Tested versions

| Obsidian | patch applies | notes |
|---|---|---|
| 1.14.5 (Arch, Electron 43) | yes | KDE Plasma 6.8 Wayland, 1.1x display scale |

## Process model

```
/usr/bin/obsidian  ->  electron43 /usr/lib/obsidian/app.asar  [--flags from ~/.config/obsidian/user-flags.conf]

app.asar (launcher/main.js)
  - installs a require hook for "electron"; sets up @electron/remote
  - picks which obsidian.asar to run: a newer  <userData>/obsidian-<ver>.asar  if present
    (auto-update downloads to obsidian.asar.tmp, then renames), else /usr/lib/obsidian/obsidian.asar
  - loadApp(): require('<asar>/main.js')            [launcher/main.js: loadApp, lines ~300-460]

obsidian.asar
  main.js      Electron MAIN process: windows, menus, IPC, app:// protocol, single instance, updates   (252k beautified)
  app.js       RENDERER bundle for vault windows (webpack, nodeIntegration on, no sandbox)            (6.3M beautified)
  starter.js   renderer for the vault picker window          help.js   renderer for the help window
  worker.js    web worker (indexing / parsing)               sim.js    the sandbox-vault simulation
  quicklook.js macOS quick look (unused on Linux)            enhance.js small preload-ish helpers
  i18n.js + i18n/<lang>.json   translations                  lib/  vendored: mermaid, mathjax, prism, pdf.js, defuddle, pele
  app.css      all built-in styling (the variables that themes override)   public/   fonts, icons
```

## Main process (`pretty/main.js`, 5845 lines)

* single instance lock: line ~4152. Second launches forward their args (`obsidian://` URIs, file paths) to the first instance.
* `app://` protocol: `registerFileProtocol("app", ...)` at ~5200 (older Electron) or `protocol.handle("app", ...)` at ~5218.
  Serves the asar contents and vault files; sets `X-Frame-Options: DENY` for no-frame URLs.
* `obsidian://` handling: `setAsDefaultProtocolClient("obsidian")` ~5755, URI dispatcher `Ze(...)`.
* window creation
  * vault window: `new BrowserWindow(h)` ~4946. Options: `width/height/minWidth/minHeight`, `backgroundColor:"#00000000"`,
    `frame: Oe`, `titleBarStyle: qe`, `webPreferences {contextIsolation:false, nodeIntegration:true, nodeIntegrationInWorker:true, spellcheck:true, webviewTag:true}`.
  * pop-out windows: `setWindowOpenHandler` options near ~4429 (same prefs plus `affinity:"main-window"`).
  * starter / help windows: helper `Tt(...)` ~5013 (`backgroundColor:"#1e1e1e"`).
  * `Oe = (config.frame === "native")`, `qe = Oe ? "default" : "hidden"`. So the default is a frameless window with a hidden
    titlebar and Obsidian-drawn window buttons; the `frame` value lives in obsidian.json and is settable over IPC (~5306).
* web viewer / browser sessions: `session.fromPartition(...)` ~5498, with adblock lists over IPC.
* GPU: `disableGpu` in obsidian.json calls `app.disableHardwareAcceleration()` ~4532.

### IPC surface (`ipcMain.on/handle` in main.js, all invoked by app.js via `ipcRenderer`)

`adblock-frequency adblock-lists check-update cli context-menu copy-asar create-browser-session desktop-dir disable-gpu
disable-update documents-dir file-url frame get-default-vault-path get-documents-path get-icon get-sandbox-vault-path help
insider-build is-closing is-quitting latest-public-version open-file open-url policy print-to-pdf register-cli relaunch
render-menu request-url resources sandbox set-icon set-language set-menu starter terms trash update update-menu-items
vault vault-list vault-message vault-move vault-open vault-remove version`

Global state is `~/.config/obsidian/obsidian.json` (vault registry `{vaults:{id:{path,ts,open}}}`, plus `frame`, `disableGpu`,
`updateDisabled`, `insider`, `cli`, `icon`) and one `<vault-id>.json` per vault holding window bounds/zoom.
Per-vault settings live in `<vault>/.obsidian/` (`app.json`, `appearance.json`, `core-plugins.json`, `community-plugins.json`,
`workspace.json`, `graph.json`, `hotkeys.json`, `plugins/`, `snippets/`, `themes/`).

## Renderer (`app.js`)

Webpack bundle with two parts:

1. **Vendor modules** (`app_split/modules/*.js`, 135 files, ~12k lines): small npm dependencies (I only spot-checked a few: one YAML,
   one mdast and one color module showed up; the rest are not identified). The largest are 5416 and 5759 (~2100 and ~2300 lines).
2. **The body** (`app_split/bootstrap_tail.js`, ~137k lines): one flat function scope containing, in order:
   * CodeMirror 6 (`@codemirror/state`, `view`, `language`, `commands`, ...) and the Lezer parsers, exported through
     `n.r(x), n.d(x, {...})` blocks at the start (chunks 000-003)
   * property/YAML handling (004-005), metadata cache and link resolution (006, 012-018)
   * vault, file adapters, themes/snippets loading (009-014)
   * plugin loader and community-plugin API (015, 024, 033)
   * Bases (019-021, 026-027), Canvas (027-029), Sync/Publish (030-031), importer/web viewer (023, 025)
   * workspace, leaves, UI chrome, menus, settings (008, 011, 022, 032)

   `app_chunks/_toc.json` gives the per-chunk keyword counts; searching `app_chunks/` for a string such as
   `"enabledCssSnippets"` is the fastest way in.

### Vault config defaults (the object containing `translucency: !1`, `cssTheme`, `enabledCssSnippets` ...)

Defaults include `useTab`, `tabSize:4`, `livePreview:true`, `defaultViewMode:"source"`, `trashOption:"system"`,
`newLinkFormat:"shortest"`, `theme:"system"`, `cssTheme:""`, `enabledCssSnippets:[]`, `translucency:false`,
`baseFontSizeAction:false`, `hotkeys:{}`. Only the keys that differ from the defaults are written to `app.json` / `appearance.json`,
which is why `app.json` can be `{}`.

### Core plugin ids (strings in app.js)

canvas, bookmarks, graph, bases, global-search, sync, properties, file-explorer, daily-notes, outline, footnotes,
file-recovery, templates, publish, command-palette, zk-prefixer, workspaces, switcher, slides, random-note,
outgoing-link, editor-status, backlink, word-count, tag-pane, slash-command, page-preview, note-composer,
audio-recorder, markdown-importer.

### Translucency in the stock app

`appearance.json` key `translucency` toggles a settings row ("Translucent window") that is only built when a platform
check (`fw()`) passes, i.e. macOS and Windows. Enabling it calls `vw(electronWindow, true)` and adds `body.is-translucent`.
On Linux the row is never created, so the flag cannot be turned on from the UI, and the window is created opaque
(no `transparent: true`), which is why CSS alone cannot make it see-through.

## The translucency patch

One same-length substitution in `obsidian.asar`, applied to the vault window options (see `src/obsidian_translucent/patch.py`):

```
backgroundColor:"#00000000",trafficLightPosition      original
transparent:!0,             trafficLightPosition      patched (the replacement is padded with 13 spaces)
```

Only the vault window is patched; pop-out windows are built from a different options object and stay opaque.
The tool never edits the system install: it builds a patched copy under `~/.local/share/obsidian-translucent/dist`.

When a new Obsidian release breaks the match, `run` fails with a `PatchError`. Update `VAULT_WINDOW` as described in
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Studying your own install

```bash
pip install jsbeautifier      # once, in a venv is fine
make re                       # extracts, beautifies and splits into .local/study/ (git-ignored)
```

`make re` produces, under `.local/study/`: `raw/` (the extracted asar), `pretty/` (beautified bundles), `app_split/` (the
renderer bundle's webpack modules plus its body) and `app_chunks/` (the body cut into ~3500-line chunks with a `_toc.json`).
Identifiers stay minified, but string literals and public API names survive; searching for a string such as
`enabledCssSnippets` is the quickest way in. This output is proprietary: do not commit or publish it.
