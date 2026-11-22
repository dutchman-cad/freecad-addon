# SPDX-License-Identifier: Apache-2.0
"""FreeCADCmd test using only a public synthetic 10 mm cube."""
import os
from pathlib import Path
import sys
import traceback

ROOT = (Path(__file__).resolve().parents[1] if "__file__" in globals()
        else Path(os.environ.get("ADDON_ROOT", os.getcwd())))
sys.path.insert(0, str(ROOT))
# FreeCAD may have imported its namespace before this standalone checkout was
# on sys.path. Refresh it here, in the harness, as installation would at startup.
import freecad
from pkgutil import extend_path
freecad.__path__ = extend_path(freecad.__path__, "freecad")


def run():
    import FreeCAD
    from freecad.dutchman_freecad import importer
    fixture = ROOT / "tests" / "fixtures" / "generated_unit_cube.f3d"
    before = set(FreeCAD.listDocuments())
    document = importer.open(str(fixture))
    assert document.Name not in before, "Expected a new document"
    assert document.Label == fixture.stem, "Document must be named after the file"
    assert document.Objects, "Expected at least one feature/object"
    bodies = [obj for obj in document.Objects if obj.isDerivedFrom("PartDesign::Body")
              and hasattr(obj, "Shape") and len(obj.Shape.Solids) >= 1]
    assert bodies, "Expected at least one solid body"
    assert any(abs(obj.Shape.Volume - 1000.0) < 0.1 for obj in bodies), "Expected a 1000 mm3 cube"
    assert importer.LAST_REPORT and importer.LAST_REPORT.get("ok"), "Conversion report must say ok"
    # Exercise insert too: reuse the document instead of creating another one.
    count = len(document.Objects)
    inserted = importer.insert(str(fixture), document.Name)
    assert inserted.Name == document.Name and len(document.Objects) > count
    assert set(FreeCAD.listDocuments()) == before | {document.Name}, "Unexpected extra document"
    os.write(1, b"Namespaced FreeCAD import and insert integration tests passed\n")
    return document


# FreeCADCmd imports .py scripts as modules on some builds.
if os.environ.get("DUTCHMAN_TEST_LIBRARY") != "1":
    try:
        run()
    except BaseException:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
    sys.stdout.flush()
    os._exit(0)
