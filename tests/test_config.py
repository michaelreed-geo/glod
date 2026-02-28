"""
Tests for glod/geometry.py

Run with:  pytest test_geometry.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import unittest.mock as mock

import pytest


class TestConfig:
    def setup_method(self):
        # Reset USE_PYPROJ to False before each test.
        import glod.config
        glod.config.USE_PYPROJ = False

    def test_use_pyproj_defaults_to_false(self):
        import glod.config
        assert glod.config.USE_PYPROJ is False

    def test_set_use_pyproj_true_raises_if_not_installed(self):
        import glod.config
        with mock.patch.dict("sys.modules", {"pyproj": None}):
            with pytest.raises(ImportError, match="pyproj is not installed"):
                glod.config.set_use_pyproj(True)

    def test_set_use_pyproj_true_succeeds_if_installed(self):
        import glod.config
        fake_pyproj = mock.MagicMock()
        with mock.patch.dict("sys.modules", {"pyproj": fake_pyproj}):
            glod.config.set_use_pyproj(True)
        assert glod.config.USE_PYPROJ is True

    def test_set_use_pyproj_false_always_succeeds(self):
        import glod.config
        glod.config.set_use_pyproj(False)
        assert glod.config.USE_PYPROJ is False