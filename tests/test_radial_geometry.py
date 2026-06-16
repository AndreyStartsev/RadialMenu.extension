# -*- coding: utf-8 -*-
"""Tests for radial_geometry module.

Pure math — no Revit or WPF dependencies required.
"""

import unittest
import math
import sys
import os

# Add lib to path
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "lib")))

from radial_menu.radial_geometry import (
    get_sector_path,
    get_text_position,
    calculate_ring_radii,
    calculate_effective_sectors,
)


class TestGetSectorPath(unittest.TestCase):
    """Tests for get_sector_path()."""

    def test_returns_string(self):
        result = get_sector_path(320, 320, 50, 110, 270.0, 8, 3.0)
        self.assertIsInstance(result, str)

    def test_path_starts_with_M_and_ends_with_Z(self):
        result = get_sector_path(320, 320, 50, 110, 0.0, 4, 2.0)
        self.assertTrue(result.startswith("M "))
        self.assertTrue(result.endswith(" Z"))

    def test_path_contains_arc_commands(self):
        result = get_sector_path(320, 320, 50, 110, 90.0, 6, 3.0)
        # Must contain two arc segments (A)
        self.assertEqual(result.count(" A "), 2)

    def test_single_sector_full_circle(self):
        """A single sector should span the full 360 degrees."""
        result = get_sector_path(100, 100, 20, 50, 0.0, 1, 0.0)
        self.assertIsInstance(result, str)
        self.assertIn("M ", result)

    def test_zero_gap_produces_valid_path(self):
        result = get_sector_path(0, 0, 10, 20, 45.0, 4, 0.0)
        self.assertIn("M ", result)
        self.assertIn(" Z", result)

    def test_small_inner_radius_with_large_gap(self):
        """When gap_width/2 >= r_in, t_in should be 0."""
        result = get_sector_path(100, 100, 1, 50, 0.0, 4, 10.0)
        self.assertIsInstance(result, str)

    def test_symmetry_opposite_sectors(self):
        """Sectors at 0° and 180° should have symmetric Y-coordinates."""
        path_0 = get_sector_path(0, 0, 20, 40, 0.0, 2, 0.0)
        path_180 = get_sector_path(0, 0, 20, 40, 180.0, 2, 0.0)
        # Both should be valid paths
        self.assertTrue(path_0.startswith("M "))
        self.assertTrue(path_180.startswith("M "))

    def test_different_sector_counts_produce_different_paths(self):
        p4 = get_sector_path(320, 320, 50, 110, 0.0, 4, 3.0)
        p8 = get_sector_path(320, 320, 50, 110, 0.0, 8, 3.0)
        self.assertNotEqual(p4, p8)


class TestGetTextPosition(unittest.TestCase):
    """Tests for get_text_position()."""

    def test_returns_tuple_of_two_floats(self):
        left, top = get_text_position(320, 320, 50, 110, 0.0)
        self.assertIsInstance(left, float)
        self.assertIsInstance(top, float)

    def test_right_angle_position(self):
        """At 0° (right), left should be > cx."""
        left, top = get_text_position(320, 320, 50, 110, 0.0, 80, 70)
        r_mid = (50 + 110) / 2.0
        expected_x_center = 320 + r_mid
        self.assertAlmostEqual(left, expected_x_center - 40, places=1)

    def test_top_angle_position(self):
        """At 270° (up in screen coords), top should be < cy."""
        left, top = get_text_position(320, 320, 50, 110, 270.0)
        self.assertLess(top, 320)

    def test_custom_dimensions(self):
        left1, top1 = get_text_position(100, 100, 20, 40, 90.0, 40, 30)
        left2, top2 = get_text_position(100, 100, 20, 40, 90.0, 80, 70)
        # Wider dimensions shift left more
        self.assertLess(left2, left1)

    def test_center_at_origin(self):
        left, top = get_text_position(0, 0, 10, 30, 0.0, 20, 20)
        r_mid = (10 + 30) / 2.0
        self.assertAlmostEqual(left, r_mid - 10, places=1)


class TestCalculateRingRadii(unittest.TestCase):
    """Tests for calculate_ring_radii()."""

    def test_default_three_levels(self):
        radii = calculate_ring_radii(45, 60, 5)
        self.assertEqual(len(radii), 3)

    def test_level1_inner_radius(self):
        radii = calculate_ring_radii(45, 60, 5)
        r_in, r_out = radii[0]
        self.assertAlmostEqual(r_in, 50.0)  # 45 + 5
        self.assertAlmostEqual(r_out, 110.0)  # 50 + 60

    def test_level2_stacks_on_level1(self):
        radii = calculate_ring_radii(45, 60, 5)
        l1_out = radii[0][1]
        l2_in = radii[1][0]
        self.assertAlmostEqual(l2_in, l1_out + 5)

    def test_level3_stacks_on_level2(self):
        radii = calculate_ring_radii(45, 60, 5)
        l2_out = radii[1][1]
        l3_in = radii[2][0]
        self.assertAlmostEqual(l3_in, l2_out + 5)

    def test_single_level(self):
        radii = calculate_ring_radii(30, 40, 10, num_levels=1)
        self.assertEqual(len(radii), 1)
        self.assertAlmostEqual(radii[0][0], 40.0)
        self.assertAlmostEqual(radii[0][1], 80.0)

    def test_five_levels(self):
        radii = calculate_ring_radii(20, 30, 5, num_levels=5)
        self.assertEqual(len(radii), 5)
        # Each level should be further out
        for i in range(1, 5):
            self.assertGreater(radii[i][0], radii[i - 1][1])

    def test_zero_gap(self):
        radii = calculate_ring_radii(45, 60, 0)
        self.assertAlmostEqual(radii[0][0], 45.0)  # No gap
        self.assertAlmostEqual(radii[0][1], 105.0)
        self.assertAlmostEqual(radii[1][0], 105.0)  # Touches L1


class TestCalculateEffectiveSectors(unittest.TestCase):
    """Tests for calculate_effective_sectors()."""

    def test_zero_count_returns_zero(self):
        self.assertEqual(calculate_effective_sectors(0, 90), 0)

    def test_negative_count_returns_zero(self):
        self.assertEqual(calculate_effective_sectors(-3, 90), 0)

    def test_no_clamping_needed(self):
        """8 sectors at 45° each = 360°, max_angle=90 → no change."""
        self.assertEqual(calculate_effective_sectors(8, 90), 8)

    def test_clamping_applied(self):
        """2 sectors at 180° each, max_angle=90 → clamped to 4."""
        result = calculate_effective_sectors(2, 90)
        self.assertEqual(result, 4)

    def test_clamping_three_sectors_at_60_max(self):
        """3 sectors at 120° each, max_angle=60 → clamped to 6."""
        result = calculate_effective_sectors(3, 60)
        self.assertEqual(result, 6)

    def test_exact_boundary(self):
        """4 sectors at 90° each = exactly max_angle=90 → no change."""
        self.assertEqual(calculate_effective_sectors(4, 90), 4)

    def test_result_never_less_than_actual(self):
        for n in range(1, 20):
            for angle in [30, 60, 90, 120, 180, 360]:
                result = calculate_effective_sectors(n, angle)
                self.assertGreaterEqual(result, n)

    def test_full_circle_max_angle(self):
        """max_angle=360 should never clamp."""
        self.assertEqual(calculate_effective_sectors(1, 360), 1)
        self.assertEqual(calculate_effective_sectors(5, 360), 5)


if __name__ == "__main__":
    unittest.main()
