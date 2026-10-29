import json
import os
import tempfile
import unittest
from pathlib import Path

from obsidian_translucent import app, asar, cli, patch


def make_install(root: Path, version="1.2.3") -> Path:
    """A fake /usr/lib/obsidian: a launcher asar with node_modules, and an obsidian.asar holding the patch target."""
    src = root / "install"
    launcher = root / "launcher_src"
    (launcher / "node_modules" / "@electron" / "remote").mkdir(parents=True)
    (launcher / "node_modules" / "@electron" / "remote" / "index.js").write_text("module.exports={}")
    (launcher / "main.js").write_text("// launcher")
    src.mkdir()
    asar.pack(launcher, src / "app.asar")
    (src / "app.asar.unpacked" / "node_modules" / "btime").mkdir(parents=True)
    (src / "app.asar.unpacked" / "node_modules" / "btime" / "index.js").write_text("//")
    app_dir = root / "obsidian_src"
    app_dir.mkdir()
    (app_dir / "package.json").write_text(json.dumps({"version": version}))
    (app_dir / "main.js").write_bytes(b"x" + patch.VAULT_WINDOW.old + b"y")
    asar.pack(app_dir, src / "obsidian.asar")
    return src


class SeedUserData(unittest.TestCase):
    def test_copies_vault_list_once_and_disables_updates(self):
        tmp = Path(tempfile.mkdtemp())
        stock, ours = tmp / "stock", tmp / "ours"
        stock.mkdir()
        (stock / "obsidian.json").write_text(json.dumps({"vaults": {"a": {"path": "/v"}}}))
        (stock / "abc.json").write_text("{}")
        self.assertTrue(app.seed_user_data(stock, ours))
        cfg = json.loads((ours / "obsidian.json").read_text())
        self.assertEqual(cfg["vaults"]["a"]["path"], "/v")
        self.assertIs(cfg["updateDisabled"], True)
        self.assertTrue((ours / "abc.json").is_file())
        # later changes in the stock app are not copied again, and our own edits survive
        (stock / "obsidian.json").write_text("{}")
        cfg["vaults"]["b"] = {"path": "/w"}
        (ours / "obsidian.json").write_text(json.dumps(cfg))
        self.assertFalse(app.seed_user_data(stock, ours))
        self.assertIn("b", json.loads((ours / "obsidian.json").read_text())["vaults"])

    def test_never_writes_to_the_stock_directory(self):
        tmp = Path(tempfile.mkdtemp())
        stock = tmp / "stock"
        stock.mkdir()
        (stock / "obsidian.json").write_text("{}")
        before = sorted(p.name for p in stock.iterdir()), (stock / "obsidian.json").read_text()
        app.seed_user_data(stock, tmp / "ours")
        self.assertEqual(before, (sorted(p.name for p in stock.iterdir()), (stock / "obsidian.json").read_text()))


class DesktopEntry(unittest.TestCase):
    def test_entry_is_separate_from_stock_obsidian(self):
        text = app.desktop_entry("/usr/bin/obsidian-translucent")
        self.assertIn("Name=Obsidian Translucent", text)
        self.assertIn("Exec=/usr/bin/obsidian-translucent run %U", text)
        self.assertIn("Icon=obsidian-translucent", text)
        self.assertIn("StartupWMClass=obsidian-translucent", text)
        self.assertNotIn("MimeType", text)  # must not steal obsidian:// links from the stock app

    def test_install_and_uninstall_roundtrip(self):
        tmp = tempfile.mkdtemp()
        old = os.environ.get("XDG_DATA_HOME")
        os.environ["XDG_DATA_HOME"] = tmp
        try:
            written = app.install_desktop("/x/obsidian-translucent")
            self.assertTrue(any(p.name == "obsidian-translucent.desktop" for p in written))
            self.assertTrue(all(p.is_file() for p in written))
            self.assertEqual(len(app.uninstall_desktop()), len(written))
        finally:
            if old is None:
                os.environ.pop("XDG_DATA_HOME")
            else:
                os.environ["XDG_DATA_HOME"] = old


class BuildLayout(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src = make_install(self.tmp)
        os.environ["OBSIDIAN_TRANSLUCENT_SOURCE"] = str(self.src)
        os.environ["OBSIDIAN_TRANSLUCENT_DATA"] = str(self.tmp / "data")

    def tearDown(self):
        os.environ.pop("OBSIDIAN_TRANSLUCENT_SOURCE")
        os.environ.pop("OBSIDIAN_TRANSLUCENT_DATA")

    def test_build_makes_a_self_contained_patched_app_and_leaves_the_source_alone(self):
        before = (self.src / "obsidian.asar").read_bytes()
        dist = cli.build()
        self.assertEqual((self.src / "obsidian.asar").read_bytes(), before)  # stock install untouched
        self.assertNotEqual((dist / "obsidian.asar").read_bytes(), before)
        self.assertEqual(len((dist / "obsidian.asar").read_bytes()), len(before))
        for name in ("main.js", "package.json", "translucent.css", "icon.png", "app.asar"):
            self.assertTrue((dist / name).is_file(), name)
        self.assertTrue((dist / "node_modules" / "@electron" / "remote" / "index.js").is_file())
        self.assertTrue((dist / "node_modules" / "btime" / "index.js").is_file())
        pkg = json.loads((dist / "package.json").read_text())
        self.assertEqual(pkg["version"], "1.2.3")  # must equal Obsidian's, the launcher compares it with update versions
        self.assertEqual(pkg["main"], "main.js")

    def test_second_build_is_a_noop_and_force_rebuilds(self):
        dist = cli.build()
        marker = dist / "marker"
        marker.write_text("x")
        cli.build()
        self.assertTrue(marker.exists())
        cli.build(force=True)
        self.assertFalse(marker.exists())

    def test_unsupported_obsidian_fails_before_writing_anything(self):
        (self.src / "obsidian.asar").write_bytes(b"not the code we patch")
        with self.assertRaises(patch.PatchError):
            cli.build()
        self.assertFalse((self.tmp / "data" / "dist").exists())


if __name__ == "__main__":
    unittest.main()
