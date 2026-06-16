# -*- coding: utf-8 -*-
"""Theme engine for Radial Menu.

Provides color management, theme presets, luminance calculations,
Revit theme detection, and icon theming utilities.
"""

import os

# ---------------------------------------------------------------------------
# Theme presets
# ---------------------------------------------------------------------------

THEMES = {
    "pyRevit Dark": {
        "color_normal": "#F21E1E24",
        "color_hover_start": "#FF0083B0",
        "color_hover_end": "#FF004B66",
        "color_border": "#25FFFFFF",
    },
    "Neon Fusion": {
        "color_normal": "#F21F1F24",
        "color_hover_start": "#FFFF4E50",
        "color_hover_end": "#FFF9D423",
        "color_border": "#35FFFFFF",
    },
    "Classic Blue": {
        "color_normal": "#F21C263B",
        "color_hover_start": "#FF0088CC",
        "color_hover_end": "#FF0044AA",
        "color_border": "#30FFFFFF",
    },
    "Forest Green": {
        "color_normal": "#F2192B1D",
        "color_hover_start": "#FF0F7050",
        "color_hover_end": "#FF1B4D22",
        "color_border": "#25FFFFFF",
    },
    "Cyberpunk": {
        "color_normal": "#F225122B",
        "color_hover_start": "#FFC51083",
        "color_hover_end": "#FF5F1BBF",
        "color_border": "#35FFFFFF",
    },
}

# Default color-related settings
DEFAULT_SETTINGS = {
    "theme": "pyRevit Dark",
    "color_normal": "#F21E1E24",
    "color_hover_start": "#FF0083B0",
    "color_hover_end": "#FF004B66",
    "color_border": "#25FFFFFF",
}

# ---------------------------------------------------------------------------
# Pure-math color utilities (no .NET dependencies)
# ---------------------------------------------------------------------------


def get_luminance(hex_str):
    """Calculate relative luminance of a hex color string.

    Uses sRGB linearization and ITU-R BT.709 coefficients.
    Accepts ``#AARRGGBB`` (ARGB, 9 chars) or ``#RRGGBB`` (RGB, 7 chars).

    Args:
        hex_str: Hex color string, e.g. ``"#FF0083B0"`` or ``"#0083B0"``.

    Returns:
        float: Relative luminance in the range [0.0, 1.0].
            Returns 0.0 on parse failure.
    """
    try:
        cleaned = hex_str.strip().replace("#", "")
        if len(cleaned) == 8:
            # ARGB format – skip alpha
            r = int(cleaned[2:4], 16)
            g = int(cleaned[4:6], 16)
            b = int(cleaned[6:8], 16)
        elif len(cleaned) == 6:
            r = int(cleaned[0:2], 16)
            g = int(cleaned[2:4], 16)
            b = int(cleaned[4:6], 16)
        else:
            return 0.0

        r_lin = r / 255.0
        g_lin = g / 255.0
        b_lin = b / 255.0

        # sRGB linearization
        r_lin = (
            r_lin / 12.92
            if r_lin <= 0.03928
            else ((r_lin + 0.055) / 1.055) ** 2.4
        )
        g_lin = (
            g_lin / 12.92
            if g_lin <= 0.03928
            else ((g_lin + 0.055) / 1.055) ** 2.4
        )
        b_lin = (
            b_lin / 12.92
            if b_lin <= 0.03928
            else ((b_lin + 0.055) / 1.055) ** 2.4
        )

        return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin
    except Exception:
        return 0.0


def get_contrast_foreground(hex_str):
    """Return a high-contrast foreground color for the given background.

    Args:
        hex_str: Background hex color string.

    Returns:
        str: ``"#1E1E24"`` (near-black) for light backgrounds,
            ``"#FFFFFF"`` (white) for dark backgrounds.
    """
    lum = get_luminance(hex_str)
    if lum > 0.45:
        return "#1E1E24"
    else:
        return "#FFFFFF"


# ---------------------------------------------------------------------------
# Color parsing (uses WPF ColorConverter when available)
# ---------------------------------------------------------------------------


def parse_hex_color(hex_str, fallback):
    """Validate an ARGB/RGB hex color string.

    Attempts to parse the string via WPF ``ColorConverter``.
    Falls back gracefully if WPF is unavailable.

    Args:
        hex_str: The color string to validate, e.g. ``"#FF0083B0"``.
        fallback: Value to return if *hex_str* is invalid.

    Returns:
        str: The validated (possibly normalized) hex string, or *fallback*.
    """
    try:
        hex_str = hex_str.strip()
        if not hex_str.startswith("#"):
            hex_str = "#" + hex_str
        if len(hex_str) in [7, 9]:
            try:
                from System.Windows.Media import ColorConverter

                ColorConverter.ConvertFromString(hex_str)
            except ImportError:
                # WPF not available – accept if format looks correct
                pass
            return hex_str
    except Exception:
        pass
    return fallback


# ---------------------------------------------------------------------------
# Revit theme detection
# ---------------------------------------------------------------------------


def get_revit_theme_colors():
    """Detect current Revit UI theme and return matching color palette.

    Returns a dict with keys ``color_normal``, ``color_hover_start``,
    ``color_hover_end``, ``color_border`` tuned for Dark or Light mode.

    Returns:
        dict: Color palette for the detected Revit theme.
    """
    try:
        from Autodesk.Revit.UI import UIThemeManager, UITheme

        is_dark = UIThemeManager.CurrentTheme == UITheme.Dark
    except Exception:
        is_dark = False

    if is_dark:
        return {
            "color_normal": "#F22B2B2B",
            "color_hover_start": "#FF2B5E8C",
            "color_hover_end": "#FF1D3A56",
            "color_border": "#40FFFFFF",
        }
    else:
        return {
            "color_normal": "#F2F0F0F0",
            "color_hover_start": "#FF4A90E2",
            "color_hover_end": "#FF1D3A56",
            "color_border": "#20000000",
        }


# ---------------------------------------------------------------------------
# Themed icon resolver
# ---------------------------------------------------------------------------


def resolve_themed_icon(icon_path):
    """Resolve an icon path to its dark/light variant based on Revit theme.

    In dark mode, looks for ``icon.dark.png`` alongside ``icon.png``.
    In light mode, strips ``.dark`` suffix if a light variant exists.

    Args:
        icon_path: Original icon file path (or ``None``).

    Returns:
        str: Resolved icon path, or the original path if no variant found.
    """
    if not icon_path:
        return icon_path

    try:
        from Autodesk.Revit.UI import UIThemeManager, UITheme

        is_revit_dark = UIThemeManager.CurrentTheme == UITheme.Dark
    except Exception:
        is_revit_dark = False

    base, ext = os.path.splitext(icon_path)
    if ext.lower() == ".png":
        if is_revit_dark:
            if not base.endswith(".dark"):
                dark_path = base + ".dark" + ext
                if os.path.exists(dark_path):
                    return dark_path
        else:
            if base.endswith(".dark"):
                light_path = base[:-5] + ext
                if os.path.exists(light_path):
                    return light_path
    return icon_path


# ---------------------------------------------------------------------------
# ThemeManager class
# ---------------------------------------------------------------------------


class ThemeManager(object):
    """Manages named color themes and applies them to settings dicts.

    Args:
        themes: Optional dict of ``{name: color_dict}`` overrides.
            Defaults to the built-in :data:`THEMES` dictionary.
    """

    def __init__(self, themes=None):
        """Initialize with an optional custom theme dictionary.

        Args:
            themes: Dict mapping theme names to color dicts.
                Falls back to the module-level ``THEMES`` if *None*.
        """
        self._themes = themes if themes is not None else dict(THEMES)

    def get_theme(self, name):
        """Return the color dict for a named theme.

        Args:
            name: Theme name (e.g. ``"pyRevit Dark"``).

        Returns:
            dict or None: Color dict if found, otherwise *None*.
        """
        theme = self._themes.get(name)
        return dict(theme) if theme is not None else None

    def apply_theme(self, name, settings):
        """Merge a theme's colors into a settings dictionary.

        Only color keys present in the theme are overwritten; other
        settings keys are preserved.

        Args:
            name: Theme name to apply.
            settings: Mutable dict to update in-place.

        Returns:
            dict: The updated *settings* dict (same reference).
        """
        theme = self._themes.get(name)
        if theme:
            settings.update(theme)
        return settings

    def list_themes(self):
        """Return a list of available theme names.

        Returns:
            list[str]: Sorted list of theme names.
        """
        return sorted(self._themes.keys())
