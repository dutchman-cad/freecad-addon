# SPDX-License-Identifier: Apache-2.0
"""Register the preferences form, without adding a workbench."""
from pathlib import Path
import FreeCAD

if FreeCAD.GuiUp:
    import FreeCADGui
    _resources = Path(__file__).parent / "resources"
    FreeCADGui.addIconPath(str(_resources / "icons"))
    FreeCADGui.addPreferencePage(str(_resources / "panels" / "DutchmanPrefs.ui"), "Dutchman")
