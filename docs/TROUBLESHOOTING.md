# Troubleshooting

Run `obsidian-translucent doctor` first; it checks the install, whether the patch applies, Electron, `xdotool`, `xprop` and the desktop.

| symptom | likely cause and fix |
|---|---|
| window is solid, not see-through | you started the stock Obsidian instead of *Obsidian Translucent* / `obsidian-translucent run`; or a theme sets opaque backgrounds with `!important` (open an issue naming the theme) |
| see-through but not blurred | enable KWin's *Background Blur* effect; check `xdotool` and `xprop` are installed; blur only works under KDE |
| `patch ... expected the original code exactly once` | the installed Obsidian version changed that code. Open an issue with the output of `doctor`; see "Updating the patch" in CONTRIBUTING |
| one corner looks tighter than the others | adjust `--tl-clip-right` / `--tl-clip-bottom` in the snippet (display scaling changes the page box by a pixel or two) |
| text shows through under the status bar | another theme/snippet overrides `.status-bar`; keep our 0.92 alpha rule last |
| my vaults are missing in the translucent app | its vault list was copied once, on first start. Open the vault from the picker, or delete `~/.config/obsidian-translucent/obsidian.json` to copy the stock list again |
| window turns opaque after an Obsidian "update" | Obsidian's launcher prefers a newer `obsidian-<version>.asar` downloaded into the user-data directory over the one next to it, which bypasses the patch. `doctor` reports it. It lives in `~/.config/obsidian-translucent/` (we switch updates off there; this only happens if the setting was reset). Delete the file |
