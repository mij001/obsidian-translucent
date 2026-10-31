import unittest
from importlib import resources


class Snippets(unittest.TestCase):
    def css(self, name):
        return resources.files("obsidian_translucent").joinpath("snippets", f"{name}.css").read_text()

    def test_braces_balance(self):
        for name in ("translucent", "compact-code"):
            text = self.css(name)
            self.assertEqual(text.count("{"), text.count("}"), name)

    def test_documented_knobs_exist(self):
        text = self.css("translucent")
        for knob in ("--tl-alpha", "--tl-radius", "--tl-clip-right", "--tl-clip-bottom", "--tl-wedge-top", "--tl-wedge-bottom"):
            self.assertIn(knob, text)

    def test_every_rule_skips_opaque_popout_windows(self):
        """Settings and other pop-outs are opaque windows; rounding/clip/alpha there leaves a dark rectangle."""
        import re

        text = re.sub(r"/\*.*?\*/", "", self.css("translucent"), flags=re.S)
        for selector in re.findall(r"([^{}]+)\{", text):
            selector = selector.strip()
            if selector.startswith("html") or selector == "body" or ".workspace-tab-header" in selector:
                continue  # knobs on plain body, html background and the harmless tab-feet rule
            parts, depth, current = [], 0, ""
            for ch in selector:  # split on commas outside parentheses, so :is(a, b) stays one selector
                depth += ch == "("
                depth -= ch == ")"
                if ch == "," and depth == 0:
                    parts.append(current)
                    current = ""
                else:
                    current += ch
            parts.append(current)
            for part in parts:
                self.assertIn("is-popout-window", part, f"rule not scoped away from pop-outs: {part.strip()}")

    def test_popups_are_nearly_solid(self):
        text = self.css("translucent")
        for var in ("--menu-background", "--suggestion-background", "--modal-background", "--tooltip-background", "--prompt-background"):
            self.assertIn(var, text)
        self.assertIn("--tl-popup: rgba(var(--tl-secondary), 0.97)", text)

    def test_default_radius_matches_cli(self):
        from obsidian_translucent import cli

        self.assertIn(f"--tl-radius: {cli.DEFAULT_RADIUS}px", self.css("translucent"))


if __name__ == "__main__":
    unittest.main()
