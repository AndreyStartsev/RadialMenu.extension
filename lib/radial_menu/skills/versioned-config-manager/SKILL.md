---
name: versioned-config-manager
description: >
  Standalone JSON configuration manager with auto-format detection and multi-version
  migration. Handles loading, saving, and migrating config files through a 3-stage
  pipeline (flat list → context dict → pool format). Zero external dependencies
  (json, os, re only). Use when building any pyRevit extension that needs persistent
  user settings with backward compatibility.
---

# Versioned Config Manager

A self-contained JSON configuration manager that transparently handles schema evolution
across multiple config format generations, ensuring users never lose their settings.

## Source Reference

- **Implementation**: `lib/radial_menu/config_manager.py`
- **Tests**: `tests/test_config_manager.py` (22 unit tests)

---

## Core Concepts

### 3-Stage Migration Pipeline

The config manager detects the format version of any loaded file and migrates it
through up to three stages:

1. **Flat List** (v1) — original format storing commands as a plain JSON array.
2. **Context Dict** (v2) — intermediate format grouping commands by context name.
3. **Pool Format** (v3, current) — full-featured format with pool metadata, levels,
   and per-item settings.

Migration is **automatic and transparent** — calling `load()` on a v1 file returns
a fully migrated v3 structure.

---

## API Reference

### `ConfigManager` Class

#### Initialization

```python
from radial_menu.config_manager import ConfigManager

# Use built-in defaults
mgr = ConfigManager(config_path="path/to/config.json")

# Override specific defaults
custom_defaults = {
    "radius": 200,
    "animation_speed": 0.3,
    "theme": "ocean"
}
mgr = ConfigManager(
    config_path="path/to/config.json",
    defaults=custom_defaults
)
```

**Parameters:**

| Parameter     | Type   | Required | Description                                  |
|---------------|--------|----------|----------------------------------------------|
| `config_path` | `str`  | Yes      | Absolute path to the JSON config file        |
| `defaults`    | `dict` | No       | Custom default settings (merged with built-in defaults) |

#### `load()` — Load with Auto-Migration

```python
settings = mgr.load()
```

- Reads the JSON file from `config_path`.
- Auto-detects the format version by inspecting the structure.
- Runs the migration pipeline if the format is outdated.
- Returns a fully migrated `dict` in the current (v3) pool format.
- If the file does not exist, returns a copy of `DEFAULT_SETTINGS`.
- If JSON parsing fails, logs a warning and returns defaults.

#### `save(settings)` — Persist Settings

```python
mgr.save(settings)
```

- Writes the settings dict to `config_path` as pretty-printed JSON.
- Uses **UTF-8 encoding** (`ensure_ascii=False`) to preserve Unicode characters.
- **Creates parent directories** automatically if they don't exist.
- Writes with `indent=2` for human-readable output.

#### `migrate_legacy(data)` — Slot-to-Level Conversion

```python
migrated = mgr.migrate_legacy(old_data)
```

- Converts legacy `slot`-based indexing to the current `level`-based hierarchy.
- Handles both flat list and context dict input formats.
- Preserves all command metadata during conversion.
- Returns a new dict — does **not** mutate the input.

#### `merge_defaults(settings)` — Forward Compatibility

```python
merged = mgr.merge_defaults(settings)
```

- Merges `DEFAULT_SETTINGS` into the loaded settings.
- Adds any **new keys** introduced in newer versions without overwriting
  existing user values.
- Ensures forward compatibility when the extension is updated.

### Utility Functions

#### `clean_id_part(text)` — Sanitize Identifiers

```python
from radial_menu.config_manager import clean_id_part

clean = clean_id_part("My Command (v2)")  # "my_command_v2"
```

- Strips non-alphanumeric characters (keeps underscores).
- Converts to lowercase.
- Collapses multiple underscores.
- Used internally for generating stable config keys from display names.

---

## Constants

### `DEFAULT_SETTINGS`

```python
DEFAULT_SETTINGS = {
    "radius": 150,
    "animation_speed": 0.2,
    "theme": "default",
    "show_labels": True,
    "icon_size": 32,
    # ... additional defaults
}
```

The base settings applied when no config file exists or when merging forward
compatibility keys.

### `DEFAULT_POOL`

```python
DEFAULT_POOL = {
    "items": [],
    "levels": {},
    "metadata": {
        "version": 3,
        "created": "",
        "modified": ""
    }
}
```

The empty pool structure used as a template for new configurations.

---

## Integration Example

```python
from radial_menu.config_manager import ConfigManager

# Initialize
config_path = os.path.join(extension_dir, "config", "user_settings.json")
mgr = ConfigManager(config_path=config_path)

# Load (auto-migrates old formats)
settings = mgr.load()

# Modify
settings["theme"] = "midnight"
settings["radius"] = 180

# Save
mgr.save(settings)
```

---

## Testing

The module has **22 unit tests** covering:

- Default initialization and custom defaults
- Loading valid, missing, and corrupted JSON files
- Full migration pipeline (v1 → v2 → v3)
- Slot-to-level conversion edge cases
- Forward compatibility merge behavior
- `clean_id_part()` with special characters, Unicode, empty strings
- Parent directory auto-creation on save
- UTF-8 encoding preservation

Run tests:

```bash
python -m pytest tests/test_config_manager.py -v
```

---

## Design Decisions

1. **Zero external dependencies** — only `json`, `os`, and `re` from the standard
   library, ensuring compatibility with IronPython and CPython.
2. **Non-destructive migration** — original files are never modified in-place during
   migration; the migrated structure is returned as a new object.
3. **Fail-safe loading** — corrupted or unparseable files fall back to defaults
   with a logged warning rather than raising exceptions.
4. **UTF-8 by default** — `ensure_ascii=False` preserves localized command names
   and descriptions in the config file.
