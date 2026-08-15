# -*- coding: utf-8 -*-
__persistentengine__ = True
__lightweightscopes__ = False


import os
import sys
import ctypes
import time
import clr
import math
import threading
import json

# Ensure lib directory is on sys.path
_SCRIPT_DIR = os.path.dirname(__file__)
_LIB_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "..", "..", "lib"))
if os.path.exists(_LIB_DIR) and _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

try:
    import radial_menu
    from radial_menu.radial_geometry import get_sector_path, get_ring_radii, get_text_position, calculate_effective_sectors
    from radial_menu.theme_engine import THEMES, get_luminance, get_contrast_foreground
    from radial_menu.config_manager import ConfigManager
except ImportError:
    pass

try:
    unicode
except NameError:
    unicode = str

_IS_REVIT_DARK = False
_IS_MENU_DARK = False
_active_close_delegates = []
_active_open_delegates = []
_delegate_lock = threading.Lock()
_CACHED_REFLECTED_CLASSES = None
_CACHED_CATEGORY_GROUPS = None

def fast_toggle_icon(state):
    try:
        import System
        from pyrevit import script, EXEC_PARAMS
        import os
        
        cached_buttons = System.AppDomain.CurrentDomain.GetData("RadialMenu_UI_Buttons")
        if not cached_buttons:
            cached_buttons = script.get_all_buttons()
            if cached_buttons:
                System.AppDomain.CurrentDomain.SetData("RadialMenu_UI_Buttons", cached_buttons)
        
        if not cached_buttons:
            return
            
        base_dir = EXEC_PARAMS.command_path
        on_icon = os.path.join(base_dir, "on.png")
        off_icon = os.path.join(base_dir, "off.png")
        
        target_icon = on_icon if state else off_icon
        
        for btn in cached_buttons:
            if hasattr(btn, "set_icon") and os.path.exists(target_icon):
                btn.set_icon(target_icon)
    except Exception as ex:
        try:
            import traceback
            with open(os.path.join(os.path.dirname(__file__), "RadialMenu_debug.log"), "a") as f:
                f.write("Fast Toggle Error: " + str(ex) + "\n" + traceback.format_exc() + "\n")
        except:
            pass

# Reference required .NET assemblies
clr.AddReference("WindowsBase")
clr.AddReference("PresentationCore")
clr.AddReference("PresentationFramework")
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")

from System.Windows import Window, Visibility, Application, Thickness, SystemParameters
from System.Windows.Media import VisualTreeHelper, SolidColorBrush, ColorConverter, Brushes, Geometry

_brush_cache = {}
_brush_cache_lock = threading.Lock()

def get_cached_brush(hex_str):
    with _brush_cache_lock:
        if hex_str not in _brush_cache:
            try:
                brush = SolidColorBrush(ColorConverter.ConvertFromString(hex_str))
                brush.Freeze()
                _brush_cache[hex_str] = brush
            except:
                # Fallback to unfrozen SolidColorBrush if freezing fails
                try:
                    _brush_cache[hex_str] = SolidColorBrush(ColorConverter.ConvertFromString(hex_str))
                except:
                    return Brushes.Transparent
        return _brush_cache[hex_str]

from System.Windows.Controls import TreeViewItem
from pyrevit.framework import wpf
from pyrevit import HOST_APP, forms
import System
from System import Action
import System.Windows.Input as wpf_input

# Win32 API setup
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Configure ctypes signatures for 64-bit safety
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = ctypes.c_void_p
user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
user32.SetForegroundWindow.restype = ctypes.c_bool
user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
user32.GetWindowThreadProcessId.restype = ctypes.c_uint32
user32.GetDesktopWindow.argtypes = []
user32.GetDesktopWindow.restype = ctypes.c_void_p
user32.GetShellWindow.argtypes = []
user32.GetShellWindow.restype = ctypes.c_void_p
user32.BringWindowToTop.argtypes = [ctypes.c_void_p]
user32.BringWindowToTop.restype = ctypes.c_bool

# Hook callback signature (64-bit compatible)
HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_int64, ctypes.c_int, ctypes.c_uint64, ctypes.c_uint64)

# Configure ctypes signatures for 64-bit safety
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.c_void_p, ctypes.c_uint32]
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.UnhookWindowsHookEx.restype = ctypes.c_bool
user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint64, ctypes.c_uint64]
user32.CallNextHookEx.restype = ctypes.c_int64
user32.GetKeyState.argtypes = [ctypes.c_int]
user32.GetKeyState.restype = ctypes.c_int16
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = ctypes.c_uint32

# Most common Revit element classes and categories shown in context rules by default
COMMON_REVIT_CLASSES = {
    "Wall", "Walls", "Floor", "Floors", "Roof", "Roofs", "Ceiling", "Ceilings",
    "Door", "Doors", "Window", "Windows", "FamilyInstance",
    "Pipe", "Pipes", "Duct", "Ducts", "Conduit", "Conduits", "Cable Tray", "Cable Trays",
    "Dimension", "Dimensions", "TextNote", "Text Notes", "Grid", "Grids", "Level", "Levels",
    "View", "Views", "Sheet", "Sheets",
    "Mechanical Equipment", "Electrical Equipment", "Lighting Fixtures", "Plumbing Fixtures",
    "Structural Framing", "Structural Columns", "Stairs", "Railings",
    "Area", "Areas", "Room", "Rooms", "Zone", "Zones", "Sprinkler", "Sprinklers"
}

# Debug Logger Setup
LOG_FILE = os.path.join(os.path.dirname(__file__), "RadialMenu_debug.log")
_ENABLE_LOGGING = True
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "radial_menu_config.json")

# Default command pool - flat list with context rules per command
DEFAULT_POOL = [
    # Level 1 commands
    {"id": "zoom_fit", "type": "built_in", "name": "Zoom Fit", "command": "zoom", "icon": u"\U0001F50D", "level": 1, "parent": None, "priority": 10, "context_rules": {}},
    {"id": "close_inact", "type": "built_in", "name": "Close Inact.", "command": "close_hidden", "icon": u"\u274C", "level": 1, "parent": None, "priority": 20, "context_rules": {}},
    {"id": "submenu1", "type": "built_in", "name": "Menu 1", "command": "submenu1", "icon": u"\u25B6", "level": 1, "parent": None, "priority": 30, "context_rules": {}},
    {"id": "save_model", "type": "built_in", "name": "Save Model", "command": "save", "icon": u"\U0001F4BE", "level": 1, "parent": None, "priority": 40, "context_rules": {}},
    {"id": "3d_view", "type": "built_in", "name": "3D View", "command": "3d", "icon": u"\U0001F3E0", "level": 1, "parent": None, "priority": 50, "context_rules": {}},
    {"id": "reveal", "type": "built_in", "name": "Reveal", "command": "reveal", "icon": u"\U0001F4A1", "level": 1, "parent": None, "priority": 60, "context_rules": {}},
    {"id": "thin_lines", "type": "built_in", "name": "Thin Lines", "command": "thin_lines", "icon": u"\u2796", "level": 1, "parent": None, "priority": 70, "context_rules": {}},
    {"id": "detail_lvl", "type": "built_in", "name": "Detail Lvl", "command": "detail_level", "icon": u"\U0001F9F1", "level": 1, "parent": None, "priority": 80, "context_rules": {}},

    # Level 2 commands (children of submenu1)
    {"id": "sub_zoom", "type": "built_in", "name": "Sub-Zoom", "command": "zoom", "icon": u"\U0001F50D", "level": 2, "parent": "submenu1", "priority": 10, "context_rules": {}},
    {"id": "sub_save", "type": "built_in", "name": "Sub-Save", "command": "save", "icon": u"\U0001F4BE", "level": 2, "parent": "submenu1", "priority": 20, "context_rules": {}},
    {"id": "sub_3d", "type": "built_in", "name": "Sub-3D", "command": "3d", "icon": u"\U0001F3E0", "level": 2, "parent": "submenu1", "priority": 30, "context_rules": {}},
    {"id": "submenu2", "type": "built_in", "name": "Menu 2", "command": "submenu2", "icon": u"\u25B6", "level": 2, "parent": "submenu1", "priority": 40, "context_rules": {}},
    {"id": "sub_thin", "type": "built_in", "name": "Sub-Thin", "command": "thin_lines", "icon": u"\u2796", "level": 2, "parent": "submenu1", "priority": 50, "context_rules": {}},

    # Level 3 commands (children of submenu2)
    {"id": "sub2_reveal", "type": "built_in", "name": "Sub2-Reveal", "command": "reveal", "icon": u"\U0001F4A1", "level": 3, "parent": "submenu2", "priority": 10, "context_rules": {}},
    {"id": "sub2_detail", "type": "built_in", "name": "Sub2-Detail", "command": "detail_level", "icon": u"\U0001F9F1", "level": 3, "parent": "submenu2", "priority": 20, "context_rules": {}},
    {"id": "sub2_zoom", "type": "built_in", "name": "Sub2-Zoom", "command": "zoom", "icon": u"\U0001F50D", "level": 3, "parent": "submenu2", "priority": 30, "context_rules": {}}
]

# Legacy DEFAULT_CONFIG for backward compatibility during migration
DEFAULT_CONFIG = [
    {"slot": 1, "type": "built_in", "name": "Zoom Fit", "command": "zoom", "icon": u"\U0001F50D"},
    {"slot": 2, "type": "built_in", "name": "Close Inact.", "command": "close_hidden", "icon": u"\u274C"},
    {"slot": 3, "type": "built_in", "name": "Menu 1", "command": "submenu1", "icon": u"\u25B6"},
    {"slot": 4, "type": "built_in", "name": "Save Model", "command": "save", "icon": u"\U0001F4BE"},
    {"slot": 5, "type": "built_in", "name": "3D View", "command": "3d", "icon": u"\U0001F3E0"},
    {"slot": 6, "type": "built_in", "name": "Reveal", "command": "reveal", "icon": u"\U0001F4A1"},
    {"slot": 7, "type": "built_in", "name": "Thin Lines", "command": "thin_lines", "icon": u"\u2796"},
    {"slot": 8, "type": "built_in", "name": "Detail Lvl", "command": "detail_level", "icon": u"\U0001F9F1"},
    {"slot": 11, "type": "built_in", "name": "Sub-Zoom", "command": "zoom", "icon": u"\U0001F50D"},
    {"slot": 12, "type": "built_in", "name": "Sub-Save", "command": "save", "icon": u"\U0001F4BE"},
    {"slot": 13, "type": "built_in", "name": "Sub-3D", "command": "3d", "icon": u"\U0001F3E0"},
    {"slot": 14, "type": "built_in", "name": "Menu 2", "command": "submenu2", "icon": u"\u25B6"},
    {"slot": 15, "type": "built_in", "name": "Sub-Thin", "command": "thin_lines", "icon": u"\u2796"},
    {"slot": 21, "type": "built_in", "name": "Sub2-Reveal", "command": "reveal", "icon": u"\U0001F4A1"},
    {"slot": 22, "type": "built_in", "name": "Sub2-Detail", "command": "detail_level", "icon": u"\U0001F9F1"},
    {"slot": 23, "type": "built_in", "name": "Sub2-Zoom", "command": "zoom", "icon": u"\U0001F50D"}
]

SLOT_BUTTONS = {}
for i in range(1, 11):
    SLOT_BUTTONS[i] = "BtnL1_" + str(i)
for i in range(11, 21):
    SLOT_BUTTONS[i] = "BtnL2_" + str(i - 10)
for i in range(21, 31):
    SLOT_BUTTONS[i] = "BtnL3_" + str(i - 20)

BUTTON_SLOTS = {name: slot for slot, name in SLOT_BUTTONS.items()}

def safe_str(ex):
    if ex is None:
        return u""
    try:
        if hasattr(ex, "Message") and ex.Message:
            return unicode(ex.Message)
        return unicode(ex)
    except:
        try:
            return str(ex).decode("utf-8", "ignore")
        except:
            return u"An error occurred"

def safe_traceback():
    try:
        import traceback
        tb = traceback.format_exc()
        if isinstance(tb, str):
            return tb.decode("utf-8", "ignore")
        return unicode(tb)
    except:
        return u"Failed to format traceback"

def get_id_value(el_id):
    if el_id is None:
        return None
    try:
        if hasattr(el_id, "Value"):
            return int(el_id.Value)
        return el_id.IntegerValue
    except:
        return None

def clear_log_file():
    """Clear or truncate the debug log file."""
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "wb") as f:
                f.write(u"[{}] Log cleared.\n".format(time.strftime("%H:%M:%S")).encode("utf-8"))
    except:
        pass

def log_debug(msg):
    if not _ENABLE_LOGGING:
        return
    try:
        # Limit log size to 512 KB to prevent log bloat
        MAX_LOG_SIZE = 512 * 1024
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_SIZE:
            try:
                backup = LOG_FILE + ".bak"
                if os.path.exists(backup):
                    os.remove(backup)
                os.rename(LOG_FILE, backup)
            except:
                try:
                    with open(LOG_FILE, "wb") as f:
                        f.write(u"[Log truncated due to size limit]\n".encode("utf-8"))
                except:
                    pass
    except:
        pass
        
    try:
        if isinstance(msg, str):
            msg = msg.decode("utf-8", "ignore")
        elif not isinstance(msg, unicode):
            msg = unicode(msg)
            
        with open(LOG_FILE, "a") as f:
            line = u"[{}] {}\n".format(time.strftime("%H:%M:%S"), msg)
            f.write(line.encode("utf-8"))
    except:
        pass

DEFAULT_SETTINGS = {
    "hold_delay_ms": 200,
    "trigger_mode": "hold",
    "enable_gestures": True,
    "gesture_threshold": 35,
    "use_circles": False,
    "animation_style": "fade",
    "enable_logging": False,
    "gap_width": 3.0,
    "core_radius": 45,
    "petal_width": 60,
    "ring_gap": 5,
    "theme": "pyRevit Dark",
    "color_scheme": "auto",
    "color_normal": "#F21E1E24",
    "color_hover_start": "#FF0083B0",
    "color_hover_end": "#FF004B66",
    "color_border": "#25FFFFFF",
    "l2_max_angle": 90,
    "l3_max_angle": 90,
    "petal_opacity": 95
}

def apply_opacity_to_hex_color(hex_color, opacity_percent):
    try:
        hex_color = hex_color.strip()
        if hex_color.startswith("#"):
            hex_color = hex_color[1:]
            
        if len(hex_color) == 6:
            r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
        elif len(hex_color) == 8:
            r, g, b = hex_color[2:4], hex_color[4:6], hex_color[6:8]
        else:
            return "#" + hex_color
            
        alpha_val = int(round((opacity_percent / 100.0) * 255.0))
        alpha_val = max(0, min(255, alpha_val))
        alpha_hex = "{:02X}".format(alpha_val)
        
        return "#" + alpha_hex + r + g + b
    except:
        return hex_color


THEMES = {
    "pyRevit Dark": {
        "color_normal": "#F21E1E24",
        "color_hover_start": "#FF0083B0",
        "color_hover_end": "#FF004B66",
        "color_border": "#25FFFFFF"
    },
    "Neon Fusion": {
        "color_normal": "#F21F1F24",
        "color_hover_start": "#FFFF4E50",
        "color_hover_end": "#FFF9D423",
        "color_border": "#35FFFFFF"
    },
    "Classic Blue": {
        "color_normal": "#F21C263B",
        "color_hover_start": "#FF0088CC",
        "color_hover_end": "#FF0044AA",
        "color_border": "#30FFFFFF"
    },
    "Forest Green": {
        "color_normal": "#F2192B1D",
        "color_hover_start": "#FF0F7050",
        "color_hover_end": "#FF1B4D22",
        "color_border": "#25FFFFFF"
    },
    "Cyberpunk": {
        "color_normal": "#F225122B",
        "color_hover_start": "#FFC51083",
        "color_hover_end": "#FF5F1BBF",
        "color_border": "#35FFFFFF"
    }
}

def parse_hex_color(hex_str, fallback):
    try:
        hex_str = hex_str.strip()
        if not hex_str.startswith("#"):
            hex_str = "#" + hex_str
        if len(hex_str) in [7, 9]:
            from System.Windows.Media import ColorConverter
            ColorConverter.ConvertFromString(hex_str)
            return hex_str
    except:
        pass
    return fallback

def get_luminance(hex_str):
    try:
        cleaned = hex_str.strip().replace("#", "")
        if len(cleaned) == 8:
            r = int(cleaned[2:4], 16)
            g = int(cleaned[4:6], 16)
            b = int(cleaned[6:8], 16)
        elif len(cleaned) == 6:
            r = int(cleaned[0:2], 16)
            g = int(cleaned[2:4], 16)
            b = int(cleaned[4:6], 16)
        else:
            return 0.0
        
        r_lin = r / 255.0
        g_lin = g / 255.0
        b_lin = b / 255.0
        
        r_lin = r_lin / 12.92 if r_lin <= 0.03928 else ((r_lin + 0.055) / 1.055) ** 2.4
        g_lin = g_lin / 12.92 if g_lin <= 0.03928 else ((g_lin + 0.055) / 1.055) ** 2.4
        b_lin = b_lin / 12.92 if b_lin <= 0.03928 else ((b_lin + 0.055) / 1.055) ** 2.4
        
        return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin
    except:
        return 0.0

def get_contrast_foreground(hex_str):
    lum = get_luminance(hex_str)
    if lum > 0.45:
        return "#1E1E24"
    else:
        return "#FFFFFF"

def get_revit_theme_colors():
    try:
        from Autodesk.Revit.UI import UIThemeManager, UITheme
        is_dark = (UIThemeManager.CurrentTheme == UITheme.Dark)
    except:
        is_dark = False
        
    if is_dark:
        return {
            "color_normal": "#F22B2B2B",
            "color_hover_start": "#FF2B5E8C",
            "color_hover_end": "#FF1D3A56",
            "color_border": "#40FFFFFF"
        }
    else:
        return {
            "color_normal": "#F2F0F0F0",
            "color_hover_start": "#FF4A90E2",
            "color_hover_end": "#FF1D3A56",
            "color_border": "#20000000"
        }

def resolve_themed_icon(icon_path):
    if not icon_path:
        return icon_path
    global _IS_MENU_DARK
    base, ext = os.path.splitext(icon_path)
    if ext.lower() == ".png":
        if _IS_MENU_DARK:
            if not base.endswith(".dark"):
                dark_path = base + ".dark" + ext
                if os.path.exists(dark_path):
                    return dark_path
        else:
            if base.endswith(".dark"):
                light_path = base[:-5] + ext
                if os.path.exists(light_path):
                    return light_path
    return icon_path

_bitmap_image_cache = {}

def load_bitmap_image_themed(img_path):
    if not img_path:
        return None
    global _bitmap_image_cache
    if img_path in _bitmap_image_cache:
        return _bitmap_image_cache[img_path]
    try:
        abs_path = img_path
        if not os.path.isabs(abs_path):
            abs_path = os.path.join(os.path.dirname(__file__), abs_path)
            
        if not os.path.exists(abs_path):
            return None
            
        # Verify file size is not zero to prevent decoder crashes
        if os.path.getsize(abs_path) == 0:
            log_debug(u"Warning: icon file is empty (0 bytes): {}".format(abs_path))
            return None
            
        from System.Windows.Media.Imaging import BitmapImage, BitmapCacheOption, BitmapCreateOptions
        from System import Uri
        
        bi = BitmapImage()
        bi.BeginInit()
        bi.UriSource = Uri(abs_path)
        bi.CacheOption = BitmapCacheOption.OnLoad
        bi.CreateOptions = getattr(BitmapCreateOptions, "None")
        bi.EndInit()
        
        try:
            bi.Freeze()
        except:
            pass
            
        _bitmap_image_cache[img_path] = bi
        return bi
    except:
        return None

def clean_id_part(name):
    import re
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '', name)
    return cleaned.lower()

def suggest_emoji_by_name(name):
    if not name:
        return u""
    name_lower = name.lower()
    mapping = {
        "wall": u"🧱", "стена": u"🧱",
        "door": u"🚪", "дверь": u"🚪",
        "window": u"🪟", "окно": u"🪟",
        "line": u"✏️", "линия": u"✏️",
        "3d": u"🏠",
        "save": u"💾", "сохранить": u"💾",
        "zoom": u"🔍", "зум": u"🔍",
        "dimension": u"📏", "размер": u"📏",
        "delete": u"❌", "удалить": u"❌",
        "sync": u"🔄", "синхр": u"🔄",
        "text": u"🔤", "текст": u"🔤",
        "floor": u"🥞", "перекрытие": u"🥞",
        "roof": u"🏠", "крыша": u"🏠",
        "pipe": u"🧪", "труба": u"🧪",
        "duct": u"💨", "воздуховод": u"💨",
        "align": u"📏", "выравнивание": u"📏"
    }
    for k, v in mapping.items():
        if k in name_lower:
            return v
    return u"⚙️"

BUILTIN_MAPS = {
    "wall": ("PlaceAWall", "ID_OBJECTS_WALL"),
    "стена": ("PlaceAWall", "ID_OBJECTS_WALL"),
    "placeawall": ("PlaceAWall", "ID_OBJECTS_WALL"),
    "id_objects_wall": ("ID_OBJECTS_WALL", "ID_OBJECTS_WALL"),
    
    "door": ("PlaceADoor", "ID_OBJECTS_DOOR"),
    "дверь": ("PlaceADoor", "ID_OBJECTS_DOOR"),
    "placeadoor": ("PlaceADoor", "ID_OBJECTS_DOOR"),
    "id_objects_door": ("ID_OBJECTS_DOOR", "ID_OBJECTS_DOOR"),
    
    "window": ("PlaceAWindow", "ID_OBJECTS_WINDOW"),
    "окно": ("PlaceAWindow", "ID_OBJECTS_WINDOW"),
    "placeawindow": ("PlaceAWindow", "ID_OBJECTS_WINDOW"),
    "id_objects_window": ("ID_OBJECTS_WINDOW", "ID_OBJECTS_WINDOW"),
    
    "pipe": ("Pipe", "ID_RBS_PIPE_PIPE"),
    "труба": ("Pipe", "ID_RBS_PIPE_PIPE"),
    "placeapipe": ("Pipe", "ID_RBS_PIPE_PIPE"),
    "id_rbs_pipe_pipe": ("ID_RBS_PIPE_PIPE", "ID_RBS_PIPE_PIPE"),
    
    "duct": ("Duct", "ID_RBS_DUCT_DUCT"),
    "воздуховод": ("Duct", "ID_RBS_DUCT_DUCT"),
    "placeaduct": ("Duct", "ID_RBS_DUCT_DUCT"),
    "id_rbs_duct_duct": ("ID_RBS_DUCT_DUCT", "ID_RBS_DUCT_DUCT"),
    
    "line": ("PlaceDetailLine", "ID_OBJECTS_DETAIL_CURVES"),
    "линия": ("PlaceDetailLine", "ID_OBJECTS_DETAIL_CURVES"),
    "placedetailline": ("PlaceDetailLine", "ID_OBJECTS_DETAIL_CURVES"),
    "id_objects_detail_curves": ("ID_OBJECTS_DETAIL_CURVES", "ID_OBJECTS_DETAIL_CURVES"),
    
    "dimension": ("AlignedDimension", "ID_ANNOTATIONS_DIMENSION_ALIGNED"),
    "размер": ("AlignedDimension", "ID_ANNOTATIONS_DIMENSION_ALIGNED"),
    "aligneddimension": ("AlignedDimension", "ID_ANNOTATIONS_DIMENSION_ALIGNED"),
    "placealigneddimension": ("AlignedDimension", "ID_ANNOTATIONS_DIMENSION_ALIGNED"),
    "id_annotations_dimension_aligned": ("ID_ANNOTATIONS_DIMENSION_ALIGNED", "ID_ANNOTATIONS_DIMENSION_ALIGNED"),
    
    "3d": ("ID_VIEW_DEFAULT_3DVIEW", "ID_VIEW_DEFAULT_3DVIEW"),
    "3d view": ("ID_VIEW_DEFAULT_3DVIEW", "ID_VIEW_DEFAULT_3DVIEW"),
    "id_view_default_3dview": ("ID_VIEW_DEFAULT_3DVIEW", "ID_VIEW_DEFAULT_3DVIEW"),
    
    "save": ("Save", "ID_FILE_SAVE"),
    "сохранить": ("Save", "ID_FILE_SAVE"),
    "id_file_save": ("ID_FILE_SAVE", "ID_FILE_SAVE"),
}

def resolve_builtin_command(cmd_value):
    if not cmd_value:
        return None, None
        
    cmd_lower = cmd_value.strip().lower()
    
    # 1. Exact match in BUILTIN_MAPS
    if cmd_lower in BUILTIN_MAPS:
        return BUILTIN_MAPS[cmd_lower]
        
    # 2. Check if cmd_value itself is a valid file name in extracted_icons
    safe_cmd = "".join([c for c in cmd_value if c.isalnum() or c in ("_", "-")]).strip()
    icons_dir = os.path.join(os.path.dirname(__file__), "extracted_icons")
    local_png = os.path.join(icons_dir, safe_cmd + ".png")
    if os.path.exists(local_png):
        return cmd_value, safe_cmd
        
    # Try case-insensitive file lookup in extracted_icons
    if os.path.exists(icons_dir):
        try:
            files = os.listdir(icons_dir)
            files_lower = {f.lower(): f for f in files}
            target_file_lower = (safe_cmd + ".png").lower()
            if target_file_lower in files_lower:
                matched_filename = files_lower[target_file_lower]
                matched_name_without_ext = os.path.splitext(matched_filename)[0]
                return cmd_value, matched_name_without_ext
        except:
            pass
            
    # 3. Case-insensitive PostableCommand check
    try:
        from Autodesk.Revit.UI import PostableCommand
        for name in dir(PostableCommand):
            if name.lower() == cmd_lower:
                matched_icon = None
                if os.path.exists(icons_dir):
                    for filename in os.listdir(icons_dir):
                        filename_no_ext = os.path.splitext(filename)[0]
                        if cmd_lower in filename_no_ext.lower() or filename_no_ext.lower() in cmd_lower:
                            matched_icon = filename_no_ext
                            break
                return name, matched_icon or safe_cmd
    except:
        pass
            
    return cmd_value, safe_cmd

def extract_icons_from_ribbon(force_overwrite=False):
    try:
        import os
        clr.AddReference("AdWindows")
        import Autodesk.Windows as adWin
        from System.Windows.Media.Imaging import PngBitmapEncoder, BitmapFrame
        import System.IO
        
        icons_dir = os.path.join(os.path.dirname(__file__), "extracted_icons")
        if not os.path.exists(icons_dir):
            os.makedirs(icons_dir)
            
        saved_count = [0]
        skipped_count = [0]
        failed_count = [0]
        
        def save_img(img, item_id):
            if not img or not item_id:
                return
            safe_filename = "".join([c for c in item_id if c.isalnum() or c in ("_", "-")]).strip()
            if not safe_filename:
                return
                
            global _IS_REVIT_DARK
            suffix = ".dark.png" if _IS_REVIT_DARK else ".png"
            file_path = os.path.join(icons_dir, safe_filename + suffix)
            
            if not force_overwrite and os.path.exists(file_path):
                skipped_count[0] += 1
                return
                
            try:
                encoder = PngBitmapEncoder()
                encoder.Frames.Add(BitmapFrame.Create(img))
                with System.IO.FileStream(file_path, System.IO.FileMode.Create, System.IO.FileAccess.Write, getattr(System.IO.FileShare, "None")) as fs:
                    encoder.Save(fs)
                saved_count[0] += 1
            except Exception as e_save:
                failed_count[0] += 1
                
        def process_item(item):
            if not item:
                return
            if hasattr(item, "Id") and item.Id:
                if hasattr(item, "LargeImage") and item.LargeImage:
                    save_img(item.LargeImage, item.Id)
                elif hasattr(item, "Image") and item.Image:
                    save_img(item.Image, item.Id)
            if hasattr(item, "Items") and item.Items:
                for sub_item in item.Items:
                    process_item(sub_item)
                    
        log_debug("Starting ribbon icon extraction...")
        ribbon_ctrl = adWin.ComponentManager.Ribbon
        if ribbon_ctrl:
            tab_count = len(ribbon_ctrl.Tabs)
            log_debug("Found RibbonControl with {} tabs.".format(tab_count))
            for tab in ribbon_ctrl.Tabs:
                if tab.Panels:
                    for panel in tab.Panels:
                        if panel.Source and panel.Source.Items:
                            for item in panel.Source.Items:
                                process_item(item)
            log_debug("Ribbon icon extraction finished. Extracted: {}, Skipped (already exist): {}, Failed: {}.".format(
                saved_count[0], skipped_count[0], failed_count[0]
            ))
        else:
            log_debug("RibbonControl not found in ComponentManager.")
    except Exception as ex:
        log_debug("Error extracting ribbon icons: " + str(ex))


_THEME_ICONS_CHECKED = {}

def check_and_suggest_icon_extraction(window):
    try:
        from Autodesk.Revit.UI import UIThemeManager, UITheme
        is_dark = False
        try:
            is_dark = (UIThemeManager.CurrentTheme == UITheme.Dark)
        except:
            pass
        theme_key = "dark" if is_dark else "light"
        
        global _THEME_ICONS_CHECKED
        if _THEME_ICONS_CHECKED.get(theme_key):
            return
            
        _THEME_ICONS_CHECKED[theme_key] = True
        
        import os
        icons_dir = os.path.join(os.path.dirname(__file__), "extracted_icons")
        has_icons = False
        if os.path.exists(icons_dir):
            if is_dark:
                theme_files = [f for f in os.listdir(icons_dir) if f.lower().endswith(".dark.png")]
            else:
                theme_files = [f for f in os.listdir(icons_dir) if f.lower().endswith(".png") and not f.lower().endswith(".dark.png")]
            
            if len(theme_files) >= 10:
                has_icons = True
                
        if not has_icons:
            from System.Windows import MessageBox, MessageBoxButton, MessageBoxImage
            msg = u"Revit Ribbon icons for the active theme ({}) have not been extracted yet.\nExtract them now? (Required for customizer icons)".format(theme_key.upper())
            res = MessageBox.Show(window, msg, "Extract Icons", MessageBoxButton.YesNo, MessageBoxImage.Question)
            if res.ToString() == "Yes":
                from System.Windows.Input import Cursors, Mouse
                Mouse.OverrideCursor = Cursors.Wait
                try:
                    extract_icons_from_ribbon(force_overwrite=True)
                    MessageBox.Show(window, "Icons extracted successfully!", "Success", MessageBoxButton.OK, MessageBoxImage.Information)
                except Exception as ex_ext:
                    log_debug("Failed to extract icons: " + str(ex_ext))
                finally:
                    Mouse.OverrideCursor = None
    except Exception as ex:
        log_debug("Error checking or extracting icons: " + str(ex))


def migrate_old_config(data):
    """Migrate old context-based config to new pool-based format."""
    try:
        pool = []
        seen_commands = set()
        
        # Get default context as primary source
        contexts = data.get("contexts", {})
        primary_config = contexts.get("default", [])
        if not primary_config:
            for ctx_name, ctx_config in contexts.items():
                if ctx_config:
                    primary_config = ctx_config
                    break
        
        if not primary_config:
            return list(DEFAULT_POOL)
        
        # Build pool from old slot-based config
        for item in primary_config:
            slot = item.get("slot", 0)
            cmd = item.get("command", "empty")
            if cmd == "empty":
                continue
                
            # Determine level from slot number
            if 1 <= slot <= 10:
                level = 1
                parent = None
            elif 11 <= slot <= 20:
                level = 2
                parent = "submenu1"
            elif 21 <= slot <= 30:
                level = 3
                parent = "submenu2"
            else:
                continue
            
            # Generate unique id
            cmd_id = clean_id_part(item.get("name", cmd))
            if cmd_id in seen_commands:
                cmd_id = "{}_{}".format(cmd_id, slot)
            seen_commands.add(cmd_id)
            
            # Migrate old context_rules if present
            context_rules = item.get("context_rules", {})
            
            pool_item = {
                "id": cmd_id,
                "type": item.get("type", "built_in"),
                "name": item.get("name", cmd),
                "command": cmd,
                "icon": item.get("icon", ""),
                "level": level,
                "parent": parent,
                "priority": slot * 10,
                "context_rules": context_rules
            }
            pool.append(pool_item)
        
        if not pool:
            return list(DEFAULT_POOL)
        
        log_debug(u"Migrated {} commands from old config to pool format.".format(len(pool)))
        return pool
    except Exception as ex:
        log_debug(u"Error in migrate_old_config: {}".format(safe_str(ex)))
        return list(DEFAULT_POOL)

def load_config():
    global _ENABLE_LOGGING
    default_structure = {
        "settings": dict(DEFAULT_SETTINGS),
        "command_pool": list(DEFAULT_POOL)
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "rb") as f:
                content = f.read().decode("utf-8")
                data = json.loads(content)
                
                # Check if old flat array format
                if isinstance(data, list):
                    log_debug(u"Migrating old flat config to new pool format.")
                    new_data = dict(default_structure)
                    new_data["command_pool"] = migrate_old_config({"contexts": {"default": data}})
                    save_config(new_data)
                    return new_data
                
                if not isinstance(data, dict):
                    return default_structure
                
                # Detect old context-based format and migrate
                if "contexts" in data and "command_pool" not in data:
                    log_debug(u"Migrating old context-based config to pool format.")
                    new_data = {
                        "settings": data.get("settings", dict(DEFAULT_SETTINGS)),
                        "command_pool": migrate_old_config(data)
                    }
                    # Migrate old settings: replace l1/l2/l3_count with max_angle
                    settings = new_data["settings"]
                    if "l1_count" in settings:
                        del settings["l1_count"]
                    if "l2_count" in settings:
                        del settings["l2_count"]
                    if "l3_count" in settings:
                        del settings["l3_count"]
                    for k, v in DEFAULT_SETTINGS.items():
                        if k not in settings:
                            settings[k] = v
                    save_config(new_data)
                    return new_data
                
                # New format - verify and merge defaults
                if "settings" not in data or not isinstance(data["settings"], dict):
                    data["settings"] = dict(DEFAULT_SETTINGS)
                else:
                    for k, v in DEFAULT_SETTINGS.items():
                        if k not in data["settings"]:
                            data["settings"][k] = v
                
                if "command_pool" not in data or not isinstance(data["command_pool"], list):
                    data["command_pool"] = list(DEFAULT_POOL)
                else:
                    # Automatically clean any legacy stack/slideout naming issues from config
                    config_changed = False
                    for item in data["command_pool"]:
                        if item.get("type") == "pyrevit" and item.get("command"):
                            cmd_val = item["command"]
                            parts = cmd_val.split("_")
                            cleaned_parts = [p for p in parts if "stack" not in p.lower() and "slideout" not in p.lower()]
                            cleaned_val = "_".join(cleaned_parts)
                            if cleaned_val != cmd_val:
                                log_debug(u"Auto-migrated config command ID from '{}' to '{}'".format(cmd_val, cleaned_val))
                                item["command"] = cleaned_val
                                config_changed = True
                                # Update ID too if it matches command
                                if item.get("id") == cmd_val:
                                    item["id"] = cleaned_val
                    if config_changed:
                        save_config(data)
                
                _ENABLE_LOGGING = data.get("settings", {}).get("enable_logging", False)
                return data
    except Exception as ex:
        log_debug(u"Failed to load config: {}".format(safe_str(ex)))
    _ENABLE_LOGGING = default_structure.get("settings", {}).get("enable_logging", False)
    return default_structure

def save_config(config_data):
    try:
        global _ENABLE_LOGGING
        _ENABLE_LOGGING = config_data.get("settings", {}).get("enable_logging", False)
        content = json.dumps(config_data, indent=4)
        with open(CONFIG_FILE, "wb") as f:
            f.write(content.encode("utf-8"))
        log_debug(u"Configuration saved successfully.")
    except Exception as ex:
        log_debug(u"Failed to save config: {}".format(safe_str(ex)))

class POINT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_int32),
        ("y", ctypes.c_int32)
    ]

class MOUSEHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("hwnd", ctypes.c_uint64),
        ("wHitTestCode", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_uint64)
    ]

# Globals to persist between callback cycles
_hook_id = None
_hook_proc = None
_rbutton_down_x = 0
_rbutton_down_y = 0
_is_holding = False
_menu_opened_by_hold = False
_active_window = None
_window_lock = threading.Lock()

def get_persistence():
    try:
        import System
        p = System.AppDomain.CurrentDomain.GetData("RevitRadialMenuPersistence")
        if not p:
            from System.Collections.Generic import Dictionary
            p = Dictionary[str, object]()
            System.AppDomain.CurrentDomain.SetData("RevitRadialMenuPersistence", p)
        return p
    except:
        return None

def get_active_window():
    global _active_window
    with _window_lock:
        if _active_window is not None:
            return _active_window
    try:
        p = get_persistence()
        if p and p.ContainsKey("active_window"):
            return p["active_window"]
    except:
        pass
    return None

def set_active_window(win):
    global _active_window
    with _window_lock:
        _active_window = win
    try:
        p = get_persistence()
        if p:
            p["active_window"] = win
    except:
        pass

_ui_dispatcher = None
_hold_delay_ms = 400
_trigger_mode = "hold"
_last_rbutton_down_time = 0.0
_last_rbutton_down_x = 0
_last_rbutton_down_y = 0
_menu_opened_by_double_click = False
_selection_before_click = None
_cached_commands = None
_cached_commands_lock = threading.Lock()

def get_statusbar_text():
    try:
        from pyrevit.revit import ui
        import ctypes
        hwnd = ui.get_statusbar_hwnd()
        if hwnd:
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                return buf.value
    except Exception as ex:
        log_debug("Failed to read status bar text: " + str(ex))
    return ""

def is_element_prehighlighted():
    text = get_statusbar_text()
    if not text:
        return False
    text_lower = text.lower()
    idle_prompts = [
        "ready",
        "готово",
        "click to select",
        "для выбора",
        "нажмите"
    ]
    for prompt in idle_prompts:
        if prompt in text_lower:
            return False
    if len(text.strip()) < 3:
        return False
    return True

def get_hovered_category():
    text = get_statusbar_text()
    if not text:
        return None
    text_lower = text.lower()
    idle_prompts = [
        "ready",
        "готово",
        "click to select",
        "для выбора",
        "нажмите"
    ]
    for prompt in idle_prompts:
        if prompt in text_lower:
            return None
    parts = text.split(":")
    if parts:
        cat_name = parts[0].strip()
        if len(cat_name) > 1:
            return cat_name
    return None

def get_current_selection_state():
    try:
        uiapp = HOST_APP.uiapp
        if uiapp and uiapp.ActiveUIDocument:
            sel_ids = list(uiapp.ActiveUIDocument.Selection.GetElementIds())
            if sel_ids and len(sel_ids) > 0:
                return "Selection"
    except:
        pass
    if is_element_prehighlighted():
        return "Pre-highlighted"
    return "None"

# Thread safety lock and identifier counter for hold detection
_hold_lock = threading.Lock()
_hold_id_counter = 0
_enable_gestures = True
_gesture_threshold = 35.0
_gesture_flick_detected = False
_gesture_target_item = None

def resolve_gesture_command_at_point(start_x, start_y, curr_x, curr_y):
    try:
        import math
        dx = float(curr_x - start_x)
        dy = float(curr_y - start_y)
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 25.0:
            return None
            
        # Screen angle: 0=East, 90=South, 180=West, 270=North
        mouse_angle = (math.degrees(math.atan2(dy, dx)) + 360.0) % 360.0
        
        # 1. Try active window's filtered items if window exists
        active_win = get_active_window()
        l1_items = []
        if active_win and hasattr(active_win, "_level_items"):
            l1_items = active_win._level_items.get(1, [])
            
        # 2. If no active window or empty, load matching layout for current Revit context
        if not l1_items:
            cfg = load_config()
            pool = cfg.get("command_pool", list(DEFAULT_POOL))
            view_cat = "Plan"
            try:
                uiapp = HOST_APP.uiapp
                if uiapp and uiapp.ActiveUIDocument and uiapp.ActiveUIDocument.ActiveView:
                    from Autodesk.Revit.DB import ViewType
                    vt = uiapp.ActiveUIDocument.ActiveView.ViewType
                    if vt in [ViewType.ThreeD]:
                        view_cat = "3D"
                    elif vt in [ViewType.DrawingSheet]:
                        view_cat = "Sheet"
            except:
                pass
                
            sel_state = get_current_selection_state()
            for item in pool:
                if item.get("level", 1) == 1:
                    rules = item.get("context_rules", {})
                    if rules:
                        av = rules.get("allowed_views", [])
                        if av and view_cat not in av:
                            continue
                        as_states = rules.get("allowed_selection_states", [])
                        if as_states and sel_state not in as_states:
                            continue
                    l1_items.append(item)
                    
        n1 = len(l1_items)
        if n1 == 0:
            return None
            
        span = 360.0 / float(n1)
        # Level 1 items are centered starting with Item 1 at 270 degrees (North / Top)
        rel_angle = (mouse_angle - 270.0 + (span / 2.0)) % 360.0
        idx = int(rel_angle / span)
        if 0 <= idx < n1:
            return l1_items[idx]
    except:
        pass
    return None

def hold_detection_worker(hold_id, start_x, start_y):
    global _is_holding, _menu_opened_by_hold, _hold_delay_ms
    try:
        try:
            log_debug(u"Hold worker thread started for hold_id={}. Delay is {}ms.".format(hold_id, _hold_delay_ms))
        except:
            pass
        
        delay_sec = 0.4
        try:
            delay_sec = float(_hold_delay_ms) / 1000.0
        except:
            pass
        time.sleep(delay_sec)
        
        should_trigger = False
        with _hold_lock:
            if _is_holding and _hold_id_counter == hold_id:
                should_trigger = True
                _menu_opened_by_hold = True
                
        if should_trigger:
            try:
                log_debug(u"Hold threshold met for hold_id={}. Triggering radial menu...".format(hold_id))
            except:
                pass
            trigger_radial_menu(start_x, start_y)
        else:
            try:
                log_debug(u"Hold cancelled or superceded for hold_id={}.".format(hold_id))
            except:
                pass
    except BaseException as ex:
        try:
            log_debug(u"Exception in hold_detection_worker: {}".format(safe_str(ex)))
        except:
            pass

# Modeless Event Handler for Revit API interactions
try:
    clr.AddReference("RevitAPI")
    clr.AddReference("RevitAPIUI")
    from Autodesk.Revit.UI import IExternalEventHandler, ExternalEvent
    
    class RevitEventHandler(IExternalEventHandler):
        def __init__(self):
            self._action = None
            self._args = ()
            self._kwargs = {}
    
        def set_action(self, action, *args, **kwargs):
            self._action = action
            self._args = args
            self._kwargs = kwargs
    
        def Execute(self, uiapp):
            if self._action:
                try:
                    self._action(uiapp, *self._args, **self._kwargs)
                except Exception as ex:
                    log_debug(u"Error in Revit Event Execution (Python Exception): " + safe_str(ex))
                except System.Exception as ex:
                    log_debug(u"Error in Revit Event Execution (CLR Exception): " + safe_str(ex))
                finally:
                    self._action = None
    
        def GetName(self):
            return "Radial Menu Modeless Event Handler"
            
    _event_handler = RevitEventHandler()
    _ext_event = ExternalEvent.Create(_event_handler)
except Exception as ex:
    log_debug(u"CRITICAL: Failed to initialize ExternalEvent / RevitEventHandler: {}".format(safe_str(ex)))
    _event_handler = None
    _ext_event = None

# Revit Commands Execution Logic
def execute_command(uiapp, cmd_type, cmd_value):
    try:
        log_debug(u"Executing command of type '{}': {}".format(cmd_type, cmd_value))
        
        if cmd_type == "built_in":
            uidoc = uiapp.ActiveUIDocument
            doc = uidoc.Document
            from Autodesk.Revit.UI import PostableCommand, RevitCommandId
            from Autodesk.Revit.DB import Transaction, ViewDetailLevel
            
            resolved_cmd, _ = resolve_builtin_command(cmd_value)
            cmd_to_run = resolved_cmd or cmd_value
            
            if cmd_to_run == "zoom":
                active_view = uidoc.ActiveView
                for ui_view in uidoc.GetOpenUIViews():
                    if ui_view.ViewId == active_view.Id:
                        ui_view.ZoomToFit()
                        break
            elif cmd_to_run == "close_hidden":
                cmd_id = None
                for cmd_name in ["CloseInactiveViews", "CloseHiddenWindows"]:
                    if hasattr(PostableCommand, cmd_name):
                        try:
                            cmd_id = RevitCommandId.LookupPostableCommandId(getattr(PostableCommand, cmd_name))
                            break
                        except:
                            pass
                
                if not cmd_id:
                    for name in ["ID_VIEW_CLOSE_INACTIVE", "ID_WINDOW_CLOSE_HIDDEN"]:
                        cmd_id = RevitCommandId.LookupCommandId(name)
                        if cmd_id:
                            log_debug(u"Found Close Inactive command via string ID: {}".format(name))
                            break
                            
                if cmd_id:
                    uiapp.PostCommand(cmd_id)
                else:
                    log_debug(u"No Close Inactive command ID found, falling back to manual open views loop.")
                    for ui_view in uidoc.GetOpenUIViews():
                        if ui_view.ViewId != uidoc.ActiveView.Id:
                            try:
                                ui_view.Close()
                            except Exception as manual_e:
                                log_debug(u"Manual close of view failed: {}".format(safe_str(manual_e)))
            elif cmd_to_run == "sync":
                cmd_id = None
                if hasattr(PostableCommand, "SynchronizeWithCentral"):
                    try:
                        cmd_id = RevitCommandId.LookupPostableCommandId(PostableCommand.SynchronizeWithCentral)
                    except:
                        pass
                
                if not cmd_id:
                    for name in ["ID_FILE_SAVE_TO_CENTRAL_SHORTCUT", "ID_FILE_SAVE_TO_CENTRAL"]:
                        cmd_id = RevitCommandId.LookupCommandId(name)
                        if cmd_id:
                            log_debug(u"Found Sync command via string ID: {}".format(name))
                            break
                            
                if cmd_id:
                    uiapp.PostCommand(cmd_id)
                else:
                    log_debug(u"No Sync command ID found, trying direct document sync if workshared.")
                    if doc.IsWorkshared:
                        from Autodesk.Revit.DB import TransactWithCentralOptions, SynchronizeWithCentralOptions, RelinquishOptions
                        trans_opts = TransactWithCentralOptions()
                        sync_opts = SynchronizeWithCentralOptions()
                        rel_opts = RelinquishOptions(True)
                        sync_opts.SetRelinquishOptions(rel_opts)
                        sync_opts.Comment = "Sync via Radial Menu"
                        doc.SynchronizeWithCentral(trans_opts, sync_opts)
                        log_debug(u"Direct SynchronizeWithCentral completed.")
                    else:
                        log_debug(u"Document is not workshared, cannot sync.")
            elif cmd_to_run == "save":
                cmd_id = RevitCommandId.LookupPostableCommandId(PostableCommand.Save)
                uiapp.PostCommand(cmd_id)
            elif cmd_to_run == "3d":
                cmd_id = RevitCommandId.LookupCommandId("ID_VIEW_DEFAULT_3DVIEW")
                if cmd_id:
                    uiapp.PostCommand(cmd_id)
            elif cmd_to_run == "reveal":
                cmd_id = RevitCommandId.LookupCommandId("ID_VIEW_REVEAL_HIDDEN")
                if cmd_id:
                    uiapp.PostCommand(cmd_id)
                else:
                    log_debug(u"Command ID ID_VIEW_REVEAL_HIDDEN not found.")
            elif cmd_to_run == "thin_lines":
                cmd_id = RevitCommandId.LookupCommandId("ID_VIEW_THIN_LINES")
                if cmd_id:
                    uiapp.PostCommand(cmd_id)
            elif cmd_to_run == "detail_level":
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
                except Exception as dl_ex:
                    log_debug(u"Exception in detail_level command: {}".format(safe_str(dl_ex)))
                    if t.HasStarted() and not t.HasEnded():
                        t.RollBack()
            else:
                cmd_id = None
                try:
                    cmd_id = RevitCommandId.LookupCommandId(cmd_to_run)
                except:
                    pass
                
                if not cmd_id:
                    try:
                        if hasattr(PostableCommand, cmd_to_run):
                            cmd_id = RevitCommandId.LookupPostableCommandId(getattr(PostableCommand, cmd_to_run))
                    except:
                        pass
                
                if cmd_id:
                    uiapp.PostCommand(cmd_id)
                    log_debug(u"Posted Revit built-in command: {}".format(cmd_to_run))
                else:
                    log_debug(u"Could not resolve built-in command ID for: {}".format(cmd_to_run))
                
                
        elif cmd_type == "pyrevit":
            from pyrevit.loader import sessionmgr
            cmd_to_run = cmd_value
            if cmd_value:
                parts = cmd_value.split("_")
                cleaned_parts = [p for p in parts if "stack" not in p.lower() and "slideout" not in p.lower()]
                cleaned_val = "_".join(cleaned_parts)
                if cleaned_val != cmd_value:
                    log_debug(u"Cleaned pyRevit command unique name from '{}' to '{}'".format(cmd_value, cleaned_val))
                    cmd_to_run = cleaned_val
            log_debug(u"Calling sessionmgr.execute_command for {}".format(cmd_to_run))
            sessionmgr.execute_command(cmd_to_run)
            
    except Exception as ex:
        log_debug(u"Exception in execute_command (Python Exception): {}".format(safe_str(ex)))
        forms.toast("Execution error: " + safe_str(ex), title="Radial Menu")
    except System.Exception as ex:
        log_debug(u"Exception in execute_command (CLR Exception): {}".format(safe_str(ex)))
        forms.toast("Execution error: " + safe_str(ex), title="Radial Menu")


class TreeItem(object):
    def __init__(self, name, is_command=False, icon_path=None, unique_id=None, extension=None, is_expanded=False, is_pulldown=False):
        self._name = name
        self._is_command = is_command
        self._icon_path = icon_path
        self._unique_id = unique_id
        self._extension = extension
        self._is_expanded = is_expanded
        self._is_pulldown = is_pulldown
        from System.Collections.ObjectModel import ObservableCollection
        self._children = ObservableCollection[object]()

    @property
    def IsPulldown(self):
        return self._is_pulldown

    @property
    def Name(self):
        return self._name

    @Name.setter
    def Name(self, value):
        self._name = value

    @property
    def IsCommand(self):
        return self._is_command

    @property
    def IconPath(self):
        return self._icon_path

    @property
    def UniqueId(self):
        return self._unique_id

    @property
    def Extension(self):
        return self._extension

    @property
    def IsExpanded(self):
        return self._is_expanded

    @IsExpanded.setter
    def IsExpanded(self, value):
        self._is_expanded = value

    @property
    def Children(self):
        return self._children


def get_bundle_title(dir_path):
    bundle_yaml = os.path.join(dir_path, "bundle.yaml")
    if os.path.exists(bundle_yaml):
        try:
            with open(bundle_yaml, "rb") as f:
                for line in f:
                    line = line.strip().decode("utf-8", "ignore")
                    if line.startswith("title:"):
                        title = line.replace("title:", "").replace("'", "").replace('"', '').strip()
                        if title:
                            return title
        except Exception as e:
            pass
            
    dir_name = os.path.basename(dir_path)
    for suffix in [".extension", ".tab", ".panel", ".pulldown", ".splitbutton", ".pushbutton", ".linkbutton", ".smartbutton", ".urlbutton", ".contentbutton", ".colorbutton", ".togglebutton"]:
        if dir_name.lower().endswith(suffix):
            dir_name = dir_name[:-len(suffix)]
            break
    return dir_name


def parse_cmd_hierarchy(cmd):
    script_path = getattr(cmd, "script", None)
    if not script_path:
        return u"External", u"Commands", None
    
    norm_path = os.path.normpath(script_path)
    parts = norm_path.split(os.path.sep)
    
    # Find where the extension starts
    ext_idx = -1
    for idx, part in enumerate(parts):
        if part.lower().endswith(".extension"):
            ext_idx = idx
            break
    
    if ext_idx != -1:
        ext_path = os.path.sep.join(parts[:ext_idx+1])
        ext_name = get_bundle_title(ext_path)
        
        tab_name = u"Commands"
        pulldown_name = None
        
        tab_idx = -1
        for idx in range(ext_idx + 1, len(parts)):
            if parts[idx].lower().endswith(".tab"):
                tab_idx = idx
                tab_path = os.path.sep.join(parts[:tab_idx+1])
                tab_name = get_bundle_title(tab_path)
                break
                
        if tab_idx != -1:
            for idx in range(tab_idx + 1, len(parts) - 1):
                part_lower = parts[idx].lower()
                if part_lower.endswith(".pulldown") or part_lower.endswith(".splitbutton"):
                    pd_path = os.path.sep.join(parts[:idx+1])
                    pulldown_name = get_bundle_title(pd_path)
                    break
                    
        return ext_name, tab_name, pulldown_name
    else:
        ext_name = getattr(cmd, "extension", None) or u"External"
        return ext_name, u"Commands", None


def get_revit_ribbon_commands():
    cmds = []
    seen_ids = set()
    try:
        import clr
        clr.AddReference("AdWindows")
        import Autodesk.Windows as adWin
        
        ribbon_ctrl = adWin.ComponentManager.Ribbon
        if not ribbon_ctrl:
            return cmds
            
        def process_ribbon_item(item, tab_title, panel_title):
            if not item:
                return
            
            item_id = getattr(item, "Id", None)
            if item_id:
                id_lower = item_id.lower()
                is_valid_prefix = item_id.startswith("ID_") or item_id.startswith("CustomCtrl..")
                is_excluded = (
                    "pyrevit" in id_lower or 
                    "radialmenu" in id_lower or
                    "pyrevit" in tab_title.lower() or
                    "radialmenu" in tab_title.lower() or
                    "pyrevit" in panel_title.lower() or
                    "radialmenu" in panel_title.lower()
                )
                if is_valid_prefix and not is_excluded:
                    if id_lower not in seen_ids:
                        seen_ids.add(id_lower)
                        
                        text = getattr(item, "Text", None) or getattr(item, "Name", None) or item_id
                        if text:
                            text = text.replace("\r\n", " ").replace("\n", " ").strip()
                        
                        cmds.append({
                            "id": item_id,
                            "title": text,
                            "tab": tab_title,
                            "panel": panel_title
                        })
            
            if hasattr(item, "Items") and item.Items:
                for sub_item in item.Items:
                    process_ribbon_item(sub_item, tab_title, panel_title)
                    
        for tab in ribbon_ctrl.Tabs:
            tab_title = getattr(tab, "Title", None) or getattr(tab, "Name", None) or u"Other"
            tab_title = tab_title.strip()
            if not tab_title:
                continue
            
            if tab.Panels:
                for panel in tab.Panels:
                    panel_title = u"Other"
                    if panel.Source:
                        panel_title = getattr(panel.Source, "Title", None) or getattr(panel.Source, "Name", None) or u"Other"
                    panel_title = panel_title.strip()
                    
                    if panel.Source and panel.Source.Items:
                        for item in panel.Source.Items:
                            process_ribbon_item(item, tab_title, panel_title)
    except Exception as ex:
        log_debug(u"Error getting Revit Ribbon structure: {}".format(safe_str(ex)))
    return cmds


def find_all_extension_dirs():
    roots = []
    
    # 1. Get custom user extensions from config
    try:
        appdata = os.environ.get("APPDATA")
        if appdata:
            config_file = os.path.join(appdata, "pyRevit", "pyRevit_config.ini")
            if os.path.exists(config_file):
                with open(config_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("userextensions ="):
                            import json
                            json_str = line.split("=", 1)[1].strip()
                            custom_paths = json.loads(json_str)
                            if isinstance(custom_paths, list):
                                roots.extend(custom_paths)
                            break
    except Exception as e:
        log_debug(u"Failed to parse config file: {}".format(safe_str(e)))
        
    # 2. Get standard ext root dirs
    try:
        from pyrevit import userconfig
        roots.extend(userconfig.get_ext_root_dirs())
    except:
        pass
        
    # 3. Add default extension directory
    try:
        from pyrevit import HOME_DIR
        default_ext_dir = os.path.join(HOME_DIR, "extensions")
        if os.path.exists(default_ext_dir):
            roots.append(default_ext_dir)
    except:
        pass
        
    # 4. Add current extension directory
    try:
        cur_ext_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../../"))
        if os.path.exists(cur_ext_dir):
            roots.append(os.path.dirname(cur_ext_dir))
    except:
        pass
        
    # Unique and normalized roots
    unique_roots = list(set([os.path.normpath(r) for r in roots if r and os.path.exists(r)]))
    log_debug(u"Resolved extension roots for scanning: {}".format(unique_roots))
    
    # Find all *.extension directories
    ext_dirs = []
    for root in unique_roots:
        if root.lower().endswith(".extension"):
            ext_dirs.append(root)
        else:
            try:
                for name in os.listdir(root):
                    p = os.path.join(root, name)
                    if os.path.isdir(p):
                        if name.lower().endswith(".extension"):
                            ext_dirs.append(p)
                        else:
                            try:
                                for subname in os.listdir(p):
                                    subp = os.path.join(p, subname)
                                    if os.path.isdir(subp) and subname.lower().endswith(".extension"):
                                        ext_dirs.append(subp)
                            except:
                                pass
            except Exception as e:
                log_debug(u"Failed to list directory {}: {}".format(root, safe_str(e)))
                
    return list(set(ext_dirs))


def classify_element_type(name, category_groups=None):
    if category_groups and name in category_groups:
        return category_groups[name]
        
    name_lower = name.lower()
    
    # Exclude model text/curve
    if "modeltext" in name_lower or "modelcurve" in name_lower or name_lower == "sprinklers" or name_lower == "sprinkler":
        return "Model Elements"
        
    annotation_keywords = [
        "annotation", "tag", "text", "note", "dimension", "detail", 
        "region", "grid", "level", "view", "sheet", "legend", 
        "schedule", "viewport", "cloud", "boundary", "symbol", "spot"
    ]
    
    for kw in annotation_keywords:
        if kw in name_lower:
            return "Annotation Elements"
            
    return "Model Elements"


# Radial Menu WPF Controller
class IconItem(object):
    def __init__(self, name, clean_name, full_path, path_val):
        self._name = name
        self._clean_name = clean_name
        self._full_path = full_path
        self._path_val = path_val

    @property
    def Name(self):
        return self._name

    @property
    def CleanName(self):
        return self._clean_name

    @property
    def FullPath(self):
        if not hasattr(self, "_cached_icon_source"):
            self._cached_icon_source = load_bitmap_image_themed(self._full_path)
        return self._cached_icon_source

    @property
    def PathVal(self):
        return self._path_val


class ClassItem(object):
    def __init__(self, name, is_checked=False, group="Model Elements"):
        self._name = name
        self._is_checked = is_checked
        self._group = group
        self._show_separator = False

    @property
    def Name(self):
        return self._name

    @Name.setter
    def Name(self, value):
        self._name = value

    @property
    def IsChecked(self):
        return self._is_checked

    @IsChecked.setter
    def IsChecked(self, value):
        self._is_checked = value

    @property
    def Group(self):
        return self._group

    @Group.setter
    def Group(self, value):
        self._group = value

    @property
    def ShowSeparator(self):
        return self._show_separator

    @ShowSeparator.setter
    def ShowSeparator(self, value):
        self._show_separator = value



class PoolListItem(object):
    def __init__(self, item, window=None):
        self._item = item
        self._window = window
        self._is_selected = False
        self._children = []
        self._is_checked = False
        self._is_expanded = False

    @property
    def EyeBrush(self):
        if not self._item.get("is_active", True):
            return get_cached_brush("#FFE53935")  # Red
            
        is_visible = True
        if self._window:
            is_visible = self._window.is_item_matching_context(self._item)
            
        is_light = getattr(self._window, "_is_light", False)
        if is_light:
            if is_visible:
                return get_cached_brush("#FF1E1E24")  # Dark
            else:
                return get_cached_brush("#FFB0B0B0")  # Lighter grey
        else:
            if is_visible:
                return get_cached_brush("#FFFFFFFF")  # White
            else:
                return get_cached_brush("#FF757575")  # Grey

    @property
    def EyeGeometry(self):
        if not self._item.get("is_active", True):
            # Eye off (crossed out)
            return Geometry.Parse("M12 4.5c-5 0-9.27 3.11-11 7.5 1.22 3.1 3.96 5.57 7.24 6.78l1.45-1.45C6.9 16.29 4.67 14.39 3.42 12c1.61-3.66 5.22-6 8.58-6 1.15 0 2.26.27 3.27.76l1.46-1.46C15.19 4.8 13.62 4.5 12 4.5zM22.58 21.08L3.42 1.92 1.92 3.42l4.8 4.8C4.54 9.17 2.89 10.45 1.58 12c1.73 4.39 6 7.5 11 7.5 2.2 0 4.26-.6 6.07-1.63l2.42 2.42 1.5-1.5zM12 17c-2.76 0-5-2.24-5-5 0-.77.18-1.5.49-2.14l6.65 6.65C13.5 16.82 12.77 17 12 17zm8.58-5c-1.25-2.39-3.48-4.29-6.27-5.33l1.52-1.52C19.1 6.36 20.83 8.83 22 12c-1.22 3.1-3.96 5.57-7.24 6.78l-1.45-1.45c2.79-1.04 5.02-2.94 6.27-5.33z")
        else:
            # Eye normal
            return Geometry.Parse("M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z")

    @property
    def EyeToolTip(self):
        if not self._item.get("is_active", True):
            return u"Disabled permanently (Click to enable)"
            
        is_visible = True
        if self._window:
            is_visible = self._window.is_item_matching_context(self._item)
            
        if is_visible:
            return u"Visible in current context (Click to disable)"
        else:
            return u"Hidden by active context rules (Click to disable)"

    @property
    def IsSelected(self):
        return self._is_selected

    @IsSelected.setter
    def IsSelected(self, value):
        self._is_selected = value

    @property
    def IsChecked(self):
        return self._is_checked

    @IsChecked.setter
    def IsChecked(self, value):
        self._is_checked = value

    @property
    def IsExpanded(self):
        return getattr(self, "_is_expanded", False)

    @IsExpanded.setter
    def IsExpanded(self, value):
        self._is_expanded = value
        if self._item and self._window:
            item_id = self._item.get("id")
            if item_id:
                if not hasattr(self._window, "_expanded_item_ids_cache") or self._window._expanded_item_ids_cache is None:
                    self._window._expanded_item_ids_cache = set()
                if value:
                    self._window._expanded_item_ids_cache.add(item_id)
                else:
                    self._window._expanded_item_ids_cache.discard(item_id)

    @property
    def children(self):
        return self._children

    @property
    def Icon(self):
        val = self._item.get("icon", "")
        if not val:
            return None
        if val.lower().endswith(".png") or os.path.sep in val or "/" in val:
            try:
                # Resolve the absolute path if needed
                img_path = val
                if not os.path.isabs(img_path):
                    img_path = os.path.join(os.path.dirname(__file__), img_path)
                if os.path.exists(img_path):
                    return load_bitmap_image_themed(img_path)
            except:
                pass
            return None
        return val

    @property
    def IsImageIcon(self):
        val = self._item.get("icon", "")
        if val and (val.lower().endswith(".png") or os.path.sep in val or "/" in val):
            return True
        return False

    @property
    def DisplayName(self):
        return self._item.get("name", "")

    @property
    def ContextSummary(self):
        rules = self._item.get("context_rules", {}) or {}
        views = rules.get("allowed_views", [])
        classes = rules.get("allowed_classes", [])
        
        parts = []
        if views:
            parts.append(u"Views: " + u", ".join(views))
        if classes:
            parts.append(u"Classes: " + u", ".join(classes[:2]) + (u"..." if len(classes) > 2 else u""))
        if not parts:
            return u"Always visible"
        return u" | ".join(parts)

    @property
    def LevelLabel(self):
        return u"L{}".format(self._item.get("level", 1))

    @property
    def PriorityLabel(self):
        return u"P: {}".format(self._item.get("priority", 0))



class ContextRulesDialog(Window):
    def __init__(self, xaml_str, petal_name, current_rules, intersected_classes=None):
        import System.IO
        wpf.LoadComponent(self, System.IO.MemoryStream(xaml_str.encode("utf-8")))
        self.TxtPetalName.Text = "Configure Rules for: {}".format(petal_name)
        self.intersected_classes = intersected_classes
        self.all_classes_items = []
        
        # Populate View check boxes
        if current_rules and "allowed_views" in current_rules:
            allowed_views = current_rules["allowed_views"] or []
            self.ChkView3D.IsChecked = "3D" in allowed_views
            self.ChkViewPlan.IsChecked = "Plan" in allowed_views
            self.ChkViewSheet.IsChecked = "Sheet" in allowed_views
        else:
            self.ChkView3D.IsChecked = True
            self.ChkViewPlan.IsChecked = True
            self.ChkViewSheet.IsChecked = True
            
        # Reflected Revit DB Classes & Categories
        import Autodesk.Revit.DB as db
        reflected = []
        category_groups = {}
        try:
            assembly = System.Reflection.Assembly.GetAssembly(db.Element)
            types = assembly.GetTypes()
            for t in types:
                if t.IsClass and t.IsSubclassOf(db.Element) and t.Namespace and t.Namespace.startswith("Autodesk.Revit.DB"):
                    reflected.append(t.Name)
        except Exception as ex:
            log_debug("Failed to reflect Revit classes: " + str(ex))
            reflected = ["Wall", "Floor", "Pipe", "Duct", "FamilyInstance", "Dimension"]
            
        # Also include Revit Categories
        try:
            from pyrevit import HOST_APP
            if HOST_APP.uiapp and HOST_APP.uiapp.ActiveUIDocument:
                doc = HOST_APP.uiapp.ActiveUIDocument.Document
                if doc:
                    for cat in doc.Settings.Categories:
                        if cat.Name:
                            clean_eng = get_clean_english_category_name(cat)
                            if clean_eng:
                                reflected.append(clean_eng)
                                try:
                                    cat_type = cat.CategoryType
                                    cat_type_str = str(cat_type)
                                    if cat_type == db.CategoryType.Annotation or "Annotation" in cat_type_str:
                                        category_groups[clean_eng] = "Annotation Elements"
                                    else:
                                        category_groups[clean_eng] = "Model Elements"
                                except Exception as cat_type_ex:
                                    log_debug("Failed to get CategoryType for {}: {}".format(clean_eng, cat_type_ex))
        except Exception as cat_ex:
            log_debug("Failed to get categories in ContextRulesDialog: " + str(cat_ex))
            
        allowed_classes = current_rules.get("allowed_classes", []) if current_rules else []
        allowed_classes_set = set(allowed_classes)
        intersected_classes_set = set(self.intersected_classes) if self.intersected_classes else set()

        def get_sort_key(c):
            is_allowed = any(alias in allowed_classes_set for alias in get_category_aliases(c))
            is_intersected = c in intersected_classes_set
            if is_allowed and is_intersected:
                prio = 0
            elif is_allowed:
                prio = 1
            elif is_intersected:
                prio = 2
            else:
                prio = 3
            return (prio, c.lower())

        reflected = sorted(list(set(reflected)), key=get_sort_key)
        
        from System.Collections.ObjectModel import ObservableCollection
        self.classes_collection = ObservableCollection[object]()
        
        for name in reflected:
            is_checked = any(alias in allowed_classes for alias in get_category_aliases(name))
            group_name = classify_element_type(name, category_groups)
            item = ClassItem(name, is_checked, group_name)
            self.all_classes_items.append(item)
            self.classes_collection.Add(item)
            
        self.LstClasses.ItemsSource = self.classes_collection
        
        # Set up CollectionViewSource filtering to preserve selection state when search filters elements
        from System.Windows.Data import CollectionViewSource, PropertyGroupDescription
        from System import Predicate
        self.classes_view = CollectionViewSource.GetDefaultView(self.classes_collection)
        self._dialog_classes_filter_delegate = Predicate[object](self.dialog_classes_filter_predicate)
        self.classes_view.Filter = self._dialog_classes_filter_delegate
        self.classes_view.GroupDescriptions.Add(PropertyGroupDescription("Group"))
        
        # Hook search and buttons
        self.TxtClassSearch.TextChanged += self.on_search_changed
        self.BtnSave.Click += self.on_save_clicked
        self.BtnCancel.Click += self.on_cancel_clicked
        self.DialogResult = False
        
    def dialog_classes_filter_predicate(self, item):
        try:
            text = self.TxtClassSearch.Text
            if not text:
                return True
            query = text.lower().strip()
            if not query:
                return True
            return query in item.Name.lower()
        except:
            return True

    def on_search_changed(self, sender, args):
        try:
            if hasattr(self, "classes_view") and self.classes_view:
                self.classes_view.Refresh()
        except Exception as ex:
            log_debug("Error in on_search_changed: " + str(ex))
                
    def on_save_clicked(self, sender, args):
        self.DialogResult = True
        self.Close()
        
    def on_cancel_clicked(self, sender, args):
        self.DialogResult = False
        self.Close()
        
    def get_result(self):
        views = []
        if self.ChkView3D.IsChecked: views.append("3D")
        if self.ChkViewPlan.IsChecked: views.append("Plan")
        if self.ChkViewSheet.IsChecked: views.append("Sheet")
            
        classes = [item.Name for item in self.all_classes_items if item.IsChecked]
        return {
            "allowed_views": views,
            "allowed_classes": classes
        }


# Radial Menu WPF Controller
class RadialMenuWindow(Window):
    def __init__(self, xaml_path, active_context="default"):
        # Hook global unhandled exceptions to log tracebacks before crashing
        try:
            import System
            def global_unhandled_handler(sender, args):
                try:
                    ex = args.ExceptionObject
                    log_debug("UNHANDLED APPDOMAIN EXCEPTION: " + str(ex))
                except:
                    pass
            self._global_unhandled_handler = System.UnhandledExceptionEventHandler(global_unhandled_handler)
            System.AppDomain.CurrentDomain.UnhandledException += self._global_unhandled_handler
            
            def dispatcher_unhandled_handler(sender, args):
                try:
                    ex = args.Exception
                    log_debug("UNHANDLED DISPATCHER EXCEPTION: " + str(ex))
                    import traceback
                    log_debug(traceback.format_exc())
                except:
                    pass
            from System.Windows.Threading import DispatcherUnhandledExceptionEventHandler
            self._dispatcher_unhandled_handler = DispatcherUnhandledExceptionEventHandler(dispatcher_unhandled_handler)
            self.Dispatcher.UnhandledException += self._dispatcher_unhandled_handler
            log_debug("Registered global and dispatcher unhandled exception hooks.")
        except Exception as hooks_ex:
            log_debug("Failed to register exception hooks: " + str(hooks_ex))
            
        # Query theme and cache it in the global module-level variable safely on the main thread
        try:
            from Autodesk.Revit.UI import UIThemeManager, UITheme
            global _IS_REVIT_DARK
            _IS_REVIT_DARK = (UIThemeManager.CurrentTheme == UITheme.Dark)
            log_debug(u"Cached Revit Dark Theme status: {}".format(_IS_REVIT_DARK))
        except Exception as theme_ex:
            log_debug(u"Failed to query Revit theme at startup: {}".format(safe_str(theme_ex)))
            
        # Heavy reflection and category loading moved to lazy load (when customizer or rules editor is opened)
        self._preloaded_classes = []
        self._preloaded_category_groups = {}
        
        self._is_closing = False
        self.customizer_mode = False
        self._is_light = False
        self._all_commands = []
        self._restore_revit_focus = True
        self._drag_start_point = System.Windows.Point()
        self.active_context = active_context
        self._active_l1_parent = None
        self._active_l2_parent = None
        self.picker_mode = "all"
        self._current_revit_sel_classes = set()
        
        # Debounce Timers setup
        from System.Windows.Threading import DispatcherTimer
        from System import TimeSpan
        
        self._save_timer = DispatcherTimer()
        self._save_timer.Interval = TimeSpan.FromMilliseconds(1000)
        self._save_timer.Tick += self.on_save_timer_tick
        
        self._search_timer = DispatcherTimer()
        self._search_timer.Interval = TimeSpan.FromMilliseconds(400)
        self._search_timer.Tick += self.on_search_timer_tick
        
        self._pool_search_timer = DispatcherTimer()
        self._pool_search_timer.Interval = TimeSpan.FromMilliseconds(250)
        self._pool_search_timer.Tick += self.on_pool_search_timer_tick
        
        self._icon_search_timer = DispatcherTimer()
        self._icon_search_timer.Interval = TimeSpan.FromMilliseconds(250)
        self._icon_search_timer.Tick += self.on_icon_search_timer_tick
        self._icon_search_query = ""
        
        log_debug(u"RadialMenuWindow.__init__ started for context: {}.".format(self.active_context))
        try:
            Window.__init__(self)
            log_debug(u"Window.__init__ completed.")
        except Exception as ex:
            log_debug(u"Exception in Window.__init__: {}".format(safe_str(ex)))
            raise
            
        try:
            log_debug(u"Loading XAML from: {}".format(xaml_path))
            wpf.LoadComponent(self, xaml_path)
            log_debug(u"wpf.LoadComponent completed.")
            self.AllowDrop = True
            
            # Programmatically initialize RenderTransform and BitmapCache on Level canvases to bypass XAML parser limitations and optimize performance
            from System.Windows.Media import TransformGroup, ScaleTransform, RotateTransform, BitmapCache
            for canvas_name in ["SubMenuLevel1", "SubMenuLevel2", "SubMenuLevel3"]:
                canvas = getattr(self, canvas_name, None)
                if canvas:
                    group = TransformGroup()
                    scale = ScaleTransform(1.0, 1.0)
                    rotate = RotateTransform(0.0)
                    group.Children.Add(scale)
                    group.Children.Add(rotate)
                    canvas.RenderTransform = group
                    try:
                        canvas.CacheMode = BitmapCache()
                        log_debug(u"Enabled BitmapCache for {}".format(canvas_name))
                    except Exception as cache_ex:
                        log_debug(u"Failed to set CacheMode: {}".format(safe_str(cache_ex)))
                    log_debug(u"Initialized RenderTransform group for {}".format(canvas_name))
        except Exception as ex:
            try:
                import traceback
                tb = traceback.format_exc()
                log_debug(u"Exception in wpf.LoadComponent: {}\nTraceback:\n{}".format(safe_str(ex), tb))
            except:
                log_debug(u"Exception in wpf.LoadComponent: {}".format(safe_str(ex)))
            raise
            
        try:
            self._brush_before_after = SolidColorBrush(ColorConverter.ConvertFromString("#08FFFFFF"))
            self._brush_inside = SolidColorBrush(ColorConverter.ConvertFromString("#2500E5FF"))
            self._brush_accent = SolidColorBrush(ColorConverter.ConvertFromString("#FF00E5FF"))
            self._brush_transparent = Brushes.Transparent
            
            # Connect WPF button Click and Mouse events dynamically for all 30 buttons
            for slot_num, btn_name in SLOT_BUTTONS.items():
                btn = getattr(self, btn_name, None)
                if btn:
                    btn.Click += self.on_button_clicked_dynamic
                    btn.PreviewMouseLeftButtonDown += self.on_petal_mouse_down
                    btn.PreviewMouseMove += self.on_petal_mouse_move
                    btn.PreviewMouseLeftButtonUp += self.on_petal_mouse_up

            # Central Core buttons (Normal Mode)
            self.BtnCoreClose.Click += lambda s, e: self.on_close_request()
            self.BtnCoreSettings.Click += lambda s, e: self.setup_customizer_mode()
            
            # Central Core buttons (Settings Mode)
            self.BtnCoreMove.Click += lambda s, e: self.on_core_move_clicked()
            self.BtnCorePool.Click += lambda s, e: self.on_core_pool_clicked()
            self.BtnCoreAppearance.Click += lambda s, e: self.on_core_appearance_clicked()
            self.BtnCoreExit.Click += lambda s, e: self.on_core_exit_clicked()
            
            # Customizer Panel buttons
            self.BtnExitCustomizer.Click += self.on_exit_customizer_clicked
            self.BtnExitCustomizerLook.Click += self.on_exit_customizer_clicked
            if hasattr(self, "BtnExtractAllIcons") and self.BtnExtractAllIcons:
                self.BtnExtractAllIcons.Click += self.on_extract_all_icons_clicked
            if hasattr(self, "BtnDeleteChecked") and self.BtnDeleteChecked:
                self.BtnDeleteChecked.Click += self.on_delete_checked_clicked
            if hasattr(self, "BtnExportConfig") and self.BtnExportConfig:
                self.BtnExportConfig.Click += self.on_export_config_clicked
            if hasattr(self, "BtnImportConfig") and self.BtnImportConfig:
                self.BtnImportConfig.Click += self.on_import_config_clicked

            # Connect hover events dynamically for Level 1 & 2
            for idx in range(1, 11):
                btn1 = getattr(self, "BtnL1_{}".format(idx), None)
                if btn1:
                    btn1.MouseEnter += self.on_level1_hover
                btn2 = getattr(self, "BtnL2_{}".format(idx), None)
                if btn2:
                    btn2.MouseEnter += self.on_level2_hover

            # Center buttons hover should collapse open submenus
            self.BtnCoreClose.MouseEnter += lambda s, e: self.hide_level2()
            self.BtnCoreSettings.MouseEnter += lambda s, e: self.hide_level2()
            self.BtnCoreMove.MouseEnter += lambda s, e: self.hide_level2()
            self.BtnCorePool.MouseEnter += lambda s, e: self.hide_level2()
            self.BtnCoreAppearance.MouseEnter += lambda s, e: self.hide_level2()
            self.BtnCoreExit.MouseEnter += lambda s, e: self.hide_level2()

            log_debug(u"Connected button Click and Hover events.")
            
            # Register focus and escape behaviors
            self.Deactivated += self.on_deactivated
            self.KeyDown += self.on_key_down
            self.Closing += self.on_window_closing
            self.Loaded += self.on_window_loaded
            
            # Load layout configuration
            self.load_layout_configuration()
            
            # Apply layout geometries and colors
            self.update_radial_geometry()
            
            # Wire up drag and drop target events for all sector buttons safely
            for slot, btn_name in SLOT_BUTTONS.items():
                btn = getattr(self, btn_name, None)
                if btn:
                    btn.AllowDrop = True
                    btn.DragOver += self.on_button_drag_over
                    btn.Drop += self.on_button_drop
            self.cache_revit_context()
            
            # Check icons for the current theme asynchronously after window loads
            def check_icons_async():
                check_and_suggest_icon_extraction(self)
            from System import Action
            self.Dispatcher.BeginInvoke(Action(check_icons_async))
        except Exception as ex:
            log_debug(u"Exception connecting Click events: {}".format(safe_str(ex)))
            raise

    def on_level1_hover(self, sender, args):
        try:
            pool_item = getattr(self, "_button_to_pool_item", {}).get(sender.Name)
            if pool_item:
                cmd_value = pool_item.get("command")
                if cmd_value in ["submenu1", "submenu2"]:
                    old_parent = self._active_l1_parent
                    new_parent = pool_item.get("id")
                    
                    if old_parent != new_parent:
                        self._active_l1_parent = new_parent
                        self._active_l2_parent = None
                        self.load_layout_configuration()
                        self.update_radial_geometry()
                        self.animate_level("SubMenuLevel2", True)
                    else:
                        self.show_level2()
                else:
                    self.hide_level2()
            else:
                self.hide_level2()
        except Exception as ex:
            log_debug(u"Error in on_level1_hover: {}".format(safe_str(ex)))

    def on_level2_hover(self, sender, args):
        try:
            pool_item = getattr(self, "_button_to_pool_item", {}).get(sender.Name)
            if pool_item:
                cmd_value = pool_item.get("command")
                if cmd_value in ["submenu1", "submenu2"]:
                    old_parent = self._active_l2_parent
                    new_parent = pool_item.get("id")
                    
                    if old_parent != new_parent:
                        self._active_l2_parent = new_parent
                        self.load_layout_configuration()
                        self.update_radial_geometry()
                        self.animate_level("SubMenuLevel3", True)
                    else:
                        self.show_level3()
                else:
                    self.hide_level3()
            else:
                self.hide_level3()
        except Exception as ex:
            log_debug(u"Error in on_level2_hover: {}".format(safe_str(ex)))

    def toggle_level2(self):
        try:
            from System.Windows import Visibility
            if self.SubMenuLevel2.Visibility == Visibility.Visible:
                self.hide_level2()
            else:
                self.show_level2()
        except Exception as ex:
            log_debug(u"Error toggling level2: {}".format(safe_str(ex)))

    def toggle_level3(self):
        try:
            from System.Windows import Visibility
            if self.SubMenuLevel3.Visibility == Visibility.Visible:
                self.hide_level3()
            else:
                self.show_level3()
        except Exception as ex:
            log_debug(u"Error toggling level3: {}".format(safe_str(ex)))

    def animate_level(self, canvas_name, is_show):
        try:
            settings = self._config_data.get("settings", dict(DEFAULT_SETTINGS))
            style = settings.get("animation_style", "fade")
            
            canvas = getattr(self, canvas_name, None)
            if not canvas:
                return
                
            scale = None
            rotate = None
            if canvas.RenderTransform and hasattr(canvas.RenderTransform, "Children"):
                children = canvas.RenderTransform.Children
                if children.Count >= 2:
                    scale = children[0]
                    rotate = children[1]
            
            from System.Windows.Media.Animation import DoubleAnimation, CubicEase, EasingMode
            from System import TimeSpan
            from System.Windows import Visibility
            from System.Windows.Media import ScaleTransform, RotateTransform
            
            # Setup easing functions for professional look and feel
            ease_out = CubicEase()
            ease_out.EasingMode = EasingMode.EaseOut
            
            ease_in = CubicEase()
            ease_in.EasingMode = EasingMode.EaseIn
            
            if is_show:
                canvas.Visibility = Visibility.Visible
                
                # Opacity animation (always fade in)
                da_opacity = DoubleAnimation(0.0, 1.0, TimeSpan.FromMilliseconds(200))
                da_opacity.EasingFunction = ease_out
                canvas.BeginAnimation(System.Windows.UIElement.OpacityProperty, da_opacity)
                
                if style == "pop":
                    # Scale from 0 to 1
                    if scale:
                        da_scale = DoubleAnimation(0.0, 1.0, TimeSpan.FromMilliseconds(200))
                        da_scale.EasingFunction = ease_out
                        scale.BeginAnimation(ScaleTransform.ScaleXProperty, da_scale)
                        scale.BeginAnimation(ScaleTransform.ScaleYProperty, da_scale)
                elif style == "fan":
                    # Fan/Rotate from -45 to 0 while scaling slightly
                    if rotate:
                        da_rotate = DoubleAnimation(-45.0, 0.0, TimeSpan.FromMilliseconds(200))
                        da_rotate.EasingFunction = ease_out
                        rotate.BeginAnimation(RotateTransform.AngleProperty, da_rotate)
                    if scale:
                        da_scale = DoubleAnimation(0.6, 1.0, TimeSpan.FromMilliseconds(200))
                        da_scale.EasingFunction = ease_out
                        scale.BeginAnimation(ScaleTransform.ScaleXProperty, da_scale)
                        scale.BeginAnimation(ScaleTransform.ScaleYProperty, da_scale)
                else:
                    # Reset transforms to default (fade style)
                    if scale:
                        scale.BeginAnimation(ScaleTransform.ScaleXProperty, None)
                        scale.BeginAnimation(ScaleTransform.ScaleYProperty, None)
                        scale.ScaleX = 1.0
                        scale.ScaleY = 1.0
                    if rotate:
                        rotate.BeginAnimation(RotateTransform.AngleProperty, None)
                        rotate.Angle = 0.0
            else:
                # Hide animation
                da_opacity = DoubleAnimation(canvas.Opacity, 0.0, TimeSpan.FromMilliseconds(150))
                da_opacity.EasingFunction = ease_in
                def on_completed(s, e):
                    canvas.Visibility = Visibility.Collapsed
                da_opacity.Completed += on_completed
                canvas.BeginAnimation(System.Windows.UIElement.OpacityProperty, da_opacity)
                
                if style == "pop":
                    if scale:
                        da_scale = DoubleAnimation(scale.ScaleX, 0.0, TimeSpan.FromMilliseconds(150))
                        da_scale.EasingFunction = ease_in
                        scale.BeginAnimation(ScaleTransform.ScaleXProperty, da_scale)
                        scale.BeginAnimation(ScaleTransform.ScaleYProperty, da_scale)
                elif style == "fan":
                    if rotate:
                        da_rotate = DoubleAnimation(rotate.Angle, -45.0, TimeSpan.FromMilliseconds(150))
                        da_rotate.EasingFunction = ease_in
                        rotate.BeginAnimation(RotateTransform.AngleProperty, da_rotate)
                    if scale:
                        da_scale = DoubleAnimation(scale.ScaleX, 0.6, TimeSpan.FromMilliseconds(150))
                        da_scale.EasingFunction = ease_in
                        scale.BeginAnimation(ScaleTransform.ScaleXProperty, da_scale)
                        scale.BeginAnimation(ScaleTransform.ScaleYProperty, da_scale)
        except Exception as ex:
            log_debug("Error in animate_level: " + str(ex))

    def show_level2(self):
        try:
            from System.Windows import Visibility
            if self.SubMenuLevel2.Visibility != Visibility.Visible:
                self.animate_level("SubMenuLevel2", True)
        except Exception as ex:
            log_debug(u"Error showing level2: {}".format(safe_str(ex)))

    def hide_level2(self):
        try:
            self._active_l1_parent = None
            self._active_l2_parent = None
            from System.Windows import Visibility
            if self.SubMenuLevel2.Visibility == Visibility.Visible:
                self.hide_level3()
                self.animate_level("SubMenuLevel2", False)
        except Exception as ex:
            log_debug(u"Error hiding level2: {}".format(safe_str(ex)))

    def show_level3(self):
        try:
            from System.Windows import Visibility
            if self.SubMenuLevel3.Visibility != Visibility.Visible:
                self.animate_level("SubMenuLevel3", True)
        except Exception as ex:
            log_debug(u"Error showing level3: {}".format(safe_str(ex)))

    def hide_level3(self):
        try:
            self._active_l2_parent = None
            from System.Windows import Visibility
            if self.SubMenuLevel3.Visibility == Visibility.Visible:
                self.animate_level("SubMenuLevel3", False)
        except Exception as ex:
            log_debug(u"Error hiding level3: {}".format(safe_str(ex)))

    def load_layout_configuration(self, force_reload=False):
        try:
            if force_reload or not hasattr(self, "_config_data") or not self._config_data:
                self._config_data = load_config()
            pool = self._config_data.get("command_pool", list(DEFAULT_POOL))
            
            # Apply context filtering only in normal mode.
            # In customizer mode, we bypass context rules so the user can see and edit the full radial menu layout statically.
            if getattr(self, "customizer_mode", False) or getattr(self, "_move_mode_active", False):
                filtered_pool = [p for p in pool if p.get("is_active", True)]
            else:
                filtered_pool = self.filter_pool_by_context(pool)
            
            self._command_pool = pool  # Full pool for settings editing
            self._filtered_pool = filtered_pool  # Context-filtered for display
                
            log_debug(u"Loaded pool with {} total, {} after filtering.".format(len(pool), len(filtered_pool)))
            
            # Build dynamic button-to-pool mapping
            self._button_to_slot_map = {}
            self._button_to_pool_item = {}
            
            # Group by level, sorted by priority
            l1_items = sorted([p for p in filtered_pool if p.get("level") == 1], key=lambda x: x.get("priority", 0))[:10]
            
            # For Level 2, filter by self._active_l1_parent (if set)
            l2_items = []
            if getattr(self, "_active_l1_parent", None):
                l2_items = sorted([p for p in filtered_pool if p.get("level") == 2 and p.get("parent") == self._active_l1_parent], key=lambda x: x.get("priority", 0))[:10]
                
            # For Level 3, filter by self._active_l2_parent (if set)
            l3_items = []
            if getattr(self, "_active_l2_parent", None):
                l3_items = sorted([p for p in filtered_pool if p.get("level") == 3 and p.get("parent") == self._active_l2_parent], key=lambda x: x.get("priority", 0))[:10]
            
            # Map pool items to Level 1 buttons or clear remaining
            for idx in range(1, 11):
                btn_name = "BtnL1_{}".format(idx)
                slot_num = idx
                if idx <= len(l1_items):
                    item = l1_items[idx - 1]
                    self._button_to_slot_map[btn_name] = slot_num
                    self._button_to_pool_item[btn_name] = item
                    self.update_button_ui_by_name(btn_name, item.get("name"), item.get("type"), item.get("icon"))
                else:
                    self.update_button_ui_by_name(btn_name, "", "emoji", "")
                    if btn_name in self._button_to_pool_item:
                        del self._button_to_pool_item[btn_name]
                    if btn_name in self._button_to_slot_map:
                        del self._button_to_slot_map[btn_name]
                
            # Clear or update Level 2 buttons
            for idx in range(1, 11):
                btn_name = "BtnL2_{}".format(idx)
                slot_num = idx + 10
                if idx <= len(l2_items):
                    item = l2_items[idx - 1]
                    self._button_to_slot_map[btn_name] = slot_num
                    self._button_to_pool_item[btn_name] = item
                    self.update_button_ui_by_name(btn_name, item.get("name"), item.get("type"), item.get("icon"))
                else:
                    self.update_button_ui_by_name(btn_name, "", "emoji", "")
                    if btn_name in self._button_to_pool_item:
                        del self._button_to_pool_item[btn_name]
                    if btn_name in self._button_to_slot_map:
                        del self._button_to_slot_map[btn_name]
                        
            # Clear or update Level 3 buttons
            for idx in range(1, 11):
                btn_name = "BtnL3_{}".format(idx)
                slot_num = idx + 20
                if idx <= len(l3_items):
                    item = l3_items[idx - 1]
                    self._button_to_slot_map[btn_name] = slot_num
                    self._button_to_pool_item[btn_name] = item
                    self.update_button_ui_by_name(btn_name, item.get("name"), item.get("type"), item.get("icon"))
                else:
                    self.update_button_ui_by_name(btn_name, "", "emoji", "")
                    if btn_name in self._button_to_pool_item:
                        del self._button_to_pool_item[btn_name]
                    if btn_name in self._button_to_slot_map:
                        del self._button_to_slot_map[btn_name]
                
            # Store counts for geometry
            self._level_counts = (len(l1_items), len(l2_items), len(l3_items))
        except Exception as ex:
            log_debug(u"Failed to load layout configuration: {}".format(safe_str(ex)))
            self._level_counts = (0, 0, 0)

    def cache_revit_context(self):
        try:
            # 1. Cache View Category
            view_cat = "Plan"
            uiapp = HOST_APP.uiapp
            if uiapp and uiapp.ActiveUIDocument:
                active_view = uiapp.ActiveUIDocument.ActiveView
                if active_view:
                    from Autodesk.Revit.DB import ViewType
                    vt = active_view.ViewType
                    if vt in [ViewType.ThreeD]:
                        view_cat = "3D"
                    elif vt in [ViewType.FloorPlan, ViewType.CeilingPlan, ViewType.AreaPlan, ViewType.EngineeringPlan, ViewType.Elevation, ViewType.Section]:
                        view_cat = "Plan"
                    elif vt in [ViewType.DrawingSheet]:
                        view_cat = "Sheet"
            self._cached_view_category = view_cat
        except Exception as ex:
            log_debug("Error caching view category: " + str(ex))
            self._cached_view_category = "Plan"

        try:
            # 2. Cache Selection State and Classes
            if getattr(self, "customizer_mode", False):
                ctx = self.active_context
                if ctx == "default":
                    self._cached_selection_state = "None"
                    self._cached_sel_classes = set()
                else:
                    self._cached_selection_state = "Selection"
                    if ctx == "pipes":
                        self._cached_sel_classes = {"Pipes", "Pipe"}
                    elif ctx == "ducts":
                        self._cached_sel_classes = {"Ducts", "Duct"}
                    elif ctx == "walls":
                        self._cached_sel_classes = {"Walls", "Wall"}
                    elif ctx == "dimensions":
                        self._cached_sel_classes = {"Dimensions", "Dimension"}
                    else:
                        self._cached_sel_classes = set()
            else:
                self._cached_selection_state = get_current_selection_state()
                self._cached_sel_classes = getattr(self, "_current_revit_sel_classes", set())
        except Exception as ex:
            log_debug("Error caching selection context: " + str(ex))
            self._cached_selection_state = "None"
            self._cached_sel_classes = set()

    def is_item_matching_context(self, item):
        try:
            rules = item.get("context_rules", {})
            if not rules:
                return True
                
            # A. Check allowed_views using cached category
            current_view_category = getattr(self, "_cached_view_category", "Plan")
            if "allowed_views" in rules:
                allowed_views = rules["allowed_views"]
                if allowed_views:
                    if current_view_category not in allowed_views:
                        return False
            
            # B. Check allowed_selection_states and allowed_classes using cached values
            allowed_states = rules.get("allowed_selection_states", []) or []
            current_state = getattr(self, "_cached_selection_state", "None")
            allowed_classes = rules.get("allowed_classes", []) or []
            sel_classes = getattr(self, "_cached_sel_classes", set())
            
            if allowed_states or allowed_classes:
                effective_states = allowed_states if allowed_states else ["Selection", "Pre-highlighted"]
                if current_state not in effective_states:
                    return False
                
                if allowed_classes:
                    class_match = False
                    if sel_classes:
                        for c in allowed_classes:
                            if c in sel_classes:
                                class_match = True
                                break
                    if not class_match:
                        return False
                                
            return True
        except:
            return True

    def filter_pool_by_context(self, pool):
        """Filter pool items by current Revit context (view type + selected element classes)."""
        if getattr(self, "customizer_mode", False) or getattr(self, "_move_mode_active", False):
            return [dict(p) for p in pool if p.get("is_active", True)]
            
        try:
            ctx = self.active_context
            
            # 1. Retrieve actual currently selected element classes/categories from Revit
            sel_classes = set()
            try:
                uiapp = HOST_APP.uiapp
                if uiapp and uiapp.ActiveUIDocument:
                    uidoc = uiapp.ActiveUIDocument
                    if uidoc:
                        doc = uidoc.Document
                        sel_ids = list(uidoc.Selection.GetElementIds())
                        if sel_ids:
                            for eid in sel_ids[:5]:
                                el = doc.GetElement(eid)
                                if el:
                                    t = el.GetType()
                                    while t is not None and t != System.Object:
                                        if t.Namespace and t.Namespace.startswith("Autodesk.Revit.DB"):
                                            sel_classes.add(t.Name)
                                        t = t.BaseType
                                    if el.Category:
                                        sel_classes.add(el.Category.Name)
                                        for eng_name in get_english_names_for_category(el.Category):
                                            sel_classes.add(eng_name)
                        else:
                            # Try to get the hovered category if nothing is selected
                            hovered_cat = get_hovered_category()
                            if hovered_cat:
                                sel_classes.add(hovered_cat)
                                cat_obj = find_category_by_localized_name(doc, hovered_cat)
                                if cat_obj:
                                    for eng_name in get_english_names_for_category(cat_obj):
                                        sel_classes.add(eng_name)
            except Exception as ex:
                log_debug("Error gathering selection classes for filtering: " + str(ex))
                
            self._current_revit_sel_classes = sel_classes
            self.cache_revit_context()
            
            def process_node(node):
                if not node.get("is_active", True):
                    return False, None, []
                
                is_sub = node.get("command") in ["submenu1", "submenu2"]
                if not is_sub:
                    if self.is_item_matching_context(node):
                        return True, dict(node), []
                    else:
                        return False, None, []
                
                node_id = node.get("id")
                children = [p for p in pool if p.get("parent") == node_id]
                
                active_children = []
                child_descendants = []
                for child in children:
                    ok, rep, desc = process_node(child)
                    if ok:
                        active_children.append(rep)
                        child_descendants.extend(desc)
                        
                if len(active_children) == 0:
                    return False, None, []
                elif len(active_children) == 1:
                    single_child = active_children[0]
                    transformed = dict(single_child)
                    transformed["level"] = node.get("level")
                    transformed["parent"] = node.get("parent")
                    transformed["priority"] = node.get("priority", 0)
                    
                    shifted_descendants = []
                    for desc in child_descendants:
                        new_desc = dict(desc)
                        new_desc["level"] = max(1, desc.get("level", 1) - 1)
                        shifted_descendants.append(new_desc)
                    return True, transformed, shifted_descendants
                else:
                    transformed_node = dict(node)
                    transformed_node["context_rules"] = {}
                    descendants = list(active_children) + child_descendants
                    return True, transformed_node, descendants

            # Root nodes are those with level == 1
            l1_roots = [p for p in pool if p.get("level") == 1]
            
            filtered = []
            for root in l1_roots:
                ok, rep, desc = process_node(root)
                if ok:
                    filtered.append(rep)
                    filtered.extend(desc)
            return filtered
        except Exception as ex:
            log_debug(u"Error filtering pool by context: {}".format(safe_str(ex)))
            return [p for p in pool if p.get("is_active", True)]

    def format_command_name_for_display(self, name):
        if not name:
            return ""
        
        name = name.replace("\\n", "\n").replace("/n", "\n")
        
        lines = name.split("\n")
        formatted_lines = []
        for line in lines:
            words = [w for w in line.split(" ") if w]
            if not words:
                continue
            
            result_line = words[0]
            for i in range(1, len(words)):
                word = words[i]
                # If the word is a single letter (or character), keep it on the same line with a space.
                if len(word) <= 1:
                    result_line += " " + word
                else:
                    result_line += "\n" + word
            formatted_lines.append(result_line)
        
        return "\n".join(formatted_lines)

    def update_button_ui_by_name(self, btn_name, name, icon_type, icon_value):
        try:
            image_element = getattr(self, btn_name + "Image")
            emoji_element = getattr(self, btn_name + "Emoji")
            label_element = getattr(self, btn_name + "Label")
            arrow_element = getattr(self, btn_name + "Arrow", None)
            
            pool_item = getattr(self, "_button_to_pool_item", {}).get(btn_name)
            is_pulldown = pool_item.get("is_pulldown", False) if pool_item else False
            
            if arrow_element:
                if is_pulldown:
                    arrow_element.Visibility = Visibility.Visible
                else:
                    arrow_element.Visibility = Visibility.Collapsed
                    
            label_element.Text = self.format_command_name_for_display(name)
            
            img_path = None
            is_image = False
            
            if icon_type == "pyrevit" and icon_value:
                img_path = resolve_themed_icon(icon_value)
                is_image = True
            elif icon_type == "built_in":
                # Check if icon_value is a file path
                if icon_value and (icon_value.lower().endswith(".png") or os.path.sep in icon_value or "/" in icon_value):
                    img_path = resolve_themed_icon(icon_value)
                    is_image = True
                else:
                    # Try to resolve extracted native Revit Ribbon icon
                    pool_item = getattr(self, "_button_to_pool_item", {}).get(btn_name)
                    cmd_val = pool_item.get("command") if pool_item else None
                    if cmd_val:
                        _, resolved_icon = resolve_builtin_command(cmd_val)
                        icon_name = resolved_icon or "".join([c for c in cmd_val if c.isalnum() or c in ("_", "-")]).strip()
                        local_png = os.path.join(os.path.dirname(__file__), "extracted_icons", icon_name + ".png")
                        if os.path.exists(local_png):
                            img_path = resolve_themed_icon(local_png)
                            is_image = True
            
            if is_image and img_path:
                if not os.path.isabs(img_path):
                    img_path = os.path.join(os.path.dirname(__file__), img_path)
                if os.path.exists(img_path):
                    try:
                        image_element.Source = load_bitmap_image_themed(img_path)
                        image_element.Visibility = Visibility.Visible
                        emoji_element.Visibility = Visibility.Collapsed
                    except Exception as ex:
                        log_debug(u"Failed to load image icon: {}".format(safe_str(ex)))
                        image_element.Visibility = Visibility.Collapsed
                        emoji_element.Text = u"❓"
                        emoji_element.Visibility = Visibility.Visible
                else:
                    image_element.Visibility = Visibility.Collapsed
                    is_image = False
            else:
                image_element.Visibility = Visibility.Collapsed
                
                # Intelligent emoji fallback for built-in commands with missing/default icons
                display_icon = icon_value
                if icon_type == "built_in" and (not display_icon or display_icon in [u"⚙️", u"➕", u"▶"]):
                    pool_item = getattr(self, "_button_to_pool_item", {}).get(btn_name)
                    item_name = pool_item.get("name") if pool_item else ""
                    display_icon = suggest_emoji_by_name(item_name)
                    
                emoji_element.Text = display_icon or u"⚙️"
                emoji_element.Visibility = Visibility.Visible
        except Exception as ex:
            log_debug(u"Failed to update UI for button {}: {}".format(btn_name, safe_str(ex)))

    def update_button_ui(self, slot_num, name, icon_type, icon_value):
        btn_name = SLOT_BUTTONS.get(slot_num)
        if btn_name:
            self.update_button_ui_by_name(btn_name, name, icon_type, icon_value)

    def setup_customizer_mode(self, show_window=True):
        self.customizer_mode = True
        self.cache_revit_context()
        
        # Subscribe to Revit InputManager events for drag and drop (including dropdowns/pulldowns)
        try:
            from System.Windows.Input import InputManager
            try:
                InputManager.Current.PostNotifyInput -= self.on_input_manager_pre_notify
            except:
                pass
            InputManager.Current.PostNotifyInput += self.on_input_manager_pre_notify
            log_debug("Subscribed to global WPF InputManager events for drag-and-drop.")
        except Exception as ad_ex:
            log_debug("Failed to subscribe to InputManager events: " + str(ad_ex))
            
        log_debug(u"Setting up customizer mode UI.")
        
        # Stop hook to prevent mouse events from interfering with customizer controls and DragMove
        try:
            existing_hook = System.AppDomain.CurrentDomain.GetData("RevitRadialMenuHook")
            if existing_hook:
                existing_hook.stop(close_active_window=False)
                log_debug(u"Hook stopped temporarily for Customizer mode.")
        except Exception as hook_ex:
            log_debug(u"Failed to stop hook during customizer setup: {}".format(safe_str(hook_ex)))
        
        # Skip ribbon icon extraction because fallback icons are already loaded on disk
        log_debug("Skipping ribbon icon extraction to prevent Revit native thread exceptions.")

        # Default to Customizer / Command Pool mode on entering setup
        self._move_mode_active = False
        
        # Set backgrounds of settings buttons for Customizer / Pool active
        from System.Windows.Media import SolidColorBrush, ColorConverter
        try:
            self.BtnCoreMove.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF55555C"))
            self.BtnCorePool.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF0083B0"))
            self.BtnCoreAppearance.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF55555C"))
            self.BtnCoreExit.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FFE53935"))
        except:
            pass
            
        # Setup separate customizer window
        if not hasattr(self, "customizer_window") or not self.customizer_window:
            try:
                # Remove from parent MainGrid first
                if self.CustomizerBorder.Parent:
                    self.MainGrid.Children.Remove(self.CustomizerBorder)
                
                from System.Windows import Window, WindowStyle, ResizeMode, Thickness
                from System.Windows.Shell import WindowChrome
                from System.Windows.Media import Brushes
                
                cust_win = Window()
                cust_win.Title = "Radial Menu Customizer"
                cust_win.Width = 820
                cust_win.Height = 680
                cust_win.WindowStyle = getattr(WindowStyle, "None")
                cust_win.ResizeMode = ResizeMode.CanResize
                cust_win.AllowsTransparency = True
                cust_win.Background = Brushes.Transparent
                cust_win.ShowInTaskbar = False
                cust_win.UseLayoutRounding = True
                
                chrome = WindowChrome()
                chrome.CaptionHeight = 0
                chrome.ResizeBorderThickness = Thickness(6)
                WindowChrome.SetWindowChrome(cust_win, chrome)
                
                # Copy resources so themes/styles work inside CustomizerBorder
                cust_win.Resources = self.Resources
                cust_win.Content = self.CustomizerBorder
                
                # Closing event redirect
                cust_win.Closing += lambda s, e: self.on_customizer_window_closing(s, e)
                
                # Position next to the radial menu safely
                import System.Windows.Forms as winforms
                from System.Windows import SystemParameters
                
                logical_screen_width = SystemParameters.PrimaryScreenWidth
                
                # Always center BOTH windows side-by-side when entering customizer mode
                total_width = 640 + 20 + 820  # radial + gap + customizer
                
                # Update Radial Menu (wheel) position
                self.Left = (logical_screen_width - total_width) / 2
                self.Top = (SystemParameters.PrimaryScreenHeight - 680) / 2
                
                # Update Customizer position (to the right of the radial menu)
                target_left = self.Left + 640 + 20
                
                cust_win.Left = target_left
                cust_win.Top = self.Top
                
                # Set owner
                try:
                    from System.Windows.Interop import WindowInteropHelper
                    revit_window_handle = HOST_APP.proc_window
                    if revit_window_handle:
                        helper = WindowInteropHelper(cust_win)
                        helper.Owner = revit_window_handle
                except Exception as owner_ex:
                    log_debug(u"Failed to set Customizer Window Owner: {}".format(safe_str(owner_ex)))
                
                self.customizer_window = cust_win
                try:
                    p = get_persistence()
                    if p:
                        p["customizer_window"] = cust_win
                except:
                    pass
                log_debug(u"Created separate Customizer Window successfully.")
            except Exception as win_ex:
                log_debug(u"Failed to create Customizer Window: {}".format(safe_str(win_ex)))
                
        from System.Windows import Visibility
        if show_window:
            self.CustomizerBorder.Visibility = Visibility.Visible
            if hasattr(self, "customizer_window") and self.customizer_window:
                try:
                    self.customizer_window.Show()
                    self.customizer_window.Activate()
                except:
                    pass
        else:
            self.CustomizerBorder.Visibility = Visibility.Collapsed
            if hasattr(self, "customizer_window") and self.customizer_window:
                try:
                    self.customizer_window.Hide()
                except:
                    pass
        
        # Disable edit panel by default on opening
        self.hide_edit_panel()
        
        # Select Tab 0 by default (Command Pool)
        self.CustomizerTabControl.SelectedIndex = 0
        
        # Load and populate settings from config
        self.update_settings_ui_from_config()
            
        # Wire up events once
        if not getattr(self, "_customizer_events_wired", False):
            try:
                # Wire up trigger mode combobox
                self.TriggerModeComboBox.SelectionChanged += self.on_trigger_mode_changed
                # Wire up use circles checkbox
                self.UseCirclesCheckBox.Checked += self.on_appearance_setting_changed
                self.UseCirclesCheckBox.Unchecked += self.on_appearance_setting_changed
                # Wire up enable logging checkbox
                self.EnableLoggingCheckBox.Checked += self.on_appearance_setting_changed
                self.EnableLoggingCheckBox.Unchecked += self.on_appearance_setting_changed
                # Wire up enable gestures checkbox
                if hasattr(self, "EnableGesturesCheckBox") and self.EnableGesturesCheckBox:
                    self.EnableGesturesCheckBox.Checked += self.on_appearance_setting_changed
                    self.EnableGesturesCheckBox.Unchecked += self.on_appearance_setting_changed
                # Wire up animation style combo
                self.AnimationStyleComboBox.SelectionChanged += self.on_animation_style_changed
                # Wire up appearance sliders
                self.DelaySlider.ValueChanged += self.on_appearance_setting_changed
                self.CoreRadiusSlider.ValueChanged += self.on_appearance_setting_changed
                self.PetalWidthSlider.ValueChanged += self.on_appearance_setting_changed
                self.RingSpacingSlider.ValueChanged += self.on_appearance_setting_changed
                self.SectorSpacingSlider.ValueChanged += self.on_appearance_setting_changed
                self.PetalOpacitySlider.ValueChanged += self.on_appearance_setting_changed
                
                # Wire up max angle sliders
                self.L2MaxAngleSlider.ValueChanged += self.on_appearance_setting_changed
                self.L3MaxAngleSlider.ValueChanged += self.on_appearance_setting_changed
                
                # Wire up theme combo
                self.ThemeComboBox.SelectionChanged += self.on_theme_changed
                
                # Wire up color scheme combo
                self.ColorSchemeComboBox.SelectionChanged += self.on_color_scheme_changed
                
                # Wire up hex colors
                self.HexNormalText.TextChanged += self.on_hex_color_changed
                self.HexBorderText.TextChanged += self.on_hex_color_changed
                self.HexHoverStartText.TextChanged += self.on_hex_color_changed
                self.HexHoverEndText.TextChanged += self.on_hex_color_changed
                
                # Connect search text changes
                self.PoolSearchBox.TextChanged += self.on_pool_search_changed
                
                # Connect pool tree selection and drag-drop
                self.PoolTreeView.SelectedItemChanged += self.on_pool_selection_changed
                self.PoolTreeView.PreviewMouseLeftButtonDown += self.on_pool_mouse_down
                self.PoolTreeView.PreviewMouseMove += self.on_pool_mouse_move
                self.PoolTreeView.AllowDrop = True
                self.PoolTreeView.DragOver += self.on_pool_tree_drag_over
                self.PoolTreeView.DragLeave += self.on_pool_tree_drag_leave
                self.PoolTreeView.Drop += self.on_pool_tree_drop
                
                # Wire up routed button clicks inside PoolTreeView (e.g. Row Delete trash bin)
                from System.Windows.Controls import Button as wpf_button
                from System.Windows import RoutedEventHandler
                self.PoolTreeView.AddHandler(wpf_button.ClickEvent, RoutedEventHandler(self.on_pool_list_button_click))
                
                # Connect pool edit panel buttons
                self.BtnPoolItemSave.Click += self.on_save_edit_clicked
                self.BtnPoolItemCancel.Click += self.on_cancel_edit_clicked
                
                # Connect add buttons
                self.BtnAddPoolItem.Click += self.on_add_pool_item_clicked
                
                self.SearchBox.TextChanged += self.on_search_changed
                self.BtnPickerAddCommand.Click += self.on_picker_add_command_clicked
                self.BtnPickerCancel.Click += self.on_picker_cancel_clicked
                
                # Connect EditClassSearchTextChanged
                self.EditClassSearch.TextChanged += self.on_context_class_search_changed
                
                # Connect Selection/Pre-highlighted CheckBoxes
                self.EditChkPrehighlighted.Checked += self.on_selection_checkbox_changed
                self.EditChkPrehighlighted.Unchecked += self.on_selection_checkbox_changed
                self.EditChkSelection.Checked += self.on_selection_checkbox_changed
                self.EditChkSelection.Unchecked += self.on_selection_checkbox_changed
                
                # Connect window dragging via Title
                self.TxtPanelTitle.MouseLeftButtonDown += self.on_customizer_mouse_down
                
                # Connect icon picker overlay controls
                self.BtnSelectIcon.Click += self.on_select_icon_clicked
                self.IconPickerSearchBox.TextChanged += self.on_icon_picker_search_changed
                self.BtnIconPickerSelect.Click += self.on_icon_picker_select_clicked
                self.BtnIconPickerCancel.Click += self.on_icon_picker_cancel_clicked
                self.IconPickerListBox.MouseDoubleClick += self.on_icon_picker_double_click
                
                self._customizer_events_wired = True
                log_debug(u"Wired up customizer events successfully.")
            except Exception as ex:
                log_debug(u"Error wiring up customizer events: {}".format(safe_str(ex)))
            
        # Load pool into list
        self.load_pool_list()
        
        # Load pyRevit commands
        self.load_pyrevit_commands()
        
        # Update core buttons visibility
        self.update_core_buttons_visibility()

    def on_context_changed(self, sender, args):
        try:
            idx = self.ContextComboBox.SelectedIndex
            mapping = {0: "default", 1: "pipes", 2: "ducts", 3: "walls", 4: "dimensions"}
            new_ctx = mapping.get(idx, "default")
            if new_ctx != self.active_context:
                log_debug(u"Changing customizer context from '{}' to '{}'.".format(self.active_context, new_ctx))
                self.active_context = new_ctx
                self.load_layout_configuration()
        except Exception as ex:
            log_debug(u"Error in on_context_changed: {}".format(safe_str(ex)))

    def get_sector_path_parallel(self, cx, cy, r_in, r_out, angle_center, num_sectors, gap_width):
        import math
        # If there is only one sector, draw a full concentric ring (donut) to avoid collapsed degenerate arcs
        if num_sectors == 1:
            path = "M {0:.2f},{1:.2f} A {2},{2} 0 1,1 {0:.2f},{3:.2f} A {2},{2} 0 1,1 {0:.2f},{1:.2f} M {0:.2f},{4:.2f} A {5},{5} 0 1,0 {0:.2f},{6:.2f} A {5},{5} 0 1,0 {0:.2f},{4:.2f} Z".format(
                cx, cy - r_out, r_out, cy + r_out, cy - r_in, r_in, cy + r_in
            )
            return path

        # Full sector span in degrees
        span = 360.0 / float(num_sectors)
        theta1 = angle_center - span / 2.0
        theta2 = angle_center + span / 2.0
        
        rad1 = theta1 * math.pi / 180.0
        rad2 = theta2 * math.pi / 180.0
        
        # Boundary radial unit vectors
        d1_x = math.cos(rad1)
        d1_y = math.sin(rad1)
        d2_x = math.cos(rad2)
        d2_y = math.sin(rad2)
        
        offset = float(gap_width) / 2.0
        
        # Perpendicular unit vectors pointing inside the sector
        n1_x = -d1_y
        n1_y = d1_x
        
        n2_x = d2_y
        n2_y = -d2_x
        
        # Solve for t on inner/outer circles
        if r_in > offset:
            t_in = math.sqrt(r_in * r_in - offset * offset)
        else:
            t_in = 0.0
            
        if r_out > offset:
            t_out = math.sqrt(r_out * r_out - offset * offset)
        else:
            t_out = 0.0
            
        # Calculate offset points
        p_in1_x = cx + offset * n1_x + t_in * d1_x
        p_in1_y = cy + offset * n1_y + t_in * d1_y
        
        p_out1_x = cx + offset * n1_x + t_out * d1_x
        p_out1_y = cy + offset * n1_y + t_out * d1_y
        
        p_in2_x = cx + offset * n2_x + t_in * d2_x
        p_in2_y = cy + offset * n2_y + t_in * d2_y
        
        p_out2_x = cx + offset * n2_x + t_out * d2_x
        p_out2_y = cy + offset * n2_y + t_out * d2_y
        
        # WPF path format
        path = "M {0:.2f},{1:.2f} L {2:.2f},{3:.2f} A {4},{4} 0 0,1 {5:.2f},{6:.2f} L {7:.2f},{8:.2f} A {9},{9} 0 0,0 {10:.2f},{11:.2f} Z".format(
            p_in1_x, p_in1_y, p_out1_x, p_out1_y, r_out, p_out2_x, p_out2_y, p_in2_x, p_in2_y, r_in, p_in1_x, p_in1_y
        )
        return path

    def get_text_pos(self, cx, cy, r_in, r_out, angle_center, w=80, h=70, btn_name=None):
        import math
        rad = angle_center * math.pi / 180.0
        r_mid = (r_in + r_out) / 2.0
        
        x_c = cx + r_mid * math.cos(rad)
        y_c = cy + r_mid * math.sin(rad)
        
        left = x_c - w / 2.0
        top = y_c - 12.0  # Default aligns icon Y-center to y_c
        
        norm_angle = angle_center % 360.0
        is_top_half = (185.0 <= norm_angle <= 355.0)
        
        # Only adjust top if it's a petal button in the top half (where layout is swapped)
        if is_top_half and btn_name and btn_name.startswith("BtnL"):
            label = getattr(self, btn_name + "Label", None)
            lines = 1
            if label and hasattr(label, "Text") and label.Text:
                lines = len(label.Text.split("\n"))
            
            # Approximate height of the label (FontSize 9.0 -> ~13px per line + padding)
            label_height = lines * 13.0 + 3.0
            
            # Shift the StackPanel UP by the label's height so the icon remains at y_c - 12.0
            top = top - label_height
            
        return left, top

    def update_panel_layout(self, btn_name, angle_center):
        try:
            norm_angle = angle_center % 360.0
            is_top_half = (185.0 <= norm_angle <= 355.0)
            panel = getattr(self, btn_name + "Panel", None)
            if panel and hasattr(panel, "Children") and panel.Children.Count >= 2:
                img = getattr(self, btn_name + "Image", None)
                grid_elem = img.Parent if img else None
                label_border = getattr(self, btn_name + "LabelBorder", None)
                
                if grid_elem and label_border and grid_elem in panel.Children and label_border in panel.Children:
                    grid_idx = panel.Children.IndexOf(grid_elem)
                    label_idx = panel.Children.IndexOf(label_border)
                    
                    if is_top_half and label_idx > grid_idx:
                        panel.Children.Remove(label_border)
                        panel.Children.Insert(grid_idx, label_border)
                    elif not is_top_half and label_idx < grid_idx:
                        panel.Children.Remove(label_border)
                        panel.Children.Insert(grid_idx + 1, label_border)
        except Exception as ex:
            log_debug("Error updating panel layout for {}: {}".format(btn_name, safe_str(ex)))

    def animate_gap(self, level, target_idx):
        """Animate petals on the specified level to open a gap before target_idx."""
        try:
            if not getattr(self, "_move_mode_active", False):
                return
                
            # If nothing changed, do not restart animations to avoid stuttering
            current_lvl = getattr(self, "_current_gap_level", None)
            current_idx = getattr(self, "_current_gap_idx", None)
            if current_lvl == level and current_idx == target_idx:
                return
                
            self._current_gap_level = level
            self._current_gap_idx = target_idx
            
            n1, n2, n3 = getattr(self, "_level_counts", (0, 0, 0))
            if level == 1:
                n = max(1, n1)
                prefix = "BtnL1_"
            elif level == 2:
                n = n2
                prefix = "BtnL2_"
            elif level == 3:
                n = n3
                prefix = "BtnL3_"
            else:
                return
                
            if n <= 0:
                return
                
            gap_angle = 360.0 / float(n + 1)
            if gap_angle > 40.0:
                gap_angle = 40.0
                
            half_gap = gap_angle / 2.0
            
            from System.Windows.Media.Animation import DoubleAnimation, CubicEase, EasingMode
            from System import TimeSpan
            from System.Windows.Media import TransformGroup, RotateTransform
            
            ease = CubicEase()
            ease.EasingMode = EasingMode.EaseOut
            
            for idx in range(1, n + 1):
                btn_name = "{}{}".format(prefix, idx)
                btn = getattr(self, btn_name, None)
                if not btn or btn.Visibility != System.Windows.Visibility.Visible:
                    continue
                    
                if target_idx is not None:
                    if level == 1:
                        diff = idx - target_idx
                        if diff < -n / 2.0:
                            diff += n
                        elif diff >= n / 2.0:
                            diff -= n
                            
                        if diff >= 0:
                            target_rot = half_gap
                        else:
                            target_rot = -half_gap
                    else:
                        if idx >= target_idx:
                            target_rot = half_gap
                        else:
                            target_rot = -half_gap
                else:
                    target_rot = 0.0
                    
                rt = None
                group = btn.RenderTransform
                if isinstance(group, TransformGroup):
                    for child in group.Children:
                        if isinstance(child, RotateTransform):
                            rt = child
                            break
                    if not rt:
                        rt = RotateTransform(0.0)
                        group.Children.Add(rt)
                else:
                    group = TransformGroup()
                    if btn.RenderTransform:
                        group.Children.Add(btn.RenderTransform)
                    rt = RotateTransform(0.0)
                    group.Children.Add(rt)
                    btn.RenderTransform = group
                    
                da = DoubleAnimation(target_rot, TimeSpan.FromMilliseconds(200))
                da.EasingFunction = ease
                rt.BeginAnimation(RotateTransform.AngleProperty, da)
                
        except Exception as ex:
            log_debug("Error in animate_gap: " + str(ex))

    def clear_gap(self):
        """Reset all petal rotation animations to 0."""
        try:
            self._current_gap_level = None
            self._current_gap_idx = None
            
            from System.Windows.Media.Animation import DoubleAnimation, CubicEase, EasingMode
            from System import TimeSpan
            from System.Windows.Media import TransformGroup, RotateTransform
            
            ease = CubicEase()
            ease.EasingMode = EasingMode.EaseOut
            
            for prefix in ["BtnL1_", "BtnL2_", "BtnL3_"]:
                for idx in range(1, 11):
                    btn_name = "{}{}".format(prefix, idx)
                    btn = getattr(self, btn_name, None)
                    if not btn:
                        continue
                        
                    group = btn.RenderTransform
                    if isinstance(group, TransformGroup):
                        for child in group.Children:
                            if isinstance(child, RotateTransform):
                                da = DoubleAnimation(0.0, TimeSpan.FromMilliseconds(200))
                                da.EasingFunction = ease
                                child.BeginAnimation(RotateTransform.AngleProperty, da)
                                break
        except Exception as ex:
            log_debug("Error in clear_gap: " + str(ex))

    def on_window_preview_drag_over(self, sender, args):
        try:
            if not getattr(self, "customizer_mode", False) or not getattr(self, "_move_mode_active", False):
                return
            if not args.Data.GetDataPresent("PyRevitCommandJSON"):
                return
                
            import System.Windows
            pos = args.GetPosition(self)
            
            # Show and update custom drag preview
            try:
                cmd_json = args.Data.GetData("PyRevitCommandJSON")
                import json
                cmd_data = json.loads(cmd_json)
                self.update_drag_preview(pos.X, pos.Y, cmd_data.get("icon_path"), cmd_data.get("icon"))
            except Exception as preview_ex:
                pass

            level, slot = self.get_slot_from_coordinates(pos.X, pos.Y)
            if level is not None and slot is not None:
                target_btn = SLOT_BUTTONS.get(slot)
                if target_btn:
                    target_idx = int(target_btn[6:])
                    self.animate_gap(level, target_idx)
                    args.Effects = System.Windows.DragDropEffects.Copy
                    args.Handled = True
            else:
                self.clear_gap()
                args.Effects = getattr(System.Windows.DragDropEffects, "None")
                args.Handled = True
        except Exception as ex:
            log_debug("Error in on_window_preview_drag_over: " + str(ex))

    def on_window_preview_drop(self, sender, args):
        try:
            if not getattr(self, "customizer_mode", False) or not getattr(self, "_move_mode_active", False):
                return
            if args.Data.GetDataPresent("PyRevitCommandJSON"):
                import System.Windows
                pos = args.GetPosition(self)
                level, slot = self.get_slot_from_coordinates(pos.X, pos.Y)
                log_debug(u"on_window_preview_drop: pos=({:.1f}, {:.1f}), level={}, slot={}".format(pos.X, pos.Y, level, slot))
                self.clear_gap()
                if level is not None and slot is not None:
                    cmd_json = args.Data.GetData("PyRevitCommandJSON")
                    import json
                    cmd_data = json.loads(cmd_json)
                    log_debug(u"Dropped command '{}' via window onto slot {}.".format(cmd_data["name"], slot))
                    self.assign_command_to_slot_data(slot, cmd_data)
                    args.Handled = True
            else:
                self.clear_gap()
        except Exception as ex:
            log_debug("Error in on_window_preview_drop: " + str(ex))
        finally:
            self.hide_drag_preview()

    def update_radial_geometry(self):
        try:
            from System.Windows import Visibility, CornerRadius
            from System.Windows.Controls import Canvas
            from System.Windows.Media import TransformGroup, RotateTransform
            
            # Reset all petal transforms, animations and opacities
            self._current_gap_level = None
            self._current_gap_idx = None
            for prefix in ["BtnL1_", "BtnL2_", "BtnL3_"]:
                for idx in range(1, 11):
                    btn = getattr(self, "{}{}".format(prefix, idx), None)
                    if btn:
                        btn.Opacity = 1.0
                        group = btn.RenderTransform
                        if isinstance(group, TransformGroup):
                            for child in group.Children:
                                if isinstance(child, RotateTransform):
                                    child.BeginAnimation(RotateTransform.AngleProperty, None)
                                    child.Angle = 0.0

            settings = self._config_data.get("settings", dict(DEFAULT_SETTINGS))
            core_radius = float(settings.get("core_radius", 45))
            petal_width = float(settings.get("petal_width", 60))
            ring_gap = float(settings.get("ring_gap", 5))
            gap_width = float(settings.get("gap_width", 3))
            l2_max_angle = float(settings.get("l2_max_angle", 90))
            l3_max_angle = float(settings.get("l3_max_angle", 90))
            
            # Get petal counts from pool system
            n1, n2, n3 = getattr(self, "_level_counts", (0, 0, 0))
            n1 = max(1, n1)  # Level 1 must have at least 1 petal
            
            log_debug(u"update_radial_geometry: core_r={}, petal_w={}, ring_g={}, gap={}, counts=({},{},{})".format(
                core_radius, petal_width, ring_gap, gap_width, n1, n2, n3
            ))
            
            # Ring radii calculations
            cx, cy = 320.0, 320.0
            
            # Level 1
            r1_in = core_radius + ring_gap
            r1_out = r1_in + petal_width
            
            # Level 2
            r2_in = r1_out + ring_gap
            r2_out = r2_in + petal_width
            
            # Level 3
            r3_in = r2_out + ring_gap
            r3_out = r3_in + petal_width
            
            use_circles = bool(settings.get("use_circles", False))
            
            def get_petal_or_circle_path(r_in, r_out, angle, n_eff):
                if use_circles:
                    r_mid = (r_in + r_out) / 2.0
                    rad = angle * math.pi / 180.0
                    mx = cx + r_mid * math.cos(rad)
                    my = cy + r_mid * math.sin(rad)
                    circle_r = (r_out - r_in) / 2.0 - 2.0
                    if circle_r < 5.0:
                        circle_r = 5.0
                    return "M {0:.2f},{1:.2f} a {2:.2f},{2:.2f} 0 1,0 {3:.2f},0 a {2:.2f},{2:.2f} 0 1,0 -{3:.2f},0 Z".format(
                        mx - circle_r, my, circle_r, 2.0 * circle_r
                    )
                else:
                    return self.get_sector_path_parallel(cx, cy, r_in, r_out, angle, n_eff, gap_width)
            
            # Update Center Core background size and position
            self.CenterCoreBg.Width = core_radius * 2.0
            self.CenterCoreBg.Height = core_radius * 2.0
            self.CenterCoreBg.CornerRadius = CornerRadius(core_radius)
            Canvas.SetLeft(self.CenterCoreBg, cx - core_radius)
            Canvas.SetTop(self.CenterCoreBg, cy - core_radius)
            
            # Update Center core buttons positioning and geometries
            # Normal Mode: 2 sectors (num_sectors=2, angle_center=180.0 and 0.0)
            path_settings = self.get_sector_path_parallel(cx, cy, 0.0, core_radius, 180.0, 2, 1.5)
            path_close = self.get_sector_path_parallel(cx, cy, 0.0, core_radius, 0.0, 2, 1.5)
            self.BtnCoreSettings.Tag = path_settings
            self.BtnCoreClose.Tag = path_close
            
            # Position panels for normal mode core (left, right)
            left_s, top_s = self.get_text_pos(cx, cy, 0.0, core_radius, 180.0, 50, 40)
            Canvas.SetLeft(self.BtnCoreSettingsPanel, left_s)
            Canvas.SetTop(self.BtnCoreSettingsPanel, top_s)
            
            left_c, top_c = self.get_text_pos(cx, cy, 0.0, core_radius, 0.0, 50, 40)
            Canvas.SetLeft(self.BtnCoreClosePanel, left_c)
            Canvas.SetTop(self.BtnCoreClosePanel, top_c)
            
            # Settings Mode: 4 sectors (Move=225, Pool=315, Appearance=45, Exit=135)
            path_move = self.get_sector_path_parallel(cx, cy, 0.0, core_radius, 225.0, 4, 1.5)
            path_pool = self.get_sector_path_parallel(cx, cy, 0.0, core_radius, 315.0, 4, 1.5)
            path_appearance = self.get_sector_path_parallel(cx, cy, 0.0, core_radius, 45.0, 4, 1.5)
            path_exit = self.get_sector_path_parallel(cx, cy, 0.0, core_radius, 135.0, 4, 1.5)
            
            self.BtnCoreMove.Tag = path_move
            self.BtnCorePool.Tag = path_pool
            self.BtnCoreAppearance.Tag = path_appearance
            self.BtnCoreExit.Tag = path_exit
            
            # Position panels for settings mode core
            l_move, t_move = self.get_text_pos(cx, cy, 0.0, core_radius, 225.0, 50, 40)
            Canvas.SetLeft(self.BtnCoreMovePanel, l_move)
            Canvas.SetTop(self.BtnCoreMovePanel, t_move)
            
            l_pool, t_pool = self.get_text_pos(cx, cy, 0.0, core_radius, 315.0, 50, 40)
            Canvas.SetLeft(self.BtnCorePoolPanel, l_pool)
            Canvas.SetTop(self.BtnCorePoolPanel, t_pool)
            
            l_app, t_app = self.get_text_pos(cx, cy, 0.0, core_radius, 45.0, 50, 40)
            Canvas.SetLeft(self.BtnCoreAppearancePanel, l_app)
            Canvas.SetTop(self.BtnCoreAppearancePanel, t_app)
            
            l_exit, t_exit = self.get_text_pos(cx, cy, 0.0, core_radius, 135.0, 50, 40)
            Canvas.SetLeft(self.BtnCoreExitPanel, l_exit)
            Canvas.SetTop(self.BtnCoreExitPanel, t_exit)
            
            # Calculate effective sector counts with max_angle clamping for L2/L3
            # L1 always uses full 360 degrees
            n1_eff = n1
            
            # For L2/L3, if max_angle limits the arc, compute virtual sector count
            # The virtual count determines how wide each petal is drawn
            if n2 > 0:
                natural_span = 360.0 / float(n2)
                if natural_span > l2_max_angle:
                    n2_eff = max(n2, int(360.0 / l2_max_angle))
                else:
                    n2_eff = n2
            else:
                n2_eff = 0
                
            if n3 > 0:
                natural_span = 360.0 / float(n3)
                if natural_span > l3_max_angle:
                    n3_eff = max(n3, int(360.0 / l3_max_angle))
                else:
                    n3_eff = n3
            else:
                n3_eff = 0
            
            # --- LEVEL 1 ---
            l1_angles = {}
            for idx in range(1, 11):
                btn_name = "BtnL1_{}".format(idx)
                btn = getattr(self, btn_name, None)
                if not btn:
                    continue
                
                if idx <= n1 and n1_eff > 0:
                    angle = 270.0 + (idx - 1) * (360.0 / float(n1_eff))
                    angle = angle % 360.0
                    
                    path_str = get_petal_or_circle_path(r1_in, r1_out, angle, n1_eff)
                    btn.Tag = path_str
                    
                    panel_name = "BtnL1_{}Panel".format(idx)
                    panel = getattr(self, panel_name, None)
                    if panel:
                        left, top = self.get_text_pos(cx, cy, r1_in, r1_out, angle, btn_name=btn_name)
                        Canvas.SetLeft(panel, left)
                        Canvas.SetTop(panel, top)
                        self.update_panel_layout(btn_name, angle)
                    
                    btn.Visibility = Visibility.Visible
                    
                    pool_item = getattr(self, "_button_to_pool_item", {}).get(btn_name)
                    if pool_item:
                        l1_angles[pool_item.get("id")] = angle
                else:
                    btn.Visibility = Visibility.Collapsed

            # Resolve Parent L1 Angle
            parent_l1_angle = 270.0
            if getattr(self, "_active_l1_parent", None) and self._active_l1_parent in l1_angles:
                parent_l1_angle = l1_angles[self._active_l1_parent]

            # --- LEVEL 2 ---
            l2_angles = {}
            for idx in range(1, 11):
                btn_name = "BtnL2_{}".format(idx)
                btn = getattr(self, btn_name, None)
                if not btn:
                    continue
                
                if idx <= n2 and n2_eff > 0:
                    offset = (idx - 1 - (n2 - 1) / 2.0) * (360.0 / float(n2_eff))
                    angle = (parent_l1_angle + offset) % 360.0
                    
                    path_str = get_petal_or_circle_path(r2_in, r2_out, angle, n2_eff)
                    btn.Tag = path_str
                    
                    panel_name = "BtnL2_{}Panel".format(idx)
                    panel = getattr(self, panel_name, None)
                    if panel:
                        left, top = self.get_text_pos(cx, cy, r2_in, r2_out, angle, btn_name=btn_name)
                        Canvas.SetLeft(panel, left)
                        Canvas.SetTop(panel, top)
                        self.update_panel_layout(btn_name, angle)
                    
                    btn.Visibility = Visibility.Visible
                    
                    pool_item = getattr(self, "_button_to_pool_item", {}).get(btn_name)
                    if pool_item:
                        l2_angles[pool_item.get("id")] = angle
                else:
                    btn.Visibility = Visibility.Collapsed

            # Resolve Parent L2 Angle
            parent_l2_angle = 270.0
            if getattr(self, "_active_l2_parent", None) and self._active_l2_parent in l2_angles:
                parent_l2_angle = l2_angles[self._active_l2_parent]

            # --- LEVEL 3 ---
            for idx in range(1, 11):
                btn_name = "BtnL3_{}".format(idx)
                btn = getattr(self, btn_name, None)
                if not btn:
                    continue
                
                if idx <= n3 and n3_eff > 0:
                    offset = (idx - 1 - (n3 - 1) / 2.0) * (360.0 / float(n3_eff))
                    angle = (parent_l2_angle + offset) % 360.0
                    
                    path_str = get_petal_or_circle_path(r3_in, r3_out, angle, n3_eff)
                    btn.Tag = path_str
                    
                    panel_name = "BtnL3_{}Panel".format(idx)
                    panel = getattr(self, panel_name, None)
                    if panel:
                        left, top = self.get_text_pos(cx, cy, r3_in, r3_out, angle, btn_name=btn_name)
                        Canvas.SetLeft(panel, left)
                        Canvas.SetTop(panel, top)
                        self.update_panel_layout(btn_name, angle)
                    
                    btn.Visibility = Visibility.Visible
                else:
                    btn.Visibility = Visibility.Collapsed
                        
            # Apply color themes
            self.apply_theme_colors()
            
        except Exception as ex:
            log_debug(u"Error in update_radial_geometry: {}".format(safe_str(ex)))

    def apply_theme_colors(self):
        from System.Windows.Media import ColorConverter, SolidColorBrush
        try:
            settings = self._config_data.get("settings", dict(DEFAULT_SETTINGS))
            
            # Check for color_scheme setting first, which takes precedence
            color_scheme = settings.get("color_scheme", "auto")
            
            if color_scheme == "auto":
                # Check if theme API is supported
                is_theme_api_supported = False
                try:
                    from Autodesk.Revit.UI import UIThemeManager
                    is_theme_api_supported = True
                except:
                    pass
                
                if is_theme_api_supported:
                    theme_colors = get_revit_theme_colors()
                    color_normal = theme_colors["color_normal"]
                    color_border = theme_colors["color_border"]
                    color_hover_start = theme_colors["color_hover_start"]
                    color_hover_end = theme_colors["color_hover_end"]
                else:
                    # Fallback to Light colors in Revit 2023 (since Revit 2023 is light)
                    color_normal = "#F2F0F0F0"
                    color_border = "#20000000"
                    color_hover_start = "#FF4A90E2"
                    color_hover_end = "#FF1D3A56"

            elif color_scheme == "dark":
                theme_colors = THEMES["pyRevit Dark"]
                color_normal = theme_colors["color_normal"]
                color_border = theme_colors["color_border"]
                color_hover_start = theme_colors["color_hover_start"]
                color_hover_end = theme_colors["color_hover_end"]
            elif color_scheme == "light":
                color_normal = "#F2F0F0F0"
                color_border = "#20000000"
                color_hover_start = "#FF4A90E2"
                color_hover_end = "#FF1D3A56"
            else:
                # Fallback to theme or manual values
                theme_name = settings.get("theme", "Revit Theme")
                if theme_name == "Revit Theme":
                    theme_colors = get_revit_theme_colors()
                    color_normal = theme_colors["color_normal"]
                    color_border = theme_colors["color_border"]
                    color_hover_start = theme_colors["color_hover_start"]
                    color_hover_end = theme_colors["color_hover_end"]
                else:
                    color_normal = settings.get("color_normal", "#F21E1E24")
                    color_border = settings.get("color_border", "#25FFFFFF")
                    color_hover_start = settings.get("color_hover_start", "#FF0083B0")
                    color_hover_end = settings.get("color_hover_end", "#FF004B66")
            
            # Apply user-defined petal opacity to the normal background color
            petal_opacity = int(settings.get("petal_opacity", 95))
            color_normal = apply_opacity_to_hex_color(color_normal, petal_opacity)
            
            self.Resources["NormalColor"] = ColorConverter.ConvertFromString(color_normal)
            self.Resources["BorderColor"] = ColorConverter.ConvertFromString(color_border)
            self.Resources["HoverStartColor"] = ColorConverter.ConvertFromString(color_hover_start)
            self.Resources["HoverEndColor"] = ColorConverter.ConvertFromString(color_hover_end)
            
            # Dynamically compute the contrast text color for the hover state
            hover_text_color = get_contrast_foreground(color_hover_start)
            self.Resources["HoverTextColor"] = SolidColorBrush(ColorConverter.ConvertFromString(hover_text_color))
            
            # Check if resolved theme is dark or light based on normal color luminance
            normal_lum = get_luminance(color_normal)
            is_light = (normal_lum > 0.5)
            self._is_light = is_light
            
            global _IS_MENU_DARK
            _IS_MENU_DARK = not is_light
            
            if is_light:
                c_bg = "#FFF5F5F7"         # Window Background
                c_panel_bg = "#FFE5E5EA"    # Edit Panel Background (distinct light-gray)
                c_text = "#FF1E1E24"        # Main Text
                c_sec_text = "#FF55555C"    # Secondary Text (clear, not disabled-looking)
                c_input_bg = "#FFFFFFFF"    # Textbox / Input Background (crisp white!)
                c_input_text = "#FF1E1E24"
                c_border_brush = "#FFCCCCCC"
                c_highlight = "#FF0083B0"
            else:
                c_bg = "#FF1E1E24"
                c_panel_bg = "#FF2D2D30"    # Edit Panel Background
                c_text = "#FFFFFFFF"
                c_sec_text = "#FFAAAAAA"
                c_input_bg = "#FF121212"    # Input Background (darker than panel background)
                c_input_text = "#FFFFFFFF"
                c_border_brush = "#FF3E3E42"
                c_highlight = "#FF00E5FF"
                
            self.Resources["CustomizerBg"] = SolidColorBrush(ColorConverter.ConvertFromString(c_bg))
            self.Resources["CustomizerPanelBg"] = SolidColorBrush(ColorConverter.ConvertFromString(c_panel_bg))
            self.Resources["CustomizerText"] = SolidColorBrush(ColorConverter.ConvertFromString(c_text))
            self.Resources["CustomizerSecText"] = SolidColorBrush(ColorConverter.ConvertFromString(c_sec_text))
            self.Resources["CustomizerInputBg"] = SolidColorBrush(ColorConverter.ConvertFromString(c_input_bg))
            self.Resources["CustomizerInputText"] = SolidColorBrush(ColorConverter.ConvertFromString(c_input_text))
            self.Resources["CustomizerBorderBrush"] = SolidColorBrush(ColorConverter.ConvertFromString(c_border_brush))
            self.Resources["CustomizerHighlight"] = SolidColorBrush(ColorConverter.ConvertFromString(c_highlight))
        except Exception as ex:
            log_debug(u"Error applying theme colors: {}".format(safe_str(ex)))

    def on_color_scheme_changed(self, sender, args):
        if getattr(self, "_updating_ui_elements", False):
            return
        try:
            idx = self.ColorSchemeComboBox.SelectedIndex
            mapping = {
                0: "dark",
                1: "light",
                2: "auto"
            }
            color_scheme = mapping.get(idx, "dark")
            
            # Read and update settings
            settings = self._config_data.get("settings", {})
            settings["color_scheme"] = color_scheme
            
            # Update active colors based on the chosen scheme
            if color_scheme == "dark":
                theme_colors = THEMES["pyRevit Dark"]
                settings["color_normal"] = theme_colors["color_normal"]
                settings["color_border"] = theme_colors["color_border"]
                settings["color_hover_start"] = theme_colors["color_hover_start"]
                settings["color_hover_end"] = theme_colors["color_hover_end"]
            elif color_scheme == "light":
                settings["color_normal"] = "#F2F0F0F0"
                settings["color_border"] = "#20000000"
                settings["color_hover_start"] = "#FF4A90E2"
                settings["color_hover_end"] = "#FF1D3A56"
            elif color_scheme == "auto":
                theme_colors = get_revit_theme_colors()
                settings["color_normal"] = theme_colors["color_normal"]
                settings["color_border"] = theme_colors["color_border"]
                settings["color_hover_start"] = theme_colors["color_hover_start"]
                settings["color_hover_end"] = theme_colors["color_hover_end"]
                
            self.apply_theme_colors()
            self.update_radial_geometry()
            self.queue_save_config()
        except Exception as ex:
            log_debug(u"Error in on_color_scheme_changed: {}".format(safe_str(ex)))


    def on_appearance_setting_changed(self, sender, args):
        if not hasattr(self, "_config_data") or not self._config_data:
            return
            
        if getattr(self, "_updating_ui_elements", False):
            return
            
        try:
            settings = self._config_data.get("settings", {})
            
            settings["use_circles"] = bool(self.UseCirclesCheckBox.IsChecked)
            settings["enable_logging"] = bool(self.EnableLoggingCheckBox.IsChecked)
            if hasattr(self, "EnableGesturesCheckBox") and self.EnableGesturesCheckBox:
                settings["enable_gestures"] = bool(self.EnableGesturesCheckBox.IsChecked)
                global _enable_gestures
                _enable_gestures = settings["enable_gestures"]
            
            settings["hold_delay_ms"] = int(self.DelaySlider.Value)
            self.DelayValueText.Text = u"{} ms".format(settings["hold_delay_ms"])
            global _hold_delay_ms
            _hold_delay_ms = settings["hold_delay_ms"]
            
            settings["core_radius"] = int(self.CoreRadiusSlider.Value)
            self.CoreRadiusValueText.Text = u"{} px".format(settings["core_radius"])
            
            settings["petal_width"] = int(self.PetalWidthSlider.Value)
            self.PetalWidthValueText.Text = u"{} px".format(settings["petal_width"])
            
            settings["ring_gap"] = int(self.RingSpacingSlider.Value)
            self.RingSpacingValueText.Text = u"{} px".format(settings["ring_gap"])
            
            settings["gap_width"] = float(self.SectorSpacingSlider.Value)
            self.SectorSpacingValueText.Text = u"{:.1f} px".format(settings["gap_width"])
            
            settings["petal_opacity"] = int(self.PetalOpacitySlider.Value)
            self.PetalOpacityValueText.Text = u"{}%".format(settings["petal_opacity"])
            
            settings["l2_max_angle"] = int(self.L2MaxAngleSlider.Value)
            self.L2MaxAngleValueText.Text = u"{}°".format(settings["l2_max_angle"])
            
            settings["l3_max_angle"] = int(self.L3MaxAngleSlider.Value)
            self.L3MaxAngleValueText.Text = u"{}°".format(settings["l3_max_angle"])
                
            self.update_radial_geometry()
            self.queue_save_config()
        except Exception as ex:
            log_debug(u"Error in on_appearance_setting_changed: {}".format(safe_str(ex)))

    def on_trigger_mode_changed(self, sender, args):
        if getattr(self, "_updating_ui_elements", False):
            return
            
        try:
            settings = self._config_data.get("settings", {})
            mode_idx = self.TriggerModeComboBox.SelectedIndex
            mode_name = "hold" if mode_idx == 0 else "double_click"
            
            settings["trigger_mode"] = mode_name
            
            global _trigger_mode
            _trigger_mode = mode_name
            
            # Enable/disable DelaySlider depending on trigger mode
            if mode_name == "double_click":
                self.DelaySlider.IsEnabled = False
                self.DelayValueText.Foreground = self.Resources["CustomizerSecText"]
            else:
                self.DelaySlider.IsEnabled = True
                self.DelayValueText.Foreground = self.Resources["CustomizerHighlight"]
                
            self.queue_save_config()
        except Exception as ex:
            log_debug(u"Error in on_trigger_mode_changed: {}".format(safe_str(ex)))

    def on_animation_style_changed(self, sender, args):
        if getattr(self, "_updating_ui_elements", False):
            return
        try:
            settings = self._config_data.get("settings", {})
            idx = self.AnimationStyleComboBox.SelectedIndex
            mapping = {0: "fade", 1: "pop", 2: "fan"}
            settings["animation_style"] = mapping.get(idx, "fade")
            self.queue_save_config()
        except Exception as ex:
            log_debug("Error in on_animation_style_changed: " + str(ex))

    def on_theme_changed(self, sender, args):
        if getattr(self, "_updating_ui_elements", False):
            return
            
        try:
            theme_idx = self.ThemeComboBox.SelectedIndex
            mapping = {
                0: "Revit Theme",
                1: "pyRevit Dark",
                2: "Neon Fusion",
                3: "Classic Blue",
                4: "Forest Green",
                5: "Cyberpunk",
                6: "Custom Theme"
            }
            theme_name = mapping.get(theme_idx, "Revit Theme")
            
            if theme_name != "Custom Theme" and (theme_name in THEMES or theme_name == "Revit Theme"):
                if theme_name == "Revit Theme":
                    theme_colors = get_revit_theme_colors()
                else:
                    theme_colors = THEMES[theme_name]
                    
                settings = self._config_data["settings"]
                settings["theme"] = theme_name
                settings["color_normal"] = theme_colors["color_normal"]
                settings["color_border"] = theme_colors["color_border"]
                settings["color_hover_start"] = theme_colors["color_hover_start"]
                settings["color_hover_end"] = theme_colors["color_hover_end"]
                
                self.update_settings_ui_from_config()
                self.apply_theme_colors()
                self.queue_save_config()
        except Exception as ex:
            log_debug(u"Error in on_theme_changed: {}".format(safe_str(ex)))

    def on_hex_color_changed(self, sender, args):
        if getattr(self, "_updating_ui_elements", False):
            return
            
        try:
            settings = self._config_data["settings"]
            
            normal = parse_hex_color(self.HexNormalText.Text, settings.get("color_normal", "#F21E1E24"))
            border = parse_hex_color(self.HexBorderText.Text, settings.get("color_border", "#25FFFFFF"))
            start = parse_hex_color(self.HexHoverStartText.Text, settings.get("color_hover_start", "#FF0083B0"))
            end = parse_hex_color(self.HexHoverEndText.Text, settings.get("color_hover_end", "#FF004B66"))
            
            settings["theme"] = "Custom Theme"
            settings["color_normal"] = normal
            settings["color_border"] = border
            settings["color_hover_start"] = start
            settings["color_hover_end"] = end
            
            self._updating_ui_elements = True
            self.ThemeComboBox.SelectedIndex = 6
            self._updating_ui_elements = False
            
            self.apply_theme_colors()
            self.queue_save_config()
        except Exception as ex:
            log_debug(u"Error in on_hex_color_changed: {}".format(safe_str(ex)))

    def update_settings_ui_from_config(self):
        try:
            self._updating_ui_elements = True
            settings = self._config_data.get("settings", dict(DEFAULT_SETTINGS))
            
            trigger_mode_str = settings.get("trigger_mode", "hold")
            self.TriggerModeComboBox.SelectedIndex = 1 if trigger_mode_str == "double_click" else 0
            
            if trigger_mode_str == "double_click":
                self.DelaySlider.IsEnabled = False
                self.DelayValueText.Foreground = self.Resources["CustomizerSecText"]
            else:
                self.DelaySlider.IsEnabled = True
                self.DelayValueText.Foreground = self.Resources["CustomizerHighlight"]
            
            self.DelaySlider.Value = float(settings.get("hold_delay_ms", 400))
            self.DelayValueText.Text = u"{} ms".format(int(self.DelaySlider.Value))
            
            self.CoreRadiusSlider.Value = float(settings.get("core_radius", 45))
            self.CoreRadiusValueText.Text = u"{} px".format(int(self.CoreRadiusSlider.Value))
            
            self.PetalWidthSlider.Value = float(settings.get("petal_width", 60))
            self.PetalWidthValueText.Text = u"{} px".format(int(self.PetalWidthSlider.Value))
            
            self.RingSpacingSlider.Value = float(settings.get("ring_gap", 5))
            self.RingSpacingValueText.Text = u"{} px".format(int(self.RingSpacingSlider.Value))
            
            self.SectorSpacingSlider.Value = float(settings.get("gap_width", 3))
            self.SectorSpacingValueText.Text = u"{:.1f} px".format(self.SectorSpacingSlider.Value)
            
            self.PetalOpacitySlider.Value = float(settings.get("petal_opacity", 95))
            self.PetalOpacityValueText.Text = u"{}%".format(int(self.PetalOpacitySlider.Value))
            
            self.L2MaxAngleSlider.Value = float(settings.get("l2_max_angle", 90))
            self.L2MaxAngleValueText.Text = u"{}°".format(int(self.L2MaxAngleSlider.Value))
            
            self.L3MaxAngleSlider.Value = float(settings.get("l3_max_angle", 90))
            self.L3MaxAngleValueText.Text = u"{}°".format(int(self.L3MaxAngleSlider.Value))
            
            self.UseCirclesCheckBox.IsChecked = bool(settings.get("use_circles", False))
            self.EnableLoggingCheckBox.IsChecked = bool(settings.get("enable_logging", False))
            if hasattr(self, "EnableGesturesCheckBox") and self.EnableGesturesCheckBox:
                self.EnableGesturesCheckBox.IsChecked = bool(settings.get("enable_gestures", True))
            
            anim_style = settings.get("animation_style", "fade")
            anim_mapping = {"fade": 0, "pop": 1, "fan": 2}
            self.AnimationStyleComboBox.SelectedIndex = anim_mapping.get(anim_style, 0)
            
            # Populate Color Scheme selection
            color_scheme = settings.get("color_scheme", "auto")
            scheme_mapping = {
                "dark": 0,
                "light": 1,
                "auto": 2
            }
            
            # Check if Revit theme manager is supported
            is_theme_api_supported = False
            try:
                from Autodesk.Revit.UI import UIThemeManager
                is_theme_api_supported = True
            except:
                pass
                
            if not is_theme_api_supported:
                self.ColorSchemeAutoItem.IsEnabled = False
                self.ColorSchemeAutoItem.ToolTip = "Revit Theme detection is only available in Revit 2024+"
                if color_scheme == "auto":
                    color_scheme = "light"
                    settings["color_scheme"] = "light"

                    
            self.ColorSchemeComboBox.SelectedIndex = scheme_mapping.get(color_scheme, 0)

            
            theme_name = settings.get("theme", "Revit Theme")
            mapping = {
                "Revit Theme": 0,
                "pyRevit Dark": 1,
                "Neon Fusion": 2,
                "Classic Blue": 3,
                "Forest Green": 4,
                "Cyberpunk": 5,
                "Custom Theme": 6
            }
            self.ThemeComboBox.SelectedIndex = mapping.get(theme_name, 0)
            
            self.HexNormalText.Text = settings.get("color_normal", "#F21E1E24")
            self.HexBorderText.Text = settings.get("color_border", "#25FFFFFF")
            self.HexHoverStartText.Text = settings.get("color_hover_start", "#FF0083B0")
            self.HexHoverEndText.Text = settings.get("color_hover_end", "#FF004B66")
            
            self._updating_ui_elements = False
        except Exception as ex:
            log_debug(u"Error in update_settings_ui_from_config: {}".format(safe_str(ex)))
            self._updating_ui_elements = False

    def normalize_slots(self):
        """Normalize pool priorities within each level and parent."""
        try:
            pool = self._config_data.get("command_pool", [])
            grouped = {}
            for item in pool:
                lvl = item.get("level", 1)
                par = item.get("parent")
                key = (lvl, par)
                grouped.setdefault(key, []).append(item)
                
            for key, items in grouped.items():
                sorted_items = sorted(items, key=lambda x: x.get("priority", 0))
                for idx, item in enumerate(sorted_items):
                    item["priority"] = (idx + 1) * 10
            save_config(self._config_data)
            log_debug(u"normalize_slots (pool) completed.")
        except Exception as ex:
            log_debug(u"Error in normalize_slots: {}".format(safe_str(ex)))

    def sync_config_slots(self):
        self.normalize_slots()

    def get_active_level(self):
        try:
            if self.SubMenuLevel3.Visibility == System.Windows.Visibility.Visible:
                return 3
            elif self.SubMenuLevel2.Visibility == System.Windows.Visibility.Visible:
                return 2
        except:
            pass
        return 1

    def on_core_move_clicked(self):
        try:
            self._move_mode_active = True
            
            from System.Windows import Visibility
            from System.Windows.Media import SolidColorBrush, ColorConverter
            
            # Highlight Drag & Drop button, dim others
            self.BtnCoreMove.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF0083B0"))
            self.BtnCorePool.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF55555C"))
            self.BtnCoreAppearance.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF55555C"))
            self.BtnCoreExit.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FFE53935"))
            
            # Collapse customizer panel inside customizer window
            self.CustomizerBorder.Visibility = Visibility.Collapsed
            
            # Hide separate customizer window
            if hasattr(self, "customizer_window") and self.customizer_window:
                try:
                    self.customizer_window.Hide()
                except Exception as hide_ex:
                    log_debug("Failed to hide customizer window: " + str(hide_ex))
            
            # Expand all commands and submenus in tree view regardless of context
            pool = self._config_data.get("command_pool", [])
            if not hasattr(self, "_expanded_item_ids_cache") or self._expanded_item_ids_cache is None:
                self._expanded_item_ids_cache = set()
            for item in pool:
                if item.get("id"):
                    self._expanded_item_ids_cache.add(item.get("id"))
            
            # Reload pool and update radial geometry to show all petals without context filtering
            self.load_layout_configuration()
            self.update_radial_geometry()
            
            log_debug(u"Drag & Drop mode activated. All commands expanded regardless of context.")
        except Exception as ex:
            log_debug(u"Error in on_core_move_clicked: {}".format(safe_str(ex)))

    def on_core_pool_clicked(self):
        try:
            self._move_mode_active = False
            
            from System.Windows import Visibility
            from System.Windows.Media import SolidColorBrush, ColorConverter
            
            # Highlight Pool button
            self.BtnCoreMove.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF55555C"))
            self.BtnCorePool.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF0083B0"))
            self.BtnCoreAppearance.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF55555C"))
            self.BtnCoreExit.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FFE53935"))
            
            # Expand customizer panel, switch to Tab 0 (Command Pool)
            self.CustomizerBorder.Visibility = Visibility.Visible
            self.CustomizerTabControl.SelectedIndex = 0
            
            # Show separate customizer window
            if hasattr(self, "customizer_window") and self.customizer_window:
                try:
                    self.customizer_window.Show()
                    self.customizer_window.Activate()
                except Exception as show_ex:
                    log_debug("Failed to show customizer window: " + str(show_ex))
            
            # Refresh pool list to reflect any changes made in Move mode
            self.load_pool_list()
            
            log_debug(u"Pool mode activated. Customizer window shown and switched to Command Pool tab.")
        except Exception as ex:
            log_debug(u"Error in on_core_pool_clicked: {}".format(safe_str(ex)))

    def on_core_appearance_clicked(self):
        try:
            self._move_mode_active = False
            
            from System.Windows import Visibility
            from System.Windows.Media import SolidColorBrush, ColorConverter
            
            # Highlight Appearance button
            self.BtnCoreMove.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF55555C"))
            self.BtnCorePool.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FFE53935"))
            self.BtnCoreAppearance.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF0083B0"))
            self.BtnCoreExit.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FFE53935"))
            
            # Expand customizer panel, switch to Tab 1 (Appearance)
            self.CustomizerBorder.Visibility = Visibility.Visible
            self.CustomizerTabControl.SelectedIndex = 1
            
            # Show separate customizer window
            if hasattr(self, "customizer_window") and self.customizer_window:
                try:
                    self.customizer_window.Show()
                    self.customizer_window.Activate()
                except Exception as show_ex:
                    log_debug("Failed to show customizer window: " + str(show_ex))
            
            log_debug(u"Appearance mode activated. Customizer window shown and switched to Appearance tab.")
        except Exception as ex:
            log_debug(u"Error in on_core_appearance_clicked: {}".format(safe_str(ex)))

    def on_core_exit_clicked(self):
        """Exit settings mode - same as on_exit_customizer_clicked but called from core button."""
        self.on_exit_customizer_clicked(None, None)

    def on_extract_all_icons_clicked(self, sender, args):
        try:
            from System.Windows import MessageBox, MessageBoxButton, MessageBoxImage
            
            msg = u"Extract all Revit Ribbon icons for the active theme?\nThis will take a few seconds."
            if _IS_REVIT_DARK:
                msg += u"\n\nActive theme: Dark (saving as *.dark.png)"
            else:
                msg += u"\n\nActive theme: Light (saving as *.png)"
                
            res = MessageBox.Show(msg, "Extract Icons", MessageBoxButton.OKCancel, MessageBoxImage.Information)
            if res.ToString() == "OK":
                from System.Windows.Input import Cursors, Mouse
                Mouse.OverrideCursor = Cursors.Wait
                try:
                    extract_icons_from_ribbon(force_overwrite=True)
                    MessageBox.Show("Icons extracted successfully!", "Success", MessageBoxButton.OK, MessageBoxImage.Information)
                finally:
                    Mouse.OverrideCursor = None
        except Exception as ex:
            log_debug("Error in on_extract_all_icons_clicked: " + str(ex))

    def on_exit_customizer_clicked(self, sender, args):
        try:
            # Force immediate save if configuration changes are queued
            if hasattr(self, "_save_timer") and self._save_timer.IsEnabled:
                self._save_timer.Stop()
                save_config(self._config_data)
                log_debug(u"Forced configuration save on exit customizer.")

            self.customizer_mode = False
            
            # Unsubscribe from Revit InputManager events
            try:
                from System.Windows.Input import InputManager
                InputManager.Current.PostNotifyInput -= self.on_input_manager_pre_notify
                log_debug("Unsubscribed from global WPF InputManager events.")
            except Exception as ad_ex:
                log_debug("Failed to unsubscribe from InputManager events: " + str(ad_ex))
            
            # Collapse edit panel if open
            self.hide_edit_panel()
            
            # Collapse customizer panel
            from System.Windows import Visibility
            self.CustomizerBorder.Visibility = Visibility.Collapsed
            
            # Hide customizer window
            if hasattr(self, "customizer_window") and self.customizer_window:
                try:
                    self.customizer_window.Hide()
                except Exception as hide_ex:
                    log_debug("Failed to hide customizer window: " + str(hide_ex))
            
            # Show normal mode core buttons, hide settings mode core buttons
            self.update_core_buttons_visibility()
            
            # Deactivate move mode
            self._move_mode_active = False
            
            # Reset backgrounds
            from System.Windows.Media import SolidColorBrush, ColorConverter
            self.BtnCoreMove.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF55555C"))
            self.BtnCorePool.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FFE53935"))
            self.BtnCoreAppearance.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF55555C"))
            self.BtnCoreExit.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FFE53935"))
            
            # Reload layouts and apply geometries
            self.load_layout_configuration()
            self.update_radial_geometry()
            
            # Restart hook if exiting customizer to normal mode
            try:
                existing_hook = System.AppDomain.CurrentDomain.GetData("RevitRadialMenuHook")
                if existing_hook and not existing_hook.hook_id:
                    existing_hook.start()
                    log_debug(u"Hook restarted after exiting customizer.")
            except Exception as hook_ex:
                log_debug(u"Failed to restart hook on exiting customizer: {}".format(safe_str(hook_ex)))
                
            log_debug(u"Exited Customizer Mode.")
        except Exception as ex:
            log_debug(u"Error in on_exit_customizer_clicked: {}".format(safe_str(ex)))

    def show_edit_panel(self):
        try:
            self.PoolEditPanel.Visibility = System.Windows.Visibility.Visible
            if hasattr(self, "PoolEditPlaceholder") and self.PoolEditPlaceholder:
                self.PoolEditPlaceholder.Visibility = System.Windows.Visibility.Collapsed
        except Exception as ex:
            log_debug("Error showing edit panel: " + str(ex))

    def hide_edit_panel(self):
        try:
            self.PoolEditPanel.Visibility = System.Windows.Visibility.Collapsed
            if hasattr(self, "PoolEditPlaceholder") and self.PoolEditPlaceholder:
                self.PoolEditPlaceholder.Visibility = System.Windows.Visibility.Visible
        except Exception as ex:
            log_debug("Error hiding edit panel: " + str(ex))

    def on_save_timer_tick(self, sender, args):
        self._save_timer.Stop()
        try:
            save_config(self._config_data)
            log_debug(u"Deferred configuration save completed.")
        except Exception as ex:
            log_debug(u"Error in deferred save: {}".format(safe_str(ex)))

    def queue_save_config(self):
        self._save_timer.Stop()
        self._save_timer.Start()

    def on_search_timer_tick(self, sender, args):
        self._search_timer.Stop()
        query = self.SearchBox.Text.lower().strip()
        self.filter_commands(query)

    def on_pool_search_timer_tick(self, sender, args):
        self._pool_search_timer.Stop()
        self.load_pool_list()

    def on_customizer_window_closing(self, sender, args):
        args.Cancel = True
        try:
            self.on_exit_customizer_clicked(None, None)
        except Exception as ex:
            log_debug("Error in customizer window closing: " + str(ex))

    def restore_revit_focus(self):
        try:
            revit_hwnd = HOST_APP.proc_window
            if revit_hwnd:
                hwnd_val = revit_hwnd.ToInt64()
                active_hwnd = user32.GetForegroundWindow()
                if active_hwnd != hwnd_val:
                    # Bring to top and request foreground activation
                    user32.BringWindowToTop(hwnd_val)
                    res = user32.SetForegroundWindow(hwnd_val)
                    log_debug(u"Restored focus to Revit MainWindow (HWND={}, Success={}).".format(hwnd_val, res))
                else:
                    log_debug(u"Revit MainWindow is already active (HWND={}).".format(hwnd_val))
        except Exception as focus_ex:
            log_debug(u"Failed to restore focus to Revit: {}".format(safe_str(focus_ex)))

    def on_window_closing(self, sender, args):
        global _active_window
        # Unsubscribe from unhandled exception handlers to prevent memory leaks
        try:
            if hasattr(self, "_global_unhandled_handler") and self._global_unhandled_handler:
                import System
                System.AppDomain.CurrentDomain.UnhandledException -= self._global_unhandled_handler
                self._global_unhandled_handler = None
                log_debug("Unsubscribed from global AppDomain exception handler.")
        except Exception as ex_unsub:
            log_debug("Failed to unsubscribe global exception handler: " + str(ex_unsub))

        try:
            if hasattr(self, "_dispatcher_unhandled_handler") and self._dispatcher_unhandled_handler:
                self.Dispatcher.UnhandledException -= self._dispatcher_unhandled_handler
                self._dispatcher_unhandled_handler = None
                log_debug("Unsubscribed from Dispatcher exception handler.")
        except Exception as ex_unsub:
            log_debug("Failed to unsubscribe Dispatcher exception handler: " + str(ex_unsub))

        # Close customizer window if open
        try:
            # Unsubscribe from Revit InputManager events on window closing
            try:
                from System.Windows.Input import InputManager
                InputManager.Current.PostNotifyInput -= self.on_input_manager_pre_notify
                log_debug("Unsubscribed from global WPF InputManager events on window closing.")
            except Exception as ad_ex:
                log_debug("Failed to unsubscribe from InputManager events on window closing: " + str(ad_ex))

            if hasattr(self, "customizer_window") and self.customizer_window:
                self.customizer_window.Closing -= self.on_customizer_window_closing
                self.customizer_window.Close()
                self.customizer_window = None
                try:
                    p = get_persistence()
                    if p:
                        p["customizer_window"] = None
                except:
                    pass
                log_debug("Closed customizer window on main window closing.")
        except Exception as ex:
            log_debug("Error closing customizer_window: " + str(ex))
            
        try:
            if hasattr(self, "_save_timer") and self._save_timer.IsEnabled:
                self._save_timer.Stop()
                save_config(self._config_data)
                log_debug(u"Forced configuration save on window closing.")
        except Exception as ex:
            log_debug(u"Error forcing save on closing: {}".format(safe_str(ex)))
            
        # Restart the hook if it was temporarily stopped for this window
        try:
            existing_hook = System.AppDomain.CurrentDomain.GetData("RevitRadialMenuHook")
            if existing_hook and not existing_hook.hook_id:
                existing_hook.start()
                log_debug(u"Hook restarted on window closing.")
        except Exception as hook_ex:
            log_debug(u"Failed to restart hook on window closing: {}".format(safe_str(hook_ex)))
            
        # Force restore focus to Revit MainWindow if requested
        if getattr(self, "_restore_revit_focus", True):
            self.restore_revit_focus()
            
        set_active_window(None)
        log_debug(u"RadialMenuWindow closed, _active_window cleared.")

    def on_window_loaded(self, sender, args):
        try:
            self.PreviewDragOver += self.on_window_preview_drag_over
            self.PreviewDrop += self.on_window_preview_drop
            self.PreviewDragLeave += self.on_window_preview_drag_leave
            self.DragPreviewBorder = self.FindName("DragPreviewBorder")
            self.DragPreviewImage = self.FindName("DragPreviewImage")
            self.DragPreviewEmoji = self.FindName("DragPreviewEmoji")
            self.animate_level("SubMenuLevel1", True)
        except Exception as ex:
            log_debug("Error in on_window_loaded: " + str(ex))

    # ==================== POOL LIST UI METHODS ====================
    
    def load_pool_list(self):
        """Populate the PoolTreeView with commands from the command pool hierarchically."""
        try:
            self.PoolTreeView.ItemsSource = None
            pool = self._config_data.get("command_pool", [])
            
            search_text = self.PoolSearchBox.Text.strip().lower() if hasattr(self, "PoolSearchBox") else ""
            
            # Wrap all items
            checked_ids = getattr(self, "_checked_item_ids_cache", set())
            expanded_ids = getattr(self, "_expanded_item_ids_cache", None)
            wrappers = []
            for item in pool:
                w = PoolListItem(item, self)
                item_id = item.get("id")
                if item_id and item_id in checked_ids:
                    w._is_checked = True
                if expanded_ids is not None:
                    w._is_expanded = bool(item_id and item_id in expanded_ids)
                else:
                    w._is_expanded = False
                wrappers.append(w)
            item_map = {w._item.get("id"): w for w in wrappers if w._item.get("id")}
            
            # Reset children
            for w in wrappers:
                w._children = []
                
            # Build hierarchy
            roots = []
            for w in wrappers:
                parent_id = w._item.get("parent")
                if parent_id and parent_id in item_map:
                    item_map[parent_id]._children.append(w)
                else:
                    roots.append(w)
                    
            # Sort roots and children by level, then priority
            def sort_nodes(nodes):
                nodes.sort(key=lambda x: (x._item.get("level", 1), x._item.get("priority", 0)))
                for n in nodes:
                    if n._children:
                        sort_nodes(n._children)
                        
            sort_nodes(roots)
            
            # Apply search filter if search_text is not empty
            if search_text:
                filtered_roots = []
                # Helper to check if a node or any of its descendants matches search
                def filter_node(node):
                    matches_self = search_text in node.DisplayName.lower() or search_text in node.ContextSummary.lower()
                    
                    # Filter children recursively
                    matching_children = []
                    for child in node._children:
                        filtered_child = filter_node(child)
                        if filtered_child:
                            matching_children.append(filtered_child)
                            
                    if matches_self or matching_children:
                        # Return a new wrapper or modify _children for display
                        node._children = matching_children
                        return node
                    return None
                    
                for r in roots:
                    filtered_r = filter_node(r)
                    if filtered_r:
                        filtered_roots.append(filtered_r)
                display_items = filtered_roots
            else:
                display_items = roots
                
            self._pool_list_items = wrappers # Keep reference to all
            self.PoolTreeView.ItemsSource = display_items
            log_debug(u"Loaded tree items into pool.")
        except Exception as ex:
            log_debug(u"Error in load_pool_list: {}".format(safe_str(ex)))

    def clear_tree_selection(self):
        try:
            self._checked_item_ids_cache = set()
            for wrapper in getattr(self, "_pool_list_items", []):
                wrapper.IsSelected = False
                wrapper.IsChecked = False
        except Exception as ex:
            log_debug("Failed to clear tree selection: " + str(ex))

    def select_tree_node_by_item(self, target_item):
        try:
            if not target_item:
                return
            target_id = target_item.get("id")
            if not target_id:
                return
            # First clear selection
            self.clear_tree_selection()
            for wrapper in getattr(self, "_pool_list_items", []):
                if wrapper._item.get("id") == target_id:
                    wrapper.IsSelected = True
                    break
        except Exception as ex:
            log_debug("Failed to select tree node: " + str(ex))
     
    def on_pool_search_changed(self, sender, args):
        self._pool_search_timer.Stop()
        self._pool_search_timer.Start()
     

                
    def _init_revit_classes_list(self):
        if getattr(self, "_revit_classes_initialized", False):
            return
            
        try:
            global _CACHED_REFLECTED_CLASSES, _CACHED_CATEGORY_GROUPS
            if _CACHED_REFLECTED_CLASSES is not None:
                reflected = list(_CACHED_REFLECTED_CLASSES)
                category_groups = dict(_CACHED_CATEGORY_GROUPS)
            else:
                import Autodesk.Revit.DB as db
                category_groups = {}
                reflected = []
                # 1. Reflect Revit assembly types
                try:
                    assembly = System.Reflection.Assembly.GetAssembly(db.Element)
                    try:
                        types = assembly.GetTypes()
                    except:
                        import sys
                        ex_ref = sys.exc_info()[1]
                        types = getattr(ex_ref, "Types", None) or []
                    for t in types:
                        if t and t.IsClass and t.IsSubclassOf(db.Element) and t.Namespace and t.Namespace.startswith("Autodesk.Revit.DB"):
                            reflected.append(t.Name)
                except:
                    import sys
                    ex = sys.exc_info()[1]
                    log_debug("Failed to reflect Revit classes fallback: " + str(ex))
                    reflected = ["Wall", "Floor", "Pipe", "Duct", "FamilyInstance", "Dimension"]
                    
                # 2. Get Category names from document
                try:
                    uiapp = HOST_APP.uiapp
                    if uiapp and uiapp.ActiveUIDocument:
                        doc = uiapp.ActiveUIDocument.Document
                        for cat in doc.Settings.Categories:
                            if cat.Name:
                                clean_eng = get_clean_english_category_name(cat)
                                if clean_eng:
                                    reflected.append(clean_eng)
                                    try:
                                        cat_type = cat.CategoryType
                                        cat_type_str = str(cat_type)
                                        if cat_type == db.CategoryType.Annotation or "Annotation" in cat_type_str:
                                            category_groups[clean_eng] = "Annotation Elements"
                                        else:
                                            category_groups[clean_eng] = "Model Elements"
                                    except:
                                        pass
                except:
                    import sys
                    cat_ex = sys.exc_info()[1]
                    log_debug("Failed to get categories fallback: " + str(cat_ex))
                
                # Save to cache
                _CACHED_REFLECTED_CLASSES = list(reflected)
                _CACHED_CATEGORY_GROUPS = dict(category_groups)

            # 3. Get currently selected element classes from Revit (ONCE)
            intersected_classes = []
            try:
                uiapp = HOST_APP.uiapp
                if uiapp and uiapp.ActiveUIDocument:
                    uidoc = uiapp.ActiveUIDocument
                    if uidoc:
                        doc = uidoc.Document
                        sel_ids = list(uidoc.Selection.GetElementIds())
                        if sel_ids:
                            selected_classes_sets = []
                            # Limit to first 5 items to prevent lag in huge selections
                            for eid in sel_ids[:5]:
                                el = doc.GetElement(eid)
                                if el:
                                    t = el.GetType()
                                    el_classes = []
                                    while t is not None and t != System.Object:
                                        if t.Namespace and t.Namespace.startswith("Autodesk.Revit.DB"):
                                            el_classes.append(t.Name)
                                        t = t.BaseType
                                    if el.Category:
                                        el_classes.append(el.Category.Name)
                                        el_classes.extend(get_english_names_for_category(el.Category))
                                    selected_classes_sets.append(set(el_classes))
                            if selected_classes_sets:
                                common = selected_classes_sets[0]
                                for s in selected_classes_sets[1:]:
                                    common = common.intersection(s)
                                intersected_classes = list(common)
            except:
                import sys
                sel_ex = sys.exc_info()[1]
                log_debug("Failed to get selection classes for initialization sorting: " + str(sel_ex))
                
            self._intersected_classes_set = set(intersected_classes)
            
            # Sort: selection classes first, then alphabetical
            def get_init_sort_key(c):
                prio = 0 if c in self._intersected_classes_set else 1
                return (prio, c.lower())
                
            reflected = sorted(list(set(reflected)), key=get_init_sort_key)
            
            # Create ObservableCollection and ClassItem objects
            self._all_classes_items = []
            from System.Collections.ObjectModel import ObservableCollection
            self._classes_collection = ObservableCollection[object]()
            
            for name in reflected:
                group_name = classify_element_type(name, category_groups)
                c_item = ClassItem(name, False, group_name)
                self._all_classes_items.append(c_item)
                self._classes_collection.Add(c_item)
                
            self.EditClassList.ItemsSource = self._classes_collection
            
            from System.Windows.Data import CollectionViewSource, PropertyGroupDescription
            from System import Predicate
            self._classes_view = CollectionViewSource.GetDefaultView(self._classes_collection)
            self._classes_filter_delegate = Predicate[object](self.classes_filter_predicate)
            self._classes_view.Filter = self._classes_filter_delegate
            self._classes_view.GroupDescriptions.Add(PropertyGroupDescription("Group"))
            
            self._revit_classes_initialized = True
        except:
            import sys
            ex = sys.exc_info()[1]
            log_debug("Error initializing Revit classes list: " + str(ex))

    def on_pool_selection_changed(self, sender, args):
        """When a pool item is selected, populate the edit panel."""
        try:
            selected_wrapper = self.PoolTreeView.SelectedItem
            if not selected_wrapper:
                self.hide_edit_panel()
                return
            
            item = selected_wrapper._item
            self.show_edit_panel()
            self._editing_pool_item = item
            
            self._updating_ui_elements = True
            
            # 1. Update Title Label
            self.TxtEditItemName.Text = u"Configure Rules: {}".format(item.get("name", "Unnamed"))
            
            # Fill details fields
            self.EditItemNameTxt.Text = item.get("name", "")
            self.EditItemCommandTxt.Text = item.get("command", "")
            self.EditItemIconTxt.Text = item.get("icon", "")
            
            # Toggle Visibility Rules Section for submenus
            is_submenu = item.get("command") in ["submenu1", "submenu2"]
            if is_submenu:
                self.VisibilityRulesSection.Visibility = System.Windows.Visibility.Collapsed
            else:
                self.VisibilityRulesSection.Visibility = System.Windows.Visibility.Visible
            
            
            # 4. View filters CheckBoxes
            rules = item.get("context_rules", {}) or {}
            if "allowed_views" in rules:
                allowed_views = rules["allowed_views"] or []
                self.EditChkView3D.IsChecked = "3D" in allowed_views
                self.EditChkViewPlan.IsChecked = "Plan" in allowed_views
                self.EditChkViewSheet.IsChecked = "Sheet" in allowed_views
            else:
                self.EditChkView3D.IsChecked = True
                self.EditChkViewPlan.IsChecked = True
                self.EditChkViewSheet.IsChecked = True
                
            # 4b. Selection filters CheckBoxes
            if "allowed_selection_states" in rules:
                allowed_states = rules["allowed_selection_states"] or []
                self.EditChkPrehighlighted.IsChecked = "Pre-highlighted" in allowed_states
                self.EditChkSelection.IsChecked = "Selection" in allowed_states
            else:
                self.EditChkPrehighlighted.IsChecked = True
                self.EditChkSelection.IsChecked = True
                
            # 5. Revit DB Classes list
            self._updating_ui_elements = True
            allowed_classes = rules.get("allowed_classes", []) or []
            self.update_class_list_selection(allowed_classes)
                
            # Enable/disable class search and list based on checkboxes
            has_filtering = (self.EditChkPrehighlighted.IsChecked == True) or (self.EditChkSelection.IsChecked == True)
            self.EditClassSearch.IsEnabled = has_filtering
            self.EditClassList.IsEnabled = has_filtering
            
            self._updating_ui_elements = False
        except:
            import sys
            ex = sys.exc_info()[1]
            log_debug(u"Error in on_pool_selection_changed: {}".format(safe_str(ex)))
    
    def on_save_edit_clicked(self, sender, args):
        """Save edits from the edit panel back to the pool item(s)."""
        try:
            checked_items = [w for w in getattr(self, "_pool_list_items", []) if w.IsChecked]
            
            # View type filter
            views = []
            if self.EditChkView3D.IsChecked: views.append("3D")
            if self.EditChkViewPlan.IsChecked: views.append("Plan")
            if self.EditChkViewSheet.IsChecked: views.append("Sheet")
                
            # Selection state filter
            states = []
            if self.EditChkPrehighlighted.IsChecked: states.append("Pre-highlighted")
            if self.EditChkSelection.IsChecked: states.append("Selection")
                
            # Class filter
            classes = [c.Name for c in self._all_classes_items if c.IsChecked]
            
            rules = {
                "allowed_views": views,
                "allowed_selection_states": states,
                "allowed_classes": classes
            }
            
            if len(checked_items) > 1:
                # Bulk edit saving
                for w in checked_items:
                    if w._item.get("command") not in ["submenu1", "submenu2"]:
                        w._item["context_rules"] = dict(rules)
                    else:
                        w._item["context_rules"] = {}
                log_debug(u"Bulk saved context rules for {} items.".format(len(checked_items)))
            else:
                item = getattr(self, "_editing_pool_item", None)
                if not item and len(checked_items) == 1:
                    item = checked_items[0]._item
                if not item:
                    item = self.PoolTreeView.SelectedItem._item if self.PoolTreeView.SelectedItem else None
                if not item:
                    return
                
                # Update basic details
                item["name"] = self.EditItemNameTxt.Text.strip()
                item["command"] = self.EditItemCommandTxt.Text.strip()
                
                icon_val = self.EditItemIconTxt.Text.strip()
                if not icon_val:
                    icon_val = suggest_emoji_by_name(item["name"])
                item["icon"] = icon_val
                
                if item["command"] in ["submenu1", "submenu2"]:
                    item["context_rules"] = {}
                else:
                    item["context_rules"] = rules
                log_debug(u"Saved pool item: {}".format(item.get("name")))
            
            save_config(self._config_data)
            self.load_layout_configuration()
            self.load_pool_list()
            self.update_radial_geometry()
            
            # Hide edit panel
            self.hide_edit_panel()
            self.clear_tree_selection()
        except Exception as ex:
            log_debug(u"Error in on_save_edit_clicked: {}".format(safe_str(ex)))
            
    def on_cancel_edit_clicked(self, sender, args):
        try:
            self.hide_edit_panel()
            self.clear_tree_selection()
            self.load_pool_list()
        except Exception as ex:
            log_debug(u"Error in on_cancel_edit_clicked: {}".format(safe_str(ex)))

    def on_pool_item_checked_changed(self, sender, args):
        try:
            checked_ids = set()
            for w in getattr(self, "_pool_list_items", []):
                if w.IsChecked:
                    item_id = w._item.get("id")
                    if item_id:
                        checked_ids.add(item_id)
            self._checked_item_ids_cache = checked_ids
            self.update_edit_panel_for_checked_items()
        except Exception as ex:
            log_debug("Error in on_pool_item_checked_changed: " + str(ex))

    def update_edit_panel_for_checked_items(self):
        try:
            checked_items = [w for w in getattr(self, "_pool_list_items", []) if w.IsChecked]
            if not checked_items:
                selected_wrapper = self.PoolTreeView.SelectedItem
                if selected_wrapper:
                    self.on_pool_selection_changed(None, None)
                else:
                    self.hide_edit_panel()
                return

            self.show_edit_panel()
            self._updating_ui_elements = True
            
            if len(checked_items) == 1:
                item = checked_items[0]._item
                self._editing_pool_item = item
                self.TxtEditItemName.Text = u"Configure Rules: {}".format(item.get("name", "Unnamed"))
                
                self.EditItemNameTxt.Text = item.get("name", "")
                self.EditItemCommandTxt.Text = item.get("command", "")
                self.EditItemIconTxt.Text = item.get("icon", "")
                
                self.EditItemNameTxt.IsEnabled = True
                self.EditItemCommandTxt.IsEnabled = True
                self.EditItemIconTxt.IsEnabled = True
                self.BtnSelectIcon.IsEnabled = True
                rules = item.get("context_rules", {}) or {}
            else:
                self._editing_pool_item = None
                self.TxtEditItemName.Text = u"Bulk Edit: {} items".format(len(checked_items))
                
                self.EditItemNameTxt.Text = u"[Multiple Values]"
                self.EditItemCommandTxt.Text = u"[Multiple Values]"
                self.EditItemIconTxt.Text = u"[Multiple Values]"
                
                self.EditItemNameTxt.IsEnabled = False
                self.EditItemCommandTxt.IsEnabled = False
                self.EditItemIconTxt.IsEnabled = False
                self.BtnSelectIcon.IsEnabled = False
                
                rules = checked_items[0]._item.get("context_rules", {}) or {}
                
            # Toggle Visibility Rules Section for submenus
            any_submenu = any(w._item.get("command") in ["submenu1", "submenu2"] for w in checked_items)
            if any_submenu:
                self.VisibilityRulesSection.Visibility = System.Windows.Visibility.Collapsed
            else:
                self.VisibilityRulesSection.Visibility = System.Windows.Visibility.Visible
                
            if "allowed_views" in rules:
                allowed_views = rules["allowed_views"] or []
                self.EditChkView3D.IsChecked = "3D" in allowed_views
                self.EditChkViewPlan.IsChecked = "Plan" in allowed_views
                self.EditChkViewSheet.IsChecked = "Sheet" in allowed_views
            else:
                self.EditChkView3D.IsChecked = True
                self.EditChkViewPlan.IsChecked = True
                self.EditChkViewSheet.IsChecked = True
                
            if "allowed_selection_states" in rules:
                allowed_states = rules["allowed_selection_states"] or []
                self.EditChkPrehighlighted.IsChecked = "Pre-highlighted" in allowed_states
                self.EditChkSelection.IsChecked = "Selection" in allowed_states
            else:
                self.EditChkPrehighlighted.IsChecked = True
                self.EditChkSelection.IsChecked = True
                
            allowed_classes = rules.get("allowed_classes", []) or []
            self.update_class_list_selection(allowed_classes)
                
            has_filtering = (self.EditChkPrehighlighted.IsChecked == True) or (self.EditChkSelection.IsChecked == True)
            self.EditClassSearch.IsEnabled = has_filtering
            self.EditClassList.IsEnabled = has_filtering
            
            self._updating_ui_elements = False
        except Exception as ex:
            log_debug("Error in update_edit_panel_for_checked_items: " + str(ex))

    def on_delete_checked_clicked(self, sender, args):
        try:
            checked_items = [w for w in getattr(self, "_pool_list_items", []) if w.IsChecked]
            if not checked_items:
                from pyrevit import forms
                forms.alert("No commands checked. Please check the items you want to delete.")
                return
                
            from pyrevit import forms
            if forms.alert(u"Delete {} selected commands from pool?".format(len(checked_items)), yes=True, no=True):
                pool = self._config_data.get("command_pool", [])
                for w in checked_items:
                    item = w._item
                    if item in pool:
                        pool.remove(item)
                    item_id = item.get("id")
                    if item_id and item.get("command") in ["submenu1", "submenu2"]:
                        for p_item in pool:
                            if p_item.get("parent") == item_id:
                                p_item["parent"] = None
                                p_item["level"] = 1
                save_config(self._config_data)
                self.load_layout_configuration()
                self.load_pool_list()
                self.update_radial_geometry()
                self.hide_edit_panel()
                self.clear_tree_selection()
                log_debug(u"Bulk deleted {} items from pool.".format(len(checked_items)))
        except Exception as ex:
            log_debug(u"Error in on_delete_checked_clicked: {}".format(safe_str(ex)))
            
    def on_export_config_clicked(self, sender, args):
        try:
            import System.Windows.Forms as winforms
            import json
            dialog = winforms.SaveFileDialog()
            dialog.Title = "Export Configuration"
            dialog.Filter = "JSON files (*.json)|*.json|All files (*.*)|*.*"
            dialog.DefaultExt = "json"
            dialog.FileName = "RadialMenu_Config.json"
            if dialog.ShowDialog() == winforms.DialogResult.OK:
                file_path = dialog.FileName
                with open(file_path, 'w') as f:
                    json.dump(self._config_data, f, indent=4)
                from pyrevit import forms
                forms.toast("Configuration exported successfully.", title="Export Config")
        except Exception as ex:
            log_debug(u"Error in on_export_config_clicked: {}".format(safe_str(ex)))
            from pyrevit import forms
            forms.alert("Failed to export configuration: " + safe_str(ex))

    def on_import_config_clicked(self, sender, args):
        try:
            import System.Windows.Forms as winforms
            import json
            dialog = winforms.OpenFileDialog()
            dialog.Title = "Import Configuration"
            dialog.Filter = "JSON files (*.json)|*.json|All files (*.*)|*.*"
            if dialog.ShowDialog() == winforms.DialogResult.OK:
                file_path = dialog.FileName
                with open(file_path, 'r') as f:
                    new_config = json.load(f)
                
                # Basic validation
                if not isinstance(new_config, dict) or "command_pool" not in new_config:
                    from pyrevit import forms
                    forms.alert("Invalid configuration file. It must contain 'command_pool'.")
                    return
                
                from pyrevit import forms
                if forms.alert(u"This will overwrite your current configuration. Continue?", yes=True, no=True):
                    self._config_data = new_config
                    save_config(self._config_data)
                    self.load_layout_configuration()
                    self.load_pool_list()
                    self.update_radial_geometry()
                    self.hide_edit_panel()
                    self.clear_tree_selection()
                    forms.toast("Configuration imported successfully.", title="Import Config")
        except Exception as ex:
            log_debug(u"Error in on_import_config_clicked: {}".format(safe_str(ex)))
            from pyrevit import forms
            forms.alert("Failed to import configuration: " + safe_str(ex))
    
    def load_all_icons(self):
        """Load all icons from extracted_icons directory."""
        if hasattr(self, "_cached_icon_items"):
            return self._cached_icon_items
            
        icons_dir = os.path.join(os.path.dirname(__file__), "extracted_icons")
        icon_items = []
        if os.path.exists(icons_dir):
            try:
                for filename in os.listdir(icons_dir):
                    if filename.lower().endswith(".png") and not filename.lower().endswith(".dark.png"):
                        cmd_id = filename[:-4] # Remove .png
                        
                        name_part = cmd_id
                        if name_part.startswith("ID_"):
                            name_part = name_part[3:]
                            
                        prefixes_to_clean = ["OBJECTS_", "RBS_", "ANNOTATIONS_", "ANNOTATE_", "VIEW_", "EDIT_", "FILE_", "SETTINGS_", "BUTTON_", "MODIFY_", "WINDOW_"]
                        for prefix in prefixes_to_clean:
                            if name_part.startswith(prefix):
                                name_part = name_part[len(prefix):]
                                break
                                
                        words = name_part.split("_")
                        clean_words = []
                        for w in words:
                            if w and w not in clean_words:
                                clean_words.append(w)
                        clean_name = " ".join(clean_words).title()
                        
                        full_path = os.path.join(icons_dir, filename)
                        path_val = "extracted_icons/" + filename
                        
                        icon_items.append(IconItem(cmd_id, clean_name, full_path, path_val))
            except Exception as ex:
                log_debug("Error loading icons from folder: " + str(ex))
                
        # Sort icons by CleanName
        icon_items = sorted(icon_items, key=lambda x: x.CleanName)
        self._cached_icon_items = icon_items
        return icon_items

    def update_visible_icons(self):
        try:
            query = getattr(self, "_icon_search_query", "").strip().lower()
            all_icons = self.load_all_icons()
            
            filtered = []
            for icon in all_icons:
                if not query or query in icon.Name.lower() or query in icon.CleanName.lower():
                    filtered.append(icon)
                    if len(filtered) >= 150:  # Hard limit of 150 visible items to prevent UI lag/crashes!
                        break
                        
            from System.Collections.ObjectModel import ObservableCollection
            self._icon_collection = ObservableCollection[object]()
            for icon in filtered:
                self._icon_collection.Add(icon)
                
            self.IconPickerListBox.ItemsSource = self._icon_collection
        except Exception as ex:
            log_debug("Error updating visible icons: " + str(ex))

    def on_select_icon_clicked(self, sender, args):
        try:
            self._icon_search_query = ""
            self.IconPickerSearchBox.Text = ""
            self.update_visible_icons()
            
            # Show overlay
            self.IconPickerOverlay.Visibility = Visibility.Visible
            log_debug("Opened Icon Picker overlay.")
        except Exception as ex:
            log_debug("Error opening Icon Picker: " + str(ex))

    def on_icon_picker_search_changed(self, sender, args):
        self._icon_search_timer.Stop()
        self._icon_search_timer.Start()

    def on_icon_search_timer_tick(self, sender, args):
        self._icon_search_timer.Stop()
        try:
            self._icon_search_query = self.IconPickerSearchBox.Text.strip().lower() if self.IconPickerSearchBox.Text else ""
            self.update_visible_icons()
        except Exception as ex:
            log_debug("Error in icon search tick: " + str(ex))

    def on_icon_picker_select_clicked(self, sender, args):
        try:
            selected_icon = self.IconPickerListBox.SelectedItem
            if selected_icon:
                # Set TextBox text
                self.EditItemIconTxt.Text = selected_icon.PathVal
                log_debug("Selected icon: " + selected_icon.PathVal)
            
            self.IconPickerOverlay.Visibility = Visibility.Collapsed
        except Exception as ex:
            log_debug("Error selecting icon: " + str(ex))

    def on_icon_picker_cancel_clicked(self, sender, args):
        try:
            self.IconPickerOverlay.Visibility = Visibility.Collapsed
            log_debug("Cancelled Icon Picker.")
        except Exception as ex:
            log_debug("Error cancelling Icon Picker: " + str(ex))

    def on_icon_picker_double_click(self, sender, args):
        self.on_icon_picker_select_clicked(None, None)

    def on_add_builtin_clicked(self, sender, args):
        """Switch to command picker tab and filter for Revit Ribbon commands."""
        try:
            self.picker_mode = "built_in"
            self.SearchBox.Text = ""
            self.filter_commands(None)
            self.CustomizerTabControl.SelectedIndex = 2
            log_debug(u"Switched to command picker tab and filtered for Revit Ribbon.")
        except Exception as ex:
            log_debug(u"Error in on_add_builtin_clicked: {}".format(safe_str(ex)))
            
    def on_add_pool_item_clicked(self, sender, args):
        """Handle pool item addition based on ComboBox selection."""
        try:
            selected_index = self.ComboAddType.SelectedIndex
            if selected_index == 0:
                self.on_add_from_pyrevit_clicked(sender, args)
            elif selected_index == 1:
                self.on_add_submenu_clicked(sender, args)
            elif selected_index == 2:
                self.on_add_empty_clicked(sender, args)
            else:
                log_debug(u"Unknown add type selected in ComboBox.")
        except Exception as ex:
            log_debug(u"Error in on_add_pool_item_clicked: {}".format(safe_str(ex)))

    def on_add_submenu_clicked(self, sender, args):
        """Add a new submenu to the pool."""
        try:
            pool = self._config_data.get("command_pool", [])
            submenus_count = sum(1 for p in pool if p.get("command") in ["submenu1", "submenu2"])
            submenu_cmd = "submenu1" if submenus_count == 0 else "submenu2"
            
            base_id = "new_submenu"
            cmd_id = base_id
            existing_ids = {p.get("id", "") for p in pool}
            counter = 1
            while cmd_id in existing_ids:
                cmd_id = "{}_{}".format(base_id, counter)
                counter += 1
                
            l1_priorities = [p.get("priority", 0) for p in pool if p.get("level") == 1]
            max_priority = max(l1_priorities) if l1_priorities else 0
            new_item = {
                "id": cmd_id,
                "type": "built_in",
                "name": "New Submenu",
                "command": submenu_cmd,
                "icon": u"\u25B6",
                "level": 1,
                "parent": None,
                "priority": max_priority + 10,
                "context_rules": {}
            }
            pool.append(new_item)
            save_config(self._config_data)
            self.load_layout_configuration()
            self.load_pool_list()
            self.update_radial_geometry()
            
            self.select_tree_node_by_item(new_item)
            log_debug(u"Added new submenu: {}".format(cmd_id))
        except Exception as ex:
            log_debug(u"Error in on_add_submenu_clicked: {}".format(safe_str(ex)))
            
    def on_add_empty_clicked(self, sender, args):
        """Add a new empty petal to the pool."""
        try:
            pool = self._config_data.get("command_pool", [])
            base_id = "empty_petal"
            cmd_id = base_id
            existing_ids = {p.get("id", "") for p in pool}
            counter = 1
            while cmd_id in existing_ids:
                cmd_id = "{}_{}".format(base_id, counter)
                counter += 1
                
            l1_priorities = [p.get("priority", 0) for p in pool if p.get("level") == 1]
            max_priority = max(l1_priorities) if l1_priorities else 0
            new_item = {
                "id": cmd_id,
                "type": "built_in",
                "name": "Empty Petal",
                "command": "empty",
                "icon": u"⚪",
                "level": 1,
                "parent": None,
                "priority": max_priority + 10,
                "context_rules": {}
            }
            pool.append(new_item)
            save_config(self._config_data)
            self.load_layout_configuration()
            self.load_pool_list()
            self.update_radial_geometry()
            
            self.select_tree_node_by_item(new_item)
            log_debug(u"Added new empty petal: {}".format(cmd_id))
        except Exception as ex:
            log_debug(u"Error in on_add_empty_clicked: {}".format(safe_str(ex)))
            
    def on_add_from_pyrevit_clicked(self, sender, args):
        try:
            self.picker_mode = "all"
            self.SearchBox.Text = ""
            self.filter_commands(None)
            self.CustomizerTabControl.SelectedIndex = 2
            log_debug(u"Switched to command picker tab (all commands).")
        except Exception as ex:
            log_debug(u"Error in on_add_from_pyrevit_clicked: {}".format(safe_str(ex)))
            
    def on_picker_cancel_clicked(self, sender, args):
        try:
            self.CustomizerTabControl.SelectedIndex = 0
            log_debug(u"Cancelled command picker, returned to pool.")
        except Exception as ex:
            log_debug(u"Error in on_picker_cancel_clicked: {}".format(safe_str(ex)))

    def on_picker_add_command_clicked(self, sender, args):
        try:
            selected_item = self.CommandTreeView.SelectedItem
            if not selected_item:
                log_debug(u"No pyRevit command selected in TreeView.")
                return
            is_cmd = getattr(selected_item, "IsCommand", False)
            is_pd = getattr(selected_item, "IsPulldown", False)
            
            if not is_cmd and not is_pd:
                log_debug(u"Selected item is not a command or pulldown node.")
                return
                
            pool = self._config_data.get("command_pool", [])
            base_id = selected_item.UniqueId or "pyrevit_cmd"
            
            if is_pd:
                existing_ids = {p.get("id", "") for p in pool}
                if base_id in existing_ids:
                    from pyrevit import forms
                    forms.toast("Pulldown is already in the pool.", title="Radial Menu")
                    return
                    
                l1_priorities = [p.get("priority", 0) for p in pool if p.get("level") == 1]
                max_priority = max(l1_priorities) if l1_priorities else 0
                
                new_item = {
                    "id": base_id,
                    "type": "built_in",
                    "name": selected_item.Name,
                    "command": "submenu1",
                    "icon": selected_item._icon_path or u"\u25B6",
                    "level": 1,
                    "parent": None,
                    "priority": max_priority + 10,
                    "context_rules": {}
                }
                pool.append(new_item)
                
                # Find all child commands belonging to this pulldown
                child_cmds = []
                for c in self._all_commands:
                    uid = c.get("unique_id", "")
                    if uid.startswith(base_id + "_"):
                        child_cmds.append(c)
                
                child_cmds = sorted(child_cmds, key=lambda x: x.get("title", ""))
                
                # Add child commands to Level 2
                for idx, child in enumerate(child_cmds[:10]):
                    new_child = {
                        "id": child["unique_id"],
                        "type": "pyrevit",
                        "name": child["title"],
                        "command": child["unique_id"],
                        "icon": child["icon_path"] or "",
                        "level": 2,
                        "parent": base_id,
                        "priority": (idx + 1) * 10,
                        "context_rules": {}
                    }
                    pool.append(new_child)
                    
                self._config_data["command_pool"] = pool
                save_config(self._config_data)
                
                self.CustomizerTabControl.SelectedIndex = 0
                self.load_layout_configuration()
                self.load_pool_list()
                self.update_radial_geometry()
                
                self.select_tree_node_by_item(new_item)
                log_debug(u"Added pyRevit pulldown to pool: {}".format(selected_item.Name))
            else:
                is_builtin = (getattr(selected_item, "Extension", None) in ["Revit Built-in", "Revit Ribbon"])
                cmd_type = "built_in" if is_builtin else "pyrevit"
                
                existing_commands = {p.get("command", "") for p in pool if p.get("type") == cmd_type}
                if selected_item.UniqueId in existing_commands:
                    from pyrevit import forms
                    forms.toast("Command '{}' is already in the pool.".format(selected_item.Name), title="Radial Menu")
                    return
                    
                display_name = selected_item.Name
                if is_builtin and " (" in display_name:
                    display_name = display_name.split(" (")[0].strip()
                    
                icon_val = selected_item._icon_path
                if icon_val:
                    if os.path.isabs(icon_val) and "extracted_icons" in icon_val:
                        parts = icon_val.split("extracted_icons")
                        if len(parts) > 1:
                            icon_val = "extracted_icons" + parts[-1].replace("\\", "/")
                            
                cmd_id = base_id
                existing_ids = {p.get("id", "") for p in pool}
                counter = 1
                while cmd_id in existing_ids:
                    cmd_id = "{}_{}".format(base_id, counter)
                    counter += 1
                    
                l1_priorities = [p.get("priority", 0) for p in pool if p.get("level") == 1]
                max_priority = max(l1_priorities) if l1_priorities else 0
                new_item = {
                    "id": cmd_id,
                    "type": cmd_type,
                    "name": display_name,
                    "command": selected_item.UniqueId,
                    "icon": icon_val,
                    "level": 1,
                    "parent": None,
                    "priority": max_priority + 10,
                    "context_rules": {}
                }
                pool.append(new_item)
                save_config(self._config_data)
                
                self.CustomizerTabControl.SelectedIndex = 0
                self.load_layout_configuration()
                self.load_pool_list()
                self.update_radial_geometry()
                
                self.select_tree_node_by_item(new_item)
                log_debug(u"Added command '{}' (type: {}) to pool.".format(display_name, cmd_type))
        except:
            import sys
            ex = sys.exc_info()[1]
            log_debug(u"Error in on_picker_add_command_clicked: {}".format(safe_str(ex)))
            
    def on_pool_list_button_click(self, sender, args):
        """Handle button clicks routed from within the PoolListBox items (e.g. trash can delete button)."""
        try:
            button = args.OriginalSource
            # Traverse visual tree up slightly if they clicked on the content inside button
            from System.Windows.Controls import Button as wpf_button
            from System.Windows.Media import VisualTreeHelper
            dep = button
            while dep is not None and not isinstance(dep, wpf_button):
                dep = VisualTreeHelper.GetParent(dep)
            if dep is not None and getattr(dep, "Name", None) == "BtnRowDelete":
                args.Handled = True
                wrapper = dep.DataContext
                if wrapper:
                    item = wrapper._item
                    from pyrevit import forms
                    if forms.alert(u"Delete command '{}' from pool?".format(item.get("name", "Unnamed")), yes=True, no=True):
                        self.delete_pool_item(item)
            elif dep is not None and getattr(dep, "Name", None) == "BtnRowEye":
                args.Handled = True
                wrapper = dep.DataContext
                if wrapper:
                    item = wrapper._item
                    is_active = item.get("is_active", True)
                    item["is_active"] = not is_active
                    
                    save_config(self._config_data)
                    
                    self.load_layout_configuration()
                    self.load_pool_list()
                    self.update_radial_geometry()
                    
                    log_debug(u"Toggled command '{}' active state to {}.".format(item.get("name"), item["is_active"]))
        except:
            import sys
            ex = sys.exc_info()[1]
            log_debug("Error in on_pool_list_button_click: " + str(ex))

    def delete_pool_item(self, item):
        """Remove a command item from the pool, reset parent relationships, and refresh UI."""
        try:
            if not item:
                return
            pool = self._config_data.get("command_pool", [])
            if item in pool:
                pool.remove(item)
                
            # Reset parent and level for child commands of deleted submenus
            item_id = item.get("id")
            if item_id and item.get("command") in ["submenu1", "submenu2"]:
                for p_item in pool:
                    if p_item.get("parent") == item_id:
                        p_item["parent"] = None
                        p_item["level"] = 1
                
            save_config(self._config_data)
            self.load_layout_configuration()
            self.load_pool_list()
            self.update_radial_geometry()
            
            # If we were editing this deleted item, hide edit panel
            editing_item = getattr(self, "_editing_pool_item", None)
            if editing_item == item:
                self.hide_edit_panel()
                self.clear_tree_selection()
                
            log_debug(u"Deleted pool command: {}".format(item.get("name")))
        except Exception as ex:
            log_debug(u"Error in delete_pool_item: {}".format(safe_str(ex)))

    def on_delete_command_clicked(self, sender, args):
        """Legacy handler for the deleted delete button."""
        try:
            selected_wrapper = self.PoolTreeView.SelectedItem
            if selected_wrapper:
                self.delete_pool_item(selected_wrapper._item)
        except Exception as ex:
            log_debug(u"Error in on_delete_command_clicked: {}".format(safe_str(ex)))

    def classes_filter_predicate(self, item):
        try:
            box = getattr(self, "EditClassSearch", None) or getattr(self, "TxtClassSearch", None)
            query = ""
            if box:
                text = box.Text
                if text:
                    query = text.lower().strip()
            
            if query:
                return query in item.Name.lower()
                
            # If search query is empty, only show allowed/checked classes,
            # classes that are part of the active selection (intersected classes),
            # or the top common Revit classes/categories.
            # This keeps the list small and fast, avoiding rendering 2,000 offscreen check boxes!
            is_allowed = any(alias in getattr(self, "_allowed_classes_set", set()) for alias in get_category_aliases(item.Name))
            is_intersected = item.Name in getattr(self, "_intersected_classes_set", set())
            is_common = item.Name in COMMON_REVIT_CLASSES
            return is_allowed or is_intersected or is_common
        except:
            return True

    def recalculate_class_separators(self):
        try:
            # Reset all separators first
            for c_item in getattr(self, "_all_classes_items", []):
                c_item.ShowSeparator = False
                
            # Find the last checked item in "Model Elements" and "Annotation Elements"
            last_checked_model = None
            last_checked_anno = None
            
            # Since the collection is sorted (checked first), we can just iterate.
            # But wait, we should only consider currently visible items (matching the query).
            query = ""
            box = getattr(self, "EditClassSearch", None) or getattr(self, "TxtClassSearch", None)
            if box and box.Text:
                query = box.Text.lower().strip()
                
            for c_item in getattr(self, "_all_classes_items", []):
                # Apply the search query filter
                if query and query not in c_item.Name.lower():
                    continue
                    
                # Apply the empty query filter (same as classes_filter_predicate)
                if not query:
                    is_allowed = any(alias in getattr(self, "_allowed_classes_set", set()) for alias in get_category_aliases(c_item.Name))
                    is_intersected = c_item.Name in getattr(self, "_intersected_classes_set", set())
                    is_common = c_item.Name in COMMON_REVIT_CLASSES
                    if not (is_allowed or is_intersected or is_common):
                        continue
                        
                if c_item.IsChecked:
                    if c_item.Group == "Model Elements":
                        last_checked_model = c_item
                    elif c_item.Group == "Annotation Elements":
                        last_checked_anno = c_item
                        
            if last_checked_model:
                last_checked_model.ShowSeparator = True
            if last_checked_anno:
                last_checked_anno.ShowSeparator = True
                
            # Force UI refresh
            if hasattr(self, "_classes_view") and self._classes_view:
                self._classes_view.Refresh()
        except Exception as ex:
            log_debug("Error recalculating class separators: " + str(ex))

    def update_class_list_selection(self, allowed_classes):
        try:
            self._init_revit_classes_list()
            self._allowed_classes_set = set(allowed_classes)
            
            # 1. Update IsChecked
            for c_item in getattr(self, "_all_classes_items", []):
                c_item.IsChecked = any(alias in self._allowed_classes_set for alias in get_category_aliases(c_item.Name))
                
            # 2. Sort _all_classes_items (checked first, then alphabetically)
            if hasattr(self, "_all_classes_items") and self._all_classes_items:
                self._all_classes_items = sorted(
                    self._all_classes_items,
                    key=lambda x: (0 if x.IsChecked else 1, x.Name.lower())
                )
                
            # Temporarily disconnect ItemsSource to prevent WPF layout storm
            if hasattr(self, "EditClassList") and self.EditClassList:
                self.EditClassList.ItemsSource = None
                
            # 3. Clear and re-populate _classes_collection
            if hasattr(self, "_classes_collection") and self._classes_collection:
                self._classes_collection.Clear()
                for c_item in self._all_classes_items:
                    self._classes_collection.Add(c_item)
                    
            # Reconnect ItemsSource
            if hasattr(self, "EditClassList") and self.EditClassList:
                self.EditClassList.ItemsSource = self._classes_collection
                
            # 4. Recalculate separators
            self.recalculate_class_separators()
        except Exception as ex:
            log_debug("Error updating class list selection: " + str(ex))

    def on_class_checkbox_clicked(self, sender, args):
        self.recalculate_class_separators()

    def on_context_class_search_changed(self, sender, args):
        try:
            if hasattr(self, "_classes_view") and self._classes_view:
                self._classes_view.Refresh()
            self.recalculate_class_separators()
        except Exception as ex:
            log_debug(u"Error in on_context_class_search_changed: {}".format(safe_str(ex)))

    def on_selection_checkbox_changed(self, sender, args):
        try:
            has_filtering = (self.EditChkPrehighlighted.IsChecked == True) or (self.EditChkSelection.IsChecked == True)
            self.EditClassSearch.IsEnabled = has_filtering
            self.EditClassList.IsEnabled = has_filtering
        except Exception as ex:
            log_debug("Error in on_selection_checkbox_changed: " + str(ex))

    def on_customizer_mouse_down(self, sender, args):
        try:
            from System.Windows.Input import MouseButtonState
            if args.LeftButton == MouseButtonState.Pressed:
                if hasattr(self, "customizer_window") and self.customizer_window:
                    self.customizer_window.DragMove()
                else:
                    self.DragMove()
        except Exception as ex:
            pass

    def filter_config_by_revit_context(self, config_items):
        try:
            uiapp = HOST_APP.uiapp
            if not uiapp:
                return config_items
            uidoc = uiapp.ActiveUIDocument
            if not uidoc:
                return config_items
            doc = uidoc.Document
            active_view = uidoc.ActiveView
            if not active_view:
                return config_items
                
            # 1. Determine Current View Type Category
            from Autodesk.Revit.DB import ViewType
            vt = active_view.ViewType
            current_view_category = None
            if vt in [ViewType.ThreeD]:
                current_view_category = "3D"
            elif vt in [ViewType.FloorPlan, ViewType.CeilingPlan, ViewType.AreaPlan, ViewType.EngineeringPlan, ViewType.Elevation, ViewType.Section]:
                current_view_category = "Plan"
            elif vt in [ViewType.DrawingSheet]:
                current_view_category = "Sheet"
                
            # 2. Get Selected Element Classes & Categories
            sel_ids = list(uidoc.Selection.GetElementIds())
            selected_classes = []
            if sel_ids:
                for eid in sel_ids[:5]:
                    el = doc.GetElement(eid)
                    if el:
                        t = el.GetType()
                        while t is not None and t != System.Object:
                            if t.Namespace and t.Namespace.startswith("Autodesk.Revit.DB"):
                                selected_classes.append(t.Name)
                            t = t.BaseType
                        if el.Category:
                            selected_classes.append(el.Category.Name)
                            selected_classes.extend(get_english_names_for_category(el.Category))
            selected_classes = list(set(selected_classes))
            
            filtered = []
            for item in config_items:
                rules = item.get("context_rules")
                if not rules:
                    filtered.append(item)
                    continue
                    
                # Check view type rule
                allowed_views = rules.get("allowed_views", [])
                if allowed_views and current_view_category:
                    if current_view_category not in allowed_views:
                        continue
                        
                # Check element class rule
                allowed_classes = rules.get("allowed_classes", [])
                if allowed_classes:
                    if not selected_classes:
                        continue
                    match_class = False
                    for cls in allowed_classes:
                        if cls in selected_classes:
                            match_class = True
                            break
                    if not match_class:
                        continue
                        
                filtered.append(item)
            return filtered
        except Exception as ex:
            log_debug(u"Error filtering config by Revit context: {}".format(safe_str(ex)))
            return config_items

    def update_core_buttons_visibility(self):
        from System.Windows import Visibility
        if self.customizer_mode:
            self.BtnCoreClose.Visibility = Visibility.Collapsed
            self.BtnCoreSettings.Visibility = Visibility.Collapsed
            self.BtnCoreMove.Visibility = Visibility.Visible
            self.BtnCorePool.Visibility = Visibility.Visible
            self.BtnCoreAppearance.Visibility = Visibility.Visible
            self.BtnCoreExit.Visibility = Visibility.Visible
        else:
            self.BtnCoreClose.Visibility = Visibility.Visible
            self.BtnCoreSettings.Visibility = Visibility.Visible
            self.BtnCoreMove.Visibility = Visibility.Collapsed
            self.BtnCorePool.Visibility = Visibility.Collapsed
            self.BtnCoreAppearance.Visibility = Visibility.Collapsed
            self.BtnCoreExit.Visibility = Visibility.Collapsed

    def on_petal_mouse_down(self, sender, args):
        try:
            if not self.customizer_mode or not getattr(self, "_move_mode_active", False):
                return
                
            from System.Windows.Media import TransformGroup, TranslateTransform
            from System.Windows import Visibility
            
            self._dragged_petal = sender
            self._drag_start_mouse_pos = args.GetPosition(self)
            sender.CaptureMouse()
            
            # Hide the text label and arrow of the dragged petal button during drag
            label_border = getattr(self, sender.Name + "LabelBorder", None)
            if label_border:
                label_border.Visibility = Visibility.Collapsed
            arrow_element = getattr(self, sender.Name + "Arrow", None)
            if arrow_element:
                arrow_element.Visibility = Visibility.Collapsed
            
            self._original_transform = sender.RenderTransform
            self._translate_transform = TranslateTransform(0.0, 0.0)
            
            group = TransformGroup()
            if self._original_transform:
                group.Children.Add(self._original_transform)
            group.Children.Add(self._translate_transform)
            sender.RenderTransform = group
            
            args.Handled = True
            log_debug(u"Started dragging petal: {}".format(sender.Name))
        except Exception as ex:
            log_debug(u"Error in on_petal_mouse_down: {}".format(safe_str(ex)))

    def on_petal_mouse_move(self, sender, args):
        try:
            if not hasattr(self, "_dragged_petal") or self._dragged_petal != sender:
                return
                
            current_pos = args.GetPosition(self)
            dx = current_pos.X - self._drag_start_mouse_pos.X
            dy = current_pos.Y - self._drag_start_mouse_pos.Y
            
            if hasattr(self, "_translate_transform") and self._translate_transform:
                self._translate_transform.X = dx
                self._translate_transform.Y = dy
                
            canvas = sender.Parent
            if canvas:
                mouse_in_canvas = args.GetPosition(canvas)
                dist = math.sqrt((mouse_in_canvas.X - 320.0)**2 + (mouse_in_canvas.Y - 320.0)**2)
                
                btn_name = sender.Name
                level = int(btn_name[4])
                
                settings = self._config_data.get("settings", dict(DEFAULT_SETTINGS))
                core_radius = float(settings.get("core_radius", 45))
                petal_width = float(settings.get("petal_width", 60))
                ring_gap = float(settings.get("ring_gap", 5))
                
                if level == 1:
                    r_out = core_radius + ring_gap + petal_width
                elif level == 2:
                    r_out = core_radius + ring_gap + petal_width + ring_gap + petal_width
                else:
                    r_out = core_radius + ring_gap + petal_width + ring_gap + petal_width + ring_gap + petal_width
                    
                if dist > r_out + 30.0:
                    sender.Opacity = 0.4
                    self.clear_gap()
                else:
                    sender.Opacity = 1.0
                    target_level, target_slot = self.get_slot_from_coordinates(mouse_in_canvas.X, mouse_in_canvas.Y)
                    if target_level == level and target_slot is not None:
                        target_btn = SLOT_BUTTONS.get(target_slot)
                        if target_btn:
                            target_idx = int(target_btn[6:])
                            self.animate_gap(level, target_idx)
                    else:
                        self.clear_gap()
            args.Handled = True
        except Exception as ex:
            log_debug(u"Error in on_petal_mouse_move: {}".format(safe_str(ex)))

    def get_slot_from_coordinates(self, x, y):
        cx, cy = 320.0, 320.0
        dist = math.sqrt((x - cx)**2 + (y - cy)**2)
        
        settings = self._config_data.get("settings", dict(DEFAULT_SETTINGS))
        core_radius = float(settings.get("core_radius", 45))
        petal_width = float(settings.get("petal_width", 60))
        ring_gap = float(settings.get("ring_gap", 5))
        
        # Calculate level boundaries
        r1_in = core_radius + ring_gap
        r1_out = r1_in + petal_width
        
        r2_in = r1_out + ring_gap
        r2_out = r2_in + petal_width
        
        r3_in = r2_out + ring_gap
        r3_out = r3_in + petal_width
        
        # Mid-point boundaries between levels to avoid any overlapping tolerance zones
        b_core_l1 = core_radius + ring_gap / 2.0
        b_l1_l2 = r1_out + ring_gap / 2.0
        b_l2_l3 = r2_out + ring_gap / 2.0
        
        level = None
        if dist < b_core_l1 - 10.0:
            level = None
        elif dist < b_l1_l2:
            level = 1
        elif dist < b_l2_l3:
            level = 2
        elif dist <= r3_out + 25.0:
            level = 3
            
        if not level:
            return None, None
            
        n1, n2, n3 = getattr(self, "_level_counts", (0, 0, 0))
        
        # We need the parent's angle to determine starting position of Level 2/3
        parent_angle = 270.0
        if level == 1:
            n_sectors = max(1, n1)
            n_eff = n_sectors
            start_slot = 1
            start_angle = 270.0 - (360.0 / float(n_eff)) / 2.0
        elif level == 2:
            n_sectors = max(1, n2)
            # Find effective n_sectors (n2_eff)
            l2_max_angle = float(settings.get("l2_max_angle", 90))
            natural_span = 360.0 / float(n_sectors) if n_sectors > 0 else 360.0
            if natural_span > l2_max_angle:
                n_eff = max(n_sectors, int(360.0 / l2_max_angle))
            else:
                n_eff = n_sectors
                
            # Get parent L1 angle
            active_l1 = getattr(self, "_active_l1_parent", None)
            if active_l1:
                # Find the level 1 angle
                for idx in range(1, 11):
                    btn_name = "BtnL1_{}".format(idx)
                    pool_item = getattr(self, "_button_to_pool_item", {}).get(btn_name)
                    if pool_item and pool_item.get("id") == active_l1:
                        parent_angle = 270.0 + (idx - 1) * (360.0 / float(max(1, n1)))
                        break
            start_slot = 11
            span = 360.0 / float(n_eff)
            start_angle = parent_angle - (n_sectors / 2.0) * span
        else:
            n_sectors = max(1, n3)
            l3_max_angle = float(settings.get("l3_max_angle", 90))
            natural_span = 360.0 / float(n_sectors) if n_sectors > 0 else 360.0
            if natural_span > l3_max_angle:
                n_eff = max(n_sectors, int(360.0 / l3_max_angle))
            else:
                n_eff = n_sectors
                
            # Get parent L2 angle
            active_l2 = getattr(self, "_active_l2_parent", None)
            active_l1 = getattr(self, "_active_l1_parent", None)
            parent_l1_angle = 270.0
            if active_l1:
                for idx in range(1, 11):
                    btn_name = "BtnL1_{}".format(idx)
                    pool_item = getattr(self, "_button_to_pool_item", {}).get(btn_name)
                    if pool_item and pool_item.get("id") == active_l1:
                        parent_l1_angle = 270.0 + (idx - 1) * (360.0 / float(max(1, n1)))
                        break
            if active_l2:
                for idx in range(1, 11):
                    btn_name = "BtnL2_{}".format(idx)
                    pool_item = getattr(self, "_button_to_pool_item", {}).get(btn_name)
                    if pool_item and pool_item.get("id") == active_l2:
                        l2_eff = max(n2, int(360.0 / float(settings.get("l2_max_angle", 90)))) if n2 > 0 else 0
                        offset = (idx - 1 - (n2 - 1) / 2.0) * (360.0 / float(l2_eff))
                        parent_angle = parent_l1_angle + offset
                        break
            start_slot = 21
            span = 360.0 / float(n_eff)
            start_angle = parent_angle - (n_sectors / 2.0) * span
            
        rad = math.atan2(y - cy, x - cx)
        deg = rad * 180.0 / math.pi
        if deg < 0:
            deg += 360.0
            
        # Shift angle relative to start_angle
        normalized_deg = deg - start_angle
        while normalized_deg < 0:
            normalized_deg += 360.0
        while normalized_deg >= 360.0:
            normalized_deg -= 360.0
            
        span = 360.0 / float(n_eff)
        boundary_idx = int(round(normalized_deg / span))
        if boundary_idx > n_sectors:
            boundary_idx = n_sectors
            
        target_idx = boundary_idx + 1
        if target_idx < 1:
            target_idx = 1
        elif target_idx > n_sectors + 1:
            target_idx = n_sectors + 1
            
        # Apply hysteresis to make the gap sticky
        curr_lvl = getattr(self, "_current_gap_level", None)
        curr_idx = getattr(self, "_current_gap_idx", None)
        
        if curr_lvl == level and curr_idx is not None:
            curr_boundary_angle = start_angle + (curr_idx - 1) * span
            diff_angle = deg - curr_boundary_angle
            while diff_angle < -180.0:
                diff_angle += 360.0
            while diff_angle >= 180.0:
                diff_angle -= 360.0
                
            # Sticky range is (span / 2.0) + 4.0 degrees.
            # This allows a tiny 4-degree overshoot past the petal center,
            # which prevents flickering but makes the gap follow the mouse instantly.
            gap_threshold = (span / 2.0) + 4.0
            
            if abs(diff_angle) <= gap_threshold:
                target_idx = curr_idx
                
        target_slot = start_slot + target_idx - 1
        return level, target_slot

    def on_petal_mouse_up(self, sender, args):
        try:
            if not hasattr(self, "_dragged_petal") or self._dragged_petal != sender:
                return
                
            sender.ReleaseMouseCapture()
            sender.Opacity = 1.0
            
            # Restore the text label and arrow visibility of the dragged petal button
            from System.Windows import Visibility
            label_border = getattr(self, sender.Name + "LabelBorder", None)
            if label_border:
                label_border.Visibility = Visibility.Visible
            arrow_element = getattr(self, sender.Name + "Arrow", None)
            if arrow_element:
                pool_item = getattr(self, "_button_to_pool_item", {}).get(sender.Name)
                is_pulldown = pool_item.get("is_pulldown", False) if pool_item else False
                if is_pulldown:
                    arrow_element.Visibility = Visibility.Visible
                else:
                    arrow_element.Visibility = Visibility.Collapsed
            
            if hasattr(self, "_original_transform"):
                sender.RenderTransform = self._original_transform
                
            canvas = sender.Parent
            should_delete = False
            btn_name = sender.Name
            level = int(btn_name[4])
            mouse_in_canvas = None
            if canvas:
                mouse_in_canvas = args.GetPosition(canvas)
                dist = math.sqrt((mouse_in_canvas.X - 320.0)**2 + (mouse_in_canvas.Y - 320.0)**2)
                
                settings = self._config_data.get("settings", dict(DEFAULT_SETTINGS))
                core_radius = float(settings.get("core_radius", 45))
                petal_width = float(settings.get("petal_width", 60))
                ring_gap = float(settings.get("ring_gap", 5))
                
                if level == 1:
                    r_out = core_radius + ring_gap + petal_width
                elif level == 2:
                    r_out = core_radius + ring_gap + petal_width + ring_gap + petal_width
                else:
                    r_out = core_radius + ring_gap + petal_width + ring_gap + petal_width + ring_gap + petal_width
                    
                if dist > r_out + 30.0:
                    should_delete = True
                    
            self._dragged_petal = None
            self._original_transform = None
            self._translate_transform = None
            
            if should_delete:
                self.clear_gap()
                pool_item = getattr(self, "_button_to_pool_item", {}).get(sender.Name)
                if pool_item:
                    pool = self._config_data.get("command_pool", [])
                    level1_items = [item for item in pool if item.get("level") == 1]
                    if level == 1 and len(level1_items) <= 1:
                        log_debug(u"Cannot remove the last petal on Level 1.")
                        args.Handled = True
                        return
                        
                    if pool_item in pool:
                        pool.remove(pool_item)
                        
                    self.normalize_slots()
                    save_config(self._config_data)
                    self.load_layout_configuration()
                    self.update_radial_geometry()
                    self.load_pool_list()
                    log_debug(u"Removed petal '{}' (id: {}) via drag-out.".format(pool_item.get("name"), pool_item.get("id")))
            elif mouse_in_canvas:
                source_btn = sender.Name
                source_item = getattr(self, "_button_to_pool_item", {}).get(source_btn)
                
                target_level, target_slot = self.get_slot_from_coordinates(mouse_in_canvas.X, mouse_in_canvas.Y)
                self.clear_gap()
                
                if target_level == level and target_slot is not None:
                    target_btn = SLOT_BUTTONS.get(target_slot)
                    target_item = getattr(self, "_button_to_pool_item", {}).get(target_btn)
                    
                    if source_item and target_item and source_item != target_item:
                        if getattr(self, "_move_mode_active", False):
                            pool = self._config_data.get("command_pool", [])
                            actual_source = None
                            actual_target = None
                            for item in pool:
                                if item.get("id") == source_item.get("id"):
                                    actual_source = item
                                if item.get("id") == target_item.get("id"):
                                    actual_target = item
                            
                            if actual_source and actual_target:
                                target_parent = actual_target.get("parent")
                                level_items = sorted(
                                    [p for p in pool if p.get("level") == level and p.get("parent") == target_parent],
                                    key=lambda x: x.get("priority", 0)
                                )
                                
                                if actual_source in level_items:
                                    level_items.remove(actual_source)
                                    
                                try:
                                    target_idx = level_items.index(actual_target)
                                except ValueError:
                                    target_idx = len(level_items)
                                    
                                actual_source["level"] = level
                                actual_source["parent"] = target_parent
                                level_items.insert(target_idx, actual_source)
                                
                                for idx, item in enumerate(level_items):
                                    item["priority"] = (idx + 1) * 10
                                    
                                save_config(self._config_data)
                                self.load_layout_configuration()
                                self.update_radial_geometry()
                                self.load_pool_list()
                                log_debug(u"Moved petal '{}' before '{}'.".format(actual_source.get("name"), actual_target.get("name")))
                        else:
                            # Swap their priorities
                            sp = source_item.get("priority", 0)
                            tp = target_item.get("priority", 0)
                            source_item["priority"] = tp
                            target_item["priority"] = sp
                            
                            save_config(self._config_data)
                            self.load_layout_configuration()
                            self.update_radial_geometry()
                            self.load_pool_list()
                            log_debug(u"Swapped priorities of '{}' and '{}'.".format(source_item.get("name"), target_item.get("name")))
            else:
                self.clear_gap()
            args.Handled = True
        except Exception as ex:
            log_debug(u"Error in on_petal_mouse_up: {}".format(safe_str(ex)))
            args.Handled = True

    def find_all_commands_safe(self, preloaded_sessionmgr_cmds=None):
        global _cached_commands
        with _cached_commands_lock:
            if _cached_commands is not None:
                log_debug(u"Returning cached pyRevit commands.")
                return _cached_commands

        log_debug(u"Loading active pyRevit commands safely...")
        cmds = []
        unique_ids = set()
        
        # 1. Try to load from sessionmgr
        try:
            all_cmds = preloaded_sessionmgr_cmds
            if all_cmds is None:
                from pyrevit.loader import sessionmgr
                all_cmds = sessionmgr.find_all_commands(cache=True)
            log_debug(u"Found {} commands via sessionmgr.".format(len(all_cmds) if all_cmds else 0))
            if all_cmds:
                for cmd in all_cmds:
                    uid = getattr(cmd, "unique_id", None)
                    if uid:
                        if uid.lower() in unique_ids:
                            continue
                        cmds.append(cmd)
                        unique_ids.add(uid.lower())
        except Exception as ex:
            log_debug(u"Default find_all_commands failed ({}).".format(safe_str(ex)))
            
        # 2. Filesystem scan to discover missing commands
        ext_dirs = []
        try:
            ext_dirs = find_all_extension_dirs()
            log_debug(u"Scanning extension directories: {}".format(ext_dirs))
        except Exception as e_exts:
            log_debug(u"Failed to find extension directories: {}".format(safe_str(e_exts)))

        class MockCommand(object):
            def __init__(self, name, unique_id, extension, script_path):
                self.name = name
                self.title = name
                self.bundle = name
                self.unique_id = unique_id
                self.extension = extension
                self.script = script_path

        suffixes = (".pushbutton", ".smartbutton", ".linkbutton", ".urlbutton", ".contentbutton", ".colorbutton", ".togglebutton")
        
        for ext_dir in ext_dirs:
            try:
                ext_name = get_bundle_title(ext_dir)
                
                # We walk inside the extension directory
                for dirpath, dirnames, filenames in os.walk(ext_dir):
                    if ".git" in dirpath or "bin" in dirpath or "obj" in dirpath:
                        continue
                        
                    for dirname in list(dirnames):
                        lower_dir = dirname.lower()
                        is_btn = False
                        for suffix in suffixes:
                            if lower_dir.endswith(suffix):
                                is_btn = True
                                break
                                
                        if is_btn:
                            button_dir = os.path.join(dirpath, dirname)
                            script_file = os.path.join(button_dir, "script.py")
                            bundle_yaml = os.path.join(button_dir, "bundle.yaml")
                            
                            # A valid button must have either script.py or bundle.yaml
                            if not os.path.exists(script_file) and not os.path.exists(bundle_yaml):
                                continue
                                
                            parent_dir = os.path.dirname(ext_dir)
                            rel_path = button_dir.replace(parent_dir, "").strip(os.path.sep)
                            parts = rel_path.split(os.path.sep)
                            
                            clean_parts = []
                            for p in parts:
                                p_lower = p.lower()
                                if p_lower.endswith(".stack") or p_lower.endswith(".slideout") or any(p_lower.endswith(".stack{}".format(i)) for i in range(1, 10)):
                                    continue
                                stripped = p
                                for suffix in [".extension", ".tab", ".panel", ".pulldown", ".splitbutton"] + list(suffixes):
                                    if p_lower.endswith(suffix):
                                        stripped = p[:-len(suffix)]
                                        break
                                clean_parts.append(clean_id_part(stripped))
                                
                            unique_id = "_".join(clean_parts)
                            
                            if unique_id == "radialmenu_radialmenu_radialmenu_toggleradialmenu":
                                continue
                                
                            if unique_id.lower() in unique_ids:
                                continue
                                
                            # Resolve display title
                            real_name = get_bundle_title(button_dir)
                            
                            cmds.append(MockCommand(real_name, unique_id, ext_name, script_file if os.path.exists(script_file) else button_dir))
                            unique_ids.add(unique_id.lower())
                            log_debug(u"Filesystem scan added missing command: {} ({})".format(real_name, unique_id))
            except Exception as e_scan:
                log_debug(u"Filesystem scan failed for ext {}: {}".format(ext_dir, safe_str(e_scan)))
            
        log_debug(u"Total resolved commands: {}".format(len(cmds)))
        with _cached_commands_lock:
            _cached_commands = cmds
        return cmds

    def load_pyrevit_commands(self):
        log_debug(u"Starting async load of pyRevit commands...")
        try:
            self._ribbon_commands = get_revit_ribbon_commands()
            log_debug(u"Pre-loaded {} Ribbon commands on UI thread.".format(len(self._ribbon_commands)))
        except Exception as ex:
            self._ribbon_commands = []
            log_debug(u"Error pre-loading Ribbon commands: {}".format(safe_str(ex)))
            
        sessionmgr_cmds = []
        try:
            from pyrevit.loader import sessionmgr
            sessionmgr_cmds = list(sessionmgr.find_all_commands(cache=True))
            log_debug(u"Pre-loaded {} commands via sessionmgr on UI thread.".format(len(sessionmgr_cmds)))
        except Exception as e_sm:
            log_debug(u"Failed to pre-load sessionmgr commands on UI thread: {}".format(safe_str(e_sm)))
            
        self._commands_worker_dispatcher = self.Dispatcher
        t = threading.Thread(target=self._async_load_commands_worker, args=(sessionmgr_cmds,))
        t.daemon = True
        t.start()

    def _async_load_commands_worker(self, preloaded_sessionmgr_cmds=None):
        try:
            all_cmds = self.find_all_commands_safe(preloaded_sessionmgr_cmds)
            
            parsed_list = []
            seen_uids = set()
            for cmd in all_cmds:
                if not cmd.unique_id:
                    continue
                if cmd.unique_id == "radialmenu_radialmenu_radialmenu_toggleradialmenu":
                    continue
                
                uid_lower = cmd.unique_id.lower()
                if uid_lower in seen_uids:
                    continue
                seen_uids.add(uid_lower)
                
                # 1. Parse Title safely
                title = getattr(cmd, "title", None) or getattr(cmd, "name", None) or getattr(cmd, "bundle", None) or u"Unknown Command"
                
                # 2. Parse Icon safely
                icon_path = None
                if cmd.script:
                    dir_path = os.path.dirname(cmd.script)
                    for name in ["icon.png", "icon32.png", "icon16.png"]:
                        p = os.path.join(dir_path, name)
                        if os.path.exists(p):
                            icon_path = p
                            break
                            
                # 3. Parse Hierarchy
                ext_name, tab_name, pulldown_name = parse_cmd_hierarchy(cmd)
                
                parsed_list.append({
                    "title": title,
                    "unique_id": cmd.unique_id,
                    "icon_path": resolve_themed_icon(icon_path),
                    "ext_name": ext_name,
                    "tab_name": tab_name,
                    "pulldown_name": pulldown_name
                })
                
            # 4. Load Revit Built-in Commands using the pre-loaded Ribbon structure
            try:
                icons_dir = os.path.join(os.path.dirname(__file__), "extracted_icons")
                ribbon_cmds = getattr(self, "_ribbon_commands", [])
                log_debug(u"Processing {} Ribbon commands in worker...".format(len(ribbon_cmds)))
                
                # Build signatures of discovered pyRevit commands to filter them out of Revit Ribbon list
                pyrevit_sigs = set()
                for p_cmd in parsed_list:
                    try:
                        p_title = p_cmd.get("title") or ""
                        p_tab = p_cmd.get("tab_name") or ""
                        p_pd = p_cmd.get("pulldown_name") or ""
                        t_clean = "".join(c for c in p_title.lower() if c.isalnum())
                        tab_clean = "".join(c for c in p_tab.lower() if c.isalnum())
                        pd_clean = "".join(c for c in p_pd.lower() if c.isalnum())
                        pyrevit_sigs.add((t_clean, tab_clean, pd_clean))
                        if not pd_clean:
                            pyrevit_sigs.add((t_clean, tab_clean, ""))
                    except:
                        pass
                
                # Pre-clean pyRevit unique IDs for fast substring matching
                precleaned_pcmds = []
                for p_cmd in parsed_list:
                    try:
                        p_uid = p_cmd.get("unique_id") or ""
                        uid_clean = "".join(c for c in p_uid.lower() if c.isalnum())
                        precleaned_pcmds.append(uid_clean)
                    except:
                        pass

                seen_ribbon_ids = set()
                for r_cmd in ribbon_cmds:
                    try:
                        cmd_id = r_cmd.get("id")
                        title = r_cmd.get("title") or ""
                        tab_name = r_cmd.get("tab") or ""
                        panel_name = r_cmd.get("panel") or ""
                        
                        if not cmd_id:
                            continue
                            
                        # Clean properties of Ribbon command
                        r_title_clean = "".join(c for c in title.lower() if c.isalnum())
                        r_tab_clean = "".join(c for c in tab_name.lower() if c.isalnum())
                        r_panel_clean = "".join(c for c in panel_name.lower() if c.isalnum())
                        
                        is_pyrevit_match = False
                        if (r_title_clean, r_tab_clean, r_panel_clean) in pyrevit_sigs:
                            is_pyrevit_match = True
                        elif (r_title_clean, r_tab_clean, "") in pyrevit_sigs:
                            is_pyrevit_match = True
                            
                        if not is_pyrevit_match:
                            # Fallback match: if pyRevit command unique_id matches a substring of the Ribbon ID
                            r_id_clean = "".join(c for c in cmd_id.lower() if c.isalnum())
                            for uid_clean in precleaned_pcmds:
                                if uid_clean in r_id_clean:
                                    is_pyrevit_match = True
                                    break
                                    
                        if is_pyrevit_match:
                            continue
                        
                        seen_ribbon_ids.add(cmd_id.lower())
                        
                        # Find matching icon file in extracted_icons
                        safe_filename = "".join([c for c in cmd_id if c.isalnum() or c in ("_", "-")]).strip()
                        icon_path = os.path.join(icons_dir, safe_filename + ".png")
                        if not os.path.exists(icon_path):
                            icon_path = None
                            
                        parsed_list.append({
                            "title": u"{} ({})".format(title, cmd_id),
                            "unique_id": cmd_id,
                            "icon_path": resolve_themed_icon(icon_path) if icon_path else None,
                            "ext_name": u"Revit Ribbon",
                            "tab_name": tab_name,
                            "pulldown_name": panel_name
                        })
                    except:
                        pass
                
                # 5. Load remaining offline/unused icons from extracted_icons folder as fallback
                if os.path.exists(icons_dir):
                    fallback_count = 0
                    for filename in os.listdir(icons_dir):
                        if filename.lower().endswith(".png") and not filename.lower().endswith(".dark.png"):
                            cmd_id = filename[:-4]
                            if cmd_id.lower() not in seen_ribbon_ids:
                                name_part = cmd_id
                                if name_part.startswith("ID_"):
                                    name_part = name_part[3:]
                                prefixes_to_clean = ["OBJECTS_", "RBS_", "ANNOTATIONS_", "ANNOTATE_", "VIEW_", "EDIT_", "FILE_", "SETTINGS_", "BUTTON_", "MODIFY_", "WINDOW_"]
                                for prefix in prefixes_to_clean:
                                    if name_part.startswith(prefix):
                                        name_part = name_part[len(prefix):]
                                        break
                                words = name_part.split("_")
                                clean_words = []
                                for w in words:
                                    if w and w not in clean_words:
                                        clean_words.append(w)
                                formatted_title = " ".join(clean_words).title()
                                
                                parsed_list.append({
                                    "title": u"{} ({})".format(formatted_title, cmd_id),
                                    "unique_id": cmd_id,
                                    "icon_path": resolve_themed_icon(os.path.join(icons_dir, filename)),
                                    "ext_name": u"Revit Ribbon",
                                    "tab_name": u"Other Commands",
                                    "pulldown_name": u"Unsorted"
                                })
                                fallback_count += 1
                    if fallback_count > 0:
                        log_debug(u"Loaded {} additional Revit commands from extracted_icons as fallback.".format(fallback_count))
            except:
                import sys
                e_builtin = sys.exc_info()[1]
                log_debug(u"Failed to load Revit Ribbon commands in worker: {}".format(safe_str(e_builtin)))
                
            self._all_commands = parsed_list
            
            def populate_ui():
                try:
                    self.filter_commands(None)
                    log_debug(u"Async populated CommandTreeView with {} items.".format(len(self._all_commands)))
                except:
                    import sys
                    ex = sys.exc_info()[1]
                    log_debug(u"Error populating CommandTreeView: {}".format(safe_str(ex)))
            
            dispatcher = getattr(self, "_commands_worker_dispatcher", None)
            if dispatcher:
                from System import Action
                self._populate_delegate = Action(populate_ui)
                dispatcher.BeginInvoke(self._populate_delegate)
        except:
            import sys
            ex = sys.exc_info()[1]
            log_debug(u"Error in _async_load_commands_worker: {}".format(safe_str(ex)))

    def on_search_changed(self, sender, args):
        self._search_timer.Stop()
        self._search_timer.Start()

    def filter_commands(self, query):
        try:
            query = query.lower().strip() if query else ""
            # Only populate leaf commands if search query is at least 3 characters long
            # to prevent WPF from rendering thousands of items and freezing Revit.
            has_query = len(query) >= 3
            
            # Step 1: Filter flat list of commands matching query
            filtered_cmds = []
            mode = getattr(self, "picker_mode", "all")
            for cmd in self._all_commands:
                ext_name = cmd["ext_name"]
                
                # Filter by picker mode: built_in shows only Revit Ribbon, pyrevit excludes Revit Ribbon
                if mode == "built_in" and ext_name != u"Revit Ribbon":
                    continue
                if mode == "pyrevit" and ext_name == u"Revit Ribbon":
                    continue
                    
                if has_query:
                    match = (query in cmd["title"].lower() or 
                             query in cmd["ext_name"].lower() or 
                             query in cmd["tab_name"].lower() or
                             (cmd["pulldown_name"] and query in cmd["pulldown_name"].lower()))
                    if not match:
                        continue
                filtered_cmds.append(cmd)
            
            # Step 2: Build hierarchy structure
            tree_data = {}
            for cmd in filtered_cmds:
                ext = cmd["ext_name"]
                tab = cmd["tab_name"]
                pd = cmd["pulldown_name"]
                
                if ext not in tree_data:
                    tree_data[ext] = {}
                if tab not in tree_data[ext]:
                    tree_data[ext][tab] = {}
                if pd not in tree_data[ext][tab]:
                    tree_data[ext][tab][pd] = []
                    
                tree_data[ext][tab][pd].append(cmd)
                
            # Step 3: Build TreeItem hierarchy
            from System.Collections.ObjectModel import ObservableCollection
            root_collection = ObservableCollection[object]()
            
            should_expand = bool(query)
            
            # Helper function to populate tabs/commands under an extension item
            def populate_ext_children(ext_item, tabs):
                for tab_name in sorted(tabs.keys()):
                    tab_item = TreeItem(tab_name, is_command=False, is_expanded=should_expand)
                    ext_item.Children.Add(tab_item)
                    
                    pulldowns = tabs[tab_name]
                    # Folders (pulldowns) first
                    sorted_pd_names = sorted([k for k in pulldowns.keys() if k is not None])
                    for pd_name in sorted_pd_names:
                        cmds_in_pd = sorted(pulldowns[pd_name], key=lambda x: x["title"])
                        first_cmd = cmds_in_pd[0] if cmds_in_pd else None
                        
                        pulldown_id = None
                        pd_icon_path = None
                        if first_cmd:
                            parts = first_cmd["unique_id"].split("_")
                            if len(parts) > 1:
                                pulldown_id = "_".join(parts[:-1])
                            else:
                                pulldown_id = first_cmd["unique_id"]
                            
                            first_cmd_icon = first_cmd.get("icon_path")
                            if first_cmd_icon:
                                pd_dir = os.path.dirname(os.path.dirname(first_cmd_icon))
                                if pd_dir.lower().endswith(".pulldown") or pd_dir.lower().endswith(".splitbutton"):
                                    for name in ["icon.png", "icon32.png", "icon16.png"]:
                                        p = os.path.join(pd_dir, name)
                                        if os.path.exists(p):
                                            pd_icon_path = resolve_themed_icon(p)
                                            break
                                            
                        pd_item = TreeItem(
                            name=pd_name,
                            is_command=False,
                            icon_path=pd_icon_path,
                            unique_id=pulldown_id,
                            extension=first_cmd["ext_name"] if first_cmd else None,
                            is_expanded=should_expand,
                            is_pulldown=True
                        )
                        tab_item.Children.Add(pd_item)
                        
                        cmds_in_pd = sorted(pulldowns[pd_name], key=lambda x: x["title"])
                        for c_info in cmds_in_pd:
                            c_item = TreeItem(
                                name=c_info["title"],
                                is_command=True,
                                icon_path=c_info["icon_path"],
                                unique_id=c_info["unique_id"],
                                extension=c_info["ext_name"]
                            )
                            pd_item.Children.Add(c_item)
                            
                    # Direct commands under tab next
                    if None in pulldowns:
                        direct_cmds = sorted(pulldowns[None], key=lambda x: x["title"])
                        for c_info in direct_cmds:
                            c_item = TreeItem(
                                name=c_info["title"],
                                is_command=True,
                                icon_path=c_info["icon_path"],
                                unique_id=c_info["unique_id"],
                                extension=c_info["ext_name"]
                            )
                            tab_item.Children.Add(c_item)

            # Revit Ribbon root node (if present)
            if "Revit Ribbon" in tree_data:
                ribbon_root = TreeItem("Revit Ribbon", is_command=False, is_expanded=should_expand)
                root_collection.Add(ribbon_root)
                populate_ext_children(ribbon_root, tree_data["Revit Ribbon"])
                
            # pyRevit root node (if there are other extensions present)
            pyrevit_ext_names = sorted([name for name in tree_data.keys() if name != "Revit Ribbon"])
            if pyrevit_ext_names:
                pyrevit_root = TreeItem("pyRevit", is_command=False, is_expanded=should_expand)
                root_collection.Add(pyrevit_root)
                for ext_name in pyrevit_ext_names:
                    ext_item = TreeItem(ext_name, is_command=False, is_expanded=should_expand)
                    pyrevit_root.Children.Add(ext_item)
                    populate_ext_children(ext_item, tree_data[ext_name])
                    
            self.CommandTreeView.ItemsSource = root_collection
        except:
            import sys
            ex = sys.exc_info()[1]
            log_debug(u"Error filtering commands: {}".format(safe_str(ex)))

    def on_pool_mouse_down(self, sender, args):
        try:
            dep = args.OriginalSource
            if dep is not None:
                # Traverse up to see if we clicked a CheckBox, Button or scrollbar/non-item element
                from System.Windows.Media import VisualTreeHelper
                from System.Windows.Controls import CheckBox, Button, TreeViewItem
                curr = dep
                is_control = False
                is_tree_view_item = False
                while curr is not None:
                    if isinstance(curr, (CheckBox, Button)):
                        is_control = True
                        break
                    if isinstance(curr, TreeViewItem):
                        is_tree_view_item = True
                    try:
                        curr = VisualTreeHelper.GetParent(curr)
                    except:
                        break
                
                if is_control or not is_tree_view_item:
                    self._pool_drag_start = None
                    return
                    
                if hasattr(dep, "DataContext") and isinstance(dep.DataContext, PoolListItem):
                    self._pool_drag_start = args.GetPosition(None)
                else:
                    self._pool_drag_start = None
            else:
                self._pool_drag_start = None
        except:
            import sys
            ex = sys.exc_info()[1]
            log_debug("Error in on_pool_mouse_down: " + str(ex))
            self._pool_drag_start = None

    def on_pool_mouse_move(self, sender, args):
        try:
            if args.LeftButton == wpf_input.MouseButtonState.Pressed:
                pos = args.GetPosition(None)
                start_pos = getattr(self, "_pool_drag_start", None)
                if not start_pos:
                    return
                
                dx = abs(pos.X - start_pos.X)
                dy = abs(pos.Y - start_pos.Y)
                
                if dx > SystemParameters.MinimumHorizontalDragDistance or dy > SystemParameters.MinimumVerticalDragDistance:
                    self._pool_drag_start = None  # Clear to prevent duplicate triggers
                    wrapper = self.PoolTreeView.SelectedItem
                    if wrapper and isinstance(wrapper, PoolListItem):
                        item = wrapper._item
                        log_debug(u"Starting drag from pool tree for: {}".format(item.get("name")))
                        
                        # Set up the drag preview popup
                        try:
                            self._init_drag_preview()
                            if getattr(self, "DragPreviewPopup", None):
                                icon = item.get("icon", "")
                                is_image = False
                                if icon:
                                    lower_icon = icon.lower()
                                    if (".png" in lower_icon or ".jpg" in lower_icon or ".jpeg" in lower_icon or "pack://application" in lower_icon or "file:" in lower_icon):
                                        is_image = True
                                        
                                if is_image:
                                    try:
                                        from System.Windows.Media.Imaging import BitmapImage
                                        from System import Uri
                                        self.DragPreviewIconImage.Source = BitmapImage(Uri(icon))
                                        self.DragPreviewIconImage.Visibility = System.Windows.Visibility.Visible
                                        self.DragPreviewIconText.Visibility = System.Windows.Visibility.Collapsed
                                    except:
                                        self.DragPreviewIconImage.Visibility = System.Windows.Visibility.Collapsed
                                        self.DragPreviewIconText.Visibility = System.Windows.Visibility.Collapsed
                                elif icon:
                                    self.DragPreviewIconText.Text = icon
                                    self.DragPreviewIconText.Visibility = System.Windows.Visibility.Visible
                                    self.DragPreviewIconImage.Visibility = System.Windows.Visibility.Collapsed
                                else:
                                    self.DragPreviewIconText.Visibility = System.Windows.Visibility.Collapsed
                                    self.DragPreviewIconImage.Visibility = System.Windows.Visibility.Collapsed
                                    
                                self.DragPreviewText.Text = self.format_command_name_for_display(item.get("name", ""))
                                self.DragPreviewPopup.HorizontalOffset = dx + 15
                                self.DragPreviewPopup.VerticalOffset = dy + 15
                                self.DragPreviewPopup.IsOpen = True
                        except:
                            import sys
                            p_ex = sys.exc_info()[1]
                            log_debug("Failed to show drag preview: " + str(p_ex))

                        import json
                        cmd_dict = {
                            "name": item.get("name"),
                            "unique_id": item.get("command"),
                            "extension": item.get("extension", "pyRevit"),
                            "icon_path": item.get("icon"),
                            "is_pulldown": item.get("command") in ["submenu1", "submenu2"],
                            "is_from_pool": True,
                            "pool_item_id": item.get("id")
                        }
                        cmd_json = json.dumps(cmd_dict)
                        
                        from System import Action
                        def run_drag_drop():
                            try:
                                drag_data = System.Windows.DataObject("PyRevitCommandJSON", cmd_json)
                                System.Windows.DragDrop.DoDragDrop(self.PoolTreeView, drag_data, System.Windows.DragDropEffects.Copy)
                            except:
                                import sys
                                drag_ex = sys.exc_info()[1]
                                log_debug("Async pool DoDragDrop failed: " + str(drag_ex))
                            finally:
                                self.clear_drag_feedback()
                                self.clear_gap()
                                self.hide_drag_preview()
                                
                        self._pool_drag_delegate = Action(run_drag_drop)
                        self.Dispatcher.BeginInvoke(self._pool_drag_delegate)
        except:
            import sys
            ex = sys.exc_info()[1]
            log_debug(u"Error in on_pool_mouse_move: {}".format(safe_str(ex)))

    def update_drag_preview(self, x, y, icon_path, icon_char):
        try:
            if not getattr(self, "DragPreviewBorder", None):
                self.DragPreviewBorder = self.FindName("DragPreviewBorder")
                self.DragPreviewImage = self.FindName("DragPreviewImage")
                self.DragPreviewEmoji = self.FindName("DragPreviewEmoji")
                
            if not self.DragPreviewBorder:
                return
                
            from System.Windows.Controls import Canvas as WPFCanvas
            WPFCanvas.SetLeft(self.DragPreviewBorder, x + 15.0)
            WPFCanvas.SetTop(self.DragPreviewBorder, y + 15.0)
            
            if self.DragPreviewBorder.Visibility != System.Windows.Visibility.Visible:
                self.DragPreviewBorder.Visibility = System.Windows.Visibility.Visible
                
            path_to_use = icon_path if icon_path else icon_char
            if path_to_use:
                looks_like_path = False
                try:
                    p_str = unicode(path_to_use)
                    if p_str.startswith("pack:") or p_str.startswith("http") or (":" in p_str) or ("/" in p_str) or ("\\" in p_str):
                        looks_like_path = True
                except:
                    pass
                    
                if looks_like_path:
                    try:
                        import os
                        if os.path.exists(p_str):
                            from System.Windows.Media.Imaging import BitmapImage, BitmapCacheOption
                            from System.IO import FileStream, FileMode, FileAccess, FileShare
                            bi = BitmapImage()
                            bi.BeginInit()
                            bi.CacheOption = BitmapCacheOption.OnLoad
                            with FileStream(p_str, FileMode.Open, FileAccess.Read, FileShare.Read) as stream:
                                bi.StreamSource = stream
                                bi.EndInit()
                            self.DragPreviewImage.Source = bi
                            self.DragPreviewImage.Visibility = System.Windows.Visibility.Visible
                            self.DragPreviewEmoji.Visibility = System.Windows.Visibility.Collapsed
                            return
                        else:
                            from System.Windows.Media.Imaging import BitmapImage
                            from System import Uri
                            bi = BitmapImage()
                            bi.BeginInit()
                            bi.UriSource = Uri(p_str)
                            bi.EndInit()
                            self.DragPreviewImage.Source = bi
                            self.DragPreviewImage.Visibility = System.Windows.Visibility.Visible
                            self.DragPreviewEmoji.Visibility = System.Windows.Visibility.Collapsed
                            return
                    except Exception as img_ex:
                        log_debug("Drag preview image stream load exception: " + str(img_ex))
                
                self.DragPreviewImage.Visibility = System.Windows.Visibility.Collapsed
                self.DragPreviewEmoji.Text = unicode(path_to_use)
                self.DragPreviewEmoji.Visibility = System.Windows.Visibility.Visible
            else:
                self.DragPreviewImage.Visibility = System.Windows.Visibility.Collapsed
                self.DragPreviewEmoji.Text = u"📦"
                self.DragPreviewEmoji.Visibility = System.Windows.Visibility.Visible
        except Exception as ex:
            log_debug("Error in update_drag_preview: " + str(ex))

    def hide_drag_preview(self):
        try:
            if getattr(self, "DragPreviewBorder", None):
                self.DragPreviewBorder.Visibility = System.Windows.Visibility.Collapsed
        except:
            pass

    def on_window_preview_drag_leave(self, sender, args):
        try:
            self.hide_drag_preview()
        except:
            pass

    def _init_drag_preview(self):
        try:
            if not hasattr(self, "DragPreviewPopup") or not self.DragPreviewPopup:
                popup = self.FindName("DragPreviewPopup")
                if popup:
                    self.DragPreviewPopup = popup
                    self.DragPreviewIconImage = popup.FindName("DragPreviewIconImage")
                    self.DragPreviewIconText = popup.FindName("DragPreviewIconText")
                    self.DragPreviewText = popup.FindName("DragPreviewText")
                else:
                    self.DragPreviewPopup = None
        except Exception as ex:
            log_debug("Error in _init_drag_preview: " + str(ex))

    def clear_drag_feedback(self):
        try:
            self._init_drag_preview()
            if getattr(self, "DragPreviewPopup", None):
                self.DragPreviewPopup.IsOpen = False
                
            if hasattr(self, "_active_drag_tvi") and self._active_drag_tvi:
                self._active_drag_tvi.BorderThickness = Thickness(0)
                self._active_drag_tvi.BorderBrush = self._brush_transparent
                self._active_drag_tvi.Background = self._brush_transparent
                self._active_drag_tvi = None
                self._active_drop_pos = None
        except:
            pass

    def on_pool_tree_drag_leave(self, sender, args):
        self.clear_drag_feedback()

    def on_pool_tree_drag_over(self, sender, args):
        if not args.Data.GetDataPresent("PyRevitCommandJSON"):
            args.Effects = getattr(System.Windows.DragDropEffects, "None")
            args.Handled = True
            return
            
        args.Effects = System.Windows.DragDropEffects.Copy
        args.Handled = True
        
        try:
            # Update Drag Preview position relative to PoolTreeView
            self._init_drag_preview()
            if getattr(self, "DragPreviewPopup", None):
                pos = args.GetPosition(self.PoolTreeView)
                self.DragPreviewPopup.HorizontalOffset = pos.X + 15
                self.DragPreviewPopup.VerticalOffset = pos.Y + 15
            
            dep = args.OriginalSource
            target_tvi = None
            while dep is not None:
                if isinstance(dep, TreeViewItem):
                    target_tvi = dep
                    break
                dep = VisualTreeHelper.GetParent(dep)
                
            if target_tvi:
                point = args.GetPosition(target_tvi)
                item_height = target_tvi.ActualHeight
                if item_height <= 0:
                    item_height = 32
                    
                target_wrapper = target_tvi.DataContext
                if not target_wrapper or not isinstance(target_wrapper, PoolListItem):
                    self.clear_drag_feedback()
                    return
                    
                target_item = target_wrapper._item
                is_submenu = target_item.get("command") in ["submenu1", "submenu2"]
                
                # Determine drop position (Before, After, or Inside)
                if is_submenu:
                    if point.Y < item_height * 0.25:
                        drop_pos = "Before"
                    elif point.Y > item_height * 0.75:
                        drop_pos = "After"
                    else:
                        drop_pos = "Inside"
                else:
                    if point.Y < item_height * 0.5:
                        drop_pos = "Before"
                    else:
                        drop_pos = "After"
                        
                # Update visuals if target or position changed
                active_tvi = getattr(self, "_active_drag_tvi", None)
                active_pos = getattr(self, "_active_drop_pos", None)
                
                if target_tvi != active_tvi or drop_pos != active_pos:
                    if active_tvi and active_tvi != target_tvi:
                        active_tvi.BorderThickness = Thickness(0)
                        active_tvi.BorderBrush = self._brush_transparent
                        active_tvi.Background = self._brush_transparent
                        
                    self._active_drag_tvi = target_tvi
                    self._active_drop_pos = drop_pos
                    
                    if drop_pos == "Before":
                        target_tvi.BorderThickness = Thickness(0, 2.5, 0, 0)
                        target_tvi.BorderBrush = self._brush_accent
                        target_tvi.Background = self._brush_before_after
                    elif drop_pos == "After":
                        target_tvi.BorderThickness = Thickness(0, 0, 0, 2.5)
                        target_tvi.BorderBrush = self._brush_accent
                        target_tvi.Background = self._brush_before_after
                    elif drop_pos == "Inside":
                        target_tvi.BorderThickness = Thickness(0)
                        target_tvi.BorderBrush = self._brush_transparent
                        target_tvi.Background = self._brush_inside
            else:
                self.clear_drag_feedback()
        except Exception as ex:
            pass

    def on_pool_tree_drop(self, sender, args):
        if not args.Data.GetDataPresent("PyRevitCommandJSON"):
            self.clear_drag_feedback()
            return
            
        cmd_json = args.Data.GetData("PyRevitCommandJSON")
        try:
            import json
            cmd_data = json.loads(cmd_json)
            
            if not cmd_data.get("is_from_pool"):
                self.clear_drag_feedback()
                return
                
            pool_item_id = cmd_data.get("pool_item_id")
            if not pool_item_id:
                self.clear_drag_feedback()
                return
                
            pool = self._config_data.setdefault("command_pool", [])
            
            # Find the dragged item in the pool
            dragged_item = None
            for item in pool:
                if item.get("id") == pool_item_id:
                    dragged_item = item
                    break
                    
            if not dragged_item:
                self.clear_drag_feedback()
                return
                
            # Get target item and position from the active drag feedback
            target_tvi = getattr(self, "_active_drag_tvi", None)
            drop_pos = getattr(self, "_active_drop_pos", None)
            
            # Resolve target wrapper
            target_wrapper = target_tvi.DataContext if target_tvi else None
            
            # 1. Dropped onto empty space
            if not target_wrapper or not isinstance(target_wrapper, PoolListItem):
                # Exclude from submenu: move to level 1, parent = None
                dragged_item["level"] = 1
                dragged_item["parent"] = None
                
                # Move to the end of the pool list
                if dragged_item in pool:
                    pool.remove(dragged_item)
                pool.append(dragged_item)
                
                log_debug(u"Moved item '{}' to Level 1 (excluded from submenu).".format(dragged_item.get("name")))
                
            # 2. Dropped onto another item
            else:
                target_item = target_wrapper._item
                if target_item.get("id") == dragged_item.get("id"):
                    self.clear_drag_feedback()
                    return
                    
                # A. Dropped INSIDE a submenu: Add to this submenu!
                if drop_pos == "Inside":
                    is_dragged_submenu = dragged_item.get("command") in ["submenu1", "submenu2"]
                    if is_dragged_submenu:
                        from pyrevit import forms
                        forms.toast("Cannot nest submenus inside submenus.", title="Radial Menu")
                        self.clear_drag_feedback()
                        return
                        
                    # Add to submenu
                    target_level = target_item.get("level", 1)
                    dragged_item["level"] = target_level + 1
                    dragged_item["parent"] = target_item.get("id")
                    
                    # Place at the end of the submenu's children
                    if dragged_item in pool:
                        pool.remove(dragged_item)
                    # Insert after the target_item in list order
                    t_idx = pool.index(target_item)
                    pool.insert(t_idx + 1, dragged_item)
                    
                    # Ensure target submenu is expanded to show dropped item
                    if not hasattr(self, "_expanded_item_ids_cache") or self._expanded_item_ids_cache is None:
                        self._expanded_item_ids_cache = set()
                    self._expanded_item_ids_cache.add(target_item.get("id"))
                    
                    log_debug(u"Added item '{}' to submenu '{}'.".format(dragged_item.get("name"), target_item.get("name")))
                    
                # B. Dropped BEFORE or AFTER an item
                else:
                    # Inherit parent and level from target item
                    dragged_item["level"] = target_item.get("level", 1)
                    dragged_item["parent"] = target_item.get("parent")
                    
                    if dragged_item in pool:
                        pool.remove(dragged_item)
                        
                    t_idx = pool.index(target_item)
                    if drop_pos == "Before":
                        pool.insert(t_idx, dragged_item)
                        log_debug(u"Reordered item '{}' before '{}'.".format(dragged_item.get("name"), target_item.get("name")))
                    else:
                        pool.insert(t_idx + 1, dragged_item)
                        log_debug(u"Reordered item '{}' after '{}'.".format(dragged_item.get("name"), target_item.get("name")))
            
            # Recalculate priorities based on new list order
            for idx, item in enumerate(pool):
                item["priority"] = (idx + 1) * 10
                
            # Save configuration and reload UI
            save_config(self._config_data)
            self.load_layout_configuration()
            self.load_pool_list()
            self.update_radial_geometry()
            
        except Exception as ex:
            log_debug(u"Error in on_pool_tree_drop: {}".format(safe_str(ex)))
        
        self.clear_drag_feedback()
        args.Handled = True

    def on_tree_mouse_down(self, sender, args):
        try:
            dep = args.OriginalSource
            if dep is not None:
                from System.Windows.Media import VisualTreeHelper
                from System.Windows.Controls import TreeViewItem
                curr = dep
                is_tree_view_item = False
                while curr is not None:
                    if isinstance(curr, TreeViewItem):
                        is_tree_view_item = True
                        break
                    try:
                        curr = VisualTreeHelper.GetParent(curr)
                    except:
                        break
                if is_tree_view_item:
                    self._drag_start_point = args.GetPosition(None)
                else:
                    self._drag_start_point = None
            else:
                self._drag_start_point = None
        except:
            self._drag_start_point = None

    def on_tree_mouse_move(self, sender, args):
        if args.LeftButton == wpf_input.MouseButtonState.Pressed:
            start_pt = getattr(self, "_drag_start_point", None)
            if not start_pt:
                return
            position = args.GetPosition(None)
            if (abs(position.X - start_pt.X) > System.Windows.SystemParameters.MinimumHorizontalDragDistance or \
                abs(position.Y - start_pt.Y) > System.Windows.SystemParameters.MinimumVerticalDragDistance):
                
                self._drag_start_point = None  # Clear to prevent duplicate triggers
                
                from System.Windows.Media import VisualTreeHelper
                from System.Windows.Controls import TreeViewItem
                
                dependency_obj = args.OriginalSource
                while dependency_obj is not None and not isinstance(dependency_obj, TreeViewItem):
                    dependency_obj = VisualTreeHelper.GetParent(dependency_obj)
                
                if dependency_obj is not None:
                    cmd_item = dependency_obj.Header
                    if cmd_item and (getattr(cmd_item, "IsCommand", False) or getattr(cmd_item, "IsPulldown", False)):
                        log_debug(u"Starting drag for command: {}".format(cmd_item.Name))
                        import json
                        cmd_dict = {
                            "name": cmd_item.Name,
                            "unique_id": cmd_item.UniqueId,
                            "extension": cmd_item.Extension,
                            "icon_path": cmd_item._icon_path,
                            "is_pulldown": getattr(cmd_item, "IsPulldown", False)
                        }
                        cmd_json = json.dumps(cmd_dict)
                        
                        from System import Action
                        def run_drag_drop():
                            try:
                                drag_data = System.Windows.DataObject("PyRevitCommandJSON", cmd_json)
                                System.Windows.DragDrop.DoDragDrop(dependency_obj, drag_data, System.Windows.DragDropEffects.Copy)
                            except:
                                import sys
                                drag_ex = sys.exc_info()[1]
                                log_debug("Async picker tree DoDragDrop failed: " + str(drag_ex))
                            finally:
                                self.clear_gap()
                                self.hide_drag_preview()
                                
                        self._tree_drag_delegate = Action(run_drag_drop)
                        self.Dispatcher.BeginInvoke(self._tree_drag_delegate)

    def on_button_drag_over(self, sender, args):
        if args.Data.GetDataPresent("PyRevitCommandJSON"):
            args.Effects = System.Windows.DragDropEffects.Copy
            args.Handled = True
        else:
            args.Effects = getattr(System.Windows.DragDropEffects, "None")
            args.Handled = True

    def on_button_drop(self, sender, args):
        if args.Data.GetDataPresent("PyRevitCommandJSON"):
            cmd_json = args.Data.GetData("PyRevitCommandJSON")
            try:
                import json
                cmd_data = json.loads(cmd_json)
                slot_num = BUTTON_SLOTS.get(sender.Name)
                if slot_num is not None:
                    log_debug(u"Dropped command '{}' onto slot {}.".format(cmd_data["name"], slot_num))
                    self.assign_command_to_slot_data(slot_num, cmd_data)
                else:
                    log_debug(u"Dropped command but could not resolve slot for button '{}'.".format(sender.Name))
            except:
                import sys
                ex = sys.exc_info()[1]
                log_debug(u"Failed to process dropped data: {}".format(safe_str(ex)))
            args.Handled = True

    def assign_command_to_slot_data(self, slot_num, cmd_data):
        try:
            # Check if we are dragging an existing pool item
            is_from_pool = cmd_data.get("is_from_pool", False)
            pool_item_id = cmd_data.get("pool_item_id")
            
            # Find the dragged item in the pool
            dragged_item = None
            pool = self._config_data.setdefault("command_pool", [])
            if is_from_pool and pool_item_id:
                for item in pool:
                    if item.get("id") == pool_item_id:
                        dragged_item = item
                        break
                        
            btn_name = SLOT_BUTTONS.get(slot_num)
            pool_item = getattr(self, "_button_to_pool_item", {}).get(btn_name)
            
            # Resolve pool_item to the actual dict reference in config_data to prevent modifying copies
            actual_pool_item = None
            if pool_item:
                item_id = pool_item.get("id")
                for item in pool:
                    if item.get("id") == item_id:
                        actual_pool_item = item
                        break
            
            # Determine target properties
            if 1 <= slot_num <= 10:
                target_level = 1
                target_parent = None
                target_priority = slot_num * 10
            elif 11 <= slot_num <= 20:
                target_level = 2
                target_parent = getattr(self, "_active_l1_parent", "submenu1") or "submenu1"
                target_priority = (slot_num - 10) * 10
            else:
                target_level = 3
                target_parent = getattr(self, "_active_l2_parent", "submenu2") or "submenu2"
                target_priority = (slot_num - 20) * 10
                
            if actual_pool_item:
                target_level = actual_pool_item.get("level", target_level)
                target_parent = actual_pool_item.get("parent", target_parent)
                target_priority = actual_pool_item.get("priority", target_priority)
                
            if dragged_item:
                # We are moving an existing pool item!
                if getattr(self, "_move_mode_active", False) and actual_pool_item and actual_pool_item != dragged_item:
                    level_items = sorted(
                        [p for p in pool if p.get("level") == target_level and p.get("parent") == target_parent],
                        key=lambda x: x.get("priority", 0)
                    )
                    if dragged_item in level_items:
                        level_items.remove(dragged_item)
                        
                    try:
                        target_idx = level_items.index(actual_pool_item)
                    except ValueError:
                        target_idx = len(level_items)
                        
                    dragged_item["level"] = target_level
                    dragged_item["parent"] = target_parent
                    level_items.insert(target_idx, dragged_item)
                    
                    for idx, item in enumerate(level_items):
                        item["priority"] = (idx + 1) * 10
                        
                    log_debug(u"Moved pool item '{}' before '{}'.".format(dragged_item.get("name"), actual_pool_item.get("name")))
                else:
                    # If there's a target item currently in that slot, swap their positions!
                    if actual_pool_item and actual_pool_item != dragged_item:
                        # Save dragged item's current position
                        orig_level = dragged_item.get("level", 1)
                        orig_parent = dragged_item.get("parent")
                        orig_priority = dragged_item.get("priority", 0)
                        
                        # Update dragged item to target position
                        dragged_item["level"] = target_level
                        dragged_item["parent"] = target_parent
                        dragged_item["priority"] = target_priority
                        
                        # Update target item to dragged item's original position
                        actual_pool_item["level"] = orig_level
                        actual_pool_item["parent"] = orig_parent
                        actual_pool_item["priority"] = orig_priority
                        
                        log_debug(u"Swapped pool item '{}' with '{}'.".format(dragged_item.get("name"), actual_pool_item.get("name")))
                    else:
                        # Target slot is empty, just move dragged item there
                        dragged_item["level"] = target_level
                        dragged_item["parent"] = target_parent
                        dragged_item["priority"] = target_priority
                        log_debug(u"Moved pool item '{}' to slot {}.".format(dragged_item.get("name"), slot_num))
                        
                # Save config and refresh everything
                save_config(self._config_data)
                self.load_layout_configuration()
                self.update_radial_geometry()
                self.load_pool_list()
                return

            # If not dragging from pool, we use the normal assignment/overwrite logic
            insert_before_item = None
            if getattr(self, "_move_mode_active", False) and actual_pool_item:
                insert_before_item = actual_pool_item
                actual_pool_item = None

            if actual_pool_item:
                level = actual_pool_item.get("level", 1)
                parent = actual_pool_item.get("parent")
                priority = actual_pool_item.get("priority", slot_num * 10)
            else:
                level = target_level
                parent = target_parent
                priority = target_priority

            is_pulldown = cmd_data.get("is_pulldown", False)
            pulldown_id = cmd_data["unique_id"]

            if is_pulldown:
                if level == 3:
                    from pyrevit import forms
                    forms.toast("Pulldowns cannot be added to Level 3 (max depth reached).", title="Radial Menu")
                    return
                
                submenu_cmd = "submenu1" if level == 1 else "submenu2"
                
                # Check if pool item already exists for this slot
                if actual_pool_item:
                    actual_pool_item["type"] = "built_in"
                    actual_pool_item["name"] = cmd_data["name"]
                    actual_pool_item["command"] = submenu_cmd
                    actual_pool_item["icon"] = cmd_data["icon_path"] or u"\u25B6"
                    actual_pool_item["id"] = pulldown_id
                else:
                    import System
                    new_item = {
                        "id": pulldown_id,
                        "type": "built_in",
                        "name": cmd_data["name"],
                        "command": submenu_cmd,
                        "icon": cmd_data["icon_path"] or u"\u25B6",
                        "level": level,
                        "parent": parent,
                        "priority": priority,
                        "context_rules": {}
                    }
                    self._config_data.setdefault("command_pool", []).append(new_item)
                
                # Find all child commands belonging to this pulldown
                child_cmds = []
                for c in self._all_commands:
                    uid = c.get("unique_id", "")
                    if uid.startswith(pulldown_id + "_"):
                        child_cmds.append(c)
                
                child_cmds = sorted(child_cmds, key=lambda x: x.get("title", ""))
                
                # Clear any existing children of this pulldown from the pool
                pool = self._config_data.setdefault("command_pool", [])
                pool = [p for p in pool if p.get("parent") != pulldown_id]
                
                # Add child commands to the next level
                next_level = level + 1
                custom_children = cmd_data.get("children", [])
                if custom_children:
                    for idx, child in enumerate(custom_children[:10]):  # Max 10 items per level
                        child_uid = child["unique_id"]
                        child_type = "pyrevit" if "customctrl_%" in child_uid.lower() else "built_in"
                        new_child = {
                            "id": child_uid,
                            "type": child_type,
                            "name": child["name"],
                            "command": child_uid,
                            "icon": child.get("icon_path") or "",
                            "level": next_level,
                            "parent": pulldown_id,
                            "priority": (idx + 1) * 10,
                            "context_rules": {}
                        }
                        pool.append(new_child)
                else:
                    for idx, child in enumerate(child_cmds[:10]):  # Max 10 items per level
                        new_child = {
                            "id": child["unique_id"],
                            "type": "pyrevit",
                            "name": child["title"],
                            "command": child["unique_id"],
                            "icon": child["icon_path"] or "",
                            "level": next_level,
                            "parent": pulldown_id,
                            "priority": (idx + 1) * 10,
                            "context_rules": {}
                        }
                        pool.append(new_child)
                
                # If we are in Move mode and dropped onto an existing petal, insert before it
                if insert_before_item:
                    target_level = insert_before_item.get("level", 1)
                    target_parent = insert_before_item.get("parent")
                    level_items = sorted(
                        [p for p in pool if p.get("level") == target_level and p.get("parent") == target_parent and p.get("id") != pulldown_id],
                        key=lambda x: x.get("priority", 0)
                    )
                    try:
                        target_idx = level_items.index(insert_before_item)
                    except ValueError:
                        target_idx = len(level_items)
                        
                    actual_new_item = None
                    for p in pool:
                        if p.get("id") == pulldown_id:
                            actual_new_item = p
                            break
                    if actual_new_item:
                        actual_new_item["level"] = target_level
                        actual_new_item["parent"] = target_parent
                        level_items.insert(target_idx, actual_new_item)
                        for idx, item in enumerate(level_items):
                            item["priority"] = (idx + 1) * 10
                            
                self._config_data["command_pool"] = pool
                save_config(self._config_data)
                self.load_layout_configuration()
                self.update_radial_geometry()
                self.load_pool_list()
                log_debug(u"Assigned pulldown '{}' as submenu with {} children.".format(cmd_data["name"], len(child_cmds)))
            else:
                is_builtin = (cmd_data.get("extension") in ["Revit Built-in", "Revit Ribbon"])
                cmd_type = "built_in" if is_builtin else "pyrevit"
                
                display_name = cmd_data["name"]
                if is_builtin and " (" in display_name:
                    display_name = display_name.split(" (")[0].strip()
                    
                icon_val = cmd_data.get("icon_path")
                if icon_val:
                    if os.path.isabs(icon_val) and "extracted_icons" in icon_val:
                        parts = icon_val.split("extracted_icons")
                        if len(parts) > 1:
                            icon_val = "extracted_icons" + parts[-1].replace("\\", "/")
                            
                if actual_pool_item:
                    actual_pool_item["type"] = cmd_type
                    actual_pool_item["name"] = display_name
                    actual_pool_item["command"] = cmd_data["unique_id"]
                    actual_pool_item["icon"] = icon_val
                    
                    save_config(self._config_data)
                    self.load_layout_configuration()
                    self.update_radial_geometry()
                    self.load_pool_list()
                    log_debug(u"Assigned command '{}' (type: {}) to pool item for slot {}.".format(display_name, cmd_type, slot_num))
                else:
                    import System
                    new_item = {
                        "id": "item_" + str(slot_num) + "_" + System.Guid.NewGuid().ToString()[:8],
                        "type": cmd_type,
                        "name": display_name,
                        "command": cmd_data["unique_id"],
                        "icon": icon_val,
                        "level": level,
                        "parent": parent,
                        "priority": priority,
                        "context_rules": {}
                    }
                    self._config_data.setdefault("command_pool", []).append(new_item)
                    
                    if insert_before_item:
                        target_level = insert_before_item.get("level", 1)
                        target_parent = insert_before_item.get("parent")
                        pool = self._config_data.setdefault("command_pool", [])
                        level_items = sorted(
                            [p for p in pool if p.get("level") == target_level and p.get("parent") == target_parent and p != new_item],
                            key=lambda x: x.get("priority", 0)
                        )
                        try:
                            target_idx = level_items.index(insert_before_item)
                        except ValueError:
                            target_idx = len(level_items)
                            
                        new_item["level"] = target_level
                        new_item["parent"] = target_parent
                        level_items.insert(target_idx, new_item)
                        for idx, item in enumerate(level_items):
                            item["priority"] = (idx + 1) * 10
                            
                    save_config(self._config_data)
                    self.load_layout_configuration()
                    self.update_radial_geometry()
                    self.load_pool_list()
                    log_debug(u"Created new pool item for slot {} with command '{}' (type: {}).".format(slot_num, display_name, cmd_type))

        except Exception as ex:
            log_debug(u"Failed to assign command to slot: {}".format(safe_str(ex)))
            
    def on_input_manager_pre_notify(self, sender, args):
        try:
            if not getattr(self, "customizer_mode", False) or not getattr(self, "_move_mode_active", False):
                return
            if not args or not args.StagingItem or not args.StagingItem.Input:
                return
            e = args.StagingItem.Input
            
            from System.Windows.Input import MouseButtonEventArgs, MouseEventArgs, MouseButtonState, MouseButton
            
            # Check for mouse down
            if isinstance(e, MouseButtonEventArgs) and e.RoutedEvent and e.RoutedEvent.Name == "PreviewMouseDown":
                if e.ChangedButton == MouseButton.Left:
                    self._ribbon_drag_start = System.Windows.Input.Mouse.GetPosition(None)
                    self._ribbon_dragged_item = None
                    
                    dep = e.OriginalSource
                    log_debug("PreviewMouseDown source: {} ({})".format(str(dep), type(dep).__name__))
                    import System.Windows.Media as media
                    
                    best_match = None
                    while dep is not None:
                        # Check both the DataContext and the visual element itself
                        candidates = []
                        if hasattr(dep, "DataContext") and dep.DataContext:
                            candidates.append(dep.DataContext)
                        candidates.append(dep)
                        
                        for candidate in candidates:
                            try:
                                c_type = candidate.GetType()
                                c_type_name = c_type.FullName
                                c_ns = c_type.Namespace or ""
                                if "Autodesk.Windows" in c_ns:
                                    is_pulldown = (
                                        "RibbonSplitButton" in c_type_name 
                                        or "RibbonListButton" in c_type_name 
                                        or "RibbonGallery" in c_type_name
                                    )
                                    is_btn = (
                                        "RibbonButton" in c_type_name 
                                        or "RibbonCommandItem" in c_type_name 
                                        or "RibbonItem" in c_type_name
                                    )
                                    if (is_pulldown or is_btn) and getattr(candidate, "Id", None):
                                        if is_pulldown:
                                            best_match = candidate
                                            break  # Found the container, stop looking at this element's candidates
                                        elif best_match is None:
                                            best_match = candidate
                            except Exception as c_ex:
                                log_debug("Candidate check failed: " + str(c_ex))
                                pass
                                
                        # If we found a pulldown container, we can stop traversing higher up the visual tree
                        if best_match:
                            bm_type_name = best_match.GetType().Name
                            if "RibbonSplitButton" in bm_type_name or "RibbonListButton" in bm_type_name or "RibbonGallery" in bm_type_name:
                                break
                                
                        if isinstance(dep, media.Visual) or hasattr(media.VisualTreeHelper, "GetParent"):
                            try:
                                dep = media.VisualTreeHelper.GetParent(dep)
                            except Exception as tree_ex:
                                log_debug("GetParent failed: " + str(tree_ex))
                                break
                        else:
                            break
                            
                    if best_match:
                        self._ribbon_dragged_item = best_match
                        log_debug("Found Ribbon Item! Id={}, Type={}".format(best_match.Id, best_match.GetType().Name))
                            
            # Check for mouse move
            elif isinstance(e, MouseEventArgs) and e.RoutedEvent and e.RoutedEvent.Name == "PreviewMouseMove":
                if not getattr(self, "_ribbon_dragged_item", None):
                    return
                    
                if e.LeftButton != MouseButtonState.Pressed:
                    self._ribbon_dragged_item = None
                    return
                    
                pos = System.Windows.Input.Mouse.GetPosition(None)
                start_pos = getattr(self, "_ribbon_drag_start", None)
                if not start_pos:
                    return
                    
                from System.Windows import SystemParameters
                diff_x = abs(pos.X - start_pos.X)
                diff_y = abs(pos.Y - start_pos.Y)
                
                if diff_x > SystemParameters.MinimumHorizontalDragDistance or diff_y > SystemParameters.MinimumVerticalDragDistance:
                    item = self._ribbon_dragged_item
                    self._ribbon_dragged_item = None # Reset immediately to prevent multiple triggers
                    
                    item_id = getattr(item, "Id", None)
                    if not item_id:
                        return
                        
                    # Mark the event as Handled so Revit doesn't also process mouse movement (e.g. dragging panels)
                    e.Handled = True
                    
                    item_text = getattr(item, "Text", "Command")
                    item_name = item_text.replace("\n", " ").replace("\r", " ").strip()
                    
                    is_pyrevit = "customctrl_%customctrl_%" in item_id.lower()
                    pyrevit_unique_id = None
                    
                    if is_pyrevit:
                        id_lower = item_id.lower()
                        if hasattr(self, "_all_commands") and self._all_commands:
                            for p_cmd in self._all_commands:
                                p_uid = p_cmd.get("unique_id", "")
                                if p_uid.lower() in id_lower or p_uid.replace("_", "").lower() in id_lower.replace("%", "").replace("_", ""):
                                    pyrevit_unique_id = p_uid
                                    break
                        if not pyrevit_unique_id:
                            pyrevit_unique_id = item_id
                    
                    # Helper to save Ribbon item icon on-the-fly
                    def save_item_icon(r_item):
                        if not r_item or not getattr(r_item, "Id", None):
                            return ""
                        r_id = r_item.Id
                        safe_fn = "".join([c for c in r_id if c.isalnum() or c in ("_", "-")]).strip()
                        if not safe_fn:
                            return ""
                            
                        import os
                        icons_dir = os.path.join(os.path.dirname(__file__), "extracted_icons")
                        if not os.path.exists(icons_dir):
                            try:
                                os.makedirs(icons_dir)
                            except:
                                pass
                                
                        global _IS_REVIT_DARK
                        suffix = ".dark.png" if _IS_REVIT_DARK else ".png"
                        file_path = os.path.join(icons_dir, safe_fn + suffix)
                        
                        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                            img = None
                            if hasattr(r_item, "LargeImage") and r_item.LargeImage:
                                img = r_item.LargeImage
                            elif hasattr(r_item, "Image") and r_item.Image:
                                img = r_item.Image
                                
                            if img:
                                try:
                                    from System.Windows.Media.Imaging import PngBitmapEncoder, BitmapFrame
                                    encoder = PngBitmapEncoder()
                                    encoder.Frames.Add(BitmapFrame.Create(img))
                                    with System.IO.FileStream(file_path, System.IO.FileMode.Create, System.IO.FileAccess.Write, getattr(System.IO.FileShare, "None")) as fs:
                                        encoder.Save(fs)
                                    log_debug(u"Extracted icon on drag for: {} (theme={})".format(r_id, suffix))
                                except Exception as e_save:
                                    log_debug(u"Failed to extract icon on drag: {}".format(str(e_save)))
                        return file_path if os.path.exists(file_path) else ""

                    is_pulldown = False
                    ctx_type_name = item.GetType().Name
                    if "RibbonListButton" in ctx_type_name or "RibbonSplitButton" in ctx_type_name or "RibbonGallery" in ctx_type_name:
                        is_pulldown = True
                        
                    children_list = []
                    if is_pulldown:
                        try:
                            if hasattr(item, "Items") and item.Items:
                                for child in item.Items:
                                    child_id = getattr(child, "Id", None)
                                    if child_id:
                                        child_text = getattr(child, "Text", "") or getattr(child, "Name", "") or "Command"
                                        child_name = child_text.replace("\n", " ").replace("\r", " ").strip()
                                        
                                        # Save and resolve icon
                                        child_icon = save_item_icon(child)
                                        
                                        children_list.append({
                                            "name": child_name,
                                            "unique_id": child_id,
                                            "icon_path": child_icon
                                        })
                        except Exception as child_ex:
                            log_debug("Failed to extract children of pulldown: " + str(child_ex))
                        
                    cmd_type = "pyrevit" if is_pyrevit else "built_in"
                    cmd_value = pyrevit_unique_id if is_pyrevit else item_id
                    
                    # Save main item icon on-the-fly
                    icon_path = save_item_icon(item)
                            
                    import json
                    cmd_dict = {
                        "name": item_name,
                        "unique_id": cmd_value,
                        "extension": "pyRevit" if is_pyrevit else "Revit Built-in",
                        "icon_path": icon_path,
                        "is_pulldown": is_pulldown,
                        "children": children_list
                    }
                    cmd_json = json.dumps(cmd_dict)
                    
                    log_debug(u"Initiating async drag from Revit UI for: {} (type={}, val={}, is_pulldown={})".format(
                        item_name, cmd_type, cmd_value, is_pulldown
                    ))
                    
                    # Schedule DoDragDrop to run asynchronously on the Dispatcher
                    from System import Action
                    def run_drag_drop():
                        try:
                            import System.Windows
                            drag_data = System.Windows.DataObject("PyRevitCommandJSON", cmd_json)
                            System.Windows.DragDrop.DoDragDrop(self, drag_data, System.Windows.DragDropEffects.Copy)
                        except Exception as drag_ex:
                            log_debug("Async DoDragDrop failed: " + str(drag_ex))
                        finally:
                            self.clear_gap()
                            self.hide_drag_preview()
                            
                    self._menu_drag_delegate = Action(run_drag_drop)
                    self.Dispatcher.BeginInvoke(self._menu_drag_delegate)
                    
        except Exception as ex:
            log_debug("Error in on_input_manager_pre_notify: " + str(ex))

    def on_reset_clicked(self, sender, args):
        try:
            self._config_data["command_pool"] = list(DEFAULT_POOL)
            self._config_data["settings"] = dict(DEFAULT_SETTINGS)
            save_config(self._config_data)
            self.load_layout_configuration()
            self.update_radial_geometry()
            self.update_settings_ui_from_config()
            self.load_pool_list()
            log_debug(u"Radial Menu reset to default flat pool.")
        except Exception as ex:
            log_debug(u"Failed to reset: {}".format(safe_str(ex)))

    def on_button_clicked_dynamic(self, sender, args):
        try:
            if hasattr(self, "_button_to_slot_map") and sender.Name in self._button_to_slot_map:
                slot_num = self._button_to_slot_map[sender.Name]
                self.on_slot_clicked(slot_num)
        except Exception as ex:
            log_debug(u"Error in on_button_clicked_dynamic: {}".format(safe_str(ex)))

    def on_slot_clicked(self, slot_num):
        if self._is_closing:
            return
            
        # If we are in customization mode, clicking button shouldn't run commands!
        if self.customizer_mode:
            return
            
        # Find the pool item associated with this slot via button name
        btn_name = SLOT_BUTTONS.get(slot_num)
        pool_item = getattr(self, "_button_to_pool_item", {}).get(btn_name)
        
        if not pool_item:
            # Fallback: try reverse lookup
            for bname, item in getattr(self, "_button_to_pool_item", {}).items():
                if self._button_to_slot_map.get(bname) == slot_num:
                    pool_item = item
                    break
                
        if pool_item:
            cmd_type = pool_item.get("type")
            cmd_value = pool_item.get("command")
            
            if cmd_value == "empty":
                log_debug(u"Clicked empty slot {}. Doing nothing.".format(slot_num))
                return
            
            # Submenu triggers
            if cmd_value in ["submenu1", "submenu2"]:
                button_level = pool_item.get("level", 1)
                if button_level == 1:
                    self.toggle_level2()
                elif button_level == 2:
                    self.toggle_level3()
                return
                
    def hide_radial_menu(self):
        if getattr(self, "customizer_mode", False):
            return
        try:
            from System.Windows import Visibility
            self.Visibility = Visibility.Hidden
            self._is_closing = False
        except:
            pass

    def on_slot_clicked(self, slot_num):
        if self._is_closing:
            return
            
        if self.customizer_mode:
            return
            
        # Find the pool item associated with this slot via button name
        btn_name = SLOT_BUTTONS.get(slot_num)
        pool_item = getattr(self, "_button_to_pool_item", {}).get(btn_name)
        
        if not pool_item:
            # Fallback: try reverse lookup
            for bname, item in getattr(self, "_button_to_pool_item", {}).items():
                if self._button_to_slot_map.get(bname) == slot_num:
                    pool_item = item
                    break
                
        if pool_item:
            cmd_type = pool_item.get("type")
            cmd_value = pool_item.get("command")
            
            if cmd_value == "empty":
                log_debug(u"Clicked empty slot {}. Doing nothing.".format(slot_num))
                return
            
            # Submenu triggers
            if cmd_value in ["submenu1", "submenu2"]:
                button_level = pool_item.get("level", 1)
                if button_level == 1:
                    self.toggle_level2()
                elif button_level == 2:
                    self.toggle_level3()
                return
                
            log_debug(u"RadialMenuWindow slot {} clicked. Command: {}".format(slot_num, cmd_value))
            self.hide_radial_menu()
            
            if _event_handler and _ext_event:
                _event_handler.set_action(execute_command, cmd_type, cmd_value)
                _ext_event.Raise()

    def on_deactivated(self, sender, args):
        if self.customizer_mode:
            return
        if self.IsMouseOver:
            log_debug(u"Window deactivated but mouse is over window. Ignoring close.")
            return
        log_debug(u"RadialMenuWindow deactivated (clicked outside). Hiding.")
        self.hide_radial_menu()

    def on_key_down(self, sender, args):
        if args.Key == wpf_input.Key.Escape:
            if self.customizer_mode:
                return
            log_debug(u"RadialMenuWindow Escape pressed. Hiding.")
            self.hide_radial_menu()

    def on_close_request(self):
        if self._is_closing:
            return
        self._is_closing = True
        log_debug(u"RadialMenuWindow close requested via center button. Closing.")
        
        try:
            self.Deactivated -= self.on_deactivated
            self.KeyDown -= self.on_key_down
        except:
            pass
        self.Close()
           
_LOCALIZED_CATEGORIES_CACHE = {}

def find_category_by_localized_name(doc, name):
    if not doc or not name:
        return None
    global _LOCALIZED_CATEGORIES_CACHE
    name_lower = name.lower()
    
    if name_lower in _LOCALIZED_CATEGORIES_CACHE:
        bic_id = _LOCALIZED_CATEGORIES_CACHE[name_lower]
        if bic_id is not None:
            try:
                from Autodesk.Revit.DB import BuiltInCategory
                import System
                bic = System.Enum.ToObject(BuiltInCategory, bic_id)
                return doc.Settings.Categories.get_Item(bic)
            except:
                pass
        return None
        
    try:
        # Direct name lookup (very fast)
        cat = doc.Settings.Categories.get_Item(name)
        if cat:
            _LOCALIZED_CATEGORIES_CACHE[name_lower] = cat.Id.IntegerValue
            return cat
    except:
        pass
        
    try:
        # Fallback to slower iteration and build the cache once
        for cat in doc.Settings.Categories:
            if cat.Name:
                _LOCALIZED_CATEGORIES_CACHE[cat.Name.lower()] = cat.Id.IntegerValue
                
        bic_id = _LOCALIZED_CATEGORIES_CACHE.get(name_lower)
        if bic_id is not None:
            from Autodesk.Revit.DB import BuiltInCategory
            import System
            bic = System.Enum.ToObject(BuiltInCategory, bic_id)
            return doc.Settings.Categories.get_Item(bic)
    except Exception as ex:
        log_debug("Error in find_category_by_localized_name: " + str(ex))
    return None

def get_english_names_for_category(category):
    names = []
    if not category:
        return names
    try:
        from Autodesk.Revit.DB import BuiltInCategory
        import System
        bic_val = get_id_value(category.Id)
        try:
            bic = System.Enum.ToObject(BuiltInCategory, bic_val)
            bic_str = bic.ToString()
            names.append(bic_str)
            if bic_str.startswith("OST_"):
                names.append(bic_str[4:])
        except:
            pass
            
        mapping = {
            -2000011: ["Walls", "Wall"],
            -2000032: ["Floors", "Floor"],
            -2000035: ["Roofs", "Roof"],
            -2000038: ["Ceilings", "Ceiling"],
            -2000023: ["Doors", "Door"],
            -2000014: ["Windows", "Window"],
            -2008065: ["Pipes", "Pipe"],
            -2008130: ["Ducts", "Duct"],
            -2009000: ["Conduits", "Conduit"],
            -2009020: ["Cable Trays", "Cable Tray"],
            -2000021: ["Dimensions", "Dimension"],
            -2000220: ["Text Notes", "TextNote"],
            -2000010: ["Grids", "Grid"],
            -2000005: ["Levels", "Level"],
            -2000279: ["Views", "View"],
            -2000500: ["Sheets", "Sheet"],
            -2001140: ["Mechanical Equipment"],
            -2001040: ["Electrical Equipment"],
            -2001120: ["Lighting Fixtures"],
            -2001160: ["Plumbing Fixtures"],
            -2001320: ["Structural Framing"],
            -2001330: ["Structural Columns"],
            -2000080: ["Stairs"],
            -2000095: ["Railings"],
            -2000050: ["Areas", "Area"],
            -2000160: ["Rooms", "Room"],
            -2008049: ["Pipe Fittings", "Pipe Fitting"],
            -2000100: ["Zones", "Zone"],
            -2008099: ["Sprinklers", "Sprinkler"],
            -2008100: ["Sprinkler Tags", "Sprinkler Tag"],
            -2008105: ["Pipe Schedules", "Pipe Schedule"],
        }
        if bic_val in mapping:
            names.extend(mapping[bic_val])
    except:
        pass
    return list(set(names))

def get_clean_english_category_name(category):
    if not category:
        return ""
    try:
        from Autodesk.Revit.DB import BuiltInCategory
        import System
        import re
        bic_val = get_id_value(category.Id)
        
        # 1. Check our custom mapping first for the best name
        mapping = {
            -2000011: "Walls",
            -2000032: "Floors",
            -2000035: "Roofs",
            -2000038: "Ceilings",
            -2000023: "Doors",
            -2000014: "Windows",
            -2008065: "Pipes",
            -2008130: "Ducts",
            -2009000: "Conduits",
            -2009020: "Cable Trays",
            -2000021: "Dimensions",
            -2000220: "Text Notes",
            -2000010: "Grids",
            -2000005: "Levels",
            -2000279: "Views",
            -2000500: "Sheets",
            -2001140: "Mechanical Equipment",
            -2001040: "Electrical Equipment",
            -2001120: "Lighting Fixtures",
            -2001160: "Plumbing Fixtures",
            -2001320: "Structural Framing",
            -2001330: "Structural Columns",
            -2000080: "Stairs",
            -2000095: "Railings",
            -2000050: "Areas",
            -2000160: "Rooms",
            -2008049: "Pipe Fittings",
            -2000100: "Zones",
            -2008099: "Sprinklers",
            -2008100: "Sprinkler Tags",
            -2008105: "Pipe Schedules",
        }
        if bic_val in mapping:
            return mapping[bic_val]
            
        # 2. Derive from BuiltInCategory enum name
        try:
            bic = System.Enum.ToObject(BuiltInCategory, bic_val)
            bic_str = bic.ToString()
            if bic_str.startswith("OST_"):
                bic_str = bic_str[4:]
            # Insert spaces before capital letters (e.g. SprinklerTags -> Sprinkler Tags)
            clean_name = re.sub(r'(?<!^)(?=[A-Z])', ' ', bic_str)
            return clean_name
        except:
            pass
            
        # 3. Fallback to localized Name
        return category.Name or ""
    except:
        return category.Name or ""

_CATEGORY_ALIASES_CACHE = {}
_did_build_aliases_cache = False

def build_category_aliases_cache():
    global _CATEGORY_ALIASES_CACHE, _did_build_aliases_cache
    if _did_build_aliases_cache:
        return
    _did_build_aliases_cache = True
        
    cache = {}
    try:
        from pyrevit import HOST_APP
        uiapp = HOST_APP.uiapp
        if uiapp and uiapp.ActiveUIDocument:
            doc = uiapp.ActiveUIDocument.Document
            if doc:
                for cat in doc.Settings.Categories:
                    cat_names = [cat.Name]
                    cat_names.extend(get_english_names_for_category(cat))
                    
                    aliases = set(cat_names)
                    for n in cat_names:
                        if n.startswith("OST_"):
                            aliases.add(n[4:])
                    
                    for name in aliases:
                        key = name.lower().replace(" ", "").replace("_", "")
                        cache[key] = aliases
    except Exception as ex:
        log_debug("Failed to build category aliases cache: " + str(ex))
        
    _CATEGORY_ALIASES_CACHE = cache

def get_category_aliases(name):
    global _CATEGORY_ALIASES_CACHE, _did_build_aliases_cache
    if not _did_build_aliases_cache:
        build_category_aliases_cache()
        
    aliases = {name, name.lower(), name.replace(" ", "")}
    key = name.lower().replace(" ", "").replace("_", "")
    if key in _CATEGORY_ALIASES_CACHE:
        aliases.update(_CATEGORY_ALIASES_CACHE[key])
        
    return aliases

def get_current_context():
    context = "default"
    try:
        uiapp = HOST_APP.uiapp
        if uiapp:
            uidoc = uiapp.ActiveUIDocument
            if uidoc:
                doc = uidoc.Document
                
                # Check selection before click
                global _selection_before_click
                sel_ids = _selection_before_click
                
                # Fallback to current selection if _selection_before_click was never captured
                if sel_ids is None:
                    sel_ids = list(uidoc.Selection.GetElementIds())
                
                if sel_ids and len(sel_ids) > 0:
                    first_el = doc.GetElement(sel_ids[0])
                    if first_el:
                        category = first_el.Category
                        if category:
                            cat_id = get_id_value(category.Id)
                            # Map integer category IDs
                            # OST_PipeCurves = -2008065 (Pipes)
                            # OST_DuctCurves = -2008130 (Ducts)
                            # OST_Walls = -2000011 (Walls)
                            # OST_Dimensions = -2000021 (Dimensions)
                            if cat_id == -2008065:
                                context = "pipes"
                            elif cat_id == -2008130:
                                context = "ducts"
                            elif cat_id == -2000011:
                                context = "walls"
                            elif cat_id == -2000021:
                                context = "dimensions"
                            else:
                                # Fallback enum check if integer doesn't match
                                try:
                                    from Autodesk.Revit.DB import BuiltInCategory
                                    cat_enum = category.BuiltInCategory
                                    if cat_enum == BuiltInCategory.OST_PipeCurves:
                                        context = "pipes"
                                    elif cat_enum == BuiltInCategory.OST_DuctCurves:
                                        context = "ducts"
                                    elif cat_enum == BuiltInCategory.OST_Walls:
                                        context = "walls"
                                    elif cat_enum == BuiltInCategory.OST_Dimensions:
                                        context = "dimensions"
                                except:
                                    pass
        log_debug(u"Resolved Revit selection context: {}".format(context))
    except Exception as ex:
        log_debug(u"Error detecting selection context: {}".format(safe_str(ex)))
    return context

_menu_window_singleton = None

def close_radial_menu_fast():
    try:
        def do_hide():
            try:
                win = get_active_window()
                if win and not getattr(win, "customizer_mode", False):
                    from System.Windows import Visibility
                    win.Visibility = Visibility.Hidden
            except:
                pass
        from System import Action
        if _ui_dispatcher:
            _ui_dispatcher.BeginInvoke(Action(do_hide))
        elif System.Windows.Application.Current:
            System.Windows.Application.Current.Dispatcher.BeginInvoke(Action(do_hide))
    except:
        pass

def trigger_radial_menu(x, y):
    global _ui_dispatcher, _menu_window_singleton
    log_debug(u"trigger_radial_menu called for x={}, y={}".format(x, y))
    
    active_win = get_active_window()
    if active_win is not None and getattr(active_win, "customizer_mode", False):
        log_debug(u"RadialMenuWindow is in customizer mode. Ignoring trigger_radial_menu.")
        return
        
    def show_or_create_window():
        global _menu_window_singleton
        try:
            xaml_path = os.path.join(os.path.dirname(__file__), "ui.xaml")
            
            # DPI Calculation to convert physical to logical coordinates
            import System.Windows.Forms as winforms
            from System.Windows import SystemParameters, Visibility
            screen_width = winforms.Screen.PrimaryScreen.Bounds.Width
            logical_width = SystemParameters.PrimaryScreenWidth
            scale = float(logical_width) / float(screen_width) if screen_width > 0 else 1.0
            
            logical_x = x * scale
            logical_y = y * scale
            
            ctx = get_current_context()
            
            # Check if singleton window exists and is valid
            if _menu_window_singleton is not None and getattr(_menu_window_singleton, "IsLoaded", False):
                win = _menu_window_singleton
                win.active_context = ctx
                win._is_closing = False
                win.Left = logical_x - 320
                win.Top = logical_y - 320
                win.cache_revit_context()
                win.load_layout_configuration()
                win.update_radial_geometry()
                win.Visibility = Visibility.Visible
                set_active_window(win)
                log_debug(u"Reused existing RadialMenuWindow singleton at Left={}, Top={}.".format(win.Left, win.Top))
                return
                
            # Fresh window creation on first run
            win = RadialMenuWindow(xaml_path, active_context=ctx)
            _menu_window_singleton = win
            
            try:
                from System.Windows.Interop import WindowInteropHelper
                revit_window_handle = HOST_APP.proc_window
                if revit_window_handle:
                    helper = WindowInteropHelper(win)
                    helper.Owner = revit_window_handle
                    log_debug(u"Window Owner set to Revit MainWindowHandle successfully.")
            except Exception as owner_ex:
                log_debug(u"Failed to set Window Owner: {}".format(safe_str(owner_ex)))
                
            win.Left = logical_x - 320
            win.Top = logical_y - 320
            win.ShowActivated = False
            win.Show()
            set_active_window(win)
            log_debug(u"Created and showed new RadialMenuWindow at Left={}, Top={}.".format(win.Left, win.Top))
        except Exception as ex:
            tb = safe_traceback()
            log_debug(u"Exception in show_or_create_window: {}\n{}".format(safe_str(ex), tb))
            
    from System import Action
    wrapped_show = Action(show_or_create_window)
    if _ui_dispatcher:
        _ui_dispatcher.BeginInvoke(wrapped_show)
    elif System.Windows.Application.Current:
        System.Windows.Application.Current.Dispatcher.BeginInvoke(wrapped_show)
    else:
        from System.Windows.Threading import Dispatcher
        Dispatcher.CurrentDispatcher.BeginInvoke(wrapped_show)

# Hook callback function logic
def hook_callback(nCode, wParam, lParam):
    global _rbutton_down_x, _rbutton_down_y, _is_holding, _menu_opened_by_hold, _hook_id, _hold_id_counter, _active_window
    global _trigger_mode, _last_rbutton_down_time, _last_rbutton_down_x, _last_rbutton_down_y, _menu_opened_by_double_click
    global _enable_gestures, _gesture_threshold, _gesture_flick_detected, _gesture_target_item
    try:
        active_win = get_active_window()
        if active_win and getattr(active_win, "customizer_mode", False):
            return user32.CallNextHookEx(_hook_id, nCode, wParam, lParam)
            
        if nCode >= 0:
            if wParam == 0x0204:  # WM_RBUTTONDOWN
                if not lParam:
                    return user32.CallNextHookEx(_hook_id, nCode, wParam, lParam)
                hook_struct = ctypes.cast(ctypes.c_void_p(lParam), ctypes.POINTER(MOUSEHOOKSTRUCT)).contents
                current_x = hook_struct.pt.x
                current_y = hook_struct.pt.y
                
                current_time = time.time()
                time_diff = current_time - _last_rbutton_down_time
                dx = abs(current_x - _last_rbutton_down_x)
                dy = abs(current_y - _last_rbutton_down_y)
                
                is_double_click = False
                if time_diff < 0.5 and dx < 10 and dy < 10:
                    is_double_click = True
                
                _last_rbutton_down_time = current_time
                _last_rbutton_down_x = current_x
                _last_rbutton_down_y = current_y
                
                if _trigger_mode == "double_click":
                    if is_double_click:
                        log_debug(u"Double-click detected (manual). Opening radial menu.")
                        with _hold_lock:
                            _is_holding = False
                            _menu_opened_by_double_click = True
                        trigger_radial_menu(current_x, current_y)
                        return 1
                else:
                    _rbutton_down_x = current_x
                    _rbutton_down_y = current_y
                    _gesture_flick_detected = False
                    _gesture_target_item = None
                    
                    with _hold_lock:
                        _is_holding = True
                        _menu_opened_by_hold = False
                        _hold_id_counter += 1
                        current_hold_id = _hold_id_counter
                    
                    t = threading.Thread(target=hold_detection_worker, args=(current_hold_id, _rbutton_down_x, _rbutton_down_y))
                    t.daemon = True
                    t.start()
                    
            elif wParam == 0x0206:  # WM_RBUTTONDBLCLK
                if _trigger_mode == "double_click":
                    if not lParam:
                        return user32.CallNextHookEx(_hook_id, nCode, wParam, lParam)
                    hook_struct = ctypes.cast(ctypes.c_void_p(lParam), ctypes.POINTER(MOUSEHOOKSTRUCT)).contents
                    with _hold_lock:
                        _is_holding = False
                        _menu_opened_by_double_click = True
                    trigger_radial_menu(hook_struct.pt.x, hook_struct.pt.y)
                    return 1
                    
            elif wParam == 0x0205:  # WM_RBUTTONUP
                swallow = False
                with _hold_lock:
                    was_holding = _is_holding
                    was_opened_by_hold = _menu_opened_by_hold
                    was_double_click = _menu_opened_by_double_click
                    _is_holding = False
                    _menu_opened_by_hold = False
                    _menu_opened_by_double_click = False
                
                # Check for Fast Gesture Flick execution
                if _enable_gestures and _gesture_flick_detected and _gesture_target_item:
                    target_cmd_item = _gesture_target_item
                    _gesture_flick_detected = False
                    _gesture_target_item = None
                    
                    cmd_type = target_cmd_item.get("type")
                    cmd_value = target_cmd_item.get("command")
                    log_debug(u"Gesture flick executed command: {} ({})".format(target_cmd_item.get("name"), cmd_value))
                    
                    close_radial_menu_fast()
                    
                    if _event_handler and _ext_event and cmd_value not in ["empty", "submenu1", "submenu2"]:
                        _event_handler.set_action(execute_command, cmd_type, cmd_value)
                        _ext_event.Raise()
                    return 1  # Swallow RBUTTONUP
                    
                if was_opened_by_hold or was_double_click:
                    swallow = True
                
                if swallow:
                    return 1  # Swallow RBUTTONUP to prevent Revit context menu
                    
            elif wParam == 0x0200:  # WM_MOUSEMOVE
                if not _is_holding:
                    return user32.CallNextHookEx(_hook_id, nCode, wParam, lParam)
                
                if lParam:
                    hook_struct = ctypes.cast(ctypes.c_void_p(lParam), ctypes.POINTER(MOUSEHOOKSTRUCT)).contents
                    curr_x = hook_struct.pt.x
                    curr_y = hook_struct.pt.y
                    dx = float(curr_x - _rbutton_down_x)
                    dy = float(curr_y - _rbutton_down_y)
                    dist = math.sqrt(dx * dx + dy * dy)
                    
                    if _enable_gestures:
                        if dist >= _gesture_threshold:
                            _gesture_flick_detected = True
                            item = resolve_gesture_command_at_point(_rbutton_down_x, _rbutton_down_y, curr_x, curr_y)
                            if item:
                                _gesture_target_item = item
                    else:
                        if abs(dx) > 10.0 or abs(dy) > 10.0:
                            with _hold_lock:
                                _is_holding = False
    except BaseException as ex:
        try:
            tb = safe_traceback()
            log_debug(u"Exception in hook_callback: {}\n{}".format(safe_str(ex), tb))
        except:
            pass
            
    return user32.CallNextHookEx(_hook_id, nCode, wParam, lParam)

# Hook manager wrapper class
def get_main_thread_id():
    try:
        import System.Diagnostics
        hwnd = System.Diagnostics.Process.GetCurrentProcess().MainWindowHandle
        if hwnd:
            hwnd_val = hwnd.ToInt64()
            user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
            user32.GetWindowThreadProcessId.restype = ctypes.c_uint32
            thread_id = user32.GetWindowThreadProcessId(hwnd_val, None)
            if thread_id:
                log_debug(u"Found Revit main window thread_id={} via HWND.".format(thread_id))
                return thread_id
    except Exception as ex:
        log_debug(u"Failed to get thread_id via HWND: {}. Falling back to GetCurrentThreadId.".format(safe_str(ex)))
    
    tid = kernel32.GetCurrentThreadId()
    log_debug(u"Using GetCurrentThreadId() = {}.".format(tid))
    return tid

class RadialMenuManager(object):
    def __init__(self):
        self.hook_id = None
        self.hook_proc = None
        self.ui_dispatcher = None
        self._unload_handler = None

    def _on_domain_unload(self, sender, args):
        try:
            log_debug("AppDomain unloading or Process exiting. Automatically stopping Win32 hook.")
            self.stop(close_active_window=True)
        except Exception as ex:
            log_debug("Error in _on_domain_unload: " + safe_str(ex))

    def start(self):
        global _hook_id, _hook_proc, _ui_dispatcher, _hold_delay_ms, _trigger_mode
        log_debug(u"RadialMenuManager.start() called.")
        
        try:
            config = load_config()
            _hold_delay_ms = config.get("settings", {}).get("hold_delay_ms", 400)
            _trigger_mode = config.get("settings", {}).get("trigger_mode", "hold")
            log_debug(u"Loaded hold delay: {}ms".format(_hold_delay_ms))
        except Exception as e_cfg:
            log_debug(u"Failed to load delay on start: {}".format(safe_str(e_cfg)))
            _hold_delay_ms = 400
            
        from System.Windows.Threading import Dispatcher
        self.ui_dispatcher = Dispatcher.CurrentDispatcher
        _ui_dispatcher = self.ui_dispatcher
        log_debug(u"Captured UI thread dispatcher: {}.".format(self.ui_dispatcher))
        
        self.hook_proc = HOOKPROC(hook_callback)
        _hook_proc = self.hook_proc
        
        # WH_MOUSE = 7 (thread-local mouse hook)
        thread_id = get_main_thread_id()
        log_debug(u"Registering WH_MOUSE (7) hook for thread_id={}".format(thread_id))
        self.hook_id = user32.SetWindowsHookExW(7, self.hook_proc, 0, thread_id)
        _hook_id = self.hook_id
        
        if not self.hook_id:
            err = kernel32.GetLastError()
            log_debug(u"Failed to set thread-local mouse hook. Win32 Error: {}".format(err))
            raise Exception("Failed to set thread-local mouse hook. Win32 Error: " + str(err))
        log_debug(u"Hook registered successfully. hook_id={}".format(self.hook_id))

        # Subscribe to AppDomain unload to prevent crashes/hangs if reload occurs
        try:
            import System
            self._unload_handler = System.EventHandler(self._on_domain_unload)
            System.AppDomain.CurrentDomain.DomainUnload += self._unload_handler
            System.AppDomain.CurrentDomain.ProcessExit += self._unload_handler
            log_debug("Subscribed to AppDomain DomainUnload/ProcessExit events.")
        except Exception as ex:
            log_debug("Failed to subscribe to AppDomain events: " + safe_str(ex))

    def stop(self, close_active_window=True):
        global _hook_id, _hook_proc, _active_window, _is_holding, _ui_dispatcher
        log_debug(u"RadialMenuManager.stop(close_active_window={}) called.".format(close_active_window))
        
        # Unsubscribe from AppDomain events
        try:
            if self._unload_handler:
                import System
                System.AppDomain.CurrentDomain.DomainUnload -= self._unload_handler
                System.AppDomain.CurrentDomain.ProcessExit -= self._unload_handler
                self._unload_handler = None
                log_debug("Unsubscribed from AppDomain events.")
        except Exception as ex:
            log_debug("Failed to unsubscribe from AppDomain events: " + safe_str(ex))

        with _hold_lock:
            _is_holding = False

        if self.hook_id:
            user32.UnhookWindowsHookEx(self.hook_id)
            log_debug(u"Hook unregistered. hook_id={}".format(self.hook_id))
            self.hook_id = None
            _hook_id = None
            _hook_proc = None
            
        active_win = get_active_window()
        if close_active_window and active_win:
            try:
                # Close window on UI thread to prevent thread access crashes
                def close_window():
                    win = get_active_window()
                    if win:
                        try:
                            win.Close()
                            log_debug(u"Closed window on stop.")
                        except:
                            pass
                        set_active_window(None)
                
                dispatcher = self.ui_dispatcher or _ui_dispatcher
                if dispatcher:
                    from System import Action
                    self._stop_close_delegate = Action(close_window)
                    dispatcher.BeginInvoke(self._stop_close_delegate)
                else:
                    from System.Windows.Threading import Dispatcher
                    from System import Action
                    self._stop_close_delegate = Action(close_window)
                    Dispatcher.CurrentDispatcher.BeginInvoke(self._stop_close_delegate)
            except Exception as ex:
                log_debug(u"Error closing window on stop: {}".format(safe_str(ex)))
                
        # Clean up global dispatcher reference
        _ui_dispatcher = None

# Execution & Toggle Logic
if __name__ == "__main__":
    from System.Windows.Input import Keyboard, ModifierKeys
    is_shift = (Keyboard.Modifiers & ModifierKeys.Shift) == ModifierKeys.Shift
    
    if is_shift:
        log_debug(u"Shift-Click detected on Ribbon button. Launching customization mode directly.")
        try:
            # Customizer opens directly on the main thread (Ribbon button execution context is already main thread)
            xaml_file = os.path.join(os.path.dirname(__file__), "ui.xaml")
            win = RadialMenuWindow(xaml_file)
            
            # Set owner to Revit window
            try:
                from System.Windows.Interop import WindowInteropHelper
                revit_window_handle = HOST_APP.proc_window
                if revit_window_handle:
                    helper = WindowInteropHelper(win)
                    helper.Owner = revit_window_handle
                    log_debug(u"Customizer Window Owner set to Revit MainWindowHandle successfully.")
            except Exception as owner_ex:
                log_debug(u"Failed to set Customizer Window Owner: {}".format(safe_str(owner_ex)))
                
            # Setup customizer panel and size
            set_active_window(win)
            win.setup_customizer_mode(show_window=True)
            win.WindowStartupLocation = System.Windows.WindowStartupLocation.CenterScreen
            win.Show()
            win.Activate()
            log_debug(u"Customization Window shown and activated successfully.")
        except Exception as ex:
            forms.toast("Failed to open customizer: " + safe_str(ex), title="Radial Menu Error")
    else:
        existing_hook = System.AppDomain.CurrentDomain.GetData("RevitRadialMenuHook")
        from pyrevit import script
        if existing_hook:
            try:
                existing_hook.stop()
            except:
                pass
            System.AppDomain.CurrentDomain.SetData("RevitRadialMenuHook", None)
            try:
                fast_toggle_icon(False)
            except Exception as e_ico:
                log_debug(u"Failed to toggle icon off: {}".format(safe_str(e_ico)))
            forms.toast("Radial Menu has been disabled.", title="Radial Menu")
        else:
            try:
                manager = RadialMenuManager()
                manager.start()
                System.AppDomain.CurrentDomain.SetData("RevitRadialMenuHook", manager)
                try:
                    fast_toggle_icon(True)
                except Exception as e_ico:
                    log_debug(u"Failed to toggle icon on: {}".format(safe_str(e_ico)))
                forms.toast("Radial Menu enabled! Hold right-click to trigger. (Shift-click to configure)", title="Radial Menu")
            except Exception as ex:
                forms.toast("Failed to initialize: " + safe_str(ex), title="Radial Menu Error")
