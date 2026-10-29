# obsidian-translucent

Run [Obsidian](https://obsidian.md) on Linux with a **transparent, blurred, rounded window**: backgrounds
see through to the desktop, text and icons stay sharp.

Stock Obsidian can only do this on macOS and Windows. On Linux the window is created opaque, so CSS alone cannot
help. This project makes a small, same-length patch to a *local copy* of your own Obsidian install, runs that copy, and
ships a CSS snippet that does the look.

> **Status:** works on KDE Plasma (Wayland) with Obsidian 1.14.x on Arch. Transparency should work on any compositor;
> the blur is KDE-specific. Reports and patches for other setups are welcome (see [CONTRIBUTING](CONTRIBUTING.md)).

## Requirements

* Obsidian installed from your distro (needs `obsidian.asar` and `app.asar`, e.g. `/usr/lib/obsidian` on Arch)
* Electron as Obsidian's launcher uses it (`electron43` on Arch)
* Python 3.9+ (standard library only)
* For blur: KDE Plasma with the *Background Blur* desktop effect on, plus `xdotool` and `xprop`

## Quick start

```bash
git clone https://github.com/mij001/obsidian-translucent && cd obsidian-translucent
./bin/obsidian-translucent doctor          # check your system
./bin/obsidian-translucent install-app     # adds "Obsidian Translucent" (own icon) to your application menu
./bin/obsidian-translucent run             # or start it from a terminal; builds on first use
```

It is a **separate app**. Your stock Obsidian is not modified, keeps its own settings and keeps updating through your package
manager. The two can run side by side. Your vault list is copied into the new app's own settings on first start
(`~/.config/obsidian-translucent`); after that they are independent. Vault contents and per-vault settings are shared as usual,
and nothing is added to your vaults: the translucent look is injected by the app itself.

Pass Obsidian arguments after `--`: `obsidian-translucent run -- obsidian://open?vault=...`. Remove the menu entry with
`uninstall-app`. Or install the command: `pip install --user .`.

## Tuning

Create `~/.config/obsidian-translucent/translucent.json`:

```json
{ "alpha": 0.4, "radius": 10 }
```

| key | default | meaning |
|---|---|---|
| `alpha` | `0.4` | 0 = fully clear, 1 = solid |
| `radius` | `10` | window corner radius in px (also pass `run --radius N`, max 11) |
| `clipRight`, `clipBottom` | `2`, `1` | corner alignment fudge at 1.1× display scale; adjust if one corner looks tighter than the others |

Restart the app to apply. `obsidian-translucent install-snippet <vault> compact-code` adds an optional CSS snippet for tighter
code-block line spacing to a vault.

## How it works, in one paragraph

`run` builds a copy of `/usr/lib/obsidian` in `~/.local/share/obsidian-translucent/dist`, changes one option in the copy
(`backgroundColor:"#00000000"` becomes `transparent:true`, padded to the same length), and starts it under XWayland
because KWin only honours its blur hint from X11 windows. A small loop keeps that hint, a rounded-rectangle region,
matched to the window size. A tiny wrapper injects the CSS. Your system Obsidian is never modified, and the copy is rebuilt
automatically when the system package changes (the new app's own in-app updater is switched off for that reason). Details: [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md).

## Docs

* [How it works](docs/HOW-IT-WORKS.md) · [Architecture notes](docs/ARCHITECTURE.md) · [Troubleshooting](docs/TROUBLESHOOTING.md)
* [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md) · [Legal](docs/LEGAL.md)

## Legal

Obsidian is proprietary. This repository contains **no Obsidian code**: the patched copy is generated on your machine from
your own install, and the repo's `.gitignore` keeps generated and extracted files out. MIT license for this repository's
own files. See [docs/LEGAL.md](docs/LEGAL.md). Not affiliated with or endorsed by Obsidian.
