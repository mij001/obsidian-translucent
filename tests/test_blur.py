import unittest

from obsidian_translucent import blur


def covered(rects, w, h):
    """Set of covered pixels (small sizes only)."""
    px = set()
    for i in range(0, len(rects), 4):
        x, y, rw, rh = rects[i : i + 4]
        px |= {(a, b) for a in range(x, x + rw) for b in range(y, y + rh)}
    return px


class BlurRegion(unittest.TestCase):
    def test_fits_xprop_limit_for_supported_radii(self):
        for r in range(0, blur.MAX_RADIUS + 1):
            self.assertLessEqual(len(blur.region(1000, 700, r)), blur.MAX_VALUES, r)

    def test_stays_inside_window_and_is_symmetric(self):
        w, h, r = 120, 80, 10
        px = covered(blur.region(w, h, r), w, h)
        self.assertTrue(all(0 <= x < w and 0 <= y < h for x, y in px))
        for x, y in px:
            self.assertIn((w - 1 - x, y), px)
            self.assertIn((x, h - 1 - y), px)

    def test_corner_pixel_excluded_edges_included(self):
        w, h = 120, 80
        px = covered(blur.region(w, h, 10), w, h)
        self.assertNotIn((0, 0), px)
        self.assertIn((60, 0), px)
        self.assertIn((0, 40), px)
        self.assertEqual(len(px), w * h - len({(x, y) for x in range(w) for y in range(h)} - px))

    def test_no_seams_between_bands(self):
        w, h = 120, 80
        px = covered(blur.region(w, h, 10), w, h)
        for y in range(h):
            self.assertIn((60, y), px, f"gap at row {y}")

    def test_too_large_radius_is_rejected(self):
        with self.assertRaises(ValueError):
            blur.region(1000, 700, blur.MAX_RADIUS + 1)


if __name__ == "__main__":
    unittest.main()
