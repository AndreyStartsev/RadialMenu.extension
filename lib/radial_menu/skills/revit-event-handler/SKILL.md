---
name: revit-event-handler
description: >
  Thread-safe IExternalEventHandler wrapper for executing Revit API
  commands from background threads or modeless WPF windows. Routes
  string command IDs to Revit PostableCommand or RevitCommandId lookups.
  Use when any non-UI-thread code needs to call Revit API safely.
---

# Revit Event Handler Skill

## Overview

The Revit API is **strictly single-threaded** — all API calls must
execute on the Revit main thread.  This module provides the standard
`IExternalEventHandler` pattern that safely marshals commands from
modeless WPF windows or background threads into the Revit API context.

**Source file:** `lib/radial_menu/event_handler.py`

---

## Why This Pattern Is Mandatory

Revit enforces a **single-threaded apartment** model.  Calling any
`Autodesk.Revit.DB` or `Autodesk.Revit.UI` method from a background
thread (e.g. a WPF button handler, a timer, a mouse hook callback) will
raise an `InvalidOperationException` or silently corrupt Revit state.

The only supported way to call Revit API from non-UI code is:

1. Create an `IExternalEventHandler` + `ExternalEvent`.
2. Store the desired action in the handler.
3. Call `ExternalEvent.Raise()`.
4. Revit calls `handler.Execute(uiapp)` on the main thread.

This module encapsulates steps 1-4.

---

## `RevitEventHandler` Class

### Construction

```python
from radial_menu.event_handler import RevitEventHandler
from Autodesk.Revit.UI import ExternalEvent

handler = RevitEventHandler()
event = ExternalEvent.Create(handler)
```

### Setting an Action

```python
def my_action(uiapp, some_arg):
    """This runs on the Revit main thread."""
    doc = uiapp.ActiveUIDocument.Document
    # ... safe Revit API calls ...

handler.set_action(my_action, "some_arg")
event.Raise()
```

### API Reference

| Method / Property                          | Description                                        |
|--------------------------------------------|----------------------------------------------------|
| `set_action(action, *args, **kwargs)`      | Store callable + args for next `Raise()`.          |
| `Execute(uiapp)`                           | Called by Revit. Executes the stored action.       |
| `GetName() -> str`                         | Returns `"Radial Menu Modeless Event Handler"`.    |

> **Note:** After `Execute()` completes, `_action` is reset to `None`
> to prevent accidental re-execution.

---

## `create_external_event()` Factory

Convenience factory that creates a ready-to-use `(handler, event)` pair.

```python
from radial_menu.event_handler import create_external_event

handler, event = create_external_event()

if handler is None:
    print("Revit API not available")
```

**Returns:** `(RevitEventHandler, ExternalEvent)` or `(None, None)`
when the Revit API is unavailable.

---

## `execute_revit_command(uiapp, cmd_type, cmd_value)`

Central command router.  Dispatches commands by type:

**Signature:**

```python
def execute_revit_command(uiapp, cmd_type, cmd_value) -> None
```

**Parameters:**

| Param      | Type  | Description                                   |
|------------|-------|-----------------------------------------------|
| `uiapp`    | `UIApplication` | Revit UI application instance.       |
| `cmd_type` | `str` | `"built_in"` or `"pyrevit"`.                  |
| `cmd_value`| `str` | Command identifier string.                    |

### Built-in Commands

| `cmd_value`      | Action                                                  |
|------------------|---------------------------------------------------------|
| `"zoom"`         | Zoom to Fit the active view.                            |
| `"close_hidden"` | Close all inactive / hidden views.                      |
| `"sync"`         | Synchronize with Central (workshared models).           |
| `"save"`         | Save the current document.                              |
| `"3d"`           | Open the default 3D view.                               |
| `"reveal"`       | Toggle Reveal Hidden Elements mode.                     |
| `"thin_lines"`   | Toggle Thin Lines display.                              |
| `"detail_level"` | Cycle Detail Level: Coarse → Medium → Fine → Coarse.   |

### pyRevit Commands

When `cmd_type == "pyrevit"`, the router calls:

```python
from pyrevit.loader import sessionmgr
sessionmgr.execute_command(cmd_value)
```

where `cmd_value` is the pyRevit unique command ID.

---

## Built-in Command Implementations

### Command routing fallback chain

Most built-in commands use a multi-level resolution strategy:

1. Try `PostableCommand` enum attribute (e.g. `PostableCommand.Save`).
2. Try `RevitCommandId.LookupPostableCommandId()`.
3. Try `RevitCommandId.LookupCommandId()` with string IDs like
   `"ID_VIEW_DEFAULT_3DVIEW"`.
4. Fall back to direct API calls (e.g. manual view closing loop).

This ensures compatibility across Revit versions where some commands
may or may not be available.

### Transaction wrapping: `detail_level`

The `detail_level` command is the only built-in that modifies the
document model directly.  It wraps the change in a `Transaction`:

```python
t = Transaction(doc, "Toggle Detail Level")
t.Start()
# cycle ViewDetailLevel enum
t.Commit()
# ... or t.RollBack() on exception
```

All other built-in commands use `uiapp.PostCommand()` which does not
require an explicit transaction.

---

## Adding Custom Commands

To add a new built-in command:

1. Add an entry to `BUILT_IN_COMMANDS` (documentation only):

```python
from radial_menu.event_handler import BUILT_IN_COMMANDS
BUILT_IN_COMMANDS["my_cmd"] = "Description of my command"
```

2. Add a handler function and update `_execute_built_in()`:

```python
# In event_handler.py:
def _cmd_my_command(uiapp):
    cmd_id = RevitCommandId.LookupCommandId("ID_MY_COMMAND")
    if cmd_id:
        uiapp.PostCommand(cmd_id)

# Add to the dispatch chain in _execute_built_in():
elif cmd_value == "my_cmd":
    _cmd_my_command(uiapp)
```

---

## Typical Integration Pattern

```python
from radial_menu.event_handler import (
    create_external_event,
    execute_revit_command,
)

# At extension startup:
handler, event = create_external_event()

# From modeless WPF window button click:
def on_button_click(sender, args):
    handler.set_action(
        execute_revit_command, "built_in", "zoom"
    )
    event.Raise()
```

---

## Reference

- **Source:** [`event_handler.py`](../../event_handler.py)
- **Dependencies:** `logging` (stdlib); `clr`, `RevitAPI`, `RevitAPIUI`
  (optional, graceful degradation)
- **Lines of code:** ~371
