"""Command line interface: ``obsidian-translucent {doctor,build,run,install-app,uninstall-app,install-snippet}``."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
from importlib import resources
from pathlib import Path

from . import __version__, app, asar, blur, patch, paths

SNIPPETS = ("translucent", "compact-code")
DEFAULT_RADIUS = 10  # keep in sync with --tl-radius in snippets/translucent.css


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def obsidian_version(archive: Path) -> str:
    try:
        return json.loads(asar.read_file(archive, "package.json"))["version"]
    except (asar.AsarError, KeyError, ValueError, OSError):
        return "unknown"


def _tool_digest(source_sha: str) -> str:
    """Changes whenever the source asar or any file we generate changes, so builds refresh themselves."""
    h = hashlib.sha256(source_sha.encode())
    for name in ("wrapper-main.js", "icon-256.png"):
        h.update(app.asset(name))
    h.update(resources.files("obsidian_translucent").joinpath("snippets", "translucent.css").read_bytes())
    h.update(__version__.encode())
    return h.hexdigest()


def _install_node_modules(src: Path, dist: Path) -> None:
    """Put the launcher's node_modules next to our wrapper.

    Obsidian's renderer resolves ``@electron/remote`` (and the native btime / get-fonts modules) relative to the
    app directory. In the stock layout that directory is ``app.asar``; ours is a plain folder, so the same modules
    must exist in ``<dist>/node_modules``.
    """
    import tempfile

    target = dist / "node_modules"
    with tempfile.TemporaryDirectory() as tmp:
        asar.extract(src / "app.asar", tmp)
        packed = Path(tmp) / "node_modules"
        if packed.is_dir():
            shutil.copytree(packed, target, dirs_exist_ok=True)
    unpacked = src / "app.asar.unpacked" / "node_modules"
    if unpacked.is_dir():
        shutil.copytree(unpacked, target, dirs_exist_ok=True)


def build(force: bool = False) -> Path:
    """Create or refresh the app directory in the data directory. Returns that directory.

    Layout: our wrapper (main.js, package.json, translucent.css, icon.png) next to a copy of the stock
    launcher (app.asar) and the patched obsidian.asar. ``electron <dir>`` runs it.
    """
    src, dist = paths.source_dir(), paths.dist_dir()
    src_asar = src / "obsidian.asar"
    if not (src_asar.is_file() and (src / "app.asar").is_file()):
        raise SystemExit(f"no Obsidian install found in {src} (set OBSIDIAN_TRANSLUCENT_SOURCE)")

    stamp = dist / "build.json"
    digest = _tool_digest(_sha256(src_asar))
    if not force and stamp.is_file():
        try:
            if json.loads(stamp.read_text()).get("digest") == digest:
                return dist
        except ValueError:
            pass

    data, applied = patch.apply(src_asar.read_bytes())  # raises PatchError on unsupported versions
    version = obsidian_version(src_asar)
    if dist.exists():
        shutil.rmtree(dist)  # our own build output, never the stock install
    dist.mkdir(parents=True)
    shutil.copy2(src / "app.asar", dist / "app.asar")
    if (src / "app.asar.unpacked").is_dir():
        shutil.copytree(src / "app.asar.unpacked", dist / "app.asar.unpacked")
    _install_node_modules(src, dist)
    (dist / "obsidian.asar").write_bytes(data)
    (dist / "main.js").write_bytes(app.asset("wrapper-main.js"))
    (dist / "icon.png").write_bytes(app.asset("icon-256.png"))
    (dist / "translucent.css").write_bytes(resources.files("obsidian_translucent").joinpath("snippets", "translucent.css").read_bytes())
    # the stock launcher compares app.getVersion() with update versions, so ours must report Obsidian's own version
    (dist / "package.json").write_text(
        json.dumps({"name": app.APP_ID, "productName": app.APP_NAME, "version": version if version != "unknown" else "0.0.0", "main": "main.js"}, indent=1)
    )
    stamp.write_text(json.dumps({"digest": digest, "obsidian": version, "patches": applied or "already patched", "tool": __version__}))
    print(f"built {dist} (Obsidian {version})", file=sys.stderr)
    return dist


def cmd_build(args) -> int:
    build(force=args.force)
    return 0


def cmd_run(args) -> int:
    dist = build()
    user_data = paths.user_data_dir()
    if app.seed_user_data(paths.config_dir(), user_data):
        print(f"created {user_data} from your Obsidian settings (vault list); the stock app is not touched", file=sys.stderr)
    cmd = [
        paths.electron_command(), str(dist), "--ozone-platform=x11", f"--class={app.APP_ID}",
        f"--user-data-dir={user_data}", *paths.user_flags(), *args.obsidian_args,
    ]
    proc = subprocess.Popen(cmd)
    if not args.no_blur:
        try:
            threading.Thread(target=blur.follow, args=(proc.pid, args.radius), kwargs={"icon": app.asset("icon.wmicon")}, daemon=True).start()
        except RuntimeError as exc:  # pragma: no cover
            print(f"blur disabled: {exc}", file=sys.stderr)
    return proc.wait()


def _exec_command() -> str:
    found = shutil.which("obsidian-translucent")
    if found:
        return found
    return str(Path(__file__).resolve().parents[2] / "bin" / "obsidian-translucent")


def cmd_install_app(_args) -> int:
    for path in app.install_desktop(_exec_command()):
        if path.suffix == ".desktop":
            print(f"installed {path}")
    print(f'"{app.APP_NAME}" is now in your application menu, with its own icon. The stock Obsidian is unchanged.')
    return 0


def cmd_uninstall_app(_args) -> int:
    removed = app.uninstall_desktop()
    print(f"removed {len(removed)} files")
    return 0


def cmd_follow(args) -> int:
    blur.follow(args.pid, args.radius, icon=app.asset("icon.wmicon"))
    return 0


def cmd_doctor(_args) -> int:
    ok = True

    def line(label: str, good: bool, detail: str) -> None:
        nonlocal ok
        ok &= good
        print(f"[{'ok' if good else '!!'}] {label}: {detail}")

    src = paths.source_dir()
    line("Obsidian install", (src / "obsidian.asar").is_file(), str(src))
    if (src / "obsidian.asar").is_file():
        print(f"     version {obsidian_version(src / 'obsidian.asar')}")
        try:
            _, applied = patch.apply((src / "obsidian.asar").read_bytes())
            line("patch applies", True, ", ".join(applied) or "already patched")
        except patch.PatchError as exc:
            line("patch applies", False, str(exc))
    updates = sorted(paths.user_data_dir().glob("obsidian-*.asar"))
    line(
        "in-app update asar",
        not updates,
        "none" if not updates else f"{updates[0].name} in our user-data dir would be loaded INSTEAD of the patched copy; delete it (see docs/TROUBLESHOOTING.md)",
    )
    electron = paths.electron_command()
    line("Electron", shutil.which(electron) is not None, electron)
    for tool in ("xdotool", "xprop"):
        line(tool, shutil.which(tool) is not None, shutil.which(tool) or "missing (needed for blur)")
    session = os.environ.get("XDG_SESSION_TYPE", "?")
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "?")
    line("desktop", "KDE" in desktop, f"{desktop} / {session} (blur needs KDE Plasma; transparency works elsewhere)")
    return 0 if ok else 1


def cmd_install_snippet(args) -> int:
    vault = Path(args.vault).expanduser()
    if not (vault / ".obsidian").is_dir():
        raise SystemExit(f"{vault} does not look like an Obsidian vault (no .obsidian folder)")
    target = vault / ".obsidian" / "snippets"
    target.mkdir(exist_ok=True)
    names = args.snippets or ["translucent"]
    unknown = [n for n in names if n not in SNIPPETS]
    if unknown:
        raise SystemExit(f"unknown snippet {unknown[0]!r}; available: {', '.join(SNIPPETS)}")
    for name in names:
        text = resources.files("obsidian_translucent").joinpath("snippets", f"{name}.css").read_text()
        (target / f"{name}.css").write_text(text)
        print(f"installed {target / (name + '.css')}")
    print("Enable them in Settings -> Appearance -> CSS snippets (restart Obsidian if the list does not refresh).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="obsidian-translucent", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="check that everything needed is present and the patch applies")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("build", help="build the patched copy of Obsidian in the data directory")
    p.add_argument("--force", action="store_true", help="rebuild even if the source is unchanged")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("run", help="build if needed, then start Obsidian with a transparent, blurred window")
    p.add_argument("--radius", type=int, default=DEFAULT_RADIUS, choices=range(0, blur.MAX_RADIUS + 1), metavar=f"0-{blur.MAX_RADIUS}",
                   help="blur corner radius in px (match --tl-radius in the CSS)")
    p.add_argument("--no-blur", action="store_true", help="transparent window only, no KDE blur")
    p.add_argument("obsidian_args", nargs="*", help="passed through to Obsidian")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("install-app", help=f"add '{app.APP_NAME}' to your application menu with its own icon")
    p.set_defaults(func=cmd_install_app)

    p = sub.add_parser("uninstall-app", help="remove the menu entry and icons")
    p.set_defaults(func=cmd_uninstall_app)

    p = sub.add_parser("follow", help="keep the blur region of an already running Obsidian (by PID) matched to its window")
    p.add_argument("pid", type=int)
    p.add_argument("--radius", type=int, default=DEFAULT_RADIUS, choices=range(0, blur.MAX_RADIUS + 1), metavar=f"0-{blur.MAX_RADIUS}")
    p.set_defaults(func=cmd_follow)

    p = sub.add_parser("install-snippet", help="copy the CSS snippet(s) into a vault")
    p.add_argument("vault")
    p.add_argument("snippets", nargs="*", metavar="SNIPPET", help="translucent (default) and/or compact-code")
    p.set_defaults(func=cmd_install_snippet)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except patch.PatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
