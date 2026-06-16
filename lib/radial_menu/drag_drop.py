# -*- coding: utf-8 -*-
"""WPF drag-and-drop handler for RadialMenu command assignment.

Encapsulates the logic for dragging pyRevit commands from a TreeView and
dropping them onto radial-menu button slots.  Serialisation uses JSON via
a configurable ``DataObject`` format string.

All WPF / .NET imports are guarded so the module can be imported safely
in environments without CLR (e.g. for testing).
"""

import json
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graceful WPF / .NET imports
# ---------------------------------------------------------------------------
try:
    import System
    from System.Windows import DragDrop, DragDropEffects, DataObject
    from System.Windows import SystemParameters
    from System.Windows.Input import MouseButtonState
    from System.Windows.Media import VisualTreeHelper
    _HAS_WPF = True
except ImportError:
    _HAS_WPF = False
    System = None
    DragDrop = None
    DragDropEffects = None
    DataObject = None
    SystemParameters = None
    MouseButtonState = None
    VisualTreeHelper = None


def _safe_str(obj):
    """Safely convert any object to a unicode string."""
    try:
        return u"{}".format(obj)
    except Exception:
        return u"<non-printable>"


# =========================================================================
# Visual tree helper
# =========================================================================

def find_visual_parent(element, parent_type):
    """Walk up the WPF visual tree to find the nearest ancestor of a type.

    Args:
        element:     Starting ``DependencyObject``.
        parent_type: The CLR type to search for (e.g.
                     ``System.Windows.Controls.TreeViewItem``).

    Returns:
        The first ancestor matching *parent_type*, or ``None`` if the
        root is reached without a match.

    Raises:
        RuntimeError: If WPF is not available.
    """
    if not _HAS_WPF:
        raise RuntimeError("WPF is not available in this environment.")

    current = element
    while current is not None and not isinstance(current, parent_type):
        current = VisualTreeHelper.GetParent(current)
    return current


# =========================================================================
# DragDropHandler
# =========================================================================

class DragDropHandler(object):
    """Manages WPF drag-and-drop operations for command assignment.

    Provides methods to initiate, validate, and complete drag-and-drop
    operations between a command tree and radial-menu button slots.

    Args:
        data_format: The ``DataObject`` format string used to tag the
                     drag payload.  Defaults to ``'CommandJSON'``.
    """

    def __init__(self, data_format="CommandJSON"):
        self.data_format = data_format
        self._drag_start_point = None

    # -----------------------------------------------------------------
    # Serialisation helpers
    # -----------------------------------------------------------------

    @staticmethod
    def serialize_command(cmd_data):
        """Serialise a command dict to a JSON string.

        Args:
            cmd_data: Dict with keys such as ``name``, ``unique_id``,
                ``extension``, ``icon_path``.

        Returns:
            str: JSON-encoded string.
        """
        return json.dumps(cmd_data)

    @staticmethod
    def deserialize_command(data):
        """Deserialise a JSON string back to a command dict.

        Args:
            data: JSON string.

        Returns:
            dict: Parsed command data.

        Raises:
            ValueError: If *data* is not valid JSON.
        """
        return json.loads(data)

    # -----------------------------------------------------------------
    # Drag initiation
    # -----------------------------------------------------------------

    def start_drag(self, sender, args, start_point):
        """Check the drag threshold and, if exceeded, initiate a drag.

        Call this from a ``MouseMove`` event handler.  The method records
        the starting point and, once the mouse has moved beyond the
        system minimum drag distance, packages the command data from the
        nearest ``TreeViewItem`` header and starts a ``DoDragDrop``
        operation.

        Args:
            sender:      The source WPF element.
            args:        ``MouseEventArgs`` from the event.
            start_point: The ``Point`` recorded on ``MouseDown``.

        Returns:
            bool: ``True`` if a drag operation was initiated.
        """
        if not _HAS_WPF:
            logger.debug(u"WPF not available; cannot start drag.")
            return False

        if args.LeftButton != MouseButtonState.Pressed:
            return False

        position = args.GetPosition(None)
        dx = abs(position.X - start_point.X)
        dy = abs(position.Y - start_point.Y)

        if (dx <= SystemParameters.MinimumHorizontalDragDistance
                and dy <= SystemParameters.MinimumVerticalDragDistance):
            return False

        from System.Windows.Controls import TreeViewItem

        dependency_obj = find_visual_parent(
            args.OriginalSource, TreeViewItem)

        if dependency_obj is None:
            return False

        cmd_item = dependency_obj.Header
        if not cmd_item or not getattr(cmd_item, "IsCommand", False):
            return False

        logger.debug(u"Starting drag for command: %s", cmd_item.Name)

        cmd_dict = {
            "name": cmd_item.Name,
            "unique_id": cmd_item.UniqueId,
            "extension": cmd_item.Extension,
            "icon_path": cmd_item.IconPath,
        }
        cmd_json = self.serialize_command(cmd_dict)
        drag_data = DataObject(self.data_format, cmd_json)
        DragDrop.DoDragDrop(
            dependency_obj, drag_data, DragDropEffects.Copy)
        return True

    # -----------------------------------------------------------------
    # Drag over
    # -----------------------------------------------------------------

    def handle_drag_over(self, sender, args):
        """Handle the ``DragOver`` event on a drop target.

        Sets the drop effect to *Copy* if the payload matches the
        expected data format, or *None* otherwise.

        Args:
            sender: The target WPF element.
            args:   ``DragEventArgs`` from the event.
        """
        if not _HAS_WPF:
            return

        if args.Data.GetDataPresent(self.data_format):
            args.Effects = DragDropEffects.Copy
        else:
            args.Effects = DragDropEffects.None
        args.Handled = True

    # -----------------------------------------------------------------
    # Drop
    # -----------------------------------------------------------------

    def handle_drop(self, sender, args, callback):
        """Handle the ``Drop`` event on a drop target.

        Extracts and deserialises the command JSON from the drag payload,
        then invokes *callback* with ``(sender, cmd_data)`` so that the
        caller can assign the command to the appropriate slot.

        Args:
            sender:   The target WPF element.
            args:     ``DragEventArgs`` from the event.
            callback: Callable ``(sender, dict) -> None`` invoked on a
                successful drop.
        """
        if not _HAS_WPF:
            return

        if args.Data.GetDataPresent(self.data_format):
            cmd_json = args.Data.GetData(self.data_format)
            try:
                cmd_data = self.deserialize_command(cmd_json)
                callback(sender, cmd_data)
            except Exception as ex:
                logger.debug(u"Failed to process dropped data: %s",
                             _safe_str(ex))
            args.Handled = True
