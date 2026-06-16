---
name: wpf-data-binding-wrappers
description: >
  IronPython-compatible WPF data-binding wrapper classes using CLR property patterns.
  Provides BindableBase, CheckableItem, DictionaryWrapper, PoolItemView, and
  HierarchicalItem for ListView/TreeView binding. Falls back to plain list when
  ObservableCollection is unavailable. Use when building any WPF UI with data
  templates in pyRevit/IronPython.
---

# WPF Data Binding Wrappers

A collection of IronPython-compatible wrapper classes that bridge Python objects
to WPF's data binding system. These wrappers expose Python properties as CLR
properties that WPF `{Binding}` expressions can discover and subscribe to.

## Source Reference

- **Implementation**: `lib/radial_menu/data_binding.py`
- **Tests**: `tests/test_data_binding.py` (28 unit tests)

---

## Core Concepts

### The IronPython Binding Problem

WPF's `{Binding Path=PropertyName}` relies on CLR property descriptors or
`INotifyPropertyChanged`. Standard Python `@property` decorators are invisible
to WPF. These wrappers solve this by using IronPython's CLR property integration
patterns.

### ObservableCollection Fallback

`ObservableCollection[T]` is the standard WPF collection for dynamic lists.
However, some pyRevit/IronPython configurations fail to import it. All wrapper
classes fall back to plain Python `list` when `ObservableCollection` is
unavailable, with a logged warning that dynamic add/remove updates won't
propagate to the UI.

---

## Wrapper Classes

### `BindableBase` — Base Class for All Wrappers

```python
from radial_menu.data_binding import BindableBase

class MyViewModel(BindableBase):
    def __init__(self):
        super(MyViewModel, self).__init__()
        self._name = ""
        self._count = 0

    @property
    def Name(self):
        return self._name

    @Name.setter
    def Name(self, value):
        self._name = value
        self.on_property_changed("Name")

    @property
    def Count(self):
        return self._count

    @Count.setter
    def Count(self, value):
        self._count = value
        self.on_property_changed("Count")
```

**Key method:**

- `on_property_changed(property_name)` — fires `PropertyChanged` event for WPF
  to refresh the bound UI element.

**XAML binding:**

```xml
<TextBlock Text="{Binding Name}" />
<TextBlock Text="{Binding Count}" />
```

> **Convention:** Use PascalCase for property names (WPF convention) even though
> Python convention is snake_case. This ensures `{Binding Name}` works directly.

---

### `CheckableItem` — Checkbox List Items

```python
from radial_menu.data_binding import CheckableItem

items = [
    CheckableItem(label="Wall Tool", is_checked=True, data={"id": "wall"}),
    CheckableItem(label="Door Tool", is_checked=False, data={"id": "door"}),
    CheckableItem(label="Window Tool", is_checked=True, data={"id": "window"}),
]
```

**Properties:**

| Property    | Type   | Description                          | Bindable |
|-------------|--------|--------------------------------------|----------|
| `Label`     | `str`  | Display text for the item            | ✅       |
| `IsChecked` | `bool` | Checkbox state                       | ✅ (two-way) |
| `Data`      | `dict` | Arbitrary payload attached to item   | ✅       |

**XAML:**

```xml
<ListView ItemsSource="{Binding Items}">
    <ListView.ItemTemplate>
        <DataTemplate>
            <CheckBox Content="{Binding Label}"
                      IsChecked="{Binding IsChecked, Mode=TwoWay}" />
        </DataTemplate>
    </ListView.ItemTemplate>
</ListView>
```

**Getting checked items:**

```python
selected = [item for item in items if item.IsChecked]
```

---

### `DictionaryWrapper` — Dict-Backed View Model

```python
from radial_menu.data_binding import DictionaryWrapper

data = {"name": "Radial Menu", "version": "2.1", "enabled": True}
wrapper = DictionaryWrapper(data)

# Access via property syntax (for WPF binding)
print(wrapper.name)       # "Radial Menu"
print(wrapper.version)    # "2.1"

# Modify (triggers PropertyChanged)
wrapper.enabled = False
```

- Wraps any Python `dict` as a bindable view model.
- Dict keys become property names accessible via attribute syntax.
- Supports nested dicts (wrapped recursively).
- Modifications fire `PropertyChanged` for the corresponding key.

**XAML:**

```xml
<TextBlock Text="{Binding name}" />
<TextBlock Text="{Binding version}" />
<CheckBox IsChecked="{Binding enabled, Mode=TwoWay}" />
```

---

### `PoolItemView` — Pool Items with Computed Properties

```python
from radial_menu.data_binding import PoolItemView

item = PoolItemView(
    name="Quick Wall",
    command_class="Autodesk.Revit.DB.Wall",
    contexts=["Modeling", "Architecture"],
    level=2,
    icon_path="icons/wall.png"
)
```

**Properties:**

| Property          | Type   | Computed | Description                            |
|-------------------|--------|----------|----------------------------------------|
| `Name`            | `str`  | No       | Display name                           |
| `CommandClass`    | `str`  | No       | Revit command class name               |
| `Contexts`        | `list` | No       | Assigned context names                 |
| `Level`           | `int`  | No       | Hierarchy level in the radial menu     |
| `IconPath`        | `str`  | No       | Path to the icon file                  |
| `ContextSummary`  | `str`  | ✅ Yes   | Comma-joined contexts string           |
| `LevelLabel`      | `str`  | ✅ Yes   | Human-readable level (e.g., "Level 2") |

**Computed properties** are automatically derived from base properties and
update when the underlying values change.

**XAML:**

```xml
<ListView ItemsSource="{Binding PoolItems}">
    <ListView.ItemTemplate>
        <DataTemplate>
            <StackPanel Orientation="Horizontal">
                <Image Source="{Binding IconPath}" Width="16" Height="16" />
                <TextBlock Text="{Binding Name}" Margin="4,0,0,0" />
                <TextBlock Text="{Binding ContextSummary}"
                           Foreground="Gray" Margin="8,0,0,0" />
                <TextBlock Text="{Binding LevelLabel}"
                           Foreground="DimGray" Margin="8,0,0,0" />
            </StackPanel>
        </DataTemplate>
    </ListView.ItemTemplate>
</ListView>
```

---

### `HierarchicalItem` — TreeView with Observable Children

```python
from radial_menu.data_binding import HierarchicalItem

root = HierarchicalItem(name="Modeling", icon="folder.png")
root.add_child(HierarchicalItem(name="Wall", icon="wall.png", data=wall_cmd))
root.add_child(HierarchicalItem(name="Floor", icon="floor.png", data=floor_cmd))

sub = HierarchicalItem(name="Curtain Wall", icon="curtain.png")
sub.add_child(HierarchicalItem(name="Grid", icon="grid.png", data=grid_cmd))
root.add_child(sub)
```

**Properties:**

| Property   | Type                       | Description                        |
|------------|----------------------------|------------------------------------|
| `Name`     | `str`                      | Display name                       |
| `Icon`     | `str`                      | Icon path                          |
| `Data`     | `object`                   | Arbitrary payload                  |
| `Children` | `ObservableCollection` / `list` | Child items (auto-detected)   |
| `IsExpanded` | `bool`                   | TreeView expand state (bindable)   |

**Methods:**

- `add_child(item)` — appends to `Children` (works with both collection types).
- `remove_child(item)` — removes from `Children`.
- `clear_children()` — removes all children.

**XAML:**

```xml
<TreeView ItemsSource="{Binding RootItems}">
    <TreeView.ItemTemplate>
        <HierarchicalDataTemplate ItemsSource="{Binding Children}">
            <StackPanel Orientation="Horizontal">
                <Image Source="{Binding Icon}" Width="16" Height="16" />
                <TextBlock Text="{Binding Name}" Margin="4,0,0,0" />
            </StackPanel>
        </HierarchicalDataTemplate>
    </TreeView.ItemTemplate>
</TreeView>
```

**ObservableCollection fallback:**

```python
# The class tries to import ObservableCollection
try:
    from System.Collections.ObjectModel import ObservableCollection
    _COLLECTION_TYPE = ObservableCollection
except ImportError:
    _COLLECTION_TYPE = list  # fallback — dynamic updates won't propagate
```

When using the `list` fallback, the TreeView won't automatically reflect
runtime additions/removals. Call `Items.Refresh()` on the TreeView control
manually if needed.

---

## Complete Integration Example

```python
from radial_menu.data_binding import (
    HierarchicalItem, CheckableItem, PoolItemView
)

class MainViewModel(BindableBase):
    def __init__(self, config):
        super(MainViewModel, self).__init__()

        # Build command tree
        self._tree = []
        for category in config["categories"]:
            node = HierarchicalItem(name=category["name"])
            for cmd in category["commands"]:
                node.add_child(HierarchicalItem(
                    name=cmd["name"],
                    data=cmd
                ))
            self._tree.append(node)

        # Build pool list
        self._pool = [
            PoolItemView(**item) for item in config["pool"]
        ]

    @property
    def CommandTree(self):
        return self._tree

    @property
    def PoolItems(self):
        return self._pool

# Set as DataContext
window.DataContext = MainViewModel(settings)
```

---

## Testing

The module has **28 unit tests** covering:

- `BindableBase` property change notifications
- `CheckableItem` two-way binding and data payload
- `DictionaryWrapper` attribute access, nested dicts, missing keys
- `PoolItemView` computed properties (ContextSummary, LevelLabel)
- `HierarchicalItem` child management (add, remove, clear)
- `ObservableCollection` fallback detection
- Edge cases: empty names, None data, Unicode labels, deep nesting

Run tests:

```bash
python -m pytest tests/test_data_binding.py -v
```

---

## Design Decisions

1. **PascalCase properties** — WPF binding expressions use PascalCase by
   convention. Using `Name` instead of `name` avoids custom binding path
   workarounds.
2. **ObservableCollection fallback** — IronPython environments vary widely.
   A silent fallback to `list` ensures the code never crashes at import time,
   even if dynamic UI updates are degraded.
3. **Computed properties** — `ContextSummary` and `LevelLabel` eliminate
   the need for value converters in XAML, keeping the XAML simpler.
4. **`DictionaryWrapper` recursive wrapping** — nested dicts are automatically
   wrapped, enabling `{Binding parent.child.value}` paths without manual
   wrapping at each level.
