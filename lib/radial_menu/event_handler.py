# -*- coding: utf-8 -*-
"""
Revit External Event Handler for modeless UI interaction.

Wraps the ``IExternalEventHandler`` pattern used by Revit add-ins that
need to execute Revit API calls from a modeless (non-modal) window.
Commands are routed through :func:`execute_revit_command`.

Revit API imports are guarded so the module can be imported outside of
a Revit host environment without raising errors.
"""

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Revit / .NET imports
# ---------------------------------------------------------------------------
_REVIT_AVAILABLE = False

try:
    import clr  # noqa: F401
    clr.AddReference("RevitAPI")
    clr.AddReference("RevitAPIUI")
    from Autodesk.Revit.UI import (
        IExternalEventHandler,
        ExternalEvent,
        PostableCommand,
        RevitCommandId,
    )
    from Autodesk.Revit.DB import Transaction, ViewDetailLevel
    import System
    _REVIT_AVAILABLE = True
except (ImportError, Exception):
    IExternalEventHandler = object
    ExternalEvent = None
    PostableCommand = None
    RevitCommandId = None
    Transaction = None

def _ids_equal(id1, id2):
    if id1 is None or id2 is None:
        return id1 is id2
    if hasattr(id1, "Value"):
        return id1.Value == id2.Value
    return id1.IntegerValue == id2.IntegerValue
    ViewDetailLevel = None


# ---------------------------------------------------------------------------
# Built-in command registry
# ---------------------------------------------------------------------------

BUILT_IN_COMMANDS = {
    "zoom": "Zoom to Fit the active view",
    "close_hidden": "Close all inactive / hidden views",
    "sync": "Synchronize with Central (workshared models)",
    "save": "Save the current document",
    "3d": "Open the default 3D view",
    "reveal": "Toggle Reveal Hidden Elements mode",
    "thin_lines": "Toggle Thin Lines display",
    "detail_level": "Cycle view Detail Level (Coarse → Medium → Fine)",
}
"""dict[str, str]: Mapping of built-in command string identifiers to
human-readable descriptions.  Each key can be passed as *cmd_value* to
:func:`execute_revit_command` with ``cmd_type="built_in"``.
"""


# ---------------------------------------------------------------------------
# RevitEventHandler
# ---------------------------------------------------------------------------

class RevitEventHandler(IExternalEventHandler):
    """Modeless ``IExternalEventHandler`` implementation.

    Stores a callable *action* (plus optional positional / keyword
    arguments) and executes it inside the Revit API context when
    ``Execute`` is called by the event framework.

    Usage::

        handler = RevitEventHandler()
        event = ExternalEvent.Create(handler)

        # Later, from a modeless window:
        handler.set_action(my_func, arg1, arg2)
        event.Raise()
    """

    def __init__(self):
        self._action = None
        self._args = ()
        self._kwargs = {}

    def set_action(self, action, *args, **kwargs):
        """Store an action to be executed on the next ``Raise()``.

        Args:
            action (callable): A function accepting ``(uiapp, *args,
                **kwargs)`` as its signature.
            *args: Positional arguments forwarded to *action*.
            **kwargs: Keyword arguments forwarded to *action*.
        """
        self._action = action
        self._args = args
        self._kwargs = kwargs

    def Execute(self, uiapp):
        """Called by Revit when the external event fires.

        Args:
            uiapp: The Revit ``UIApplication`` instance.
        """
        if self._action:
            try:
                self._action(uiapp, *self._args, **self._kwargs)
            except Exception as ex:
                logger.error(
                    "Error in Revit Event Execution (Python): %s", ex
                )
            except System.Exception as ex:
                logger.error(
                    "Error in Revit Event Execution (CLR): %s", ex
                )
            finally:
                self._action = None

    def GetName(self):
        """Return the handler display name.

        Returns:
            str: ``"Radial Menu Modeless Event Handler"``.
        """
        return "Radial Menu Modeless Event Handler"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_external_event():
    """Create a ``(handler, event)`` pair ready for use.

    Returns:
        tuple[RevitEventHandler, ExternalEvent] or tuple[None, None]:
            The handler and its associated external event, or
            ``(None, None)`` when the Revit API is unavailable.
    """
    if not _REVIT_AVAILABLE or ExternalEvent is None:
        logger.debug("Revit API unavailable; external event not created.")
        return None, None

    try:
        handler = RevitEventHandler()
        event = ExternalEvent.Create(handler)
        return handler, event
    except Exception as ex:
        logger.error("Failed to create external event: %s", ex)
        return None, None


# ---------------------------------------------------------------------------
# Command router
# ---------------------------------------------------------------------------

def execute_revit_command(uiapp, cmd_type, cmd_value):
    """Route and execute a Revit command.

    Supports two command types:

    * ``"built_in"`` — one of the keys in :data:`BUILT_IN_COMMANDS`.
    * ``"pyrevit"`` — a pyRevit command id executed via the session
      manager.

    Args:
        uiapp: A Revit ``UIApplication`` instance.
        cmd_type (str): Either ``"built_in"`` or ``"pyrevit"``.
        cmd_value (str): The command identifier.

    Raises:
        Exception: Re-raised if a fatal error occurs during execution
            (non-fatal errors are logged and swallowed).
    """
    try:
        logger.debug(
            "Executing command type='%s': %s", cmd_type, cmd_value
        )

        if cmd_type == "built_in":
            _execute_built_in(uiapp, cmd_value)
        elif cmd_type == "pyrevit":
            _execute_pyrevit(cmd_value)

    except Exception as ex:
        logger.error(
            "Exception in execute_revit_command (Python): %s", ex
        )
        raise


# ---------------------------------------------------------------------------
# Internal: built-in command implementations
# ---------------------------------------------------------------------------

def _execute_built_in(uiapp, cmd_value):
    """Dispatch a built-in Revit command."""
    uidoc = uiapp.ActiveUIDocument
    doc = uidoc.Document

    if cmd_value == "zoom":
        _cmd_zoom_to_fit(uidoc)
    elif cmd_value == "close_hidden":
        _cmd_close_hidden(uiapp, uidoc)
    elif cmd_value == "sync":
        _cmd_sync(uiapp, doc)
    elif cmd_value == "save":
        _cmd_save(uiapp)
    elif cmd_value == "3d":
        _cmd_default_3d(uiapp)
    elif cmd_value == "reveal":
        _cmd_reveal_hidden(uiapp)
    elif cmd_value == "thin_lines":
        _cmd_thin_lines(uiapp)
    elif cmd_value == "detail_level":
        _cmd_detail_level(uidoc, doc)
    else:
        logger.warning("Unknown built-in command: %s", cmd_value)


def _execute_pyrevit(cmd_value):
    """Dispatch a pyRevit command via the session manager."""
    from pyrevit.loader import sessionmgr
    logger.debug("Calling sessionmgr.execute_command for %s", cmd_value)
    sessionmgr.execute_command(cmd_value)


# -- Individual built-in commands -------------------------------------------

def _cmd_zoom_to_fit(uidoc):
    """Zoom to Fit in the active view."""
    active_view = uidoc.ActiveView
    for ui_view in uidoc.GetOpenUIViews():
        if _ids_equal(ui_view.ViewId, active_view.Id):
            ui_view.ZoomToFit()
            break


def _cmd_close_hidden(uiapp, uidoc):
    """Close inactive / hidden views."""
    cmd_id = None
    for cmd_name in ["CloseInactiveViews", "CloseHiddenWindows"]:
        if hasattr(PostableCommand, cmd_name):
            try:
                cmd_id = RevitCommandId.LookupPostableCommandId(
                    getattr(PostableCommand, cmd_name)
                )
                break
            except Exception:
                pass

    if not cmd_id:
        for name in ["ID_VIEW_CLOSE_INACTIVE", "ID_WINDOW_CLOSE_HIDDEN"]:
            cmd_id = RevitCommandId.LookupCommandId(name)
            if cmd_id:
                logger.debug(
                    "Found Close Inactive via string ID: %s", name
                )
                break

    if cmd_id:
        uiapp.PostCommand(cmd_id)
    else:
        logger.debug(
            "No Close Inactive command ID found. "
            "Falling back to manual close loop."
        )
        for ui_view in uidoc.GetOpenUIViews():
            if not _ids_equal(ui_view.ViewId, uidoc.ActiveView.Id):
                try:
                    ui_view.Close()
                except Exception as e:
                    logger.debug("Manual close failed: %s", e)


def _cmd_sync(uiapp, doc):
    """Synchronize with Central."""
    cmd_id = None
    if hasattr(PostableCommand, "SynchronizeWithCentral"):
        try:
            cmd_id = RevitCommandId.LookupPostableCommandId(
                PostableCommand.SynchronizeWithCentral
            )
        except Exception:
            pass

    if not cmd_id:
        for name in [
            "ID_FILE_SAVE_TO_CENTRAL_SHORTCUT",
            "ID_FILE_SAVE_TO_CENTRAL",
        ]:
            cmd_id = RevitCommandId.LookupCommandId(name)
            if cmd_id:
                logger.debug("Found Sync via string ID: %s", name)
                break

    if cmd_id:
        uiapp.PostCommand(cmd_id)
    else:
        logger.debug(
            "No Sync command ID found. Trying direct sync."
        )
        if doc.IsWorkshared:
            from Autodesk.Revit.DB import (
                TransactWithCentralOptions,
                SynchronizeWithCentralOptions,
                RelinquishOptions,
            )
            trans_opts = TransactWithCentralOptions()
            sync_opts = SynchronizeWithCentralOptions()
            rel_opts = RelinquishOptions(True)
            sync_opts.SetRelinquishOptions(rel_opts)
            sync_opts.Comment = "Sync via Radial Menu"
            doc.SynchronizeWithCentral(trans_opts, sync_opts)
            logger.debug("Direct SynchronizeWithCentral completed.")
        else:
            logger.debug("Document is not workshared, cannot sync.")


def _cmd_save(uiapp):
    """Save the current document."""
    cmd_id = RevitCommandId.LookupPostableCommandId(PostableCommand.Save)
    uiapp.PostCommand(cmd_id)


def _cmd_default_3d(uiapp):
    """Open the default 3D view."""
    cmd_id = RevitCommandId.LookupCommandId("ID_VIEW_DEFAULT_3DVIEW")
    if cmd_id:
        uiapp.PostCommand(cmd_id)


def _cmd_reveal_hidden(uiapp):
    """Toggle Reveal Hidden Elements."""
    cmd_id = RevitCommandId.LookupCommandId("ID_VIEW_REVEAL_HIDDEN")
    if cmd_id:
        uiapp.PostCommand(cmd_id)
    else:
        logger.debug("Command ID ID_VIEW_REVEAL_HIDDEN not found.")


def _cmd_thin_lines(uiapp):
    """Toggle Thin Lines display."""
    cmd_id = RevitCommandId.LookupCommandId("ID_VIEW_THIN_LINES")
    if cmd_id:
        uiapp.PostCommand(cmd_id)


def _cmd_detail_level(uidoc, doc):
    """Cycle through Detail Level: Coarse → Medium → Fine → Coarse."""
    active_view = uidoc.ActiveView
    t = Transaction(doc, "Toggle Detail Level")
    try:
        t.Start()
        current = active_view.DetailLevel
        if current == ViewDetailLevel.Coarse:
            active_view.DetailLevel = ViewDetailLevel.Medium
        elif current == ViewDetailLevel.Medium:
            active_view.DetailLevel = ViewDetailLevel.Fine
        else:
            active_view.DetailLevel = ViewDetailLevel.Coarse
        t.Commit()
    except Exception as ex:
        logger.error("Exception in detail_level command: %s", ex)
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
