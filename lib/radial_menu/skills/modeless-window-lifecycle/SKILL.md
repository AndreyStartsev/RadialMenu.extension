---
name: modeless-window-lifecycle
description: >
  Manages the complete lifecycle of modeless WPF windows in Revit: creation via
  Dispatcher, DPI scaling, owner handle linking, singleton pattern via AppDomain,
  and thread-safe close. Use when building floating toolbars, dashboards, notification
  popups, or any non-modal UI in Revit.
---

# Modeless Window Lifecycle

A comprehensive manager for creating, showing, and closing modeless (non-blocking)
WPF windows inside Revit. Handles the unique challenges of Revit's threading model,
DPI awareness, and window ownership.

## Source Reference

- **Implementation**: `lib/radial_menu/modeless_window.py`

---

## Core Concepts

### Why Modeless Windows Are Hard in Revit

1. **Threading** — Revit's API is single-threaded. WPF windows need a UI thread
   dispatcher. Cross-thread calls crash silently or throw `InvalidOperationException`.
2. **Window ownership** — unowned modeless windows can hide behind Revit's main
   window and become unreachable.
3. **DPI scaling** — Revit may run at non-100% DPI. WPF elements sized in device
   pixels will appear wrong.
4. **Singleton enforcement** — opening the same window twice creates duplicate
   instances that fight for resources.

This module solves all four problems.

---

## API Reference

### `WindowManager` Class

#### `show(window_class, *args, **kwargs)` — Create and Show

```python
from radial_menu.modeless_window import WindowManager

wm = WindowManager()

# Show a modeless window (creates if needed, brings to front if exists)
wm.show(MyRadialMenuWindow, config=settings, theme="dark")
```

- If no instance exists, creates the window on the UI thread via `Dispatcher`.
- If an instance already exists and is open, brings it to the foreground.
- Passes `*args` and `**kwargs` to the window class constructor.
- Automatically calls `set_owner()` to link to Revit's main window.
- Applies DPI scaling.

#### `close()` — Thread-Safe Close

```python
wm.close()
```

- Closes the managed window via `Dispatcher.BeginInvoke` to ensure
  thread safety.
- Cleans up the singleton reference.
- Safe to call from any thread (Revit API thread, timer callbacks, etc.).

#### `is_open()` — Check Window State

```python
if wm.is_open():
    print("Window is currently visible")
```

- Returns `True` if the window instance exists and `IsVisible` is `True`.
- Thread-safe — reads the property via Dispatcher if needed.

#### `set_owner(window)` — Link to Revit Main Window

```python
from radial_menu.modeless_window import set_owner

set_owner(my_wpf_window)
```

- Uses `WindowInteropHelper` to set the owner handle to Revit's
  `MainWindowHandle` (or `ComponentManager.ApplicationWindow` in newer APIs).
- Ensures the modeless window stays in front of Revit and appears in
  the correct taskbar group.

### DPI Utilities

#### `get_dpi_scale()` — System DPI Ratio

```python
from radial_menu.modeless_window import get_dpi_scale

scale = get_dpi_scale()  # e.g., 1.25 for 125% DPI
```

- Queries the system DPI via `Graphics.FromHwnd` or `PresentationSource`.
- Returns a float ratio (1.0 = 96 DPI, 1.5 = 144 DPI, 2.0 = 192 DPI).
- Used to scale window dimensions and element sizes for correct rendering.

### Thread Utilities

#### `dispatch_to_ui_thread(action)` — Safe UI Thread Execution

```python
from radial_menu.modeless_window import dispatch_to_ui_thread

def update_label():
    my_window.StatusLabel.Content = "Updated!"

dispatch_to_ui_thread(update_label)
```

**3 Fallback Strategies (tried in order):**

1. **`Application.Current.Dispatcher`** — standard WPF dispatcher. Works when
   the WPF Application object exists.
2. **`Dispatcher.CurrentDispatcher`** — fallback when no Application object.
   Common in pyRevit hosted environments.
3. **`SynchronizationContext.Post`** — last resort for edge cases where no
   WPF dispatcher is available.

Each strategy is tried in sequence. If all fail, the action is executed
synchronously on the current thread with a logged warning.

### Singleton Management

#### `SingletonManager` — AppDomain-Based Singleton

```python
from radial_menu.modeless_window import SingletonManager

# Store a singleton reference
SingletonManager.set("RadialMenuWindow", window_instance)

# Retrieve it
window = SingletonManager.get("RadialMenuWindow")

# Remove it
SingletonManager.remove("RadialMenuWindow")
```

- Uses `AppDomain.CurrentDomain.SetData()` / `GetData()` for storage.
- Survives pyRevit script engine reloads (AppDomain persists).
- Keys should be unique strings per window type.
- Returns `None` if no instance is stored.

**Why AppDomain?** — pyRevit's IronPython engine may reload scripts,
destroying module-level variables. `AppDomain` data persists across reloads,
making it the only reliable singleton mechanism.

---

## Complete Integration Example

```python
import clr
clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")

from System.Windows import Window, Application
from System.Windows.Markup import XamlReader

from radial_menu.modeless_window import (
    WindowManager, get_dpi_scale, dispatch_to_ui_thread
)

class MyToolbar(Window):
    def __init__(self, config):
        # Load XAML
        xaml_path = os.path.join(os.path.dirname(__file__), "toolbar.xaml")
        with open(xaml_path, "r") as f:
            self.Content = XamlReader.Parse(f.read())

        # Apply DPI scaling
        scale = get_dpi_scale()
        self.Width = 300 * scale
        self.Height = 400 * scale

        self.config = config

# In your pyRevit command script:
wm = WindowManager()
wm.show(MyToolbar, config=loaded_settings)
```

---

## Common Pitfalls

### ❌ Calling Revit API from the WPF Thread

```python
# WRONG — this will crash or silently fail
def on_button_click(sender, e):
    doc = __revit__.ActiveUIDocument.Document
    with Transaction(doc, "Create Wall") as t:
        t.Start()
        # ... Revit API calls
        t.Commit()
```

**Solution:** Use `ExternalEvent` or `IExternalEventHandler` to marshal
Revit API calls back to the Revit thread.

### ❌ Module-Level Singleton Variables

```python
# WRONG — lost when pyRevit reloads scripts
_instance = None
```

**Solution:** Use `SingletonManager` with `AppDomain` storage.

### ❌ Forgetting Window Ownership

```python
# WRONG — window disappears behind Revit
window = MyToolbar()
window.Show()
```

**Solution:** Always call `set_owner(window)` before `Show()`.

---

## Design Decisions

1. **AppDomain singleton** — the only storage that persists across pyRevit
   script reloads. Module globals and class variables are unreliable.
2. **3-strategy dispatcher** — Revit's hosting environment varies between
   versions and pyRevit configurations. Multiple fallbacks ensure reliability.
3. **Owner handle linking** — prevents the "lost window" problem where modeless
   windows hide behind Revit's main window.
4. **DPI-aware sizing** — Revit users frequently run on high-DPI displays;
   hard-coded pixel sizes produce unusable UIs on 4K monitors.
