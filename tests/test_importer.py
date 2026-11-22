# SPDX-License-Identifier: Apache-2.0
"""Synthetic importer lifecycle tests without FreeCAD or subprocess execution."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from freecad.dutchman_freecad import importer


class ImporterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.source = Path(self.temporary.name) / "Synthetic.f3d"
        self.source.write_bytes(b"synthetic input")
        self.output = ""
        self.macro_text = "import FreeCAD as App\ndoc = App.newDocument('Dutchman')\n"
        self.payload = {"schema": "dutchman.convert/1", "ok": True, "mode": "import"}
        self.returncode = 0
        self.macro_path = None
        self.document = Mock()
        self.document.Name = "Synthetic"
        self.app = types.ModuleType("FreeCAD")
        self.app.GuiUp = False
        self.app.Console = types.SimpleNamespace(PrintMessage=Mock(), PrintError=Mock())
        self.app.newDocument = Mock(return_value=self.document)
        self.app.getDocument = Mock(return_value=self.document)
        self.app.setActiveDocument = Mock()
        self.app.closeDocument = Mock()
        params = Mock()
        params.GetString.side_effect = lambda name, default: self.output if name == "OutputFolder" else default
        self.app.ParamGet = Mock(return_value=params)
        for patcher in (patch.dict(sys.modules, {"FreeCAD": self.app}),
                        patch.object(importer, "resolve_freecad", return_value="synthetic-binary"),
                        patch.object(importer.subprocess, "run", side_effect=self.convert)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def convert(self, arguments, **kwargs):
        self.assertEqual(arguments[:2], ["synthetic-binary", "convert"])
        self.macro_path = Path(arguments[arguments.index("-o") + 1])
        self.macro_path.write_text(self.macro_text)
        stdout = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return subprocess.CompletedProcess(arguments, self.returncode, stdout, "")

    def test_open_targets_named_document_and_removes_temporary_macro(self):
        self.assertIs(importer.open(str(self.source)), self.document)
        self.app.newDocument.assert_called_once_with("Synthetic")
        self.assertEqual(self.document.Label, "Synthetic")
        self.document.recompute.assert_called_once()
        self.document.commitTransaction.assert_called_once()
        self.assertFalse(self.macro_path.parent.exists())
        self.assertTrue(importer.LAST_REPORT["ok"])

    def test_failed_insert_aborts_transaction_and_keeps_target_document(self):
        self.macro_text += "raise RuntimeError('synthetic macro failure')\n"
        with self.assertRaisesRegex(RuntimeError, "synthetic macro failure"):
            importer.insert(str(self.source), "Synthetic")
        self.document.abortTransaction.assert_called_once()
        self.document.commitTransaction.assert_not_called()
        self.app.newDocument.assert_not_called()
        self.app.closeDocument.assert_not_called()
        self.assertFalse(self.macro_path.parent.exists())

    def test_failed_conversion_creates_no_document(self):
        self.payload = {"ok": False, "error": {"message": "synthetic conversion failure"}}
        self.returncode = 1
        with self.assertRaisesRegex(importer.ImportError, "synthetic conversion failure"):
            importer.open(str(self.source))
        self.app.newDocument.assert_not_called()
        self.assertFalse(self.macro_path.parent.exists())
        self.assertFalse(importer.LAST_REPORT["ok"])

    def test_invalid_json_creates_no_document(self):
        self.payload = "invalid JSON"
        with self.assertRaisesRegex(importer.ImportError, "invalid JSON"):
            importer.open(str(self.source))
        self.app.newDocument.assert_not_called()
        self.assertFalse(importer.LAST_REPORT["ok"])
        self.assertIn("invalid JSON", importer.LAST_REPORT["error"]["message"])
        self.assertFalse(self.macro_path.parent.exists())

    def test_missing_binary_replaces_previous_success_with_actionable_report(self):
        importer.LAST_REPORT = {"ok": True}
        with patch.object(importer, "resolve_freecad", side_effect=RuntimeError("Set its executable path in Preferences > Dutchman")), patch.object(importer, "show_report") as show:
            with self.assertRaisesRegex(RuntimeError, "Preferences"):
                importer.open(str(self.source))
        self.assertFalse(importer.LAST_REPORT["ok"])
        self.assertEqual(importer.LAST_REPORT["source_name"], "Synthetic.f3d")
        self.assertIn("Preferences", importer.LAST_REPORT["error"]["message"])
        show.assert_called_once_with(importer.LAST_REPORT)
        self.app.newDocument.assert_not_called()

    def test_gui_failure_interrupts_the_user_and_flags_setup_problems(self):
        from freecad.dutchman_freecad.binary import BinaryNotFound
        self.app.GuiUp = True
        with patch.object(importer, "resolve_freecad", side_effect=BinaryNotFound("missing")), \
                patch.object(importer, "show_report"), patch.object(importer, "show_failure") as failure:
            with self.assertRaises(BinaryNotFound):
                importer.open(str(self.source))
        failure.assert_called_once_with(importer.LAST_REPORT, True)
        self.assertTrue(importer.LAST_REPORT["setup_problem"])

    def test_declined_download_does_not_raise_a_second_dialog(self):
        from freecad.dutchman_freecad.binary import BinaryNotFound
        self.app.GuiUp = True
        with patch.object(importer, "resolve_freecad", side_effect=BinaryNotFound("missing", True)), \
                patch.object(importer, "show_report"), patch.object(importer, "show_failure") as failure:
            with self.assertRaises(BinaryNotFound):
                importer.open(str(self.source))
        failure.assert_not_called()

    def test_conversion_failure_is_a_normal_failure_dialog(self):
        self.app.GuiUp = True
        self.payload = {"ok": False, "error": {"message": "truncated"}}
        self.returncode = 1
        with patch.object(importer, "show_report"), patch.object(importer, "show_failure") as failure:
            with self.assertRaises(importer.ImportError):
                importer.open(str(self.source))
        failure.assert_called_once_with(importer.LAST_REPORT, False)

    def test_saved_copy_path_reaches_the_report(self):
        destination = Path(self.temporary.name) / "copies"
        self.output = str(destination)
        with patch.object(importer, "show_report") as show:
            importer.open(str(self.source))
        self.assertEqual(show.call_args.args[0]["saved_copy"], str(destination / "Synthetic.FCStd"))

    def test_failed_macro_report_does_not_claim_conversion_success(self):
        self.macro_text += "raise RuntimeError('synthetic macro failure')\n"
        with patch.object(importer, "show_report") as show:
            with self.assertRaisesRegex(RuntimeError, "synthetic macro failure"):
                importer.open(str(self.source))
        self.assertFalse(importer.LAST_REPORT["ok"])
        self.assertIn("macro failure", importer.LAST_REPORT["error"]["message"])
        show.assert_called_once_with(importer.LAST_REPORT)
        self.app.closeDocument.assert_called_once()

    def test_output_copy_preserves_existing_file(self):
        destination = Path(self.temporary.name) / "copies"
        destination.mkdir()
        existing = destination / "Synthetic.FCStd"
        existing.write_bytes(b"existing document")
        self.output = str(destination)
        importer.open(str(self.source))
        self.document.saveCopy.assert_called_once_with(str(destination / "Synthetic_1.FCStd"))
        self.assertEqual(existing.read_bytes(), b"existing document")


if __name__ == "__main__":
    unittest.main()
