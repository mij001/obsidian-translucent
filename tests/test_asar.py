import json
import tempfile
import unittest
from pathlib import Path

from obsidian_translucent import asar


class AsarRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        src = self.tmp / "src"
        (src / "sub").mkdir(parents=True)
        (src / "package.json").write_text(json.dumps({"version": "9.9.9"}))
        (src / "sub" / "a.js").write_text("console.log(1)")
        (src / "empty.txt").write_text("")
        asar.pack(src, self.tmp / "t.asar")

    def test_read_file(self):
        self.assertEqual(json.loads(asar.read_file(self.tmp / "t.asar", "package.json"))["version"], "9.9.9")
        self.assertEqual(asar.read_file(self.tmp / "t.asar", "sub/a.js"), b"console.log(1)")

    def test_extract_matches_source(self):
        n = asar.extract(self.tmp / "t.asar", self.tmp / "out")
        self.assertEqual(n, 3)
        self.assertEqual((self.tmp / "out" / "sub" / "a.js").read_text(), "console.log(1)")

    def test_missing_file(self):
        with self.assertRaises(asar.AsarError):
            asar.read_file(self.tmp / "t.asar", "nope.js")

    def test_not_an_asar(self):
        (self.tmp / "bad").write_bytes(b"x")
        with self.assertRaises(asar.AsarError):
            asar.read_file(self.tmp / "bad", "a")


if __name__ == "__main__":
    unittest.main()
