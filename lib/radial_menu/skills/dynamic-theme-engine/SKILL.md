---
name: dynamic-theme-engine
description: >
  Color theme management system with 5 built-in presets, luminance-aware contrast
  calculation (ITU-R BT.709), Revit dark/light mode detection, and automatic icon
  theming. Pure-math color functions work without .NET. Use when building any WPF
  extension that needs dark/light mode support, custom color themes, or WCAG-compliant
  text contrast.
---

# Dynamic Theme Engine

A complete color theme system for WPF extensions running inside Revit. Handles
theme selection, contrast-safe text colors, Revit UI mode detection, and
automatic icon variant switching — all with pure Python math (no .NET color
libraries required).

## Source Reference

- **Implementation**: `lib/radial_menu/theme_engine.py`
- **Tests**: `tests/test_theme_engine.py` (25 unit tests)

---

## Core Concepts

### Luminance-Aware Contrast

All contrast decisions use **relative luminance** computed via the ITU-R BT.709
standard (the same formula used in WCAG 2.x guidelines). This ensures text
remains readable on any background color.

### Revit Theme Detection

The engine can detect whether Revit is running in dark or light mode via the
`UIThemeManager` API and automatically select an appropriate theme preset.

### Automatic Icon Theming

Icons can have dark-mode variants (e.g., `icon.dark.png`). The engine resolves
the correct variant based on the active theme's background luminance.

---

## Built-in Themes

### `THEMES` Dictionary

```python
THEMES = {
    "default":  {"bg": "#FFFFFF", "fg": "#1A1A2E", "accent": "#4A90D9", ...},
    "dark":     {"bg": "#1A1A2E", "fg": "#E8E8E8", "accent": "#6C63FF", ...},
    "midnight": {"bg": "#0D1117", "fg": "#C9D1D9", "accent": "#58A6FF", ...},
    "ocean":    {"bg": "#0A1628", "fg": "#B8C9E0", "accent": "#00D4AA", ...},
    "sunset":   {"bg": "#2D1B2E", "fg": "#F0D9E0", "accent": "#FF6B6B", ...},
}
```

Each theme provides at minimum:

| Key       | Description                            |
|-----------|----------------------------------------|
| `bg`      | Primary background color (hex)         |
| `fg`      | Primary foreground/text color (hex)    |
| `accent`  | Accent color for interactive elements  |
| `border`  | Border/separator color                 |
| `hover`   | Hover state background                 |
| `active`  | Active/selected state background       |

---

## API Reference

### `ThemeManager` Class

#### `get_theme(name)` — Retrieve a Theme

```python
from radial_menu.theme_engine import ThemeManager

tm = ThemeManager()
theme = tm.get_theme("midnight")
print(theme["bg"])  # "#0D1117"
```

- Returns a copy of the theme dict for the given name.
- Raises `KeyError` if the theme name is not registered.

#### `apply_theme(window, theme_name)` — Apply to WPF Window

```python
tm.apply_theme(my_window, "dark")
```

- Sets `Background`, `Foreground`, and resource dictionary entries on the
  WPF window.
- Updates all child elements that reference theme resource keys.

#### `list_themes()` — Available Theme Names

```python
names = tm.list_themes()  # ["default", "dark", "midnight", "ocean", "sunset"]
```

### Color Utility Functions

#### `get_luminance(hex_color)` — Relative Luminance

```python
from radial_menu.theme_engine import get_luminance

lum = get_luminance("#FFFFFF")  # 1.0
lum = get_luminance("#000000")  # 0.0
lum = get_luminance("#4A90D9")  # ~0.27
```

**Algorithm (ITU-R BT.709):**

1. Parse hex to R, G, B in [0, 255].
2. Normalize to [0.0, 1.0].
3. Apply **sRGB linearization**:
   - If `c <= 0.03928`: `c_linear = c / 12.92`
   - Else: `c_linear = ((c + 0.055) / 1.055) ^ 2.4`
4. Compute luminance: `L = 0.2126 * R + 0.7152 * G + 0.0722 * B`

#### `get_contrast_foreground(bg_hex, light="#FFFFFF", dark="#000000")` — WCAG Contrast Switch

```python
from radial_menu.theme_engine import get_contrast_foreground

fg = get_contrast_foreground("#1A1A2E")  # "#FFFFFF" (light text on dark bg)
fg = get_contrast_foreground("#F5F5F5")  # "#000000" (dark text on light bg)
```

- Computes the luminance of the background color.
- Returns `light` if luminance < 0.179, else returns `dark`.
- The threshold (0.179) is the geometric midpoint that maximizes WCAG contrast
  ratio for both black and white text.

#### `parse_hex_color(hex_str, fallback="#FFFFFF")` — Safe Hex Parsing

```python
from radial_menu.theme_engine import parse_hex_color

r, g, b = parse_hex_color("#4A90D9")      # (74, 144, 217)
r, g, b = parse_hex_color("invalid")       # (255, 255, 255) — fallback
r, g, b = parse_hex_color("#F00")           # (255, 0, 0) — 3-digit shorthand
```

- Accepts `#RGB`, `#RRGGBB`, and `#AARRGGBB` formats.
- Returns `(R, G, B)` tuple as integers in [0, 255].
- Returns the parsed fallback color if the input is invalid.

### Revit Integration

#### `get_revit_theme_colors()` — Detect Revit Dark/Light Mode

```python
from radial_menu.theme_engine import get_revit_theme_colors

colors = get_revit_theme_colors()
# Returns: {"bg": "#1A1A2E", "fg": "#E8E8E8"} for dark mode
# Returns: {"bg": "#FFFFFF", "fg": "#1A1A2E"} for light mode
# Returns: None if UIThemeManager is unavailable
```

- Accesses `Autodesk.Revit.UI.UIThemeManager.CurrentTheme`.
- Extracts the canvas background and text colors.
- Returns `None` if running outside Revit or if the API is unavailable
  (graceful fallback).

#### `resolve_themed_icon(icon_path, theme_name)` — Icon Variant Switching

```python
from radial_menu.theme_engine import resolve_themed_icon

# Given: icons/wall.png and icons/wall.dark.png exist
path = resolve_themed_icon("icons/wall.png", "dark")
# Returns: "icons/wall.dark.png"

path = resolve_themed_icon("icons/wall.png", "default")
# Returns: "icons/wall.png"
```

- For dark themes (luminance < 0.179), looks for `filename.dark.ext`.
- Returns the dark variant path if the file exists, otherwise the original.
- Convention: place dark icon variants alongside originals with `.dark` suffix.

---

## Adding Custom Themes

```python
from radial_menu.theme_engine import ThemeManager, THEMES

# Option 1: Add directly to THEMES dict
THEMES["corporate"] = {
    "bg": "#1B2838",
    "fg": "#C7D5E0",
    "accent": "#66C0F4",
    "border": "#2A475E",
    "hover": "#2A475E",
    "active": "#3D6B8E",
}

# Option 2: Register at runtime
tm = ThemeManager()
tm.register_theme("corporate", {
    "bg": "#1B2838",
    "fg": "#C7D5E0",
    "accent": "#66C0F4",
    "border": "#2A475E",
    "hover": "#2A475E",
    "active": "#3D6B8E",
})
```

**Requirements for custom themes:**

- Must include at least `bg`, `fg`, and `accent` keys.
- All colors must be valid hex strings (`#RGB` or `#RRGGBB`).
- The engine will auto-compute contrast foreground if not provided.

---

## Testing

The module has **25 unit tests** covering:

- All 5 built-in theme retrieval and structure validation
- Luminance calculation against known reference values
- sRGB linearization boundary conditions (≤ 0.03928 vs > 0.03928)
- Contrast foreground switching for light, dark, and edge-case backgrounds
- Hex parsing: valid `#RGB`, `#RRGGBB`, `#AARRGGBB`, invalid strings, empty input
- Revit theme detection mock (with and without `UIThemeManager`)
- Icon variant resolution (dark variant exists / doesn't exist)
- Custom theme registration and validation

Run tests:

```bash
python -m pytest tests/test_theme_engine.py -v
```

---

## Design Decisions

1. **Pure Python math** — luminance and contrast functions use no .NET libraries,
   so they work identically in CPython (for testing) and IronPython (in Revit).
2. **ITU-R BT.709** — chosen over simpler averaging because it matches WCAG 2.x
   guidelines and produces perceptually correct results.
3. **0.179 threshold** — the geometric mean of black/white luminance that maximizes
   minimum contrast ratio for both text colors.
4. **Icon convention** — `.dark.png` suffix was chosen over separate directories to
   keep icon files co-located and discoverable.
