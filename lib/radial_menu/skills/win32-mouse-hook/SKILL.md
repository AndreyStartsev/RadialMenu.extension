---
name: win32-mouse-hook
description: >
  Installs and manages a Win32 low-level mouse hook (WH_MOUSE) via ctypes
  for detecting mouse hold gestures in Windows applications. Provides
  HookManager for lifecycle control and HoldDetector for configurable
  hold-delay with movement-threshold cancellation. Use when building
  gesture-based UI triggers, custom context menus, or hold-to-activate
  tools in Revit/WPF extensions.
---

# Win32 Mouse Hook Skill

## Overview

This skill wraps the Windows `WH_MOUSE` thread-local hook to detect
**right-button hold** gestures.  It is intentionally decoupled from any
UI framework and can be used with WPF, WinForms, or headless apps.

**Source file:** `lib/radial_menu/win32_hook.py`

---

## Key Classes

### `HookManager`

High-level lifecycle controller.  Installs the Win32 hook on the main
window thread, delegates events to an internal `HoldDetector`, and
invokes a user callback when a valid hold gesture is detected.

```python
from radial_menu.win32_hook import HookManager

def on_hold(x, y):
    """Called when right-button hold is confirmed."""
    print("Hold detected at", x, y)

manager = HookManager(
    on_hold_callback=on_hold,
    hold_delay_ms=400,   # ms the button must stay pressed
    move_threshold=10,   # max px displacement before cancel
)
manager.start()   # install the hook
# ... application runs ...
manager.stop()    # uninstall & cleanup
```

#### Public API

| Method / Property            | Description                                              |
|------------------------------|----------------------------------------------------------|
| `start()`                    | Install the mouse hook. Raises `RuntimeError` on failure.|
| `stop()`                     | Uninstall the hook and cancel any pending hold.          |
| `update_hold_delay(ms)`      | Change the hold delay at runtime.                        |
| `is_active` *(property)*     | `True` while the hook is installed.                      |
| `hold_detector` *(attribute)*| Direct access to the underlying `HoldDetector` instance. |

### `HoldDetector`

Low-level state machine that tracks button-down / button-up / mouse-move
events and fires a callback after a configurable delay.

```python
from radial_menu.win32_hook import HoldDetector

detector = HoldDetector(
    delay_ms=400,
    move_threshold=10,
    on_hold=lambda x, y: print("hold!", x, y),
)
detector.button_down(100, 200)
# ... after delay_ms with no movement ...
# on_hold(100, 200) fires automatically
```

#### Public API

| Method / Property               | Description                                          |
|----------------------------------|------------------------------------------------------|
| `button_down(x, y)`             | Start tracking a potential hold at *(x, y)*.         |
| `button_up() -> bool`           | Release. Returns `True` if hold already triggered.   |
| `mouse_move(x, y)`              | Cancel hold if displacement exceeds threshold.       |
| `cancel()`                      | Explicitly cancel a pending hold.                    |
| `delay_ms` *(property, r/w)*    | Current hold delay in milliseconds.                  |
| `is_holding` *(property)*       | `True` while button is held and not yet cancelled.   |
| `hold_triggered` *(property)*   | `True` if the last hold resulted in a trigger.       |

---

## Configuration Options

| Parameter          | Default | Description                                         |
|--------------------|---------|-----------------------------------------------------|
| `hold_delay_ms`    | `400`   | Milliseconds the button must stay pressed.          |
| `move_threshold`   | `10`    | Maximum cursor displacement (px) before cancel.     |

Both values can be changed at runtime via `HookManager.update_hold_delay()`
and `HoldDetector.delay_ms`.

---

## Threading Considerations

1. **Hook thread requirement** — `SetWindowsHookExW` with `WH_MOUSE` is
   a *thread-local* hook.  It must be installed on a thread that owns a
   message pump (e.g. the main UI thread).  `HookManager.start()` calls
   `get_main_thread_id()` to resolve the correct thread automatically.

2. **Hold worker thread** — `HoldDetector.button_down()` spawns a
   daemon `threading.Thread` that sleeps for `delay_ms` then checks
   whether the hold is still valid.  The `on_hold` callback fires from
   this background thread.

3. **Thread-safety** — All `HoldDetector` state is guarded by an
   internal `threading.Lock`.

---

## Integration with WPF Dispatcher

Because `on_hold` fires from a background thread, you **must** marshal
back to the UI thread before touching any WPF controls:

```python
import System.Windows.Threading as WPFThreading

def on_hold(x, y):
    dispatcher = System.Windows.Application.Current.Dispatcher
    dispatcher.BeginInvoke(
        WPFThreading.DispatcherPriority.Normal,
        System.Action(lambda: show_radial_menu(x, y)),
    )

manager = HookManager(on_hold_callback=on_hold)
```

---

## Example: Hold-to-Show Radial Menu

```python
from radial_menu.win32_hook import HookManager

class RadialMenuController(object):
    def __init__(self, window):
        self.window = window
        self.hook = HookManager(
            on_hold_callback=self._on_hold,
            hold_delay_ms=400,
        )

    def activate(self):
        self.hook.start()

    def deactivate(self):
        self.hook.stop()

    def _on_hold(self, x, y):
        # Marshal to UI thread
        self.window.Dispatcher.BeginInvoke(
            System.Action(lambda: self.window.show_at(x, y))
        )
```

---

## Gotchas & Pitfalls

### 64-bit pointer handling

The hook callback signature uses `c_int64` / `c_uint64` for `wParam`
and `lParam` to ensure correct behaviour on 64-bit Python.  The
`HOOKPROC` type is defined as:

```python
HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_int64, ctypes.c_int, ctypes.c_uint64, ctypes.c_uint64
)
```

Never change these to `c_int` / `c_long` on 64-bit systems — the
pointer values will be truncated and the hook will crash.

### Swallowing the native context menu

When `HoldDetector.button_up()` returns `True` (hold was triggered),
the hook callback returns `1` instead of calling `CallNextHookEx`.
This **swallows** the `WM_RBUTTONUP` message so Windows does not show
its native context menu.  If you need the context menu in some cases,
check your conditions before the swallow.

### Shift+RMB pass-through

The hook explicitly ignores `WM_RBUTTONDOWN` when the Shift key is
held (`VK_SHIFT`).  This reserves Shift+Right-Click for other tools.

### GC of the callback

`HookManager` stores the `HOOKPROC` wrapper in `self._hook_proc` to
prevent Python's garbage collector from freeing the ctypes callback
while Windows still references it.  Never set `_hook_proc = None`
while the hook is active.

---

## Helper: `get_main_thread_id()`

Resolves the Win32 thread ID of the process's main window.  Attempts
`System.Diagnostics.Process.GetCurrentProcess().MainWindowHandle` first,
falling back to `kernel32.GetCurrentThreadId()`.

---

## Reference

- **Source:** [`win32_hook.py`](../../win32_hook.py)
- **Dependencies:** `ctypes`, `threading`, `time`, `logging` (stdlib only)
- **Lines of code:** ~386
