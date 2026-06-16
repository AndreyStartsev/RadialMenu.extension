# -*- coding: utf-8 -*-
"""WPF data-binding wrapper classes for Radial Menu.

Provides IronPython-compatible CLR property patterns for use
with WPF data templates and ``ItemsSource`` bindings.
Falls back gracefully when ``ObservableCollection`` is unavailable.
"""

# ---------------------------------------------------------------------------
# ObservableCollection import with fallback
# ---------------------------------------------------------------------------

try:
    from System.Collections.ObjectModel import ObservableCollection

    _HAS_OBSERVABLE = True
except ImportError:
    _HAS_OBSERVABLE = False


def _make_collection():
    """Create an ObservableCollection[object] or fall back to a plain list.

    Returns:
        ObservableCollection[object] | list: A new empty collection.
    """
    if _HAS_OBSERVABLE:
        return ObservableCollection[object]()
    return []


# ---------------------------------------------------------------------------
# BindableBase
# ---------------------------------------------------------------------------


class BindableBase(object):
    """Base class with CLR-style property pattern for IronPython.

    Subclasses should define properties via ``@property`` / ``@<name>.setter``
    backed by ``_<name>`` private attributes. This follows the IronPython
    convention that WPF data-binding recognizes.

    Note:
        IronPython does not support ``INotifyPropertyChanged`` directly
        on plain Python classes. For two-way binding, pair this with
        ``DependencyProperty`` in XAML or use one-time binding.
    """

    pass


# ---------------------------------------------------------------------------
# CheckableItem (based on ClassItem)
# ---------------------------------------------------------------------------


class CheckableItem(BindableBase):
    """Generic checkbox item with ``Name`` and ``IsChecked`` properties.

    Suitable for binding to ``CheckBox`` lists in WPF.

    Args:
        name: Display name.
        is_checked: Initial checked state.
    """

    def __init__(self, name, is_checked=False):
        """Initialize a checkable item.

        Args:
            name: Display name for the item.
            is_checked: Whether the item starts checked.
        """
        self._name = name
        self._is_checked = is_checked

    @property
    def Name(self):
        """str: Display name of the item."""
        return self._name

    @Name.setter
    def Name(self, value):
        self._name = value

    @property
    def IsChecked(self):
        """bool: Whether the item is checked."""
        return self._is_checked

    @IsChecked.setter
    def IsChecked(self, value):
        self._is_checked = value


# ---------------------------------------------------------------------------
# DictionaryWrapper
# ---------------------------------------------------------------------------


class DictionaryWrapper(BindableBase):
    """Base class that wraps a dict and exposes its keys as properties.

    Subclasses can override individual properties for computed values.
    Raw dict access is available via :meth:`get`.

    Args:
        data: The dictionary to wrap.
    """

    def __init__(self, data=None):
        """Initialize with an optional dictionary.

        Args:
            data: Dict to wrap. Defaults to an empty dict.
        """
        self._data = data if data is not None else {}

    def get(self, key, default=None):
        """Retrieve a value from the wrapped dict.

        Args:
            key: Dictionary key.
            default: Fallback value.

        Returns:
            The value for *key*, or *default*.
        """
        return self._data.get(key, default)


# ---------------------------------------------------------------------------
# PoolItemView (based on PoolListItem)
# ---------------------------------------------------------------------------


class PoolItemView(DictionaryWrapper):
    """Wraps a pool item dict with computed display properties.

    Expected dict keys: ``icon``, ``name``, ``context_rules``,
    ``level``, ``priority``.

    Args:
        item: Pool item dictionary.
    """

    def __init__(self, item):
        """Initialize with a pool-item dictionary.

        Args:
            item: Dict containing pool-item data.
        """
        super(PoolItemView, self).__init__(item)

    @property
    def Icon(self):
        """str: Icon path for the item."""
        return self._data.get("icon", "")

    @property
    def DisplayName(self):
        """str: Human-readable name of the item."""
        return self._data.get("name", "")

    @property
    def ContextSummary(self):
        """str: Summary of context rules (allowed views/classes).

        Returns ``"Always visible"`` when no rules are defined.
        """
        rules = self._data.get("context_rules", {}) or {}
        views = rules.get("allowed_views", [])
        classes = rules.get("allowed_classes", [])

        parts = []
        if views:
            parts.append(u"Views: " + u", ".join(views))
        if classes:
            parts.append(
                u"Classes: "
                + u", ".join(classes[:2])
                + (u"..." if len(classes) > 2 else u"")
            )
        if not parts:
            return u"Always visible"
        return u" | ".join(parts)

    @property
    def LevelLabel(self):
        """str: Formatted level label, e.g. ``"L1"``."""
        return u"L{}".format(self._data.get("level", 1))

    @property
    def PriorityLabel(self):
        """str: Formatted priority label, e.g. ``"P: 5"``."""
        return u"P: {}".format(self._data.get("priority", 0))


# ---------------------------------------------------------------------------
# HierarchicalItem (based on TreeItem)
# ---------------------------------------------------------------------------


class HierarchicalItem(BindableBase):
    """Tree node for hierarchical WPF ``TreeView`` binding.

    Children are stored in an ``ObservableCollection[object]``
    (falls back to a plain ``list`` when .NET is unavailable).

    Args:
        name: Display name.
        is_command: Whether this node represents an executable command.
        icon_path: Optional icon file path.
        unique_id: Optional unique identifier.
        extension: Optional extension name.
        is_expanded: Initial expanded state.
    """

    def __init__(
        self,
        name,
        is_command=False,
        icon_path=None,
        unique_id=None,
        extension=None,
        is_expanded=False,
    ):
        """Initialize a hierarchical tree node.

        Args:
            name: Display name of the node.
            is_command: ``True`` if this node is an executable command.
            icon_path: Path to the node's icon.
            unique_id: Unique identifier string.
            extension: Extension name the command belongs to.
            is_expanded: Whether the node starts expanded.
        """
        self._name = name
        self._is_command = is_command
        self._icon_path = icon_path
        self._unique_id = unique_id
        self._extension = extension
        self._is_expanded = is_expanded
        self._children = _make_collection()

    @property
    def Name(self):
        """str: Display name of the node."""
        return self._name

    @Name.setter
    def Name(self, value):
        self._name = value

    @property
    def IsCommand(self):
        """bool: Whether this node represents an executable command."""
        return self._is_command

    @property
    def IconPath(self):
        """str or None: Path to the node's icon file."""
        return self._icon_path

    @property
    def UniqueId(self):
        """str or None: Unique identifier of the command."""
        return self._unique_id

    @property
    def Extension(self):
        """str or None: Extension name the command belongs to."""
        return self._extension

    @property
    def IsExpanded(self):
        """bool: Whether the tree node is expanded in the UI."""
        return self._is_expanded

    @IsExpanded.setter
    def IsExpanded(self, value):
        self._is_expanded = value

    @property
    def Children(self):
        """ObservableCollection[object] | list: Child nodes."""
        return self._children
