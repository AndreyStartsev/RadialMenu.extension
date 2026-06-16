---
name: wpf-drag-drop-handler
description: >
  Reusable WPF drag-and-drop handler with JSON serialization for transferring
  command/item data between TreeView and target elements. Provides threshold-based
  drag initiation, typed DataObject format, and callback-based drop handling.
  Use when building toolbar customizers, view composers, or any drag-to-assign
  UI in WPF.
---

# WPF Drag-and-Drop Handler

A reusable drag-and-drop system designed for IronPython/WPF applications that
need to transfer structured data (commands, items, settings) between UI elements
like TreeViews and target containers.

## Source Reference

- **Implementation**: `lib/radial_menu/drag_drop.py`

---

## Core Concepts

### Threshold-Based Drag Initiation

Drag operations are only initiated after the mouse moves beyond a configurable
pixel threshold from the initial click point. This prevents accidental drags
during normal click interactions.

### JSON Serialization Protocol

Data is transferred between drag source and drop target as JSON-encoded strings
inside a WPF `DataObject`, using a custom format identifier. This avoids
COM interop issues common in IronPython and keeps the data human-readable
for debugging.

### Callback-Based Drop Handling

Drop targets register callback functions that receive the deserialized data,
decoupling the drag-drop infrastructure from business logic.

---

## API Reference

### `DragDropHandler` Class

#### Initialization

```python
from radial_menu.drag_drop import DragDropHandler

handler = DragDropHandler(data_format="RadialMenuCommand")
```

**Parameters:**

| Parameter     | Type   | Default                | Description                              |
|---------------|--------|------------------------|------------------------------------------|
| `data_format` | `str`  | `"RadialMenuCommand"`  | Custom format identifier for `DataObject` |

#### `start_drag(sender, e, data, threshold=5)` — Initiate Drag

```python
def on_mouse_move(sender, e):
    if e.LeftButton == MouseButtonState.Pressed:
        handler.start_drag(
            sender=sender,
            e=e,
            data={"name": "Wall", "class_name": "Autodesk.Revit.DB.Wall"},
            threshold=5
        )
```

- Call from `MouseMove` event handler.
- Measures distance from the initial `MouseDown` position.
- Only initiates `DragDrop.DoDragDrop()` when the threshold is exceeded.
- Serializes `data` via `serialize_command()` and wraps it in a `DataObject`.

**Parameters:**

| Parameter   | Type             | Default | Description                                 |
|-------------|------------------|---------|---------------------------------------------|
| `sender`    | `UIElement`      | —       | The source element being dragged from       |
| `e`         | `MouseEventArgs` | —       | Mouse event args for position tracking       |
| `data`      | `dict`           | —       | The data payload to transfer                |
| `threshold` | `int`            | `5`     | Minimum pixel distance before drag starts    |

#### `handle_drag_over(sender, e)` — Visual Feedback

```python
def on_drag_over(sender, e):
    handler.handle_drag_over(sender, e)
```

- Sets `e.Effects` to `DragDropEffects.Copy` if the data format matches.
- Sets `e.Effects` to `DragDropEffects.None` otherwise.
- Marks the event as handled.

#### `handle_drop(sender, e, callback)` — Process Drop

```python
def on_drop(sender, e):
    handler.handle_drop(sender, e, callback=assign_command)

def assign_command(target_element, command_data):
    """Called when a valid drop occurs."""
    target_element.Content = command_data["name"]
```

- Extracts and deserializes the data from the `DataObject`.
- Calls the `callback` with `(sender, deserialized_data)`.
- Only fires if the data format matches.

**Parameters:**

| Parameter  | Type       | Description                                          |
|------------|------------|------------------------------------------------------|
| `sender`   | `UIElement`| The drop target element                              |
| `e`        | `DragEventArgs` | Drop event args                               |
| `callback` | `callable` | Function called with `(sender, data_dict)` on drop   |

### Serialization Functions

#### `serialize_command(data)` — Dict to JSON String

```python
from radial_menu.drag_drop import serialize_command

json_str = serialize_command({
    "name": "Place Wall",
    "class_name": "Autodesk.Revit.DB.Wall",
    "icon": "wall_16.png"
})
```

- Converts a Python dict to a JSON string.
- Uses `ensure_ascii=False` for Unicode support.

#### `deserialize_command(json_str)` — JSON String to Dict

```python
from radial_menu.drag_drop import deserialize_command

data = deserialize_command(json_str)
print(data["name"])  # "Place Wall"
```

- Parses a JSON string back to a Python dict.
- Returns `None` if parsing fails (does not raise).

### Utility Functions

#### `find_visual_parent(element, parent_type)` — Walk the Visual Tree

```python
from radial_menu.drag_drop import find_visual_parent
from System.Windows.Controls import TreeViewItem

# Find the TreeViewItem ancestor of a clicked TextBlock
tree_item = find_visual_parent(clicked_element, TreeViewItem)
```

- Walks up the WPF `VisualTreeHelper` parent chain.
- Returns the first ancestor matching `parent_type`, or `None`.
- Essential for identifying the logical container of a clicked child element.

---

## Integration with WPF TreeView

### XAML Setup

```xml
<TreeView x:Name="CommandTree"
          AllowDrop="False"
          PreviewMouseLeftButtonDown="OnTreeMouseDown"
          PreviewMouseMove="OnTreeMouseMove">
    <TreeView.ItemTemplate>
        <HierarchicalDataTemplate ItemsSource="{Binding Children}">
            <TextBlock Text="{Binding Name}" />
        </HierarchicalDataTemplate>
    </TreeView.ItemTemplate>
</TreeView>

<Button x:Name="TargetSlot"
        AllowDrop="True"
        DragOver="OnSlotDragOver"
        Drop="OnSlotDrop"
        Content="Drop here" />
```

### Code-Behind

```python
from radial_menu.drag_drop import DragDropHandler

handler = DragDropHandler()

def OnTreeMouseDown(sender, e):
    handler._drag_start_point = e.GetPosition(None)

def OnTreeMouseMove(sender, e):
    item = find_visual_parent(e.OriginalSource, TreeViewItem)
    if item and item.DataContext:
        data = {
            "name": item.DataContext.Name,
            "class_name": item.DataContext.ClassName
        }
        handler.start_drag(sender, e, data)

def OnSlotDragOver(sender, e):
    handler.handle_drag_over(sender, e)

def OnSlotDrop(sender, e):
    handler.handle_drop(sender, e, callback=assign_to_slot)

def assign_to_slot(target, command_data):
    target.Content = command_data["name"]
    target.Tag = command_data
```

---

## Design Decisions

1. **JSON over COM DataObject** — IronPython has limited support for complex COM
   types in `DataObject`. JSON strings are universally safe.
2. **Threshold-based initiation** — prevents accidental drags that would interfere
   with normal TreeView expand/collapse clicks.
3. **Callback pattern** — keeps drag-drop infrastructure decoupled from business
   logic, making the handler reusable across different UI scenarios.
4. **`find_visual_parent()`** — necessary because WPF event routing can deliver
   events from deeply nested child elements (TextBlock inside Border inside
   TreeViewItem), and you usually need the logical container.
