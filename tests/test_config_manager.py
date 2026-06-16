# -*- coding: utf-8 -*-
"""Tests for config_manager module.

Standalone — no Revit or WPF dependencies required.
"""

import unittest
import tempfile
import json
import os
import sys
import shutil

# Add lib to path
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "lib")))

from radial_menu.config_manager import (
    ConfigManager,
    DEFAULT_SETTINGS,
    DEFAULT_POOL,
    clean_id_part,
)


class TestCleanIdPart(unittest.TestCase):
    """Tests for clean_id_part()."""

    def test_simple_name(self):
        self.assertEqual(clean_id_part("ZoomFit"), "zoomfit")

    def test_with_spaces_and_special_chars(self):
        self.assertEqual(clean_id_part("Zoom Fit!"), "zoomfit")

    def test_underscores_preserved(self):
        self.assertEqual(clean_id_part("my_command"), "my_command")

    def test_unicode_stripped(self):
        result = clean_id_part(u"Команда123")
        self.assertEqual(result, "123")

    def test_empty_string(self):
        self.assertEqual(clean_id_part(""), "")

    def test_numbers_only(self):
        self.assertEqual(clean_id_part("42"), "42")


class TestConfigManagerLoad(unittest.TestCase):
    """Tests for ConfigManager.load()."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, "config.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_load_missing_file_returns_defaults(self):
        mgr = ConfigManager(self.config_path)
        data = mgr.load()
        self.assertIn("settings", data)
        self.assertIn("command_pool", data)
        self.assertEqual(data["settings"]["hold_delay_ms"], 400)

    def test_load_current_format(self):
        config = {
            "settings": {"hold_delay_ms": 600, "gap_width": 5.0},
            "command_pool": [
                {"id": "test", "type": "built_in", "name": "Test",
                 "command": "test", "level": 1, "priority": 10}
            ]
        }
        with open(self.config_path, "wb") as f:
            f.write(json.dumps(config).encode("utf-8"))

        mgr = ConfigManager(self.config_path)
        data = mgr.load()
        self.assertEqual(data["settings"]["hold_delay_ms"], 600)
        self.assertEqual(len(data["command_pool"]), 1)
        # Defaults should be merged for missing keys
        self.assertIn("core_radius", data["settings"])

    def test_load_flat_list_triggers_migration(self):
        old_config = [
            {"slot": 1, "type": "built_in", "name": "Zoom",
             "command": "zoom", "icon": "Z"},
            {"slot": 2, "type": "built_in", "name": "Save",
             "command": "save", "icon": "S"},
        ]
        with open(self.config_path, "wb") as f:
            f.write(json.dumps(old_config).encode("utf-8"))

        mgr = ConfigManager(self.config_path)
        data = mgr.load()
        self.assertIn("command_pool", data)
        self.assertIn("settings", data)
        # Should have migrated 2 commands
        self.assertEqual(len(data["command_pool"]), 2)
        # File should have been re-saved in new format
        with open(self.config_path, "rb") as f:
            saved = json.loads(f.read().decode("utf-8"))
        self.assertIn("command_pool", saved)

    def test_load_context_dict_triggers_migration(self):
        old_config = {
            "contexts": {
                "default": [
                    {"slot": 1, "type": "built_in", "name": "Zoom",
                     "command": "zoom", "icon": "Z"},
                    {"slot": 11, "type": "built_in", "name": "SubZoom",
                     "command": "zoom", "icon": "Z"},
                ]
            },
            "settings": {"hold_delay_ms": 500, "l1_count": 8}
        }
        with open(self.config_path, "wb") as f:
            f.write(json.dumps(old_config).encode("utf-8"))

        mgr = ConfigManager(self.config_path)
        data = mgr.load()
        self.assertIn("command_pool", data)
        # l1_count should be removed
        self.assertNotIn("l1_count", data["settings"])
        # hold_delay_ms should be preserved
        self.assertEqual(data["settings"]["hold_delay_ms"], 500)
        # Level should be migrated correctly
        pool = data["command_pool"]
        levels = [item["level"] for item in pool]
        self.assertIn(1, levels)
        self.assertIn(2, levels)

    def test_load_invalid_json_returns_defaults(self):
        with open(self.config_path, "wb") as f:
            f.write(b"not valid json {{{")

        mgr = ConfigManager(self.config_path)
        data = mgr.load()
        self.assertEqual(data["settings"], dict(DEFAULT_SETTINGS))

    def test_load_non_dict_non_list_returns_defaults(self):
        with open(self.config_path, "wb") as f:
            f.write(json.dumps("just a string").encode("utf-8"))

        mgr = ConfigManager(self.config_path)
        data = mgr.load()
        self.assertIn("settings", data)
        self.assertIn("command_pool", data)


class TestConfigManagerSave(unittest.TestCase):
    """Tests for ConfigManager.save()."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, "config.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_creates_file(self):
        mgr = ConfigManager(self.config_path)
        mgr.save({"settings": {}, "command_pool": []})
        self.assertTrue(os.path.exists(self.config_path))

    def test_save_creates_parent_dirs(self):
        nested_path = os.path.join(self.test_dir, "sub", "dir", "config.json")
        mgr = ConfigManager(nested_path)
        mgr.save({"settings": {}, "command_pool": []})
        self.assertTrue(os.path.exists(nested_path))

    def test_saved_file_is_valid_json(self):
        mgr = ConfigManager(self.config_path)
        original = {"settings": {"hold_delay_ms": 300}, "command_pool": []}
        mgr.save(original)
        with open(self.config_path, "rb") as f:
            loaded = json.loads(f.read().decode("utf-8"))
        self.assertEqual(loaded["settings"]["hold_delay_ms"], 300)

    def test_save_utf8_content(self):
        mgr = ConfigManager(self.config_path)
        config = {"settings": {}, "command_pool": [
            {"id": "test", "name": u"Зум", "icon": u"\U0001F50D"}
        ]}
        mgr.save(config)
        with open(self.config_path, "rb") as f:
            content = f.read().decode("utf-8")
        self.assertIn("test", content)


class TestConfigManagerMigrateLegacy(unittest.TestCase):
    """Tests for ConfigManager.migrate_legacy()."""

    def test_empty_contexts_returns_defaults(self):
        mgr = ConfigManager("dummy.json")
        result = mgr.migrate_legacy({"contexts": {}})
        self.assertEqual(len(result), len(DEFAULT_POOL))

    def test_slot_to_level_mapping(self):
        mgr = ConfigManager("dummy.json")
        data = {
            "contexts": {
                "default": [
                    {"slot": 1, "name": "L1Cmd", "command": "zoom"},
                    {"slot": 15, "name": "L2Cmd", "command": "save"},
                    {"slot": 25, "name": "L3Cmd", "command": "3d"},
                ]
            }
        }
        pool = mgr.migrate_legacy(data)
        self.assertEqual(pool[0]["level"], 1)
        self.assertIsNone(pool[0]["parent"])
        self.assertEqual(pool[1]["level"], 2)
        self.assertEqual(pool[1]["parent"], "submenu1")
        self.assertEqual(pool[2]["level"], 3)
        self.assertEqual(pool[2]["parent"], "submenu2")

    def test_empty_commands_skipped(self):
        mgr = ConfigManager("dummy.json")
        data = {
            "contexts": {
                "default": [
                    {"slot": 1, "name": "Zoom", "command": "zoom"},
                    {"slot": 2, "name": "Empty", "command": "empty"},
                ]
            }
        }
        pool = mgr.migrate_legacy(data)
        self.assertEqual(len(pool), 1)

    def test_duplicate_ids_resolved(self):
        mgr = ConfigManager("dummy.json")
        data = {
            "contexts": {
                "default": [
                    {"slot": 1, "name": "Zoom", "command": "zoom"},
                    {"slot": 2, "name": "Zoom", "command": "zoom"},
                ]
            }
        }
        pool = mgr.migrate_legacy(data)
        ids = [item["id"] for item in pool]
        # All IDs should be unique
        self.assertEqual(len(ids), len(set(ids)))

    def test_context_rules_preserved(self):
        mgr = ConfigManager("dummy.json")
        data = {
            "contexts": {
                "default": [
                    {"slot": 1, "name": "Cmd", "command": "zoom",
                     "context_rules": {"allowed_views": ["3D"]}}
                ]
            }
        }
        pool = mgr.migrate_legacy(data)
        self.assertEqual(pool[0]["context_rules"]["allowed_views"], ["3D"])


class TestConfigManagerMergeDefaults(unittest.TestCase):
    """Tests for ConfigManager.merge_defaults()."""

    def test_fills_missing_settings(self):
        mgr = ConfigManager("dummy.json")
        data = {"settings": {"hold_delay_ms": 600}}
        mgr.merge_defaults(data)
        self.assertEqual(data["settings"]["hold_delay_ms"], 600)
        self.assertIn("core_radius", data["settings"])
        self.assertIn("command_pool", data)

    def test_does_not_overwrite_existing(self):
        mgr = ConfigManager("dummy.json")
        data = {"settings": {"hold_delay_ms": 999, "gap_width": 7.0},
                "command_pool": [{"id": "x"}]}
        mgr.merge_defaults(data)
        self.assertEqual(data["settings"]["hold_delay_ms"], 999)
        self.assertEqual(data["settings"]["gap_width"], 7.0)
        self.assertEqual(len(data["command_pool"]), 1)

    def test_replaces_invalid_settings(self):
        mgr = ConfigManager("dummy.json")
        data = {"settings": "invalid"}
        mgr.merge_defaults(data)
        self.assertIsInstance(data["settings"], dict)
        self.assertEqual(data["settings"]["hold_delay_ms"], 400)

    def test_replaces_invalid_pool(self):
        mgr = ConfigManager("dummy.json")
        data = {"settings": {}, "command_pool": "invalid"}
        mgr.merge_defaults(data)
        self.assertIsInstance(data["command_pool"], list)


class TestConfigManagerCustomDefaults(unittest.TestCase):
    """Tests for custom defaults in ConfigManager."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, "config.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_custom_defaults_used(self):
        custom_settings = {"my_key": "my_value"}
        custom_pool = [{"id": "custom", "name": "Custom"}]
        mgr = ConfigManager(
            self.config_path,
            default_settings=custom_settings,
            default_pool=custom_pool
        )
        data = mgr.load()
        self.assertEqual(data["settings"]["my_key"], "my_value")
        self.assertEqual(len(data["command_pool"]), 1)
        self.assertEqual(data["command_pool"][0]["id"], "custom")


if __name__ == "__main__":
    unittest.main()
