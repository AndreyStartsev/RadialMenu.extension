# -*- coding: utf-8 -*-
"""Tests for context_detector module.

Tests filter_by_context() which works without Revit.
get_current_context() requires Revit and is tested structurally.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "lib")))

from radial_menu.context_detector import (
    CATEGORY_MAP,
    filter_by_context,
    get_current_context,
)


class TestCategoryMap(unittest.TestCase):
    """Tests for CATEGORY_MAP constant."""

    def test_pipes_mapped(self):
        self.assertEqual(CATEGORY_MAP[-2008065], "pipes")

    def test_ducts_mapped(self):
        self.assertEqual(CATEGORY_MAP[-2008130], "ducts")

    def test_walls_mapped(self):
        self.assertEqual(CATEGORY_MAP[-2000011], "walls")

    def test_dimensions_mapped(self):
        self.assertEqual(CATEGORY_MAP[-2000021], "dimensions")


class TestFilterByContext(unittest.TestCase):
    """Tests for filter_by_context()."""

    def test_no_rules_always_visible(self):
        items = [
            {"name": "Zoom", "context_rules": {}},
            {"name": "Save", "context_rules": {}},
        ]
        result = filter_by_context(items, "default")
        self.assertEqual(len(result), 2)

    def test_missing_context_rules_always_visible(self):
        items = [{"name": "Zoom"}]  # No context_rules key at all
        result = filter_by_context(items, "default")
        self.assertEqual(len(result), 1)

    def test_3d_view_filter(self):
        items = [
            {"name": "3D Only", "context_rules": {"allowed_views": ["3D"]}},
            {"name": "Always", "context_rules": {}},
        ]
        # 3D context
        result = filter_by_context(items, "3d view")
        self.assertEqual(len(result), 2)
        # Plan context
        result = filter_by_context(items, "plan view")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Always")

    def test_plan_view_filter(self):
        items = [
            {"name": "Plan Only", "context_rules": {"allowed_views": ["Plan"]}},
        ]
        result = filter_by_context(items, "floor plan")
        self.assertEqual(len(result), 1)

    def test_plan_matches_section(self):
        items = [
            {"name": "Plan/Section", "context_rules": {"allowed_views": ["Plan"]}},
        ]
        result = filter_by_context(items, "section view")
        self.assertEqual(len(result), 1)

    def test_sheet_view_filter(self):
        items = [
            {"name": "Sheet Only", "context_rules": {"allowed_views": ["Sheet"]}},
        ]
        result = filter_by_context(items, "sheet")
        self.assertEqual(len(result), 1)
        result = filter_by_context(items, "3d")
        self.assertEqual(len(result), 0)

    def test_view_type_override(self):
        """view_type parameter should override context_string."""
        items = [
            {"name": "3D Only", "context_rules": {"allowed_views": ["3D"]}},
        ]
        # context_string says plan, but view_type says 3d
        result = filter_by_context(items, "plan", view_type="3d view")
        self.assertEqual(len(result), 1)

    def test_empty_items_list(self):
        result = filter_by_context([], "default")
        self.assertEqual(len(result), 0)

    def test_mixed_rules(self):
        items = [
            {"name": "A", "context_rules": {}},
            {"name": "B", "context_rules": {"allowed_views": ["3D"]}},
            {"name": "C", "context_rules": {"allowed_views": ["Sheet"]}},
            {"name": "D"},  # No context_rules
        ]
        result = filter_by_context(items, "3d")
        names = [r["name"] for r in result]
        self.assertIn("A", names)
        self.assertIn("B", names)
        self.assertIn("D", names)
        self.assertNotIn("C", names)

    def test_case_insensitive(self):
        items = [
            {"name": "3D Cmd", "context_rules": {"allowed_views": ["3D"]}},
        ]
        result = filter_by_context(items, "3D VIEW")
        self.assertEqual(len(result), 1)

    def test_allowed_classes_passes_through(self):
        """allowed_classes is reserved — items with it should pass."""
        items = [
            {"name": "WallCmd", "context_rules": {
                "allowed_classes": ["Wall"]
            }},
        ]
        result = filter_by_context(items, "default")
        self.assertEqual(len(result), 1)


class TestGetCurrentContextWithoutRevit(unittest.TestCase):
    """Tests for get_current_context() without Revit API."""

    def test_none_uiapp_returns_default(self):
        result = get_current_context(None)
        self.assertEqual(result, "default")


if __name__ == "__main__":
    unittest.main()
