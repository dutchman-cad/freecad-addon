# SPDX-License-Identifier: Apache-2.0
"""FreeCAD import protocol; all CAD conversion belongs to Dutchman."""

import builtins
import json
from pathlib import Path
import subprocess
import tempfile
import types

from .binary import PARAM_GROUP, BinaryNotFound, resolve_freecad
from .gui import show_failure, show_report

LAST_REPORT = None


class ImportError(RuntimeError):
    """An actionable conversion/import failure."""


def _execute_macro(path, app, document):
    """Give the generated macro its target document without global patching.

    Dutchman's macro imports FreeCAD as App, Part and Sketcher and creates a
    document with App.newDocument. A local module facade redirects that creation
    for both open and insert. Other modules use their ordinary FreeCAD imports.
    """
    facade = types.ModuleType("FreeCAD")
    facade.__getattr__ = lambda name: getattr(app, name)
    facade.newDocument = lambda *args, **kwargs: document
    facade.activeDocument = lambda: document
    facade.ActiveDocument = document
    original_import = builtins.__import__

    def macro_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "FreeCAD" and level == 0:
            return facade
        return original_import(name, globals, locals, fromlist, level)

    macro_builtins = dict(vars(builtins), __import__=macro_import)
    namespace = {"__builtins__": macro_builtins, "__name__": "__main__",
                 "__file__": str(path), "App": facade, "FreeCAD": facade, "doc": document}
    with path.open(encoding="utf-8") as stream:
        code = compile(stream.read(), str(path), "exec")
    exec(code, namespace)


def _convert(filename, docname=None):
    import FreeCAD as app
    global LAST_REPORT
    LAST_REPORT = None
    created = False
    saved_copy = None
    document = None
    transaction = False
    try:
        source = Path(filename).expanduser().resolve()
        binary = resolve_freecad()
        with tempfile.TemporaryDirectory(prefix="dutchman-freecad-") as temporary:
            macro = Path(temporary) / "rebuild.FCMacro"
            process = subprocess.run(
                [binary, "convert", str(source), "--to", "freecad", "-o", str(macro),
                 "--json", "--quiet", "--yes"], capture_output=True, text=True, timeout=3600)
            try:
                report = json.loads(process.stdout)
                if not isinstance(report, dict):
                    raise ValueError("Report is not an object")
            except ValueError as error:
                raise ImportError("Dutchman returned an invalid JSON conversion report") from error
            LAST_REPORT = report
            if process.returncode or not report.get("ok"):
                error = report.get("error") or {}
                detail = error.get("message", str(error)) if isinstance(error, dict) else str(error)
                raise ImportError("Dutchman conversion failed: " + detail)
            if not macro.is_file():
                raise ImportError("Dutchman did not produce a FreeCAD macro")
            if docname is not None:
                document = app.getDocument(docname)
                if document is None:
                    raise ImportError("Target document does not exist: " + docname)
            else:
                document = app.newDocument(source.stem)
                document.Label = source.stem
                created = True
            app.setActiveDocument(document.Name)
            document.openTransaction("Import with Dutchman")
            transaction = True
            _execute_macro(macro, app, document)
            document.recompute()
            document.commitTransaction()
            transaction = False
        folder = app.ParamGet(PARAM_GROUP).GetString("OutputFolder", "").strip()
        if folder:
            destination = Path(folder).expanduser()
            destination.mkdir(parents=True, exist_ok=True)
            output = destination / (source.stem + ".FCStd")
            index = 1
            while output.exists():
                output = destination / (source.stem + "_" + str(index) + ".FCStd")
                index += 1
            document.saveCopy(str(output))
            saved_copy = str(output)
        report = dict(report, source_name=source.name)
        if saved_copy:
            report["saved_copy"] = saved_copy
        LAST_REPORT = report
        show_report(report)
        if app.GuiUp:
            # Fit after the report dock has taken its width, or the model spills under it.
            import FreeCADGui
            FreeCADGui.updateGui()
            FreeCADGui.activeDocument().activeView().viewAxonometric()
            FreeCADGui.activeDocument().activeView().fitAll()
            if created:
                # A freshly opened file has no unsaved edits; do not show "*" in its tab.
                try:
                    FreeCADGui.getDocument(document.Name).Modified = False
                except Exception:
                    pass
        return document
    except Exception as error:
        if transaction and document is not None:
            document.abortTransaction()
        if created and document is not None:
            app.closeDocument(document.Name)
        # Replace any previous success even when conversion never started (for
        # example, a missing executable or an invalid JSON response).
        report = dict(LAST_REPORT or {})
        report["ok"] = False
        report["source_name"] = Path(filename).name
        if not report.get("error"):
            report["error"] = {"message": str(error)}
        setup_problem = isinstance(error, BinaryNotFound)
        report["setup_problem"] = setup_problem
        LAST_REPORT = report
        show_report(report)
        if app.GuiUp and not getattr(error, "declined", False):
            show_failure(report, setup_problem)
        app.Console.PrintError("Dutchman import failed: {}\n".format(error))
        raise


def open(filename):
    return _convert(filename)


def insert(filename, docname):
    return _convert(filename, docname)
