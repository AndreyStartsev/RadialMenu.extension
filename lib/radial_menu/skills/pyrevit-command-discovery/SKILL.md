---
name: pyrevit-command-discovery
description: >
  Discovers all installed pyRevit commands across extensions by scanning
  the session API and filesystem. Builds hierarchical
  Extension→Tab→Panel→Command trees for UI display. Use when building
  command palettes, keyboard shortcut editors, or extension managers
  for pyRevit.
---

# pyRevit Command Discovery Skill

## Overview

Discovers every pyRevit command available in the current session and on
disk, parses their bundle hierarchy, and builds a filtered tree structure
suitable for WPF `TreeView` data binding.

**Source file:** `lib/radial_menu/command_discovery.py`

---

## `CommandDiscovery` Class

### Initialization

```python
from radial_menu.command_discovery import CommandDiscovery

discovery = CommandDiscovery(
    clean_id_func=None,     # optional: (str) -> str id normaliser
    icon_resolver=None,     # optional: (str) -> str themed icon path
)
```

**Parameters:**

| Param            | Type       | Default          | Description                                    |
|------------------|------------|------------------|------------------------------------------------|
| `clean_id_func`  | `callable` | strips non-alnum | Normalises path segments into ID-safe strings. |
| `icon_resolver`  | `callable` | identity         | Resolves raw icon paths to themed variants.    |

---

### `find_all_commands()`

Discover all available pyRevit commands.  Results are cached globally
after the first call.

```python
commands = discovery.find_all_commands()
# Returns: list of command objects (real pyRevit or _MockCommand)
```

**Discovery pipeline:**

1. **Session API** — Calls `pyrevit.loader.sessionmgr.find_all_commands(cache=True)`
   to get commands loaded in the active Revit session.
2. **Filesystem scan** — Iterates all `.extension` directories found by
   `find_extension_dirs()` and discovers button bundles (`.pushbutton`,
   `.smartbutton`, etc.) that may not be loaded in the current session.
3. **Deduplication** — Commands are deduplicated by `unique_id`.
4. **Caching** — Results are stored in a module-level `_cached_commands`
   variable.

**Self-exclusion:** The `ToggleRadialMenu` button
(`radialmenu_radialmenu_radialmenu_toggleradialmenu`) is always excluded
to prevent the radial menu from listing itself.

---

### `build_command_tree(commands, query=None)`

Build a filtered hierarchical tree of commands grouped by
*Extension → Tab → Pulldown/Splitbutton → Command*.

```python
tree = discovery.build_command_tree(commands, query="pipe")
```

**Parameters:**

| Param      | Type              | Description                                      |
|------------|-------------------|--------------------------------------------------|
| `commands` | `iterable`        | Command objects from `find_all_commands()`.       |
| `query`    | `str` or `None`   | Case-insensitive search filter. Matches against title, extension, tab, pulldown name. |

**Returns:** `ObservableCollection[object]` (when CLR available) or
`list[TreeItem]`.

**When a `query` is provided:**

- Only matching commands are included.
- All tree nodes are auto-expanded (`IsExpanded=True`).

---

## `TreeItem` Class

Lightweight data node designed for WPF `TreeView` binding.  Uses
PascalCase properties for XAML `{Binding}` compatibility.

```python
from radial_menu.command_discovery import TreeItem

item = TreeItem(
    name="My Command",
    is_command=True,
    icon_path="C:/path/to/icon.png",
    unique_id="ext_tab_panel_mycommand",
    extension="MyExtension",
    is_expanded=False,
)
```

### WPF-Bindable Properties

| Property       | Type                          | Binding Example              |
|----------------|-------------------------------|------------------------------|
| `Name`         | `str`                         | `{Binding Name}`             |
| `IsCommand`    | `bool`                        | `{Binding IsCommand}`        |
| `IconPath`     | `str` or `None`               | `{Binding IconPath}`         |
| `UniqueId`     | `str` or `None`               | `{Binding UniqueId}`         |
| `Extension`    | `str` or `None`               | `{Binding Extension}`        |
| `IsExpanded`   | `bool` (read/write)           | `{Binding IsExpanded}`       |
| `Children`     | `ObservableCollection` / list | `{Binding Children}`         |

> **CLR note:** `Children` is an `ObservableCollection[object]` when
> `System.Collections.ObjectModel` is importable, otherwise a plain
> Python `list`.

---

## Helper Functions

### `find_extension_dirs()`

Scan the filesystem for all pyRevit `.extension` directories.

**Discovery sources (in order):**

1. `%APPDATA%/pyRevit/pyRevit_config.ini` → `userextensions` JSON list.
2. `pyrevit.userconfig.get_ext_root_dirs()`.
3. `pyrevit.HOME_DIR/extensions` default folder.
4. Parent directory of the current extension.

**Returns:** `list[str]` — deduplicated, normalised absolute paths.

```python
from radial_menu.command_discovery import find_extension_dirs

ext_dirs = find_extension_dirs()
# ['C:\\Users\\...\\extensions\\MyExt.extension', ...]
```

### `get_bundle_title(dir_path)`

Read the display title for a pyRevit bundle directory.

**Resolution order:**

1. Parse `bundle.yaml` for a `title:` field.
2. Fall back to the directory name with the bundle suffix stripped
   (e.g. `"MyTools.tab"` → `"MyTools"`).

```python
from radial_menu.command_discovery import get_bundle_title

title = get_bundle_title("C:/ext/MyTools.tab")
# "MyTools" (or YAML title if bundle.yaml exists)
```

### `parse_command_hierarchy(cmd)`

Extract the Extension → Tab → Pulldown hierarchy from a command object's
`script` path.

```python
from radial_menu.command_discovery import parse_command_hierarchy

ext_name, tab_name, pulldown_name = parse_command_hierarchy(cmd)
# ("MyExtension", "Tools", "Pipe Utils")
# pulldown_name is None if command is directly under a tab
```

---

## Async Loading Pattern

Command discovery can be slow (filesystem scan).  Load commands
asynchronously using the WPF Dispatcher:

```python
import System.Windows.Threading as WPFThreading
import System

def load_commands_async(tree_view, discovery):
    """Load commands on a background thread, update UI on main thread."""
    import threading

    def worker():
        commands = discovery.find_all_commands()
        tree = discovery.build_command_tree(commands)

        # Marshal back to UI thread
        tree_view.Dispatcher.BeginInvoke(
            WPFThreading.DispatcherPriority.Normal,
            System.Action(lambda: set_tree(tree_view, tree)),
        )

    def set_tree(tv, data):
        tv.ItemsSource = data

    t = threading.Thread(target=worker)
    t.daemon = True
    t.start()
```

---

## Icon Resolution

Commands discovered from the filesystem check for icon files in this
order:

1. `icon.png`
2. `icon32.png`
3. `icon16.png`

The optional `icon_resolver` callable passed to `CommandDiscovery` can
transform these paths to themed variants (e.g. dark-mode icons):

```python
def resolve_themed_icon(raw_path):
    if raw_path and os.path.exists(raw_path):
        dark_path = raw_path.replace("icon", "icon_dark")
        if is_dark_theme and os.path.exists(dark_path):
            return dark_path
    return raw_path

discovery = CommandDiscovery(icon_resolver=resolve_themed_icon)
```

---

## Bundle Suffixes

The module recognises these pyRevit bundle directory suffixes:

| Suffix             | Type                    |
|--------------------|-------------------------|
| `.extension`       | Extension root          |
| `.tab`             | Ribbon tab              |
| `.panel`           | Ribbon panel            |
| `.pulldown`        | Pull-down button group  |
| `.splitbutton`     | Split button group      |
| `.pushbutton`      | Standard push button    |
| `.smartbutton`     | Smart button            |
| `.linkbutton`      | Link button             |
| `.urlbutton`       | URL button              |
| `.contentbutton`   | Content button          |
| `.colorbutton`     | Color button            |
| `.togglebutton`    | Toggle button           |

---

## Reference

- **Source:** [`command_discovery.py`](../../command_discovery.py)
- **Dependencies:** `os`, `logging`, `re` (stdlib); `System.Collections.ObjectModel`
  (optional CLR); `pyrevit` (optional, graceful degradation)
- **Lines of code:** ~646
