# -*- coding: utf-8 -*-
"""Standalone configuration management for RadialMenu.

This module handles loading, saving, and migrating RadialMenu configuration
files.  It is intentionally kept free of any Revit, WPF, or .NET dependencies
so that it can be tested and reused independently.

Dependencies: ``json``, ``os``, ``re`` (standard library only).
"""

import json
import os
import re
import logging

logger = logging.getLogger(__name__)


# =========================================================================
# Defaults
# =========================================================================

DEFAULT_SETTINGS = {
    "hold_delay_ms": 400,
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
}
"""dict: Default radial menu appearance and behaviour settings."""

DEFAULT_POOL = [
    # Level 1 commands
    {"id": "zoom_fit",   "type": "built_in", "name": "Zoom Fit",     "command": "zoom",         "icon": u"\U0001F50D", "level": 1, "parent": None, "priority": 10, "context_rules": {}},
    {"id": "close_inact","type": "built_in", "name": "Close Inact.", "command": "close_hidden", "icon": u"\u274C",     "level": 1, "parent": None, "priority": 20, "context_rules": {}},
    {"id": "submenu1",   "type": "built_in", "name": "Menu 1",       "command": "submenu1",     "icon": u"\u25B6",     "level": 1, "parent": None, "priority": 30, "context_rules": {}},
    {"id": "save_model", "type": "built_in", "name": "Save Model",   "command": "save",         "icon": u"\U0001F4BE", "level": 1, "parent": None, "priority": 40, "context_rules": {}},
    {"id": "3d_view",    "type": "built_in", "name": "3D View",      "command": "3d",           "icon": u"\U0001F3E0", "level": 1, "parent": None, "priority": 50, "context_rules": {}},
    {"id": "reveal",     "type": "built_in", "name": "Reveal",       "command": "reveal",       "icon": u"\U0001F4A1", "level": 1, "parent": None, "priority": 60, "context_rules": {}},
    {"id": "thin_lines", "type": "built_in", "name": "Thin Lines",   "command": "thin_lines",   "icon": u"\u2796",     "level": 1, "parent": None, "priority": 70, "context_rules": {}},
    {"id": "detail_lvl", "type": "built_in", "name": "Detail Lvl",   "command": "detail_level", "icon": u"\U0001F9F1", "level": 1, "parent": None, "priority": 80, "context_rules": {}},
    # Level 2 commands (children of submenu1)
    {"id": "sub_zoom",   "type": "built_in", "name": "Sub-Zoom",     "command": "zoom",         "icon": u"\U0001F50D", "level": 2, "parent": "submenu1", "priority": 10, "context_rules": {}},
    {"id": "sub_save",   "type": "built_in", "name": "Sub-Save",     "command": "save",         "icon": u"\U0001F4BE", "level": 2, "parent": "submenu1", "priority": 20, "context_rules": {}},
    {"id": "sub_3d",     "type": "built_in", "name": "Sub-3D",       "command": "3d",           "icon": u"\U0001F3E0", "level": 2, "parent": "submenu1", "priority": 30, "context_rules": {}},
    {"id": "submenu2",   "type": "built_in", "name": "Menu 2",       "command": "submenu2",     "icon": u"\u25B6",     "level": 2, "parent": "submenu1", "priority": 40, "context_rules": {}},
    {"id": "sub_thin",   "type": "built_in", "name": "Sub-Thin",     "command": "thin_lines",   "icon": u"\u2796",     "level": 2, "parent": "submenu1", "priority": 50, "context_rules": {}},
    # Level 3 commands (children of submenu2)
    {"id": "sub2_reveal","type": "built_in", "name": "Sub2-Reveal",  "command": "reveal",       "icon": u"\U0001F4A1", "level": 3, "parent": "submenu2", "priority": 10, "context_rules": {}},
    {"id": "sub2_detail","type": "built_in", "name": "Sub2-Detail",  "command": "detail_level", "icon": u"\U0001F9F1", "level": 3, "parent": "submenu2", "priority": 20, "context_rules": {}},
    {"id": "sub2_zoom",  "type": "built_in", "name": "Sub2-Zoom",    "command": "zoom",         "icon": u"\U0001F50D", "level": 3, "parent": "submenu2", "priority": 30, "context_rules": {}},
]
"""list[dict]: Default command pool for a fresh RadialMenu installation."""


# =========================================================================
# Utility
# =========================================================================

def clean_id_part(name):
    """Normalise a path-segment string into a safe identifier part.

    Strips all characters except ASCII letters, digits and underscores,
    then converts to lower-case.

    Args:
        name: Raw string to clean.

    Returns:
        str: Cleaned, lower-case identifier fragment.
    """
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '', name)
    return cleaned.lower()


# =========================================================================
# ConfigManager
# =========================================================================

class ConfigManager(object):
    """Manages loading, saving, and migrating RadialMenu configuration.

    The configuration file is a UTF-8 encoded JSON file with the following
    top-level structure::

        {
            "settings": { ... },
            "command_pool": [ ... ]
        }

    The manager auto-detects and migrates two legacy formats:
    * **Flat list** — an old ``[{slot, command, ...}, ...]`` array.
    * **Context dict** — an old ``{"contexts": {"default": [...]}, ...}``
      mapping.

    Args:
        config_path:      Absolute path to the JSON configuration file.
        default_settings: Dict of default settings (falls back to
                          :data:`DEFAULT_SETTINGS`).
        default_pool:     List of default pool items (falls back to
                          :data:`DEFAULT_POOL`).
    """

    def __init__(self, config_path, default_settings=None, default_pool=None):
        self.config_path = config_path
        self.default_settings = (
            default_settings if default_settings is not None
            else dict(DEFAULT_SETTINGS)
        )
        self.default_pool = (
            default_pool if default_pool is not None
            else list(DEFAULT_POOL)
        )

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def load(self):
        """Load configuration from disk.

        Performs automatic format detection and migration:
        * If the file contains a flat JSON list, it is migrated to the
          pool-based format and saved back.
        * If the file contains the old ``contexts`` key, it is migrated
          and saved back.
        * Missing setting keys are filled from defaults.

        Returns:
            dict: Configuration dict with ``"settings"`` and
            ``"command_pool"`` keys.
        """
        default_structure = {
            "settings": dict(self.default_settings),
            "command_pool": list(self.default_pool),
        }
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "rb") as f:
                    content = f.read().decode("utf-8")
                    data = json.loads(content)

                    # Old flat array format
                    if isinstance(data, list):
                        logger.debug(
                            u"Migrating old flat config to new pool format.")
                        new_data = dict(default_structure)
                        new_data["command_pool"] = self.migrate_legacy(
                            {"contexts": {"default": data}})
                        self.save(new_data)
                        return new_data

                    if not isinstance(data, dict):
                        return default_structure

                    # Old context-based format
                    if "contexts" in data and "command_pool" not in data:
                        logger.debug(
                            u"Migrating old context-based config to pool "
                            u"format.")
                        new_data = {
                            "settings": data.get(
                                "settings", dict(self.default_settings)),
                            "command_pool": self.migrate_legacy(data),
                        }
                        # Remove obsolete l1/l2/l3_count keys
                        settings = new_data["settings"]
                        for old_key in ("l1_count", "l2_count", "l3_count"):
                            settings.pop(old_key, None)
                        # Fill missing keys from defaults
                        self.merge_defaults(new_data)
                        self.save(new_data)
                        return new_data

                    # Current format — verify and merge defaults
                    self.merge_defaults(data)
                    return data
        except Exception as ex:
            logger.debug(u"Failed to load config: %s", ex)
        return default_structure

    def save(self, config_data):
        """Save configuration to disk as pretty-printed UTF-8 JSON.

        Creates parent directories if they do not exist.

        Args:
            config_data: Dict to serialise.
        """
        try:
            parent_dir = os.path.dirname(self.config_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir)
            content = json.dumps(config_data, indent=4)
            with open(self.config_path, "wb") as f:
                f.write(content.encode("utf-8"))
            logger.debug(u"Configuration saved successfully.")
        except Exception as ex:
            logger.debug(u"Failed to save config: %s", ex)

    def migrate_legacy(self, data):
        """Migrate old context-based config to the new pool-based format.

        Reads the ``"contexts"`` dict, preferring ``"default"``, and
        converts slot-numbered entries to pool items with proper
        ``level`` / ``parent`` / ``priority`` fields.

        Args:
            data: Old configuration dict containing a ``"contexts"`` key.

        Returns:
            list[dict]: Migrated command pool list.
        """
        try:
            pool = []
            seen_commands = set()

            contexts = data.get("contexts", {})
            primary_config = contexts.get("default", [])
            if not primary_config:
                for _ctx_name, ctx_config in contexts.items():
                    if ctx_config:
                        primary_config = ctx_config
                        break

            if not primary_config:
                return list(self.default_pool)

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

                cmd_id = clean_id_part(item.get("name", cmd))
                if cmd_id in seen_commands:
                    cmd_id = "{}_{}".format(cmd_id, slot)
                seen_commands.add(cmd_id)

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
                    "context_rules": context_rules,
                }
                pool.append(pool_item)

            if not pool:
                return list(self.default_pool)

            logger.debug(
                u"Migrated %d commands from old config to pool format.",
                len(pool))
            return pool
        except Exception as ex:
            logger.debug(u"Error in migrate_legacy: %s", ex)
            return list(self.default_pool)

    def merge_defaults(self, data):
        """Fill missing keys in *data* from the default settings and pool.

        Mutates *data* in-place.

        Args:
            data: Configuration dict to update.
        """
        if "settings" not in data or not isinstance(data["settings"], dict):
            data["settings"] = dict(self.default_settings)
        else:
            for k, v in self.default_settings.items():
                if k not in data["settings"]:
                    data["settings"][k] = v

        if "command_pool" not in data or \
                not isinstance(data["command_pool"], list):
            data["command_pool"] = list(self.default_pool)
