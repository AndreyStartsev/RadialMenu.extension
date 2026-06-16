---
name: revit-context-detector
description: >
  Detects the current Revit selection context (pipes, walls, ducts,
  dimensions) by inspecting BuiltInCategory IDs and filters menu items
  by context rules. Use when building context-sensitive toolbars, smart
  command palettes, or element-type-aware UI panels in Revit extensions.
---

# Revit Context Detector Skill

## Overview

This module inspects the currently selected Revit element(s) to
determine a *context string* (`"pipes"`, `"walls"`, `"ducts"`,
`"dimensions"`, or `"default"`), then filters menu items against
per-item `context_rules` dictionaries.

All Revit API imports are wrapped in `try/except` so the module can be
safely imported and tested outside of a Revit host.

**Source file:** `lib/radial_menu/context_detector.py`

---

## CATEGORY_MAP

The core mapping from Revit `BuiltInCategory` integer IDs to
human-readable context strings:

```python
CATEGORY_MAP = {
    -2008065: "pipes",       # OST_PipeCurves
    -2008130: "ducts",       # OST_DuctCurves
    -2000011: "walls",       # OST_Walls
    -2000021: "dimensions",  # OST_Dimensions
}
```

### Extending CATEGORY_MAP

To add support for new element categories:

1. Find the `BuiltInCategory` enum value or its integer ID.
2. Add an entry to the dict:

```python
from radial_menu.context_detector import CATEGORY_MAP

# Add support for floors
CATEGORY_MAP[-2000032] = "floors"  # OST_Floors

# Add support for structural columns
CATEGORY_MAP[-2001330] = "columns"  # OST_StructuralColumns
```

3. Create corresponding `context_rules` entries in your menu config to
   match the new context strings.

---

## `get_current_context(uiapp)`

Determine the current Revit selection context.

**Signature:**

```python
def get_current_context(uiapp) -> str
```

**Parameters:**

| Param   | Type                           | Description                        |
|---------|--------------------------------|------------------------------------|
| `uiapp` | `Autodesk.Revit.UI.UIApplication` or `None` | Active Revit UI application. |

**Returns:** One of the context strings in `CATEGORY_MAP` (e.g.
`"pipes"`) or `"default"`.

**Resolution strategy:**

1. Get the first selected element from `uiapp.ActiveUIDocument`.
2. Read `element.Category.Id.IntegerValue`.
3. Look up in `CATEGORY_MAP` (fast integer match).
4. If not found, fall back to enum comparison via
   `category.BuiltInCategory` against a secondary map.
5. If nothing matches, return `"default"`.

**Example:**

```python
from radial_menu.context_detector import get_current_context

context = get_current_context(__revit__)  # pyRevit global
print(context)  # "pipes", "walls", etc.
```

---

## `filter_by_context(items, context_string, view_type=None)`

Filter a list of menu items by their `context_rules`.

**Signature:**

```python
def filter_by_context(items, context_string, view_type=None) -> list[dict]
```

**Parameters:**

| Param            | Type            | Description                                    |
|------------------|-----------------|------------------------------------------------|
| `items`          | `list[dict]`    | Menu items, each optionally having `"context_rules"`. |
| `context_string` | `str`           | Active context from `get_current_context()`.   |
| `view_type`      | `str` or `None` | Optional view-type hint (overrides `context_string` for view matching). |

**Returns:** Subset of `items` that pass the context filter.

**Filtering rules:**

- Items **without** `context_rules` (or with an empty dict) are
  **always included**.
- If `allowed_views` is specified, the item is included only when the
  check string matches one of the recognised tokens.

**Example:**

```python
from radial_menu.context_detector import filter_by_context

items = [
    {"name": "Pipe Tools", "context_rules": {"allowed_views": ["3D"]}},
    {"name": "General", "context_rules": {}},
    {"name": "Sheet Only", "context_rules": {"allowed_views": ["Sheet"]}},
]

visible = filter_by_context(items, context_string="3d_view")
# Returns: [Pipe Tools, General]  (Sheet Only is excluded)
```

---

## ContextRule Schema

Each menu item may carry a `context_rules` dictionary with these
optional keys:

| Key                | Type          | Description                                      |
|--------------------|---------------|--------------------------------------------------|
| `allowed_views`    | `list[str]`   | View-type filter tokens: `"3D"`, `"Plan"`, `"Sheet"`. Empty = all views. |
| `allowed_classes`  | `list[str]`   | Element-class filter (reserved for future use).   |

**Example `context_rules` dictionary:**

```python
{
    "allowed_views": ["3D", "Plan"],
    "allowed_classes": ["Wall", "Pipe"]   # reserved, not yet enforced
}
```

**View matching logic:**

| Token      | Matches when `check_str` contains |
|------------|-----------------------------------|
| `"3D"`     | `"3d"`                            |
| `"Plan"`   | `"plan"` or `"section"`           |
| `"Sheet"`  | `"sheet"`                         |

---

## Graceful Degradation Outside Revit

The module sets `_REVIT_AVAILABLE = False` if the Revit API import
fails.  In this state:

- `get_current_context(None)` always returns `"default"`.
- `filter_by_context()` works normally with any test data.
- The `BuiltInCategory` enum fallback path is skipped.

This design enables full unit testing without a Revit host.

---

## Testing

The module has **15 unit tests** in `tests/test_context_detector.py`
covering:

- `CATEGORY_MAP` completeness and expected values
- `get_current_context()` with mock `uiapp` / `None`
- `filter_by_context()` with various `allowed_views` combinations
- Edge cases: empty items list, missing `context_rules` key, unknown
  view types
- Graceful degradation when `_REVIT_AVAILABLE` is `False`

Run tests with:

```bash
python -m pytest tests/test_context_detector.py -v
```

---

## Reference

- **Source:** [`context_detector.py`](../../context_detector.py)
- **Tests:** [`tests/test_context_detector.py`](../../../tests/test_context_detector.py)
- **Dependencies:** `logging` (stdlib only; Revit API optional)
- **Lines of code:** ~205
