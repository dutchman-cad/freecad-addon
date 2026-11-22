# SPDX-License-Identifier: Apache-2.0
"""Dutchman importers in FreeCAD's shared addon namespace."""

__version__ = "0.1.7"

# FreeCAD imports namespace packages during startup, including in console mode.
# Ordinary Python can import the helpers for unit tests without FreeCAD installed.
try:
    import FreeCAD as _app
except ImportError:
    _app = None

if _app is not None:
    from .formats import register as _register
    _register(_app)
