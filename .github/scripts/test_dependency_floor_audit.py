#!/usr/bin/env python3
"""Unit tests for the PEP 440 dependency-floor parser."""
import unittest
from audit_dependency_floors import dependency_floor


class DependencyFloorTests(unittest.TestCase):
    def test_greater_equal_floor(self):
        self.assertEqual(dependency_floor("aiohttp>=3.14.5,<4"), "aiohttp==3.14.5")

    def test_exact_pin_floor(self):
        self.assertEqual(dependency_floor("pytest==9.1.1"), "pytest==9.1.1")

    def test_compatible_release_floor(self):
        self.assertEqual(dependency_floor("httpx~=0.27.1"), "httpx==0.27.1")

    def test_strict_greater_than_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "exclusive lower bound"):
            dependency_floor("example>1.2")

    def test_strict_greater_combined_with_inclusive_floor_still_fails(self):
        with self.assertRaisesRegex(ValueError, "exclusive lower bound"):
            dependency_floor("example>=1.0,>1.2,<2")

    def test_excluded_boundary_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "is excluded"):
            dependency_floor("example>=1.0,!=1.0")

    def test_wildcard_pin_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unsupported lower-bound"):
            dependency_floor("example==1.2.*")

    def test_unbounded_requirement_has_no_floor(self):
        self.assertIsNone(dependency_floor("example"))

    def test_environment_marker_is_respected(self):
        self.assertIsNone(dependency_floor('example>=1.0; sys_platform == "never"'))


if __name__ == "__main__":
    unittest.main()
