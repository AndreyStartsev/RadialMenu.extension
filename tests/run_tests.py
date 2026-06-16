# -*- coding: utf-8 -*-
"""
Test runner for radial_menu library modules.

Runs tests for all modules that can be tested without Revit/WPF dependencies.
Uses standard unittest framework for CPython compatibility.
"""

import unittest
import sys
import os

# Add lib directory to path
lib_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "lib"))
sys.path.insert(0, lib_dir)


def run_all_tests():
    """Discover and run all test_*.py files in this directory."""
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=os.path.dirname(__file__),
        pattern="test_*.py",
        top_level_dir=os.path.dirname(__file__)
    )
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result


if __name__ == "__main__":
    result = run_all_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
