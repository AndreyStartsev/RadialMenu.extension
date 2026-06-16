# -*- coding: utf-8 -*-
__persistentengine__ = True

import os
import ctypes
import time
import clr
import math
import threading
import json

# Reference required .NET assemblies
clr.AddReference("WindowsBase")
clr.AddReference("PresentationCore")
clr.AddReference("PresentationFramework")
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")

from System.Windows import Window, Visibility, Application
from pyrevit.framework import wpf
from pyrevit import HOST_APP, forms
import System
from System import Action
import System.Windows.Input as wpf_input

# Win32 API setup
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Hook callback signature (64-bit compatible)
HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_int64, ctypes.c_int, ctypes.c_uint64, ctypes.c_uint64)

# Debug Logger Setup
LOG_FILE = os.path.join(os.path.dirname(__file__), "RadialMenu_debug.log")
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

def log_debug(msg):
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
    "hold_delay_ms": 400,
    "gap_width": 3.0,
    "core_radius": 45,
    "petal_width": 60,
    "ring_gap": 5,
    "theme": "pyRevit Dark",
    "color_normal": "#F21E1E24",
    "color_hover_start": "#FF0083B0",
    "color_hover_end": "#FF004B66",
    "color_border": "#25FFFFFF",
    "l2_max_angle": 90,
    "l3_max_angle": 90
}

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
    try:
        from Autodesk.Revit.UI import UIThemeManager, UITheme
        is_revit_dark = (UIThemeManager.CurrentTheme == UITheme.Dark)
    except:
        is_revit_dark = False
        
    base, ext = os.path.splitext(icon_path)
    if ext.lower() == ".png":
        if is_revit_dark:
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

def extract_icons_from_ribbon():
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
            file_path = os.path.join(icons_dir, safe_filename + ".png")
            if os.path.exists(file_path):
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
                
                return data
    except Exception as ex:
        log_debug(u"Failed to load config: {}".format(safe_str(ex)))
    return default_structure

def save_config(config_data):
    try:
        with open(CONFIG_FILE, "wb") as f:
            content = json.dumps(config_data, indent=4)
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
_ui_dispatcher = None
_hold_delay_ms = 400
_cached_commands = None

# Thread safety lock and identifier counter for hold detection
_hold_lock = threading.Lock()
_hold_id_counter = 0

def hold_detection_worker(hold_id, start_x, start_y):
    global _is_holding, _menu_opened_by_hold, _hold_delay_ms
    log_debug(u"Hold worker thread started for hold_id={}. Delay is {}ms.".format(hold_id, _hold_delay_ms))
    
    delay_sec = float(_hold_delay_ms) / 1000.0
    time.sleep(delay_sec)
    
    should_trigger = False
    with _hold_lock:
        if _is_holding and _hold_id_counter == hold_id:
            should_trigger = True
            _menu_opened_by_hold = True
            
    if should_trigger:
        log_debug(u"Hold threshold met for hold_id={}. Triggering radial menu...".format(hold_id))
        trigger_radial_menu(start_x, start_y)
    else:
        log_debug(u"Hold cancelled or superceded for hold_id={}.".format(hold_id))

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
except:
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
            log_debug(u"Calling sessionmgr.execute_command for {}".format(cmd_value))
            sessionmgr.execute_command(cmd_value)
            
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
    if "modeltext" in name_lower or "modelcurve" in name_lower:
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
class ClassItem(object):
    def __init__(self, name, is_checked=False, group="Model Elements"):
        self._name = name
        self._is_checked = is_checked
        self._group = group

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



class PoolListItem(object):
    def __init__(self, item):
        self._item = item

    @property
    def Icon(self):
        return self._item.get("icon", "")

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
        allowed_views = current_rules.get("allowed_views", []) if current_rules else []
        if allowed_views:
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
                if t.IsClass and t.IsSubclassOf(db.Element) and t.Namespace == "Autodesk.Revit.DB":
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
                            reflected.append(cat.Name)
                            try:
                                if str(cat.CategoryType) == "Annotation":
                                    category_groups[cat.Name] = "Annotation Elements"
                                elif str(cat.CategoryType) == "Model":
                                    category_groups[cat.Name] = "Model Elements"
                            except Exception as cat_type_ex:
                                log_debug("Failed to get CategoryType for {}: {}".format(cat.Name, cat_type_ex))
        except Exception as cat_ex:
            log_debug("Failed to get categories in ContextRulesDialog: " + str(cat_ex))
            
        reflected = sorted(list(set(reflected)))
            
        # If intersected_classes are provided, restrict the list to them
        if self.intersected_classes is not None:
            reflected = [c for c in reflected if c in self.intersected_classes]
            
        # Check active classes
        allowed_classes = current_rules.get("allowed_classes", []) if current_rules else []
        
        from System.Collections.ObjectModel import ObservableCollection
        self.classes_collection = ObservableCollection[object]()
        
        for name in reflected:
            is_checked = name in allowed_classes
            group_name = classify_element_type(name, category_groups)
            item = ClassItem(name, is_checked, group_name)
            self.all_classes_items.append(item)
            self.classes_collection.Add(item)
            
        self.LstClasses.ItemsSource = self.classes_collection
        
        # Set up CollectionViewSource filtering to preserve selection state when search filters elements
        from System.Windows.Data import CollectionViewSource, PropertyGroupDescription
        from System import Predicate
        self.classes_view = CollectionViewSource.GetDefaultView(self.classes_collection)
        self.classes_view.Filter = Predicate[object](self.dialog_classes_filter_predicate)
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
        
        # If all views are selected, we can store it as empty (meaning all views)
        if len(views) == 3:
            views = []
            
        classes = [item.Name for item in self.all_classes_items if item.IsChecked]
        return {
            "allowed_views": views,
            "allowed_classes": classes
        }


# Radial Menu WPF Controller
class RadialMenuWindow(Window):
    def __init__(self, xaml_path, active_context="default"):
        self._is_closing = False
        self.customizer_mode = False
        self._all_commands = []
        self._restore_revit_focus = True
        self._drag_start_point = System.Windows.Point()
        self.active_context = active_context
        self._active_l1_parent = None
        self._active_l2_parent = None
        
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
        except Exception as ex:
            log_debug(u"Exception in wpf.LoadComponent: {}".format(safe_str(ex)))
            raise
            
        try:
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
        except Exception as ex:
            log_debug(u"Exception connecting Click events: {}".format(safe_str(ex)))
            raise

    def on_level1_hover(self, sender, args):
        try:
            pool_item = getattr(self, "_button_to_pool_item", {}).get(sender.Name)
            if pool_item:
                cmd_value = pool_item.get("command")
                if cmd_value == "submenu1":
                    self._active_l1_parent = pool_item.get("id")
                    self._active_l2_parent = None
                    self.load_layout_configuration()
                    self.update_radial_geometry()
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
                if cmd_value == "submenu2":
                    self._active_l2_parent = pool_item.get("id")
                    self.load_layout_configuration()
                    self.update_radial_geometry()
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

    def show_level2(self):
        try:
            from System.Windows import Visibility
            if self.SubMenuLevel2.Visibility != Visibility.Visible:
                self.SubMenuLevel2.Visibility = Visibility.Visible
                from System.Windows.Media.Animation import DoubleAnimation
                from System import TimeSpan
                da = DoubleAnimation(0.0, 1.0, TimeSpan.FromMilliseconds(200))
                self.SubMenuLevel2.BeginAnimation(System.Windows.UIElement.OpacityProperty, da)
        except Exception as ex:
            log_debug(u"Error showing level2: {}".format(safe_str(ex)))

    def hide_level2(self):
        try:
            self._active_l1_parent = None
            self._active_l2_parent = None
            from System.Windows import Visibility
            if self.SubMenuLevel2.Visibility == Visibility.Visible:
                self.hide_level3()
                from System.Windows.Media.Animation import DoubleAnimation
                from System import TimeSpan
                da = DoubleAnimation(self.SubMenuLevel2.Opacity, 0.0, TimeSpan.FromMilliseconds(150))
                def on_completed(s, e):
                    self.SubMenuLevel2.Visibility = Visibility.Collapsed
                da.Completed += on_completed
                self.SubMenuLevel2.BeginAnimation(System.Windows.UIElement.OpacityProperty, da)
        except Exception as ex:
            log_debug(u"Error hiding level2: {}".format(safe_str(ex)))

    def show_level3(self):
        try:
            from System.Windows import Visibility
            if self.SubMenuLevel3.Visibility != Visibility.Visible:
                self.SubMenuLevel3.Visibility = Visibility.Visible
                from System.Windows.Media.Animation import DoubleAnimation
                from System import TimeSpan
                da = DoubleAnimation(0.0, 1.0, TimeSpan.FromMilliseconds(200))
                self.SubMenuLevel3.BeginAnimation(System.Windows.UIElement.OpacityProperty, da)
        except Exception as ex:
            log_debug(u"Error showing level3: {}".format(safe_str(ex)))

    def hide_level3(self):
        try:
            self._active_l2_parent = None
            from System.Windows import Visibility
            if self.SubMenuLevel3.Visibility == Visibility.Visible:
                from System.Windows.Media.Animation import DoubleAnimation
                from System import TimeSpan
                da = DoubleAnimation(self.SubMenuLevel3.Opacity, 0.0, TimeSpan.FromMilliseconds(150))
                def on_completed(s, e):
                    self.SubMenuLevel3.Visibility = Visibility.Collapsed
                da.Completed += on_completed
                self.SubMenuLevel3.BeginAnimation(System.Windows.UIElement.OpacityProperty, da)
        except Exception as ex:
            log_debug(u"Error hiding level3: {}".format(safe_str(ex)))

    def load_layout_configuration(self):
        try:
            self._config_data = load_config()
            pool = self._config_data.get("command_pool", list(DEFAULT_POOL))
            
            # Apply context filtering only when NOT in customizer mode
            if not self.customizer_mode:
                filtered_pool = self.filter_pool_by_context(pool)
            else:
                filtered_pool = list(pool)
            
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
            
            # Map pool items to buttons
            for idx, item in enumerate(l1_items, 1):
                btn_name = "BtnL1_{}".format(idx)
                slot_num = idx
                self._button_to_slot_map[btn_name] = slot_num
                self._button_to_pool_item[btn_name] = item
                self.update_button_ui_by_name(btn_name, item.get("name"), item.get("type"), item.get("icon"))
                
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

    def filter_pool_by_context(self, pool):
        """Filter pool items by current Revit context (view type + selected element classes)."""
        try:
            ctx = self.active_context
            filtered = []
            for item in pool:
                rules = item.get("context_rules", {})
                if not rules:
                    # No rules = always visible
                    filtered.append(item)
                    continue
                    
                # Check allowed_views
                allowed_views = rules.get("allowed_views", [])
                if allowed_views:
                    view_match = False
                    if "3D" in allowed_views and "3d" in ctx.lower():
                        view_match = True
                    elif "Plan" in allowed_views and ("plan" in ctx.lower() or "section" in ctx.lower()):
                        view_match = True
                    elif "Sheet" in allowed_views and "sheet" in ctx.lower():
                        view_match = True
                    elif not allowed_views:
                        view_match = True
                    
                    if not view_match:
                        continue
                
                # Check allowed_classes
                allowed_classes = rules.get("allowed_classes", [])
                if allowed_classes:
                    # For now, if classes are specified, include the command
                    # Full class matching will be done when Revit selection context is available
                    pass
                
                filtered.append(item)
            return filtered
        except Exception as ex:
            log_debug(u"Error filtering pool by context: {}".format(safe_str(ex)))
            return list(pool)

    def update_button_ui_by_name(self, btn_name, name, icon_type, icon_value):
        try:
            image_element = getattr(self, btn_name + "Image")
            emoji_element = getattr(self, btn_name + "Emoji")
            label_element = getattr(self, btn_name + "Label")
            
            label_element.Text = name
            
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
                            img_path = local_png
                            is_image = True
            
            if is_image and img_path:
                if not os.path.isabs(img_path):
                    img_path = os.path.join(os.path.dirname(__file__), img_path)
                if os.path.exists(img_path):
                    try:
                        from System.Windows.Media.Imaging import BitmapImage
                        from System import Uri
                        image_element.Source = BitmapImage(Uri(img_path))
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

    def setup_customizer_mode(self):
        self.customizer_mode = True
        log_debug(u"Setting up customizer mode UI.")
        
        # Stop hook to prevent mouse events from interfering with customizer controls and DragMove
        try:
            existing_hook = System.AppDomain.CurrentDomain.GetData("RevitRadialMenuHook")
            if existing_hook:
                existing_hook.stop(close_active_window=False)
                log_debug(u"Hook stopped temporarily for Customizer mode.")
        except Exception as hook_ex:
            log_debug(u"Failed to stop hook during customizer setup: {}".format(safe_str(hook_ex)))
        
        # Trigger icon extraction on UI thread when idle
        try:
            from System.Windows.Threading import DispatcherPriority
            from System import Action
            
            def run_extraction():
                try:
                    extract_icons_from_ribbon()
                except Exception as ex:
                    log_debug("Background extraction failed: " + str(ex))
                    
            self.Dispatcher.BeginInvoke(DispatcherPriority.Background, Action(run_extraction))
            log_debug("Scheduled ribbon icon extraction on UI thread.")
        except Exception as ex:
            log_debug("Failed to schedule icon extraction: " + str(ex))

        # Reset modes
        self._move_mode_active = False
        
        # Reset backgrounds of settings buttons
        from System.Windows.Media import SolidColorBrush, ColorConverter
        try:
            self.BtnCoreMove.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF55555C"))
            self.BtnCorePool.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF0083B0"))
            self.BtnCoreAppearance.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FFFFC107"))
            self.BtnCoreExit.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FFE53935"))
        except:
            pass
            
        # Setup separate customizer window
        if not hasattr(self, "customizer_window") or not self.customizer_window:
            try:
                # Remove from parent MainGrid first
                if self.CustomizerBorder.Parent:
                    self.MainGrid.Children.Remove(self.CustomizerBorder)
                
                from System.Windows import Window, WindowStyle, ResizeMode
                from System.Windows.Media import Brushes
                
                cust_win = Window()
                cust_win.Title = "Radial Menu Customizer"
                cust_win.Width = 680
                cust_win.Height = 640
                cust_win.WindowStyle = getattr(WindowStyle, "None")
                cust_win.ResizeMode = ResizeMode.NoResize
                cust_win.AllowsTransparency = True
                cust_win.Background = Brushes.Transparent
                cust_win.ShowInTaskbar = False
                cust_win.UseLayoutRounding = True
                
                # Copy resources so themes/styles work inside CustomizerBorder
                cust_win.Resources = self.Resources
                cust_win.Content = self.CustomizerBorder
                
                # Closing event redirect
                cust_win.Closing += lambda s, e: self.on_customizer_window_closing(s, e)
                
                # Position next to the radial menu safely
                import System.Windows.Forms as winforms
                screen = winforms.Screen.FromPoint(System.Drawing.Point(int(self.Left), int(self.Top)))
                screen_bounds = screen.Bounds
                
                from System.Windows import SystemParameters
                logical_screen_width = SystemParameters.PrimaryScreenWidth
                scale = float(logical_screen_width) / float(screen_bounds.Width)
                
                target_left = self.Left + 650
                if target_left + 680 > screen_bounds.Right * scale:
                    target_left = self.Left - 690
                    if target_left < screen_bounds.Left * scale:
                        target_left = self.Left
                
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
                log_debug(u"Created separate Customizer Window successfully.")
            except Exception as win_ex:
                log_debug(u"Failed to create Customizer Window: {}".format(safe_str(win_ex)))
                
        from System.Windows import Visibility
        self.CustomizerBorder.Visibility = Visibility.Visible
        if hasattr(self, "customizer_window") and self.customizer_window:
            self.customizer_window.Show()
            self.customizer_window.Activate()
        
        # Disable edit panel by default on opening
        self.hide_edit_panel()
        
        # Select Tab 0 by default (Command Pool)
        self.CustomizerTabControl.SelectedIndex = 0
        
        # Load and populate settings from config
        self.update_settings_ui_from_config()
            
        # Wire up events once
        if not getattr(self, "_customizer_events_wired", False):
            try:
                # Wire up appearance sliders
                self.DelaySlider.ValueChanged += self.on_appearance_setting_changed
                self.CoreRadiusSlider.ValueChanged += self.on_appearance_setting_changed
                self.PetalWidthSlider.ValueChanged += self.on_appearance_setting_changed
                self.RingSpacingSlider.ValueChanged += self.on_appearance_setting_changed
                self.SectorSpacingSlider.ValueChanged += self.on_appearance_setting_changed
                
                # Wire up max angle sliders
                self.L2MaxAngleSlider.ValueChanged += self.on_appearance_setting_changed
                self.L3MaxAngleSlider.ValueChanged += self.on_appearance_setting_changed
                
                # Wire up theme combo
                self.ThemeComboBox.SelectionChanged += self.on_theme_changed
                
                # Wire up hex colors
                self.HexNormalText.TextChanged += self.on_hex_color_changed
                self.HexBorderText.TextChanged += self.on_hex_color_changed
                self.HexHoverStartText.TextChanged += self.on_hex_color_changed
                self.HexHoverEndText.TextChanged += self.on_hex_color_changed
                
                # Connect search text changes
                self.PoolSearchBox.TextChanged += self.on_pool_search_changed
                
                # Connect pool list selection
                self.PoolListBox.SelectionChanged += self.on_pool_selection_changed
                
                # Connect pool edit panel buttons
                self.BtnPoolItemSave.Click += self.on_save_edit_clicked
                self.BtnPoolItemDelete.Click += self.on_delete_command_clicked
                self.BtnPoolItemCancel.Click += self.on_cancel_edit_clicked
                
                # Connect add buttons
                self.BtnAddFromPyRevit.Click += self.on_add_from_pyrevit_clicked
                self.BtnAddBuiltIn.Click += self.on_add_builtin_clicked
                self.BtnAddSubmenuPool.Click += self.on_add_submenu_clicked
                
                # Connect reset all
                self.BtnReset.Click += self.on_reset_clicked
                
                # Connect command picker items
                self.SearchBox.TextChanged += self.on_search_changed
                self.BtnPickerAddCommand.Click += self.on_picker_add_command_clicked
                
                # Connect EditClassSearchTextChanged
                self.EditClassSearch.TextChanged += self.on_context_class_search_changed
                
                # Connect window dragging via Title
                self.TxtPanelTitle.MouseLeftButtonDown += self.on_customizer_mouse_down
                
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

    def get_text_pos(self, cx, cy, r_in, r_out, angle_center, w=80, h=70):
        import math
        rad = angle_center * math.pi / 180.0
        r_mid = (r_in + r_out) / 2.0
        
        x_c = cx + r_mid * math.cos(rad)
        y_c = cy + r_mid * math.sin(rad)
        
        left = x_c - w / 2.0
        top = y_c - 12.0 # align icon's Y-center to sector center
        return left, top

    def update_radial_geometry(self):
        try:
            from System.Windows import Visibility, CornerRadius
            from System.Windows.Controls import Canvas

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
                    
                    path_str = self.get_sector_path_parallel(cx, cy, r1_in, r1_out, angle, n1_eff, gap_width)
                    btn.Tag = path_str
                    
                    panel_name = "BtnL1_{}Panel".format(idx)
                    panel = getattr(self, panel_name, None)
                    if panel:
                        left, top = self.get_text_pos(cx, cy, r1_in, r1_out, angle)
                        Canvas.SetLeft(panel, left)
                        Canvas.SetTop(panel, top)
                    
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
                    
                    path_str = self.get_sector_path_parallel(cx, cy, r2_in, r2_out, angle, n2_eff, gap_width)
                    btn.Tag = path_str
                    
                    panel_name = "BtnL2_{}Panel".format(idx)
                    panel = getattr(self, panel_name, None)
                    if panel:
                        left, top = self.get_text_pos(cx, cy, r2_in, r2_out, angle)
                        Canvas.SetLeft(panel, left)
                        Canvas.SetTop(panel, top)
                    
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
                    
                    path_str = self.get_sector_path_parallel(cx, cy, r3_in, r3_out, angle, n3_eff, gap_width)
                    btn.Tag = path_str
                    
                    panel_name = "BtnL3_{}Panel".format(idx)
                    panel = getattr(self, panel_name, None)
                    if panel:
                        left, top = self.get_text_pos(cx, cy, r3_in, r3_out, angle)
                        Canvas.SetLeft(panel, left)
                        Canvas.SetTop(panel, top)
                    
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
            
            if is_light:
                c_bg = "#FFF4F4F4"
                c_text = "#1E1E24"
                c_sec_text = "#88000000"
                c_input_bg = "#E0E0E0"
                c_input_text = "#1E1E24"
                c_border_brush = "#30000000"
                c_highlight = "#FF1D3A56"  # Revit Blue
            else:
                c_bg = "#FF1A1A1A"
                c_text = "#FFFFFF"
                c_sec_text = "#88FFFFFF"
                c_input_bg = "#20FFFFFF"
                c_input_text = "#FFFFFF"
                c_border_brush = "#30FFFFFF"
                c_highlight = "#FF00E5FF"  # Cyan
                
            self.Resources["CustomizerBg"] = SolidColorBrush(ColorConverter.ConvertFromString(c_bg))
            self.Resources["CustomizerText"] = SolidColorBrush(ColorConverter.ConvertFromString(c_text))
            self.Resources["CustomizerSecText"] = SolidColorBrush(ColorConverter.ConvertFromString(c_sec_text))
            self.Resources["CustomizerInputBg"] = SolidColorBrush(ColorConverter.ConvertFromString(c_input_bg))
            self.Resources["CustomizerInputText"] = SolidColorBrush(ColorConverter.ConvertFromString(c_input_text))
            self.Resources["CustomizerBorderBrush"] = SolidColorBrush(ColorConverter.ConvertFromString(c_border_brush))
            self.Resources["CustomizerHighlight"] = SolidColorBrush(ColorConverter.ConvertFromString(c_highlight))
        except Exception as ex:
            log_debug(u"Error applying theme colors: {}".format(safe_str(ex)))

    def on_appearance_setting_changed(self, sender, args):
        if not hasattr(self, "_config_data") or not self._config_data:
            return
            
        if getattr(self, "_updating_ui_elements", False):
            return
            
        try:
            settings = self._config_data.get("settings", {})
            
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
            
            settings["l2_max_angle"] = int(self.L2MaxAngleSlider.Value)
            self.L2MaxAngleValueText.Text = u"{}°".format(settings["l2_max_angle"])
            
            settings["l3_max_angle"] = int(self.L3MaxAngleSlider.Value)
            self.L3MaxAngleValueText.Text = u"{}°".format(settings["l3_max_angle"])
                
            self.update_radial_geometry()
            self.queue_save_config()
        except Exception as ex:
            log_debug(u"Error in on_appearance_setting_changed: {}".format(safe_str(ex)))

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
            
            self.L2MaxAngleSlider.Value = float(settings.get("l2_max_angle", 90))
            self.L2MaxAngleValueText.Text = u"{}°".format(int(self.L2MaxAngleSlider.Value))
            
            self.L3MaxAngleSlider.Value = float(settings.get("l3_max_angle", 90))
            self.L3MaxAngleValueText.Text = u"{}°".format(int(self.L3MaxAngleSlider.Value))
            
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
        """Normalize pool priorities within each level."""
        try:
            pool = self._config_data.get("command_pool", [])
            for level in [1, 2, 3]:
                level_items = sorted(
                    [p for p in pool if p.get("level") == level],
                    key=lambda x: x.get("priority", 0)
                )
                for idx, item in enumerate(level_items):
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
            
            from System.Windows import GridLength, Visibility
            from System.Windows.Media import SolidColorBrush, ColorConverter
            
            # Highlight Move button, dim others
            self.BtnCoreMove.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF0083B0"))
            self.BtnCorePool.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF4CAF50"))
            self.BtnCoreAppearance.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FFFFC107"))
            self.BtnCoreExit.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FFE53935"))
            
            # Collapse customizer panel for Move mode
            self.CustomizerBorder.Visibility = Visibility.Collapsed
            self.CustomizerColumn.Width = GridLength(0)
            self.Width = 640
            
            log_debug(u"Move mode activated. Customizer panel collapsed.")
        except Exception as ex:
            log_debug(u"Error in on_core_move_clicked: {}".format(safe_str(ex)))

    def on_core_pool_clicked(self):
        try:
            self._move_mode_active = False
            
            from System.Windows import GridLength, Visibility
            from System.Windows.Media import SolidColorBrush, ColorConverter
            
            # Highlight Pool button
            self.BtnCoreMove.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF55555C"))
            self.BtnCorePool.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF0083B0"))
            self.BtnCoreAppearance.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FFFFC107"))
            self.BtnCoreExit.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FFE53935"))
            
            # Expand customizer panel, switch to Tab 0 (Command Pool)
            self.CustomizerBorder.Visibility = Visibility.Visible
            self.CustomizerColumn.Width = GridLength(680)
            self.Width = 1320
            self.CustomizerTabControl.SelectedIndex = 0
            
            log_debug(u"Pool mode activated. Switched to Command Pool tab.")
        except Exception as ex:
            log_debug(u"Error in on_core_pool_clicked: {}".format(safe_str(ex)))

    def on_core_appearance_clicked(self):
        try:
            self._move_mode_active = False
            
            from System.Windows import GridLength, Visibility
            from System.Windows.Media import SolidColorBrush, ColorConverter
            
            # Highlight Appearance button
            self.BtnCoreMove.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF55555C"))
            self.BtnCorePool.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF4CAF50"))
            self.BtnCoreAppearance.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF0083B0"))
            self.BtnCoreExit.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FFE53935"))
            
            # Expand customizer panel, switch to Tab 1 (Appearance)
            self.CustomizerBorder.Visibility = Visibility.Visible
            self.CustomizerColumn.Width = GridLength(680)
            self.Width = 1320
            self.CustomizerTabControl.SelectedIndex = 1
            
            log_debug(u"Appearance mode activated. Switched to Appearance tab.")
        except Exception as ex:
            log_debug(u"Error in on_core_appearance_clicked: {}".format(safe_str(ex)))

    def on_core_exit_clicked(self):
        """Exit settings mode - same as on_exit_customizer_clicked but called from core button."""
        self.on_exit_customizer_clicked(None, None)

    def on_exit_customizer_clicked(self, sender, args):
        try:
            # Force immediate save if configuration changes are queued
            if hasattr(self, "_save_timer") and self._save_timer.IsEnabled:
                self._save_timer.Stop()
                save_config(self._config_data)
                log_debug(u"Forced configuration save on exit customizer.")

            self.customizer_mode = False
            
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
            self.BtnCorePool.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FF4CAF50"))
            self.BtnCoreAppearance.Background = SolidColorBrush(ColorConverter.ConvertFromString("#FFFFC107"))
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
            self.PoolEditPanel.IsEnabled = True
        except Exception as ex:
            log_debug("Error showing edit panel: " + str(ex))

    def hide_edit_panel(self):
        try:
            self.PoolEditPanel.IsEnabled = False
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
        try:
            search_text = self.PoolSearchBox.Text.strip().lower() if self.PoolSearchBox.Text else ""
            pool = self._config_data.get("command_pool", [])
            filtered = []
            for item in pool:
                name = item.get("name", "").lower()
                cmd = item.get("command", "").lower()
                if not search_text or search_text in name or search_text in cmd:
                    filtered.append(PoolListItem(item))
            self.PoolListBox.ItemsSource = filtered
        except Exception as ex:
            log_debug(u"Error in on_pool_search_timer_tick: {}".format(safe_str(ex)))

    def on_customizer_window_closing(self, sender, args):
        args.Cancel = True
        try:
            self.on_exit_customizer_clicked(None, None)
        except Exception as ex:
            log_debug("Error in customizer window closing: " + str(ex))

    def on_window_closing(self, sender, args):
        global _active_window
        # Close customizer window if open
        try:
            if hasattr(self, "customizer_window") and self.customizer_window:
                self.customizer_window.Closing -= self.on_customizer_window_closing
                self.customizer_window.Close()
                self.customizer_window = None
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
            try:
                revit_hwnd = HOST_APP.proc_window
                if revit_hwnd:
                    hwnd_val = revit_hwnd.ToInt64()
                    user32.SetForegroundWindow(hwnd_val)
                    log_debug(u"Restored focus to Revit MainWindow (HWND={}).".format(hwnd_val))
            except Exception as focus_ex:
                log_debug(u"Failed to restore focus to Revit: {}".format(safe_str(focus_ex)))
            
        _active_window = None
        log_debug(u"RadialMenuWindow closed, _active_window cleared.")

    # ==================== POOL LIST UI METHODS ====================
    
    def load_pool_list(self):
        """Populate the PoolListBox with commands from the command pool using databound wrappers."""
        try:
            self.PoolListBox.ItemsSource = None
            pool = self._config_data.get("command_pool", [])
            items = [PoolListItem(item) for item in pool]
            self._pool_list_items = items
            self.PoolListBox.ItemsSource = items
            log_debug(u"Loaded {} items into pool list.".format(len(pool)))
        except Exception as ex:
            log_debug(u"Error in load_pool_list: {}".format(safe_str(ex)))
    
    def on_pool_search_changed(self, sender, args):
        self._pool_search_timer.Stop()
        self._pool_search_timer.Start()
    
    def on_pool_selection_changed(self, sender, args):
        """When a pool item is selected, populate the edit panel."""
        try:
            selected_wrapper = self.PoolListBox.SelectedItem
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
            
            # 2. Select Level in ComboBox
            level = item.get("level", 1)
            self.EditLevelCombo.SelectedIndex = max(0, min(2, level - 1))
            
            # 3. Populate and Select Parent
            self.EditParentCombo.Items.Clear()
            from System.Windows.Controls import ComboBoxItem
            root_item = ComboBoxItem()
            root_item.Content = "None (Root)"
            self.EditParentCombo.Items.Add(root_item)
            
            pool = self._config_data.get("command_pool", [])
            submenus = [p for p in pool if p.get("command") in ["submenu1", "submenu2"] and p.get("id") != item.get("id")]
            self._editing_submenus = submenus
            
            selected_parent_idx = 0
            for idx, sub in enumerate(submenus, 1):
                cbi = ComboBoxItem()
                cbi.Content = u"{} ({})".format(sub.get("name"), sub.get("id"))
                self.EditParentCombo.Items.Add(cbi)
                if sub.get("id") == item.get("parent"):
                    selected_parent_idx = idx
            
            self.EditParentCombo.SelectedIndex = selected_parent_idx
            
            # 4. View filters CheckBoxes
            rules = item.get("context_rules", {}) or {}
            allowed_views = rules.get("allowed_views", []) or []
            if allowed_views:
                self.EditChkView3D.IsChecked = "3D" in allowed_views
                self.EditChkViewPlan.IsChecked = "Plan" in allowed_views
                self.EditChkViewSheet.IsChecked = "Sheet" in allowed_views
            else:
                self.EditChkView3D.IsChecked = True
                self.EditChkViewPlan.IsChecked = True
                self.EditChkViewSheet.IsChecked = True
                
            # 5. Revit DB Classes list
            uiapp = HOST_APP.uiapp
            doc = None
            intersected_classes = None
            if uiapp:
                uidoc = uiapp.ActiveUIDocument
                if uidoc:
                    doc = uidoc.Document
                    sel_ids = uidoc.Selection.GetElementIds()
                    if sel_ids and sel_ids.Count > 0:
                        selected_classes_sets = []
                        for eid in sel_ids:
                            el = doc.GetElement(eid)
                            if el:
                                t = el.GetType()
                                el_classes = []
                                while t is not None and t != System.Object:
                                    if t.Namespace == "Autodesk.Revit.DB":
                                        el_classes.append(t.Name)
                                    t = t.BaseType
                                if el.Category:
                                    el_classes.append(el.Category.Name)
                                selected_classes_sets.append(set(el_classes))
                        if selected_classes_sets:
                            common = selected_classes_sets[0]
                            for s in selected_classes_sets[1:]:
                                common = common.intersection(s)
                            intersected_classes = list(common)
            
            import Autodesk.Revit.DB as db
            reflected = []
            category_groups = {}
            try:
                assembly = System.Reflection.Assembly.GetAssembly(db.Element)
                types = assembly.GetTypes()
                for t in types:
                    if t.IsClass and t.IsSubclassOf(db.Element) and t.Namespace == "Autodesk.Revit.DB":
                        reflected.append(t.Name)
            except Exception as ex:
                log_debug("Failed to reflect Revit classes: " + str(ex))
                reflected = ["Wall", "Floor", "Pipe", "Duct", "FamilyInstance", "Dimension"]
                
            try:
                if doc:
                    for cat in doc.Settings.Categories:
                        if cat.Name:
                            reflected.append(cat.Name)
                            try:
                                if str(cat.CategoryType) == "Annotation":
                                    category_groups[cat.Name] = "Annotation Elements"
                                elif str(cat.CategoryType) == "Model":
                                    category_groups[cat.Name] = "Model Elements"
                            except Exception as cat_type_ex:
                                log_debug("Failed to get CategoryType for {}: {}".format(cat.Name, cat_type_ex))
            except Exception as cat_ex:
                log_debug("Failed to get categories: " + str(cat_ex))
                
            reflected = sorted(list(set(reflected)))
            if intersected_classes is not None and len(intersected_classes) > 0:
                reflected = [c for c in reflected if c in intersected_classes]
                
            allowed_classes = rules.get("allowed_classes", []) or []
            
            self._all_classes_items = []
            from System.Collections.ObjectModel import ObservableCollection
            self._classes_collection = ObservableCollection[object]()
            
            for name in reflected:
                is_checked = name in allowed_classes
                group_name = classify_element_type(name, category_groups)
                c_item = ClassItem(name, is_checked, group_name)
                self._all_classes_items.append(c_item)
                self._classes_collection.Add(c_item)
                
            self.EditClassList.ItemsSource = self._classes_collection
            
            from System.Windows.Data import CollectionViewSource, PropertyGroupDescription
            from System import Predicate
            self._classes_view = CollectionViewSource.GetDefaultView(self._classes_collection)
            self._classes_view.Filter = Predicate[object](self.classes_filter_predicate)
            self._classes_view.GroupDescriptions.Add(PropertyGroupDescription("Group"))
            
            self._updating_ui_elements = False
        except Exception as ex:
            log_debug(u"Error in on_pool_selection_changed: {}".format(safe_str(ex)))
    
    def on_save_edit_clicked(self, sender, args):
        """Save edits from the edit panel back to the pool item."""
        try:
            item = getattr(self, "_editing_pool_item", None)
            if not item:
                return
            
            # Update basic details
            item["name"] = self.EditItemNameTxt.Text.strip()
            item["command"] = self.EditItemCommandTxt.Text.strip()
            
            icon_val = self.EditItemIconTxt.Text.strip()
            if not icon_val:
                icon_val = suggest_emoji_by_name(item["name"])
            item["icon"] = icon_val
            
            # Update level
            item["level"] = self.EditLevelCombo.SelectedIndex + 1
            
            # Update parent
            parent_idx = self.EditParentCombo.SelectedIndex
            if parent_idx <= 0:
                item["parent"] = None
            else:
                submenus = getattr(self, "_editing_submenus", [])
                if 0 <= parent_idx - 1 < len(submenus):
                    item["parent"] = submenus[parent_idx - 1].get("id")
            
            # View type filter
            views = []
            if self.EditChkView3D.IsChecked: views.append("3D")
            if self.EditChkViewPlan.IsChecked: views.append("Plan")
            if self.EditChkViewSheet.IsChecked: views.append("Sheet")
            # If all checked, represent as empty (always visible)
            if len(views) == 3:
                views = []
                
            # Class filter
            classes = [c.Name for c in self._all_classes_items if c.IsChecked]
            
            item["context_rules"] = {
                "allowed_views": views,
                "allowed_classes": classes
            }
            
            save_config(self._config_data)
            self.load_pool_list()
            self.load_layout_configuration()
            self.update_radial_geometry()
            
            # Hide edit panel
            self.hide_edit_panel()
            self.PoolListBox.SelectedIndex = -1
            log_debug(u"Saved pool item: {}".format(item.get("name")))
        except Exception as ex:
            log_debug(u"Error in on_save_edit_clicked: {}".format(safe_str(ex)))
            
    def on_cancel_edit_clicked(self, sender, args):
        try:
            self.hide_edit_panel()
            self.PoolListBox.SelectedIndex = -1
        except Exception as ex:
            log_debug(u"Error in on_cancel_edit_clicked: {}".format(safe_str(ex)))
    
    def on_add_builtin_clicked(self, sender, args):
        """Add a new built-in command to the pool."""
        try:
            pool = self._config_data.get("command_pool", [])
            base_id = "new_builtin"
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
                "name": "New Built-in",
                "command": "empty",
                "icon": u"\u2795",
                "level": 1,
                "parent": None,
                "priority": max_priority + 10,
                "context_rules": {}
            }
            pool.append(new_item)
            save_config(self._config_data)
            self.load_pool_list()
            self.load_layout_configuration()
            self.update_radial_geometry()
            
            # Find the wrapped item and select it
            for i, p_item in enumerate(self.PoolListBox.ItemsSource):
                if p_item._item == new_item:
                    self.PoolListBox.SelectedIndex = i
                    break
            log_debug(u"Added new built-in: {}".format(cmd_id))
        except Exception as ex:
            log_debug(u"Error in on_add_builtin_clicked: {}".format(safe_str(ex)))
            
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
            self.load_pool_list()
            self.load_layout_configuration()
            self.update_radial_geometry()
            
            for i, p_item in enumerate(self.PoolListBox.ItemsSource):
                if p_item._item == new_item:
                    self.PoolListBox.SelectedIndex = i
                    break
            log_debug(u"Added new submenu: {}".format(cmd_id))
        except Exception as ex:
            log_debug(u"Error in on_add_submenu_clicked: {}".format(safe_str(ex)))
            
    def on_add_from_pyrevit_clicked(self, sender, args):
        try:
            self.CustomizerTabControl.SelectedIndex = 2
            log_debug(u"Switched to pyRevit command picker tab.")
        except Exception as ex:
            log_debug(u"Error in on_add_from_pyrevit_clicked: {}".format(safe_str(ex)))
            
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
                    "icon": selected_item.IconPath or u"\u25B6",
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
                self.load_pool_list()
                self.load_layout_configuration()
                self.update_radial_geometry()
                
                for i, p_item in enumerate(self.PoolListBox.ItemsSource):
                    if p_item._item == new_item:
                        self.PoolListBox.SelectedIndex = i
                        break
                log_debug(u"Added pyRevit pulldown to pool: {}".format(selected_item.Name))
            else:
                is_builtin = (getattr(selected_item, "Extension", None) == "Revit Built-in")
                cmd_type = "built_in" if is_builtin else "pyrevit"
                
                existing_commands = {p.get("command", "") for p in pool if p.get("type") == cmd_type}
                if selected_item.UniqueId in existing_commands:
                    from pyrevit import forms
                    forms.toast("Command '{}' is already in the pool.".format(selected_item.Name), title="Radial Menu")
                    return
                    
                display_name = selected_item.Name
                if is_builtin and " (" in display_name:
                    display_name = display_name.split(" (")[0].strip()
                    
                icon_val = selected_item.IconPath
                if is_builtin and icon_val:
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
                self.load_pool_list()
                self.load_layout_configuration()
                self.update_radial_geometry()
                
                for i, p_item in enumerate(self.PoolListBox.ItemsSource):
                    if p_item._item == new_item:
                        self.PoolListBox.SelectedIndex = i
                        break
                log_debug(u"Added command '{}' (type: {}) to pool.".format(display_name, cmd_type))
        except Exception as ex:
            log_debug(u"Error in on_picker_add_command_clicked: {}".format(safe_str(ex)))
            
    def on_delete_command_clicked(self, sender, args):
        """Delete the selected command from the pool."""
        try:
            selected_wrapper = self.PoolListBox.SelectedItem
            if not selected_wrapper:
                return
            item = selected_wrapper._item
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
            self.load_pool_list()
            self.load_layout_configuration()
            self.update_radial_geometry()
            
            self.hide_edit_panel()
            self.PoolListBox.SelectedIndex = -1
            log_debug(u"Deleted pool command: {}".format(item.get("name")))
        except Exception as ex:
            log_debug(u"Error in on_delete_command_clicked: {}".format(safe_str(ex)))

    def classes_filter_predicate(self, item):
        try:
            box = getattr(self, "EditClassSearch", None) or getattr(self, "TxtClassSearch", None)
            if not box:
                return True
            text = box.Text
            if not text:
                return True
            query = text.lower().strip()
            return query in item.Name.lower()
        except:
            return True

    def on_context_class_search_changed(self, sender, args):
        try:
            if hasattr(self, "_classes_view") and self._classes_view:
                self._classes_view.Refresh()
        except Exception as ex:
            log_debug(u"Error in on_context_class_search_changed: {}".format(safe_str(ex)))

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
            sel_ids = uidoc.Selection.GetElementIds()
            selected_classes = []
            if sel_ids and sel_ids.Count > 0:
                for eid in sel_ids:
                    el = doc.GetElement(eid)
                    if el:
                        t = el.GetType()
                        while t is not None and t != System.Object:
                            if t.Namespace == "Autodesk.Revit.DB":
                                selected_classes.append(t.Name)
                            t = t.BaseType
                        if el.Category:
                            selected_classes.append(el.Category.Name)
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
            
            self._dragged_petal = sender
            self._drag_start_mouse_pos = args.GetPosition(self)
            sender.CaptureMouse()
            
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
                else:
                    sender.Opacity = 1.0
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
        
        level = None
        # Allow some tolerance (+/- 15px)
        if r1_in - 15.0 <= dist <= r1_out + 15.0:
            level = 1
        elif r2_in - 15.0 <= dist <= r2_out + 15.0:
            level = 2
        elif r3_in - 15.0 <= dist <= r3_out + 15.0:
            level = 3
            
        if not level:
            return None, None
            
        n1, n2, n3 = getattr(self, "_level_counts", (0, 0, 0))
        
        if level == 1:
            n_sectors = max(1, n1)
            start_slot = 1
        elif level == 2:
            n_sectors = max(1, n2)
            start_slot = 11
        else:
            n_sectors = max(1, n3)
            start_slot = 21
            
        rad = math.atan2(y - cy, x - cx)
        deg = rad * 180.0 / math.pi
        if deg < 0:
            deg += 360.0
            
        # Shift angle to align with sector 1 at 270 degrees
        normalized_deg = deg - 270.0
        if normalized_deg < 0:
            normalized_deg += 360.0
            
        sector_idx = int(math.floor(normalized_deg / (360.0 / float(n_sectors)))) + 1
        if sector_idx > n_sectors:
            sector_idx = n_sectors
            
        target_slot = start_slot + sector_idx - 1
        return level, target_slot

    def on_petal_mouse_up(self, sender, args):
        try:
            if not hasattr(self, "_dragged_petal") or self._dragged_petal != sender:
                return
                
            sender.ReleaseMouseCapture()
            sender.Opacity = 1.0
            
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
                    log_debug(u"Removed petal '{}' (id: {}) via drag-out.".format(pool_item.get("name"), pool_item.get("id")))
            elif mouse_in_canvas:
                source_btn = sender.Name
                source_item = getattr(self, "_button_to_pool_item", {}).get(source_btn)
                
                target_level, target_slot = self.get_slot_from_coordinates(mouse_in_canvas.X, mouse_in_canvas.Y)
                if target_level == level and target_slot is not None:
                    target_btn = SLOT_BUTTONS.get(target_slot)
                    target_item = getattr(self, "_button_to_pool_item", {}).get(target_btn)
                    
                    if source_item and target_item and source_item != target_item:
                        # Swap their priorities
                        sp = source_item.get("priority", 0)
                        tp = target_item.get("priority", 0)
                        source_item["priority"] = tp
                        target_item["priority"] = sp
                        
                        save_config(self._config_data)
                        self.load_layout_configuration()
                        self.update_radial_geometry()
                        log_debug(u"Swapped priorities of '{}' and '{}'.".format(source_item.get("name"), target_item.get("name")))
            args.Handled = True
        except Exception as ex:
            log_debug(u"Error in on_petal_mouse_up: {}".format(safe_str(ex)))
            args.Handled = True
        except Exception as ex:
            log_debug(u"Error in on_petal_mouse_up: {}".format(safe_str(ex)))

    def find_all_commands_safe(self):
        global _cached_commands
        if _cached_commands is not None:
            log_debug(u"Returning cached pyRevit commands.")
            return _cached_commands

        log_debug(u"Loading active pyRevit commands safely...")
        cmds = []
        unique_ids = set()
        
        # 1. Try to load from sessionmgr
        try:
            from pyrevit.loader import sessionmgr
            all_cmds = sessionmgr.find_all_commands(cache=True)
            log_debug(u"Found {} commands via sessionmgr.".format(len(all_cmds)))
            for cmd in all_cmds:
                uid = getattr(cmd, "unique_id", None)
                if uid:
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
                                stripped = p
                                for suffix in [".extension", ".tab", ".panel", ".pulldown", ".splitbutton"] + list(suffixes):
                                    if p.lower().endswith(suffix):
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
        _cached_commands = cmds
        return cmds

    def load_pyrevit_commands(self):
        log_debug(u"Starting async load of pyRevit commands...")
        t = threading.Thread(target=self._async_load_commands_worker)
        t.daemon = True
        t.start()

    def _async_load_commands_worker(self):
        try:
            all_cmds = self.find_all_commands_safe()
            
            parsed_list = []
            for cmd in all_cmds:
                if not cmd.unique_id:
                    continue
                if cmd.unique_id == "radialmenu_radialmenu_radialmenu_toggleradialmenu":
                    continue
                
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
                
            # 4. Load Revit Built-in Commands from extracted_icons folder
            try:
                icons_dir = os.path.join(os.path.dirname(__file__), "extracted_icons")
                if os.path.exists(icons_dir):
                    built_in_cmds_count = 0
                    for filename in os.listdir(icons_dir):
                        if filename.lower().endswith(".png") and not filename.lower().endswith(".dark.png"):
                            cmd_id = filename[:-4] # Remove .png
                            
                            name_part = cmd_id
                            if name_part.startswith("ID_"):
                                name_part = name_part[3:]
                            
                            tab_name = u"Other Commands"
                            if cmd_id.startswith("ID_OBJECTS_"):
                                tab_name = u"Model Elements"
                            elif cmd_id.startswith("ID_RBS_") or "DUCT" in cmd_id or "PIPE" in cmd_id or "CABLE" in cmd_id or "CONDUIT" in cmd_id:
                                tab_name = u"Systems (MEP)"
                            elif cmd_id.startswith("ID_VIEW_") or cmd_id.startswith("ID_WINDOW_") or "VIEW" in cmd_id:
                                tab_name = u"Views"
                            elif cmd_id.startswith("ID_ANNOTATIONS_") or cmd_id.startswith("ID_ANNOTATE_") or "DIMENSION" in cmd_id:
                                tab_name = u"Annotations"
                            elif cmd_id.startswith("ID_EDIT_") or cmd_id.startswith("ID_BUTTON_") or cmd_id.startswith("ID_MODIFY_") or "ALIGN" in cmd_id or "CUT" in cmd_id or "JOIN" in cmd_id:
                                tab_name = u"Modify"
                            elif cmd_id.startswith("ID_FILE_") or cmd_id.startswith("ID_APP_") or "SAVE" in cmd_id or "OPEN" in cmd_id:
                                tab_name = u"File"
                            elif cmd_id.startswith("ID_SETTINGS_") or cmd_id.startswith("ID_TOOL_") or cmd_id.startswith("ID_PREFERENCES_"):
                                tab_name = u"Settings"
                                
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
                            
                            display_title = u"{} ({})".format(formatted_title, cmd_id)
                            icon_full_path = os.path.join(icons_dir, filename)
                            
                            parsed_list.append({
                                "title": display_title,
                                "unique_id": cmd_id,
                                "icon_path": icon_full_path,
                                "ext_name": u"Revit Built-in",
                                "tab_name": tab_name,
                                "pulldown_name": None
                            })
                            built_in_cmds_count += 1
                    log_debug(u"Loaded {} Revit Built-in commands from extracted_icons.".format(built_in_cmds_count))
            except Exception as e_builtin:
                log_debug(u"Failed to load Revit Built-in commands: {}".format(safe_str(e_builtin)))
                
            self._all_commands = parsed_list
            
            def populate_ui():
                try:
                    self.filter_commands(None)
                    log_debug(u"Async populated CommandTreeView with {} items.".format(len(self._all_commands)))
                except Exception as ex:
                    log_debug(u"Error populating CommandTreeView: {}".format(safe_str(ex)))
            
            dispatcher = self.Dispatcher
            if dispatcher:
                from System import Action
                dispatcher.BeginInvoke(Action(populate_ui))
        except Exception as ex:
            log_debug(u"Error in _async_load_commands_worker: {}".format(safe_str(ex)))

    def on_search_changed(self, sender, args):
        self._search_timer.Stop()
        self._search_timer.Start()

    def filter_commands(self, query):
        try:
            if query:
                query = query.lower().strip()
            
            # Step 1: Filter flat list of commands matching query
            filtered_cmds = []
            for cmd in self._all_commands:
                match = (not query or 
                         query in cmd["title"].lower() or 
                         query in cmd["ext_name"].lower() or 
                         query in cmd["tab_name"].lower() or
                         (cmd["pulldown_name"] and query in cmd["pulldown_name"].lower()))
                if match:
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
            
            for ext_name in sorted(tree_data.keys()):
                should_expand = bool(query)
                ext_item = TreeItem(ext_name, is_command=False, is_expanded=should_expand)
                root_collection.Add(ext_item)
                
                tabs = tree_data[ext_name]
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
                            
            self.CommandTreeView.ItemsSource = root_collection
        except Exception as ex:
            log_debug(u"Error filtering commands: {}".format(safe_str(ex)))

    def on_tree_mouse_down(self, sender, args):
        self._drag_start_point = args.GetPosition(None)

    def on_tree_mouse_move(self, sender, args):
        if args.LeftButton == wpf_input.MouseButtonState.Pressed:
            position = args.GetPosition(None)
            if (abs(position.X - self._drag_start_point.X) > System.Windows.SystemParameters.MinimumHorizontalDragDistance or \
                abs(position.Y - self._drag_start_point.Y) > System.Windows.SystemParameters.MinimumVerticalDragDistance):
                
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
                            "icon_path": cmd_item.IconPath,
                            "is_pulldown": getattr(cmd_item, "IsPulldown", False)
                        }
                        cmd_json = json.dumps(cmd_dict)
                        drag_data = System.Windows.DataObject("PyRevitCommandJSON", cmd_json)
                        System.Windows.DragDrop.DoDragDrop(dependency_obj, drag_data, System.Windows.DragDropEffects.Copy)

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
            except Exception as ex:
                log_debug(u"Failed to process dropped data: {}".format(safe_str(ex)))
            args.Handled = True

    def assign_command_to_slot_data(self, slot_num, cmd_data):
        try:
            btn_name = SLOT_BUTTONS.get(slot_num)
            pool_item = getattr(self, "_button_to_pool_item", {}).get(btn_name)
            
            if pool_item:
                level = pool_item.get("level", 1)
                parent = pool_item.get("parent")
                priority = pool_item.get("priority", slot_num * 10)
            else:
                if 1 <= slot_num <= 10:
                    level = 1
                    parent = None
                    priority = slot_num * 10
                elif 11 <= slot_num <= 20:
                    level = 2
                    parent = getattr(self, "_active_l1_parent", "submenu1") or "submenu1"
                    priority = (slot_num - 10) * 10
                else:
                    level = 3
                    parent = getattr(self, "_active_l2_parent", "submenu2") or "submenu2"
                    priority = (slot_num - 20) * 10

            is_pulldown = cmd_data.get("is_pulldown", False)
            pulldown_id = cmd_data["unique_id"]

            if is_pulldown:
                if level == 3:
                    from pyrevit import forms
                    forms.toast("Pulldowns cannot be added to Level 3 (max depth reached).", title="Radial Menu")
                    return
                
                submenu_cmd = "submenu1" if level == 1 else "submenu2"
                
                # Check if pool item already exists for this slot
                if pool_item:
                    pool_item["type"] = "built_in"
                    pool_item["name"] = cmd_data["name"]
                    pool_item["command"] = submenu_cmd
                    pool_item["icon"] = cmd_data["icon_path"] or u"\u25B6"
                    pool_item["id"] = pulldown_id
                else:
                    import System
                    pool_item = {
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
                    self._config_data.setdefault("command_pool", []).append(pool_item)
                
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
                
                self._config_data["command_pool"] = pool
                save_config(self._config_data)
                self.load_layout_configuration()
                self.update_radial_geometry()
                log_debug(u"Assigned pulldown '{}' as submenu with {} children.".format(cmd_data["name"], len(child_cmds)))
            else:
                is_builtin = (cmd_data.get("extension") == "Revit Built-in")
                cmd_type = "built_in" if is_builtin else "pyrevit"
                
                display_name = cmd_data["name"]
                if is_builtin and " (" in display_name:
                    display_name = display_name.split(" (")[0].strip()
                    
                icon_val = cmd_data.get("icon_path")
                if is_builtin and icon_val:
                    if os.path.isabs(icon_val) and "extracted_icons" in icon_val:
                        parts = icon_val.split("extracted_icons")
                        if len(parts) > 1:
                            icon_val = "extracted_icons" + parts[-1].replace("\\", "/")
                            
                if pool_item:
                    pool_item["type"] = cmd_type
                    pool_item["name"] = display_name
                    pool_item["command"] = cmd_data["unique_id"]
                    pool_item["icon"] = icon_val
                    
                    save_config(self._config_data)
                    self.update_button_ui_by_name(btn_name, display_name, cmd_type, icon_val)
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
                    save_config(self._config_data)
                    self.load_layout_configuration()
                    self.update_radial_geometry()
                    log_debug(u"Created new pool item for slot {} with command '{}' (type: {}).".format(slot_num, display_name, cmd_type))
        except Exception as ex:
            log_debug(u"Failed to assign command to slot: {}".format(safe_str(ex)))

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
                if cmd_value == "submenu1":
                    self.toggle_level2()
                elif cmd_value == "submenu2":
                    self.toggle_level3()
                return
                
            self._is_closing = True
            log_debug(u"RadialMenuWindow slot {} clicked. Command: {}".format(slot_num, cmd_value))
            
            try:
                self.Deactivated -= self.on_deactivated
                self.KeyDown -= self.on_key_down
            except:
                pass
                
            self.Close()
            
            if _event_handler and _ext_event:
                _event_handler.set_action(execute_command, cmd_type, cmd_value)
                _ext_event.Raise()

    def on_deactivated(self, sender, args):
        if self._is_closing:
            return
        if self.customizer_mode:
            return
        if self.IsMouseOver:
            log_debug(u"Window deactivated but mouse is over window. Ignoring close.")
            return
        self._is_closing = True
        self._restore_revit_focus = False # Do not force focus when clicked outside
        log_debug(u"RadialMenuWindow deactivated (clicked outside). Closing.")
        
        try:
            self.Deactivated -= self.on_deactivated
            self.KeyDown -= self.on_key_down
        except:
            pass
            
        self.Close()

    def on_key_down(self, sender, args):
        if args.Key == wpf_input.Key.Escape:
            if self._is_closing:
                return
            self._is_closing = True
            log_debug(u"RadialMenuWindow Escape pressed. Closing.")
            
            try:
                self.Deactivated -= self.on_deactivated
                self.KeyDown -= self.on_key_down
            except:
                pass
                
            self.Close()

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
           
def get_current_context():
    context = "default"
    try:
        uiapp = HOST_APP.uiapp
        if uiapp:
            uidoc = uiapp.ActiveUIDocument
            if uidoc:
                doc = uidoc.Document
                sel_ids = uidoc.Selection.GetElementIds()
                if sel_ids and sel_ids.Count > 0:
                    first_el = doc.GetElement(sel_ids[0])
                    category = first_el.Category
                    if category:
                        cat_id = category.Id.IntegerValue
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

def trigger_radial_menu(x, y):
    global _active_window, _ui_dispatcher
    log_debug(u"trigger_radial_menu called for x={}, y={}".format(x, y))
    
    if _active_window is not None:
        try:
            # If active window is in customizer mode, DO NOT reopen or close it!
            if getattr(_active_window, "customizer_mode", False):
                log_debug(u"RadialMenuWindow is in customizer mode. Ignoring trigger_radial_menu.")
                return
        except Exception as active_ex:
            log_debug(u"Error checking customizer mode of active window: {}".format(safe_str(active_ex)))
        try:
            # We must close the window on the UI thread to prevent thread access crashes
            def close_window():
                global _active_window
                if _active_window:
                    try:
                        _active_window.Close()
                        log_debug(u"Closed existing window instance on UI thread.")
                    except:
                        pass
                    _active_window = None
                    
            from System.Windows import Application
            from System import Action
            if _ui_dispatcher:
                _ui_dispatcher.BeginInvoke(Action(close_window))
            elif Application.Current:
                Application.Current.Dispatcher.BeginInvoke(Action(close_window))
            else:
                from System.Windows.Threading import Dispatcher
                Dispatcher.CurrentDispatcher.BeginInvoke(Action(close_window))
        except Exception as ex:
            log_debug(u"Error dispatching close for existing window: {}".format(safe_str(ex)))
        
    def open_window():
        global _active_window
        try:
            xaml_path = os.path.join(os.path.dirname(__file__), "ui.xaml")
            
            # DPI Calculation to convert physical to logical coordinates
            import System.Windows.Forms as winforms
            from System.Windows import SystemParameters
            screen_width = winforms.Screen.PrimaryScreen.Bounds.Width
            logical_width = SystemParameters.PrimaryScreenWidth
            scale = float(logical_width) / float(screen_width)
            log_debug(u"DPI Scale = {}".format(scale))
            
            logical_x = x * scale
            logical_y = y * scale
            log_debug(u"Logical coordinates: x={}, y={}".format(logical_x, logical_y))
            
            # Detect context before window creation
            ctx = get_current_context()
            win = RadialMenuWindow(xaml_path, active_context=ctx)
            
            # Set owner window handle to avoid thread focus/re-entrancy native crashes
            try:
                from System.Windows.Interop import WindowInteropHelper
                revit_window_handle = HOST_APP.proc_window
                if revit_window_handle:
                    helper = WindowInteropHelper(win)
                    helper.Owner = revit_window_handle
                    log_debug(u"Window Owner set to Revit MainWindowHandle successfully.")
                else:
                    log_debug(u"Warning: HOST_APP.proc_window is null, cannot set Window Owner.")
            except Exception as owner_ex:
                log_debug(u"Failed to set Window Owner: {}".format(safe_str(owner_ex)))
                
            win.Left = logical_x - 320
            win.Top = logical_y - 320
            log_debug(u"Showing window at Left={}, Top={}".format(win.Left, win.Top))
            win.Show()
            win.Activate()
            _active_window = win
            log_debug(u"Window shown and activated successfully.")
        except Exception as ex:
            tb = safe_traceback()
            log_debug(u"Python Exception in open_window: {}\n{}".format(safe_str(ex), tb))
        except System.Exception as ex:
            log_debug(u"CLR Exception in open_window: {}".format(safe_str(ex)))
            if hasattr(ex, "InnerException") and ex.InnerException:
                log_debug(u"Inner CLR Exception: {}".format(safe_str(ex.InnerException)))
 
    from System.Windows import Application
    from System import Action
    log_debug(u"Dispatching open_window onto UI thread...")
    if _ui_dispatcher:
        _ui_dispatcher.BeginInvoke(Action(open_window))
    elif Application.Current:
        Application.Current.Dispatcher.BeginInvoke(Action(open_window))
    else:
        log_debug(u"No UI dispatcher available! Falling back to current thread dispatcher.")
        from System.Windows.Threading import Dispatcher
        Dispatcher.CurrentDispatcher.BeginInvoke(Action(open_window))

# Hook callback function logic
def hook_callback(nCode, wParam, lParam):
    global _rbutton_down_x, _rbutton_down_y, _is_holding, _menu_opened_by_hold, _hook_id, _hold_id_counter, _active_window
    try:
        # If the active window is in customizer mode, we should ignore all hook events to prevent deadlocks and unexpected triggers
        if _active_window and getattr(_active_window, "customizer_mode", False):
            return user32.CallNextHookEx(_hook_id, nCode, wParam, lParam)
            
        if nCode >= 0:
            if wParam in [0x0204, 0x0205]: # WM_RBUTTONDOWN, WM_RBUTTONUP
                log_debug(u"HookEvent: wParam={} (0x{:04X})".format(wParam, wParam))
            
            if wParam == 0x0204:  # WM_RBUTTONDOWN
                # Check if Shift modifier is pressed via Win32 (allows entering customization directly from mouse long-press)
                # VK_SHIFT = 0x10. If high-order bit is 1, key is down.
                is_shift_pressed = (user32.GetKeyState(0x10) & 0x8000) != 0
                if is_shift_pressed:
                    # In customization mode, we don't trigger normal hold, we can let user Shift+RMB click to configure
                    # but Shift-click on the Ribbon button is the primary approved method.
                    pass
                
                hook_struct = ctypes.cast(ctypes.c_void_p(lParam), ctypes.POINTER(MOUSEHOOKSTRUCT)).contents
                _rbutton_down_x = hook_struct.pt.x
                _rbutton_down_y = hook_struct.pt.y
                
                with _hold_lock:
                    _is_holding = True
                    _menu_opened_by_hold = False
                    _hold_id_counter += 1
                    current_hold_id = _hold_id_counter
                
                log_debug(u"RBUTTONDOWN at pt=({}, {}), starting thread hold_id={}.".format(_rbutton_down_x, _rbutton_down_y, current_hold_id))
                
                # Start hold detection in a background thread to prevent UI thread dispatcher blockages
                t = threading.Thread(target=hold_detection_worker, args=(current_hold_id, _rbutton_down_x, _rbutton_down_y))
                t.daemon = True
                t.start()
                    
            elif wParam == 0x0205:  # WM_RBUTTONUP
                log_debug(u"RBUTTONUP. _is_holding={}, _menu_opened_by_hold={}".format(_is_holding, _menu_opened_by_hold))
                swallow = False
                with _hold_lock:
                    _is_holding = False
                    if _menu_opened_by_hold:
                        _menu_opened_by_hold = False
                        swallow = True
                
                if swallow:
                    log_debug(u"Swallowing RBUTTONUP.")
                    return 1  # Swallow right button up to prevent Revit context menu
                    
            elif wParam == 0x0200:  # WM_MOUSEMOVE
                # Quick lockless check first to avoid overhead on every mouse movement
                is_holding_now = False
                with _hold_lock:
                    is_holding_now = _is_holding
                
                if is_holding_now:
                    hook_struct = ctypes.cast(ctypes.c_void_p(lParam), ctypes.POINTER(MOUSEHOOKSTRUCT)).contents
                    dx = abs(hook_struct.pt.x - _rbutton_down_x)
                    dy = abs(hook_struct.pt.y - _rbutton_down_y)
                    # If mouse moved more than 10 pixels, cancel the hold detection
                    if dx > 10 or dy > 10:
                        log_debug(u"Mouse moved (dx={}, dy={}). Cancelling hold.".format(dx, dy))
                        with _hold_lock:
                            _is_holding = False
    except Exception as ex:
        tb = safe_traceback()
        log_debug(u"Python Exception in hook_callback: {}\n{}".format(safe_str(ex), tb))
    except System.Exception as ex:
        log_debug(u"CLR Exception in hook_callback: {}".format(safe_str(ex)))
        
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

    def start(self):
        global _hook_id, _hook_proc, _ui_dispatcher, _hold_delay_ms
        log_debug(u"RadialMenuManager.start() called.")
        
        try:
            config = load_config()
            _hold_delay_ms = config.get("settings", {}).get("hold_delay_ms", 400)
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

    def stop(self, close_active_window=True):
        global _hook_id, _hook_proc, _active_window, _is_holding, _ui_dispatcher
        log_debug(u"RadialMenuManager.stop(close_active_window={}) called.".format(close_active_window))
        with _hold_lock:
            _is_holding = False

        if self.hook_id:
            user32.UnhookWindowsHookEx(self.hook_id)
            log_debug(u"Hook unregistered. hook_id={}".format(self.hook_id))
            self.hook_id = None
            _hook_id = None
            _hook_proc = None
            
        if close_active_window and _active_window:
            try:
                # Close window on UI thread to prevent thread access crashes
                def close_window():
                    global _active_window
                    if _active_window:
                        try:
                            _active_window.Close()
                            log_debug(u"Closed window on stop.")
                        except:
                            pass
                        _active_window = None
                
                dispatcher = self.ui_dispatcher or _ui_dispatcher
                if dispatcher:
                    from System import Action
                    dispatcher.BeginInvoke(Action(close_window))
                else:
                    from System.Windows.Threading import Dispatcher
                    from System import Action
                    Dispatcher.CurrentDispatcher.BeginInvoke(Action(close_window))
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
            _active_window = win
            win.setup_customizer_mode()
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
                script.toggle_icon(False)
            except Exception as e_ico:
                log_debug(u"Failed to toggle icon off: {}".format(safe_str(e_ico)))
            forms.toast("Radial Menu has been disabled.", title="Radial Menu")
        else:
            try:
                manager = RadialMenuManager()
                manager.start()
                System.AppDomain.CurrentDomain.SetData("RevitRadialMenuHook", manager)
                try:
                    script.toggle_icon(True)
                except Exception as e_ico:
                    log_debug(u"Failed to toggle icon on: {}".format(safe_str(e_ico)))
                forms.toast("Radial Menu enabled! Hold right-click to trigger. (Shift-click to configure)", title="Radial Menu")
            except Exception as ex:
                forms.toast("Failed to initialize: " + safe_str(ex), title="Radial Menu Error")
