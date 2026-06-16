# -*- coding: utf-8 -*-
"""Tests for theme_engine module.

Only pure-math functions are tested (luminance, contrast).
WPF/Revit-dependent functions are tested structurally.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "lib")))

from radial_menu.theme_engine import (
    THEMES,
    DEFAULT_SETTINGS,
    get_luminance,
    get_contrast_foreground,
    ThemeManager,
)


class TestGetLuminance(unittest.TestCase):
    """Tests for get_luminance()."""

    def test_white(self):
        lum = get_luminance("#FFFFFF")
        self.assertAlmostEqual(lum, 1.0, places=2)

    def test_black(self):
        lum = get_luminance("#000000")
        self.assertAlmostEqual(lum, 0.0, places=2)

    def test_white_with_alpha(self):
        lum = get_luminance("#FFFFFFFF")
        self.assertAlmostEqual(lum, 1.0, places=2)

    def test_black_with_alpha(self):
        lum = get_luminance("#FF000000")
        self.assertAlmostEqual(lum, 0.0, places=2)

    def test_midgray_is_midrange(self):
        lum = get_luminance("#808080")
        self.assertGreater(lum, 0.1)
        self.assertLess(lum, 0.5)

    def test_red(self):
        lum = get_luminance("#FF0000")
        self.assertGreater(lum, 0.0)
        self.assertLess(lum, 0.3)

    def test_green_is_brightest_primary(self):
        lum_r = get_luminance("#FF0000")
        lum_g = get_luminance("#00FF00")
        lum_b = get_luminance("#0000FF")
        self.assertGreater(lum_g, lum_r)
        self.assertGreater(lum_g, lum_b)

    def test_invalid_hex_returns_zero(self):
        self.assertEqual(get_luminance(""), 0.0)
        self.assertEqual(get_luminance("xyz"), 0.0)
        self.assertEqual(get_luminance("#GG0000"), 0.0)

    def test_hash_optional(self):
        lum1 = get_luminance("#FF8800")
        lum2 = get_luminance("FF8800")
        self.assertAlmostEqual(lum1, lum2, places=5)

    def test_argb_skips_alpha(self):
        """Alpha channel should not affect luminance."""
        lum_full = get_luminance("#FFFF0000")
        lum_half = get_luminance("#80FF0000")
        self.assertAlmostEqual(lum_full, lum_half, places=5)


class TestGetContrastForeground(unittest.TestCase):
    """Tests for get_contrast_foreground()."""

    def test_dark_background_gets_white(self):
        fg = get_contrast_foreground("#1E1E24")
        self.assertEqual(fg, "#FFFFFF")

    def test_light_background_gets_dark(self):
        fg = get_contrast_foreground("#F0F0F0")
        self.assertEqual(fg, "#1E1E24")

    def test_white_background(self):
        fg = get_contrast_foreground("#FFFFFF")
        self.assertEqual(fg, "#1E1E24")

    def test_black_background(self):
        fg = get_contrast_foreground("#000000")
        self.assertEqual(fg, "#FFFFFF")

    def test_theme_normal_colors_all_get_white(self):
        """All default themes have dark backgrounds → white text."""
        for name, theme in THEMES.items():
            fg = get_contrast_foreground(theme["color_normal"])
            self.assertEqual(fg, "#FFFFFF",
                             msg="Theme '{}' should have white fg".format(name))


class TestThemeManager(unittest.TestCase):
    """Tests for ThemeManager class."""

    def test_default_themes_loaded(self):
        tm = ThemeManager()
        names = tm.list_themes()
        self.assertIn("pyRevit Dark", names)
        self.assertIn("Cyberpunk", names)
        self.assertEqual(len(names), 5)

    def test_get_existing_theme(self):
        tm = ThemeManager()
        theme = tm.get_theme("Neon Fusion")
        self.assertIsNotNone(theme)
        self.assertIn("color_normal", theme)
        self.assertIn("color_hover_start", theme)

    def test_get_missing_theme_returns_none(self):
        tm = ThemeManager()
        self.assertIsNone(tm.get_theme("Nonexistent"))

    def test_apply_theme_merges_colors(self):
        tm = ThemeManager()
        settings = {"theme": "Classic Blue", "hold_delay_ms": 400}
        tm.apply_theme("Classic Blue", settings)
        self.assertEqual(settings["color_normal"], "#F21C263B")
        self.assertEqual(settings["hold_delay_ms"], 400)  # Preserved

    def test_apply_missing_theme_no_change(self):
        tm = ThemeManager()
        settings = {"theme": "Missing", "color_normal": "#123456"}
        tm.apply_theme("Missing", settings)
        self.assertEqual(settings["color_normal"], "#123456")

    def test_custom_themes(self):
        custom = {
            "MyTheme": {
                "color_normal": "#FF112233",
                "color_hover_start": "#FF445566",
                "color_hover_end": "#FF778899",
                "color_border": "#FFAABBCC",
            }
        }
        tm = ThemeManager(themes=custom)
        self.assertEqual(len(tm.list_themes()), 1)
        theme = tm.get_theme("MyTheme")
        self.assertEqual(theme["color_normal"], "#FF112233")

    def test_get_theme_returns_copy(self):
        """Modifying returned theme should not affect internal state."""
        tm = ThemeManager()
        theme = tm.get_theme("pyRevit Dark")
        theme["color_normal"] = "#CHANGED"
        original = tm.get_theme("pyRevit Dark")
        self.assertNotEqual(original["color_normal"], "#CHANGED")


class TestThemeConstants(unittest.TestCase):
    """Tests for THEMES and DEFAULT_SETTINGS constants."""

    def test_all_themes_have_required_keys(self):
        required = {"color_normal", "color_hover_start",
                     "color_hover_end", "color_border"}
        for name, theme in THEMES.items():
            self.assertTrue(
                required.issubset(theme.keys()),
                msg="Theme '{}' missing keys: {}".format(
                    name, required - set(theme.keys())))

    def test_all_theme_colors_are_valid_hex(self):
        import re
        hex_pattern = re.compile(r'^#[0-9A-Fa-f]{6,8}$')
        for name, theme in THEMES.items():
            for key, value in theme.items():
                self.assertTrue(
                    hex_pattern.match(value),
                    msg="Theme '{}' key '{}' has invalid hex: '{}'".format(
                        name, key, value))

    def test_default_settings_has_theme(self):
        self.assertIn("theme", DEFAULT_SETTINGS)


if __name__ == "__main__":
    unittest.main()
