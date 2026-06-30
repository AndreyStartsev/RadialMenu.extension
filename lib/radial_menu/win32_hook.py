# -*- coding: utf-8 -*-
"""
Win32 mouse hook utilities.

Provides a generic, reusable wrapper around the Windows low-level/thread-local
mouse hook (WH_MOUSE = 7).  The module is intentionally decoupled from any
specific UI framework so it can be used with WPF, WinForms, or headless apps.

Typical usage::

    def on_hold(x, y):
        print("Hold detected at", x, y)

    manager = HookManager(on_hold_callback=on_hold, hold_delay_ms=400)
    manager.start()
    # ... later ...
    manager.stop()
"""

import ctypes
import threading
import time
import logging

# ---------------------------------------------------------------------------
# Win32 API handles
# ---------------------------------------------------------------------------
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Hook callback signature (64-bit compatible)
HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_int64, ctypes.c_int, ctypes.c_uint64, ctypes.c_uint64
)

# Configure ctypes signatures for 64-bit safety
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    HOOKPROC,
    ctypes.c_void_p,
    ctypes.c_uint32
]
user32.SetWindowsHookExW.restype = ctypes.c_void_p

user32.UnhookWindowsHookEx.argtypes = [
    ctypes.c_void_p
]
user32.UnhookWindowsHookEx.restype = ctypes.c_bool

user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_uint64,
    ctypes.c_uint64
]
user32.CallNextHookEx.restype = ctypes.c_int64

user32.GetKeyState.argtypes = [
    ctypes.c_int
]
user32.GetKeyState.restype = ctypes.c_int16

kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = ctypes.c_uint32

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ctypes structures
# ---------------------------------------------------------------------------

class POINT(ctypes.Structure):
    """Win32 POINT structure (x, y coordinates)."""
    _fields_ = [
        ("x", ctypes.c_int32),
        ("y", ctypes.c_int32),
    ]


class MOUSEHOOKSTRUCT(ctypes.Structure):
    """Win32 MOUSEHOOKSTRUCT returned by WH_MOUSE hooks."""
    _fields_ = [
        ("pt", POINT),
        ("hwnd", ctypes.c_uint64),
        ("wHitTestCode", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_uint64),
    ]


# ---------------------------------------------------------------------------
# Win32 message constants
# ---------------------------------------------------------------------------
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_RBUTTONDBLCLK = 0x0206
WM_MOUSEMOVE = 0x0200
WH_MOUSE = 7
VK_SHIFT = 0x10


# ---------------------------------------------------------------------------
# Helper: get main window thread id
# ---------------------------------------------------------------------------

def get_main_thread_id():
    """Return the thread ID of the process's main window.

    Attempts to resolve the thread via ``System.Diagnostics`` (.NET) first,
    falling back to ``GetCurrentThreadId`` if that is unavailable.

    Returns:
        int: Win32 thread identifier.
    """
    try:
        import System.Diagnostics  # noqa: F811
        hwnd = System.Diagnostics.Process.GetCurrentProcess().MainWindowHandle
        if hwnd:
            hwnd_val = hwnd.ToInt64()
            user32.GetWindowThreadProcessId.argtypes = [
                ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)
            ]
            user32.GetWindowThreadProcessId.restype = ctypes.c_uint32
            thread_id = user32.GetWindowThreadProcessId(hwnd_val, None)
            if thread_id:
                logger.debug("Found main window thread_id=%s via HWND.", thread_id)
                return thread_id
    except Exception as ex:
        logger.debug("Failed to get thread_id via HWND: %s. Falling back.", ex)

    tid = kernel32.GetCurrentThreadId()
    logger.debug("Using GetCurrentThreadId() = %s.", tid)
    return tid


# ---------------------------------------------------------------------------
# HoldDetector
# ---------------------------------------------------------------------------

class HoldDetector(object):
    """Detects a mouse-button *hold* gesture with movement cancellation.

    A hold is triggered when the button stays pressed longer than
    ``delay_ms`` milliseconds without moving more than
    ``move_threshold`` pixels.

    Args:
        delay_ms (int): Milliseconds the button must be held.
            Defaults to 400.
        move_threshold (int): Maximum allowed cursor displacement in
            pixels before the hold is cancelled.  Defaults to 10.
        on_hold (callable): ``on_hold(x, y)`` called when a valid hold
            is detected.  *x* and *y* are the coordinates where the
            button was first pressed.
    """

    def __init__(self, delay_ms=400, move_threshold=10, on_hold=None):
        self._delay_ms = delay_ms
        self._move_threshold = move_threshold
        self._on_hold = on_hold

        self._lock = threading.Lock()
        self._is_holding = False
        self._hold_triggered = False
        self._hold_id = 0
        self._start_x = 0
        self._start_y = 0

    # -- public properties ---------------------------------------------------

    @property
    def delay_ms(self):
        """int: Current hold delay in milliseconds."""
        return self._delay_ms

    @delay_ms.setter
    def delay_ms(self, value):
        self._delay_ms = int(value)

    @property
    def is_holding(self):
        """bool: ``True`` while the button is held down and not cancelled."""
        with self._lock:
            return self._is_holding

    @property
    def hold_triggered(self):
        """bool: ``True`` if the last hold resulted in a trigger callback."""
        with self._lock:
            return self._hold_triggered

    # -- lifecycle methods ---------------------------------------------------

    def button_down(self, x, y):
        """Notify that the monitored button was pressed at *(x, y)*.

        Starts a background thread that will fire ``on_hold`` after the
        configured delay unless cancelled by movement or button-up.

        Args:
            x (int): X-coordinate of the press.
            y (int): Y-coordinate of the press.
        """
        with self._lock:
            self._is_holding = True
            self._hold_triggered = False
            self._hold_id += 1
            current_id = self._hold_id
            self._start_x = x
            self._start_y = y

        t = threading.Thread(
            target=self._worker, args=(current_id, x, y)
        )
        t.daemon = True
        t.start()

    def button_up(self):
        """Notify that the monitored button was released.

        Returns:
            bool: ``True`` if the hold had already triggered (the caller
            may want to swallow the button-up event to prevent a context
            menu from appearing).
        """
        swallow = False
        with self._lock:
            self._is_holding = False
            if self._hold_triggered:
                self._hold_triggered = False
                swallow = True
        return swallow

    def mouse_move(self, x, y):
        """Notify that the cursor moved to *(x, y)* while the button is down.

        Cancels the pending hold if displacement exceeds
        ``move_threshold``.

        Args:
            x (int): Current X-coordinate.
            y (int): Current Y-coordinate.
        """
        with self._lock:
            if not self._is_holding:
                return
            dx = abs(x - self._start_x)
            dy = abs(y - self._start_y)
            if dx > self._move_threshold or dy > self._move_threshold:
                logger.debug(
                    "Mouse moved (dx=%s, dy=%s). Cancelling hold.", dx, dy
                )
                self._is_holding = False

    def cancel(self):
        """Explicitly cancel any pending hold detection."""
        with self._lock:
            self._is_holding = False

    # -- internals -----------------------------------------------------------

    def _worker(self, hold_id, start_x, start_y):
        """Background thread that waits for the hold delay."""
        logger.debug(
            "Hold worker started for hold_id=%s. Delay=%sms.",
            hold_id, self._delay_ms,
        )
        time.sleep(self._delay_ms / 1000.0)

        should_trigger = False
        with self._lock:
            if self._is_holding and self._hold_id == hold_id:
                should_trigger = True
                self._hold_triggered = True

        if should_trigger:
            logger.debug(
                "Hold threshold met for hold_id=%s. Triggering callback.",
                hold_id,
            )
            if self._on_hold:
                self._on_hold(start_x, start_y)
        else:
            logger.debug(
                "Hold cancelled or superseded for hold_id=%s.", hold_id
            )


# ---------------------------------------------------------------------------
# HookManager
# ---------------------------------------------------------------------------

class HookManager(object):
    """Manages a Win32 thread-local mouse hook (WH_MOUSE = 7).

    The manager installs a mouse hook on the main window's thread and
    delegates button/movement events to an internal ``HoldDetector``.
    When a valid hold is detected the user-supplied *on_hold_callback*
    is invoked.

    Args:
        on_hold_callback (callable): ``callback(x, y)`` invoked when a
            right-button hold is detected.
        hold_delay_ms (int): Hold delay in milliseconds.  Defaults to 400.
        move_threshold (int): Pixel threshold for movement cancellation.
            Defaults to 10.

    Example::

        mgr = HookManager(on_hold_callback=my_handler, hold_delay_ms=500)
        mgr.start()
        # ... application runs ...
        mgr.stop()
    """

    def __init__(self, on_hold_callback=None, hold_delay_ms=400,
                 move_threshold=10, trigger_mode="hold", on_double_click_callback=None):
        self._on_hold_callback = on_hold_callback
        self._on_double_click_callback = on_double_click_callback
        self.trigger_mode = trigger_mode
        self._hook_id = None
        self._hook_proc = None  # prevent GC of the callback
        self._last_rbutton_down_time = 0.0
        self._last_rbutton_down_x = 0
        self._last_rbutton_down_y = 0
        self._menu_opened_by_double_click = False

        self.hold_detector = HoldDetector(
            delay_ms=hold_delay_ms,
            move_threshold=move_threshold,
            on_hold=on_hold_callback,
        )

    # -- public API ----------------------------------------------------------

    @property
    def is_active(self):
        """bool: ``True`` if the hook is currently installed."""
        return self._hook_id is not None

    def start(self):
        """Install the mouse hook on the main window thread.

        Raises:
            RuntimeError: If the Win32 ``SetWindowsHookExW`` call fails.
        """
        if self._hook_id is not None:
            logger.debug("HookManager.start() called but hook already set.")
            return

        self._hook_proc = HOOKPROC(self._hook_callback)
        thread_id = get_main_thread_id()

        logger.debug(
            "Registering WH_MOUSE hook for thread_id=%s", thread_id
        )
        self._hook_id = user32.SetWindowsHookExW(
            WH_MOUSE, self._hook_proc, 0, thread_id
        )

        if not self._hook_id:
            err = kernel32.GetLastError()
            raise RuntimeError(
                "Failed to set thread-local mouse hook. "
                "Win32 Error: {}".format(err)
            )
        logger.debug("Hook registered. hook_id=%s", self._hook_id)

    def stop(self):
        """Uninstall the mouse hook and cancel any pending hold."""
        logger.debug("HookManager.stop() called.")
        self.hold_detector.cancel()

        if self._hook_id:
            user32.UnhookWindowsHookEx(self._hook_id)
            logger.debug("Hook unregistered. hook_id=%s", self._hook_id)
            self._hook_id = None
            self._hook_proc = None

    def update_hold_delay(self, delay_ms):
        """Update the hold delay at runtime.

        Args:
            delay_ms (int): New delay value in milliseconds.
        """
        self.hold_detector.delay_ms = delay_ms

    # -- internal hook callback ----------------------------------------------

    def _hook_callback(self, nCode, wParam, lParam):
        """Low-level hook procedure dispatched by Windows."""
        try:
            if nCode >= 0:
                if wParam == WM_RBUTTONDOWN:
                    hs = ctypes.cast(
                        ctypes.c_void_p(lParam),
                        ctypes.POINTER(MOUSEHOOKSTRUCT),
                    ).contents
                    current_x = hs.pt.x
                    current_y = hs.pt.y
                    
                    current_time = time.time()
                    time_diff = current_time - self._last_rbutton_down_time
                    dx = abs(current_x - self._last_rbutton_down_x)
                    dy = abs(current_y - self._last_rbutton_down_y)
                    
                    is_double_click = False
                    if time_diff < 0.5 and dx < 10 and dy < 10:
                        is_double_click = True
                        
                    self._last_rbutton_down_time = current_time
                    self._last_rbutton_down_x = current_x
                    self._last_rbutton_down_y = current_y
                    
                    if self.trigger_mode == "double_click":
                        if is_double_click:
                            logger.debug("Double-click detected (manual). Triggering double-click callback.")
                            self.hold_detector.cancel()
                            self._menu_opened_by_double_click = True
                            if self._on_double_click_callback:
                                self._on_double_click_callback(current_x, current_y)
                            return 1
                    else:
                        # Ignore Shift+RMB (reserved for custom actions)
                        is_shift = (user32.GetKeyState(VK_SHIFT) & 0x8000) != 0
                        if not is_shift:
                            self.hold_detector.button_down(current_x, current_y)

                elif wParam == WM_RBUTTONDBLCLK:
                    if self.trigger_mode == "double_click":
                        logger.debug("WM_RBUTTONDBLCLK hook event. Triggering double-click callback.")
                        hs = ctypes.cast(
                            ctypes.c_void_p(lParam),
                            ctypes.POINTER(MOUSEHOOKSTRUCT),
                        ).contents
                        self.hold_detector.cancel()
                        self._menu_opened_by_double_click = True
                        if self._on_double_click_callback:
                            self._on_double_click_callback(hs.pt.x, hs.pt.y)
                        return 1

                elif wParam == WM_RBUTTONUP:
                    swallow = False
                    if self.hold_detector.button_up():
                        swallow = True
                    if self._menu_opened_by_double_click:
                        self._menu_opened_by_double_click = False
                        swallow = True
                    if swallow:
                        # Swallow the event to suppress the context menu
                        return 1

                elif wParam == WM_MOUSEMOVE:
                    if self.hold_detector.is_holding:
                        hs = ctypes.cast(
                            ctypes.c_void_p(lParam),
                            ctypes.POINTER(MOUSEHOOKSTRUCT),
                        ).contents
                        self.hold_detector.mouse_move(hs.pt.x, hs.pt.y)

        except Exception as ex:
            logger.exception("Exception in hook callback: %s", ex)

        return user32.CallNextHookEx(
            self._hook_id or 0, nCode, wParam, lParam
        )
