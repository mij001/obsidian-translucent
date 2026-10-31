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


class ShadowTiles(unittest.TestCase):
    def alpha(self, tile, x, y):
        import struct

        w, _h, data = tile
        return struct.unpack_from("<I", data, (y * w + x) * 4)[0] >> 24

    def test_eight_tiles_with_the_padding_sizes(self):
        tiles = blur.shadow_tiles()
        top, right, bottom, left = blur.SHADOW_PAD
        self.assertEqual([(w, h) for w, h, _ in tiles],
                         [(1, top), (right, top), (right, 1), (right, bottom), (1, bottom), (left, bottom), (left, 1), (left, top)])
        for w, h, data in tiles:
            self.assertEqual(len(data), w * h * 4)

    def test_fades_outward_and_is_stronger_below_than_above(self):
        tiles = blur.shadow_tiles()
        top, right, bottom, left = blur.SHADOW_PAD
        right_tile, top_tile, bottom_tile = tiles[2], tiles[0], tiles[4]
        self.assertGreater(self.alpha(right_tile, 0, 0), self.alpha(right_tile, right - 1, 0))  # near > far
        self.assertEqual(self.alpha(right_tile, right - 1, 0), 0)  # fully faded at the outer edge
        self.assertGreater(self.alpha(bottom_tile, 0, 0), self.alpha(top_tile, 0, top - 1))  # offset downward

    def test_colour_is_black_premultiplied(self):
        for _w, _h, data in blur.shadow_tiles():
            self.assertTrue(all(data[i] == data[i + 1] == data[i + 2] == 0 for i in range(0, len(data), 4)))


if __name__ == "__main__":
    unittest.main()
