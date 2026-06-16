---
name: radial-geometry-engine
description: >
  Pure-math module for generating radial/circular UI geometry. Computes
  WPF Path.Data strings for sectors with parallel-offset gaps, text
  positioning, ring stacking, and max-angle clamping. Zero external
  dependencies (math only). Use when building pie menus, donut charts,
  gauge widgets, or any circular UI in WPF.
---

# Radial Geometry Engine Skill

## Overview

A zero-dependency geometry module that computes everything needed to
render radial / circular UI elements in WPF.  All functions accept and
return plain Python types (floats, strings, tuples, lists) — no .NET,
WPF, or Revit imports required.

**Source file:** `lib/radial_menu/radial_geometry.py`

---

## Public API — 4 Functions

### 1. `get_sector_path(cx, cy, r_in, r_out, angle_center, num_sectors, gap_width)`

Generate a WPF-compatible `Path.Data` mini-language string for one
radial sector (the region between two concentric arcs).

**Signature:**

```python
def get_sector_path(cx, cy, r_in, r_out, angle_center, num_sectors,
                    gap_width) -> str
```

**Parameters:**

| Param          | Type    | Description                                               |
|----------------|---------|-----------------------------------------------------------|
| `cx`           | `float` | X-coordinate of the radial centre.                        |
| `cy`           | `float` | Y-coordinate of the radial centre.                        |
| `r_in`         | `float` | Inner radius of the ring.                                 |
| `r_out`        | `float` | Outer radius of the ring.                                 |
| `angle_center` | `float` | Centre angle of the sector in degrees (0° = 3-o'clock).   |
| `num_sectors`  | `int`   | Total sectors dividing the full 360° ring.                 |
| `gap_width`    | `float` | Visual gap (px) between neighbouring sectors.              |

**Returns:** A `str` like `"M … L … A … L … A … Z"` suitable for
`System.Windows.Shapes.Path.Data`.

**How `gap_width` works:**

The gap is implemented as a *parallel offset* from each sector boundary.
Each edge is shifted inward by `gap_width / 2` along the perpendicular
normal, creating uniform visual spacing without changing sector angles.
The four corner points are recomputed using:

```
offset = gap_width / 2
t = sqrt(r² - offset²)
corner = center + offset * normal + t * direction
```

**Example:**

```python
from radial_menu.radial_geometry import get_sector_path

path_data = get_sector_path(
    cx=200, cy=200,
    r_in=60, r_out=120,
    angle_center=90.0,
    num_sectors=8,
    gap_width=4.0,
)
# Use in WPF XAML:
# <Path Data="{Binding PathData}" Fill="..." />
```

---

### 2. `get_text_position(cx, cy, r_in, r_out, angle_center, width=80, height=70)`

Compute the top-left position for a text or icon overlay centred on a
sector arc.

**Signature:**

```python
def get_text_position(cx, cy, r_in, r_out, angle_center,
                      width=80, height=70) -> tuple[float, float]
```

**Parameters:**

| Param          | Type    | Default | Description                              |
|----------------|---------|---------|------------------------------------------|
| `cx`           | `float` | —       | X-coordinate of the radial centre.       |
| `cy`           | `float` | —       | Y-coordinate of the radial centre.       |
| `r_in`         | `float` | —       | Inner radius.                            |
| `r_out`        | `float` | —       | Outer radius.                            |
| `angle_center` | `float` | —       | Centre angle in degrees.                 |
| `width`        | `float` | `80`    | Width of the overlay bounding box.       |
| `height`       | `float` | `70`    | Height of the overlay bounding box.      |

**Returns:** `(left, top)` — coordinates for a `Canvas.SetLeft` /
`Canvas.SetTop` call in WPF.

**Positioning logic:**

- The midpoint is placed at `r_mid = (r_in + r_out) / 2` along the
  sector angle.
- Horizontal position is centred: `left = x_c - width / 2`.
- Vertical position is shifted 12 px upward to visually align icons:
  `top = y_c - 12`.

**Example:**

```python
from radial_menu.radial_geometry import get_text_position

left, top = get_text_position(200, 200, 60, 120, angle_center=45.0)
# Canvas.SetLeft(text_block, left)
# Canvas.SetTop(text_block, top)
```

---

### 3. `calculate_ring_radii(core_radius, petal_width, ring_gap, num_levels=3)`

Compute inner/outer radius pairs for concentric rings stacked outward
from a central core circle.

**Signature:**

```python
def calculate_ring_radii(core_radius, petal_width, ring_gap,
                         num_levels=3) -> list[tuple[float, float]]
```

**Parameters:**

| Param          | Type    | Default | Description                              |
|----------------|---------|---------|------------------------------------------|
| `core_radius`  | `float` | —       | Radius of the central "core" circle.     |
| `petal_width`  | `float` | —       | Radial thickness of each ring.           |
| `ring_gap`     | `float` | —       | Gap between adjacent rings.              |
| `num_levels`   | `int`   | `3`     | Number of concentric rings.              |

**Returns:** `[(r_in_1, r_out_1), (r_in_2, r_out_2), …]`

**Stacking formula:**

```
Ring 1: r_in = core_radius + ring_gap,  r_out = r_in + petal_width
Ring 2: r_in = Ring1.r_out + ring_gap,  r_out = r_in + petal_width
...
```

**Example:**

```python
from radial_menu.radial_geometry import calculate_ring_radii

radii = calculate_ring_radii(
    core_radius=30,
    petal_width=60,
    ring_gap=5,
    num_levels=3,
)
# [(35, 95), (100, 160), (165, 225)]
```

---

### 4. `calculate_effective_sectors(actual_count, max_angle)`

Compute the virtual sector count with max-angle clamping.  Prevents
sectors from becoming excessively wide when a ring has few items.

**Signature:**

```python
def calculate_effective_sectors(actual_count, max_angle) -> int
```

**Parameters:**

| Param          | Type    | Description                                       |
|----------------|---------|---------------------------------------------------|
| `actual_count` | `int`   | Number of real items in the ring.                  |
| `max_angle`    | `float` | Maximum allowed angular span per sector (degrees). |

**Returns:** `int` — the effective (virtual) sector count, always
`>= actual_count`.  Returns `0` when `actual_count` is `0`.

**Logic:**

```
natural_span = 360 / actual_count
if natural_span > max_angle:
    return max(actual_count, int(360 / max_angle))
else:
    return actual_count
```

**Example:**

```python
from radial_menu.radial_geometry import calculate_effective_sectors

# 2 items → natural span = 180° → exceeds 90° max
effective = calculate_effective_sectors(actual_count=2, max_angle=90)
# Returns 4 (virtual sectors, but only 2 have content)
```

---

## Integration with WPF Path Elements

```python
# In a WPF ViewModel or code-behind:
from radial_menu.radial_geometry import get_sector_path, get_text_position

for i, item in enumerate(menu_items):
    angle = i * (360.0 / len(menu_items))
    
    # Generate path geometry
    path_data = get_sector_path(cx, cy, r_in, r_out, angle,
                                len(menu_items), gap_width=4)
    path_element.Data = Geometry.Parse(path_data)
    
    # Position label
    left, top = get_text_position(cx, cy, r_in, r_out, angle)
    Canvas.SetLeft(label, left)
    Canvas.SetTop(label, top)
```

---

## Testing

The module has **28 unit tests** in `tests/test_radial_geometry.py` that
cover:

- Sector path generation for various sector counts and gap widths
- Text position centring accuracy
- Ring radii stacking correctness
- Max-angle clamping edge cases (0 items, 1 item, many items)
- Boundary conditions (`r_in > offset`, `r_in <= offset`)

Run tests with:

```bash
python -m pytest tests/test_radial_geometry.py -v
```

---

## Reference

- **Source:** [`radial_geometry.py`](../../radial_geometry.py)
- **Tests:** [`tests/test_radial_geometry.py`](../../../tests/test_radial_geometry.py)
- **Dependencies:** `math` (stdlib only)
- **Lines of code:** ~195
