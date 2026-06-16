# -*- coding: utf-8 -*-
"""Modeless WPF window lifecycle management for Radial Menu.

Provides thread-safe window creation, closing, DPI scaling,
UI-thread dispatching, and AppDomain-based singleton persistence.
"""

# ---------------------------------------------------------------------------
# .NET / WPF imports (graceful fallback)
# ---------------------------------------------------------------------------

try:
    import System
    from System import Action
    from System.Windows import Application
    from System.Windows.Threading import Dispatcher
    from System.Windows.Interop import WindowInteropHelper

    _HAS_WPF = True
except ImportError:
    _HAS_WPF = False

try:
    import System.Windows.Forms as _winforms
    from System.Windows import SystemParameters

    _HAS_WINFORMS = True
except ImportError:
    _HAS_WINFORMS = False


# ---------------------------------------------------------------------------
# DPI utility
# ---------------------------------------------------------------------------


def get_dpi_scale():
    """Calculate the logical-to-physical DPI scale ratio.

    Uses ``System.Windows.Forms.Screen`` for physical width and
    ``SystemParameters.PrimaryScreenWidth`` for logical width.

    Returns:
        float: Scale factor (e.g. 1.0 for 100 %, 0.666… for 150 %).
            Returns 1.0 if WinForms/WPF are unavailable.
    """
    if not _HAS_WINFORMS:
        return 1.0
    try:
        screen_width = _winforms.Screen.PrimaryScreen.Bounds.Width
        logical_width = SystemParameters.PrimaryScreenWidth
        return float(logical_width) / float(screen_width)
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# UI thread dispatch helper
# ---------------------------------------------------------------------------


def dispatch_to_ui_thread(action, dispatcher=None):
    """Run *action* on the WPF UI thread.

    Resolution order for the dispatcher:
    1. Explicit *dispatcher* argument.
    2. ``Application.Current.Dispatcher``.
    3. ``Dispatcher.CurrentDispatcher`` (last resort).

    Args:
        action: Callable (no args) to invoke on the UI thread.
        dispatcher: Optional explicit ``Dispatcher`` instance.

    Raises:
        RuntimeError: If WPF assemblies are not available.
    """
    if not _HAS_WPF:
        raise RuntimeError("WPF assemblies are not available.")

    wrapped = Action(action)
    if dispatcher:
        dispatcher.BeginInvoke(wrapped)
    elif Application.Current:
        Application.Current.Dispatcher.BeginInvoke(wrapped)
    else:
        Dispatcher.CurrentDispatcher.BeginInvoke(wrapped)


# ---------------------------------------------------------------------------
# WindowManager
# ---------------------------------------------------------------------------


class WindowManager(object):
    """Manages the lifecycle of a single modeless WPF window.

    Provides thread-safe ``show`` / ``close`` operations,
    an ``is_open`` property, and owner-handle assignment.
    """

    def __init__(self):
        """Initialize the window manager with no active window."""
        self._window = None
        self._dispatcher = None

    # -- public API --------------------------------------------------------

    def show(self, window_factory, x, y, dpi_scale=None):
        """Create and show a modeless window via the UI-thread dispatcher.

        If a window is already open it is closed first.

        Args:
            window_factory: Callable returning a WPF ``Window`` instance.
            x: Physical X coordinate for placement.
            y: Physical Y coordinate for placement.
            dpi_scale: Optional DPI scale factor.
                Calculated automatically when *None*.
        """
        if not _HAS_WPF:
            return

        # Close any existing window first
        self.close()

        scale = dpi_scale if dpi_scale is not None else get_dpi_scale()

        def _open():
            try:
                win = window_factory()
                logical_x = x * scale
                logical_y = y * scale
                win.Left = logical_x - 320
                win.Top = logical_y - 320
                win.Show()
                win.Activate()
                self._window = win
            except Exception:
                self._window = None

        self._dispatch(_open)

    def close(self):
        """Thread-safe close of the managed window.

        Uses ``Dispatcher.BeginInvoke`` to ensure the close
        runs on the UI thread.
        """
        if self._window is None:
            return

        win_ref = self._window
        self._window = None

        def _close():
            try:
                win_ref.Close()
            except Exception:
                pass

        try:
            self._dispatch(_close)
        except Exception:
            pass

    @property
    def is_open(self):
        """Whether a managed window is currently active.

        Returns:
            bool: ``True`` if a window reference is held.
        """
        return self._window is not None

    @staticmethod
    def set_owner(window, owner_handle):
        """Set the Win32 owner handle for a WPF window.

        Uses ``WindowInteropHelper`` to parent the window.

        Args:
            window: WPF ``Window`` instance.
            owner_handle: ``IntPtr`` of the owner (e.g. Revit main window).
        """
        if not _HAS_WPF:
            return
        try:
            helper = WindowInteropHelper(window)
            helper.Owner = owner_handle
        except Exception:
            pass

    # -- internal ----------------------------------------------------------

    def _dispatch(self, action):
        """Dispatch an action to the UI thread."""
        dispatch_to_ui_thread(action, self._dispatcher)


# ---------------------------------------------------------------------------
# SingletonManager (AppDomain-based persistence)
# ---------------------------------------------------------------------------


class SingletonManager(object):
    """Stores and retrieves a singleton instance via ``AppDomain.SetData / GetData``.

    This allows an object (e.g. a hook manager) to survive IronPython
    engine reloads within the same Revit session.

    Args:
        key: The ``AppDomain`` data slot name.
    """

    def __init__(self, key="RevitRadialMenuHook"):
        """Initialize with the AppDomain data-slot key.

        Args:
            key: String key used for ``AppDomain.SetData`` / ``GetData``.
        """
        self._key = key

    def get(self):
        """Retrieve the stored instance from the current ``AppDomain``.

        Returns:
            object or None: The previously stored instance, or *None*.
        """
        try:
            return System.AppDomain.CurrentDomain.GetData(self._key)
        except Exception:
            return None

    def set(self, instance):
        """Store an instance in the current ``AppDomain``.

        Args:
            instance: Object to persist (or *None* to clear).
        """
        try:
            System.AppDomain.CurrentDomain.SetData(self._key, instance)
        except Exception:
            pass

    def clear(self):
        """Remove the stored instance from the ``AppDomain``."""
        self.set(None)
