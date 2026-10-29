import unittest

from obsidian_translucent import patch


class PatchTests(unittest.TestCase):
    CODE = b'xx{width:800,backgroundColor:"#00000000",trafficLightPosition:{x:19,y:12}}yy'

    def test_applies_and_keeps_length(self):
        out, applied = patch.apply(self.CODE)
        self.assertEqual(applied, ["vault-window-transparent"])
        self.assertEqual(len(out), len(self.CODE))
        self.assertIn(b"transparent:!0,", out)
        self.assertNotIn(b'backgroundColor:"#00000000"', out)

    def test_idempotent(self):
        once, _ = patch.apply(self.CODE)
        twice, applied = patch.apply(once)
        self.assertEqual(once, twice)
        self.assertEqual(applied, [])

    def test_unsupported_version_fails_loudly(self):
        with self.assertRaises(patch.PatchError):
            patch.apply(b"completely different code")

    def test_ambiguous_match_fails(self):
        with self.assertRaises(patch.PatchError):
            patch.apply(self.CODE + self.CODE)

    def test_patch_must_keep_length(self):
        with self.assertRaises(ValueError):
            patch.Patch("bad", b"abc", b"ab")


if __name__ == "__main__":
    unittest.main()
