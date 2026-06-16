# -*- coding: utf-8 -*-
"""Tests for data_binding module.

Tests run in CPython (no WPF/IronPython). ObservableCollection falls back to list.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "lib")))

from radial_menu.data_binding import (
    BindableBase,
    CheckableItem,
    DictionaryWrapper,
    PoolItemView,
    HierarchicalItem,
)


class TestCheckableItem(unittest.TestCase):
    """Tests for CheckableItem."""

    def test_initial_values(self):
        item = CheckableItem("Walls", True)
        self.assertEqual(item.Name, "Walls")
        self.assertTrue(item.IsChecked)

    def test_default_unchecked(self):
        item = CheckableItem("Pipes")
        self.assertFalse(item.IsChecked)

    def test_setter_name(self):
        item = CheckableItem("Old")
        item.Name = "New"
        self.assertEqual(item.Name, "New")

    def test_setter_is_checked(self):
        item = CheckableItem("Test", False)
        item.IsChecked = True
        self.assertTrue(item.IsChecked)

    def test_inherits_bindable_base(self):
        item = CheckableItem("X")
        self.assertIsInstance(item, BindableBase)


class TestDictionaryWrapper(unittest.TestCase):
    """Tests for DictionaryWrapper."""

    def test_get_existing_key(self):
        w = DictionaryWrapper({"a": 1, "b": 2})
        self.assertEqual(w.get("a"), 1)

    def test_get_missing_key_default(self):
        w = DictionaryWrapper({"a": 1})
        self.assertEqual(w.get("z", 42), 42)

    def test_get_missing_key_none(self):
        w = DictionaryWrapper({})
        self.assertIsNone(w.get("x"))

    def test_empty_init(self):
        w = DictionaryWrapper()
        self.assertIsNone(w.get("anything"))


class TestPoolItemView(unittest.TestCase):
    """Tests for PoolItemView."""

    def setUp(self):
        self.item = {
            "id": "zoom_fit",
            "name": "Zoom Fit",
            "icon": u"\U0001F50D",
            "level": 1,
            "priority": 10,
            "context_rules": {}
        }

    def test_display_name(self):
        view = PoolItemView(self.item)
        self.assertEqual(view.DisplayName, "Zoom Fit")

    def test_icon(self):
        view = PoolItemView(self.item)
        self.assertEqual(view.Icon, u"\U0001F50D")

    def test_level_label(self):
        view = PoolItemView(self.item)
        self.assertEqual(view.LevelLabel, "L1")

    def test_priority_label(self):
        view = PoolItemView(self.item)
        self.assertEqual(view.PriorityLabel, "P: 10")

    def test_context_summary_always_visible(self):
        view = PoolItemView(self.item)
        self.assertEqual(view.ContextSummary, "Always visible")

    def test_context_summary_with_views(self):
        self.item["context_rules"] = {"allowed_views": ["3D", "Plan"]}
        view = PoolItemView(self.item)
        summary = view.ContextSummary
        self.assertIn("Views:", summary)
        self.assertIn("3D", summary)

    def test_context_summary_with_classes(self):
        self.item["context_rules"] = {
            "allowed_classes": ["Wall", "Pipe", "Duct", "FamilyInstance"]
        }
        view = PoolItemView(self.item)
        summary = view.ContextSummary
        self.assertIn("Classes:", summary)
        self.assertIn("...", summary)  # Truncated at 2

    def test_context_summary_combined(self):
        self.item["context_rules"] = {
            "allowed_views": ["3D"],
            "allowed_classes": ["Wall"]
        }
        view = PoolItemView(self.item)
        summary = view.ContextSummary
        self.assertIn("Views:", summary)
        self.assertIn("Classes:", summary)
        self.assertIn(" | ", summary)

    def test_missing_fields_use_defaults(self):
        view = PoolItemView({})
        self.assertEqual(view.DisplayName, "")
        self.assertEqual(view.Icon, "")
        self.assertEqual(view.LevelLabel, "L1")
        self.assertEqual(view.PriorityLabel, "P: 0")

    def test_level2_label(self):
        self.item["level"] = 2
        view = PoolItemView(self.item)
        self.assertEqual(view.LevelLabel, "L2")

    def test_inherits_dictionary_wrapper(self):
        view = PoolItemView(self.item)
        self.assertIsInstance(view, DictionaryWrapper)
        self.assertEqual(view.get("id"), "zoom_fit")


class TestHierarchicalItem(unittest.TestCase):
    """Tests for HierarchicalItem."""

    def test_basic_properties(self):
        item = HierarchicalItem("Test", is_command=True, unique_id="uid1")
        self.assertEqual(item.Name, "Test")
        self.assertTrue(item.IsCommand)
        self.assertEqual(item.UniqueId, "uid1")

    def test_default_values(self):
        item = HierarchicalItem("Node")
        self.assertFalse(item.IsCommand)
        self.assertIsNone(item.IconPath)
        self.assertIsNone(item.UniqueId)
        self.assertIsNone(item.Extension)
        self.assertFalse(item.IsExpanded)

    def test_children_is_list_like(self):
        item = HierarchicalItem("Parent")
        children = item.Children
        self.assertIsNotNone(children)
        # Should support append/Add
        if hasattr(children, 'Add'):
            children.Add(HierarchicalItem("Child"))
        else:
            children.append(HierarchicalItem("Child"))
        self.assertEqual(len(children), 1)

    def test_name_setter(self):
        item = HierarchicalItem("Old")
        item.Name = "New"
        self.assertEqual(item.Name, "New")

    def test_is_expanded_setter(self):
        item = HierarchicalItem("Node", is_expanded=False)
        item.IsExpanded = True
        self.assertTrue(item.IsExpanded)

    def test_full_properties(self):
        item = HierarchicalItem(
            name="My Command",
            is_command=True,
            icon_path="/path/to/icon.png",
            unique_id="ext_tab_cmd",
            extension="MyExtension",
            is_expanded=True,
        )
        self.assertEqual(item.Name, "My Command")
        self.assertTrue(item.IsCommand)
        self.assertEqual(item.IconPath, "/path/to/icon.png")
        self.assertEqual(item.UniqueId, "ext_tab_cmd")
        self.assertEqual(item.Extension, "MyExtension")
        self.assertTrue(item.IsExpanded)

    def test_nested_hierarchy(self):
        root = HierarchicalItem("Root")
        child1 = HierarchicalItem("Child1")
        child2 = HierarchicalItem("Child2")
        grandchild = HierarchicalItem("GrandChild", is_command=True)

        children = root.Children
        if hasattr(children, 'Add'):
            children.Add(child1)
            children.Add(child2)
            child1.Children.Add(grandchild)
        else:
            children.append(child1)
            children.append(child2)
            child1.Children.append(grandchild)

        self.assertEqual(len(root.Children), 2)
        self.assertEqual(len(child1.Children), 1)
        self.assertTrue(child1.Children[0].IsCommand)

    def test_inherits_bindable_base(self):
        item = HierarchicalItem("Node")
        self.assertIsInstance(item, BindableBase)


if __name__ == "__main__":
    unittest.main()
