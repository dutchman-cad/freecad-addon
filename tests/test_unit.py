# SPDX-License-Identifier: Apache-2.0
"""Synthetic unit tests; no FreeCAD or external network required."""
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest.mock import patch

from freecad.dutchman_freecad import binary, formats, report
from freecad.dutchman_freecad.importer import _execute_macro


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.destination = Path(self.temp.name) / "install"
        buffer = io.BytesIO()
        self.payload = b"#!/bin/sh\necho synthetic\n"
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            info = tarfile.TarInfo("release/" + binary.executable_name())
            info.size = len(self.payload)
            archive.addfile(info, io.BytesIO(self.payload))
        self.archive = buffer.getvalue()
        self.name = "dutchman-x86_64-unknown-linux-gnu.tar.gz"
        self.routes = {"/archive": self.archive,
                        "/checksum": (hashlib.sha256(self.archive).hexdigest() + "  " + self.name).encode()}
        routes = self.routes

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path not in routes:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(routes[self.path])

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.base = "http://127.0.0.1:" + str(self.server.server_port)
        self.assets = [{"name": self.name, "browser_download_url": self.base + "/archive"},
                       {"name": "SHA256SUMS", "browser_download_url": self.base + "/checksum"}]

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def download(self):
        self.routes["/release"] = json.dumps({"assets": self.assets}).encode()
        return binary.download_release(self.destination, self.base + "/release", "Linux", "x86_64")

    def test_verified_download(self):
        executable = self.download()
        self.assertEqual(executable.read_bytes(), self.payload)
        self.assertTrue(os.access(executable, os.X_OK))
        self.assertEqual(list(self.destination.iterdir()), [executable])

    def test_checksum_mismatch_refused_without_replacing_binary(self):
        self.destination.mkdir()
        target = self.destination / binary.executable_name()
        target.write_bytes(b"existing verified installation")
        self.routes["/checksum"] = ("0" * 64 + "  " + self.name).encode()
        with self.assertRaisesRegex(binary.BinaryError, "mismatch"):
            self.download()
        self.assertEqual(target.read_bytes(), b"existing verified installation")

    def test_missing_checksum_refused(self):
        self.assets.pop()
        with self.assertRaisesRegex(binary.BinaryError, "no SHA256SUMS"):
            self.download()
        self.assertFalse(self.destination.exists())

    def test_single_checksum_asset(self):
        self.assets[1]["name"] = self.name + ".sha256"
        self.routes["/checksum"] = hashlib.sha256(self.archive).hexdigest().encode()
        self.assertEqual(self.download().read_bytes(), self.payload)

    def test_shared_sha256_asset(self):
        self.assets[1]["name"] = "release.sha256"
        self.assertEqual(self.download().read_bytes(), self.payload)

    def test_checksum_for_other_archive_refused(self):
        self.routes["/checksum"] = ("0" * 64 + "  other.tar.gz").encode()
        with self.assertRaisesRegex(binary.BinaryError, "selected archive"):
            self.download()

    def test_archive_links_are_not_extracted(self):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            item = tarfile.TarInfo("dutchman")
            item.type = tarfile.SYMTYPE
            item.linkname = "/bin/sh"
            archive.addfile(item)
        with self.assertRaisesRegex(binary.BinaryError, "regular"):
            binary._unpack_executable(buffer.getvalue(), "release.tar.gz")

    def test_unsupported_architecture(self):
        with self.assertRaises(binary.BinaryError):
            binary.select_asset(self.assets, "Linux", "unknown")

    def test_progress_reports_each_stage_and_final_size(self):
        events = []
        self.routes["/release"] = json.dumps({"assets": self.assets}).encode()
        binary.download_release(self.destination, self.base + "/release", "Linux", "x86_64",
                               progress=lambda label, done, total: events.append((label, done, total)))
        labels = [label for label, _, _ in events]
        self.assertEqual(labels[0], "Looking up the latest Dutchman release")
        self.assertIn("Downloading checksums", labels)
        # The synthetic server sends no Content-Length, so the total is unknown (0).
        self.assertEqual(events[-1], ("Downloading Dutchman", len(self.archive), 0))

    def test_successful_download_leaves_only_the_executable(self):
        self.download()
        self.assertEqual([p.name for p in self.destination.iterdir()], [binary.executable_name()])

    def test_cancel_from_progress_leaves_nothing_installed(self):
        def progress(label, done, total):
            if label == "Downloading Dutchman":
                raise binary.BinaryError("Download cancelled")
        self.routes["/release"] = json.dumps({"assets": self.assets}).encode()
        with self.assertRaisesRegex(binary.BinaryError, "cancelled"):
            binary.download_release(self.destination, self.base + "/release", "Linux", "x86_64",
                                    progress=progress)
        self.assertFalse(self.destination.exists())

    def test_unreachable_network_is_a_setup_problem_with_plain_words(self):
        with self.assertRaises(binary.BinaryNotFound) as caught:
            # Port 9 on loopback refuses connections; nothing is downloaded.
            binary.download_release(self.destination, "http://127.0.0.1:9/release",
                                    "Linux", "x86_64")
        message = str(caught.exception)
        self.assertIn("could not be downloaded", message)
        self.assertIn("Edit > Preferences > Dutchman", message)
        self.assertNotIn("<urlopen", message)
        self.assertFalse(self.destination.exists())


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("override", "configured", binary.executable_name()):
            path = self.root / name
            path.write_text("synthetic executable")
            path.chmod(0o755)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_override_has_highest_priority(self):
        os.environ["DUTCHMAN_BIN"] = str(self.root / "override")
        self.assertEqual(binary.resolve(str(self.root / "configured")), str(self.root / "override"))

    def test_configured_then_path_then_managed(self):
        with patch.object(binary.shutil, "which", return_value="/synthetic/dutchman"):
            self.assertEqual(binary.resolve(str(self.root / "configured")), str(self.root / "configured"))
            self.assertEqual(binary.resolve(install_dir=self.root), "/synthetic/dutchman")
        with patch.object(binary.shutil, "which", return_value=None):
            self.assertEqual(binary.resolve(install_dir=self.root), str(self.root / binary.executable_name()))

    def test_invalid_override_and_configured_path_are_actionable(self):
        with self.assertRaises(binary.BinaryError):
            binary.resolve("/missing")
        os.environ["DUTCHMAN_BIN"] = "/missing"
        with self.assertRaisesRegex(binary.BinaryError, "DUTCHMAN_BIN"):
            binary.resolve(str(self.root / "configured"))

    def test_download_requires_both_preference_and_confirmation(self):
        with patch.object(binary.shutil, "which", return_value=None), patch.object(binary, "download_release") as download:
            for enabled, confirm in ((False, lambda: True), (True, None), (True, lambda: False)):
                with self.assertRaises(binary.BinaryError):
                    binary.resolve(install_dir=self.root / "missing", auto_download=enabled, confirm=confirm)
            download.assert_not_called()
            download.return_value = self.root / "verified"
            self.assertEqual(binary.resolve(install_dir=self.root / "missing", auto_download=True,
                                            confirm=lambda: True), str(self.root / "verified"))
            download.assert_called_once()


class FormatTests(unittest.TestCase):
    def test_native_and_unreadable_formats_excluded(self):
        payload = {"ok": True, "formats": [
            {"name": "Fusion", "extensions": ["f3d", "*.f3z", "STEP", "stl", "obj", "FCStd", "iges", "brep"]},
            {"name": "Export only", "extensions": ["write"], "can_read": False},
            {"name": "Unsupported", "extensions": ["bad"], "status": "not_supported"},
            {"name": "Versioned", "extensions": ["prt.N"]},
            {"name": "Bad extension", "extensions": ["x); injected", "../f3d"]}]}
        self.assertEqual(formats.parse_formats(payload), [("Fusion", ["f3d", "f3z"]), ("Versioned", ["prt.N"])])

    def test_discovery_failure_uses_fallback(self):
        with patch.object(formats.subprocess, "run", side_effect=OSError):
            self.assertEqual(formats.discover("missing"), formats.FALLBACK)
        self.assertTrue({"f3d", "f3z", "ipt", "iam", "sldprt", "sldasm", "CATPart", "3dm"}
                        <= {e for _, exts in formats.FALLBACK for e in exts})

    def test_discovery_uses_cli_response(self):
        from subprocess import CompletedProcess
        payload = {"ok": True, "formats": [{"name": "New reader", "extensions": ["new"]}]}
        with patch.object(formats.subprocess, "run", return_value=CompletedProcess([], 0, json.dumps(payload), "")):
            self.assertEqual(formats.discover("synthetic"), [("New reader", ["new"])])


class NotFoundTests(unittest.TestCase):
    def test_missing_binary_is_distinguishable_and_records_a_declined_download(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(binary.shutil, "which", return_value=None):
            with self.assertRaises(binary.BinaryNotFound) as raised:
                binary.resolve(install_dir="/nonexistent")
            self.assertFalse(raised.exception.declined)
            with self.assertRaises(binary.BinaryNotFound) as raised:
                binary.resolve(install_dir="/nonexistent", auto_download=True, confirm=lambda: False)
            self.assertTrue(raised.exception.declined)
            self.assertIn("Download it", str(raised.exception))
            with self.assertRaises(binary.BinaryNotFound) as raised:
                binary.resolve(install_dir="/nonexistent", auto_download=False)
            self.assertNotIn("Download it", str(raised.exception))
            self.assertIn("turn on the download offer", str(raised.exception))


class ReportTests(unittest.TestCase):
    def test_modes_and_counts(self):
        self.assertEqual(report.mode_label({"history": {"mapped": 3, "rebuilt": 3, "total": 3}}), "full history")
        self.assertEqual(report.mode_label({"history": {"mapped": 1, "total": 3}}), "partial")
        self.assertEqual(report.mode_label({"history": {"mapped": 3, "rebuilt": 1, "total": 3}}), "partial")
        self.assertEqual(report.mode_label({"mode": "import"}), "geometry only")
        self.assertIn("mapped 1 / rebuilt 0 / total 3", "\n".join(report.lines({"history": {"mapped": 1, "total": 3}})))

    def test_headless_summary_needs_no_qt(self):
        import types
        from unittest.mock import Mock
        from freecad.dutchman_freecad.gui import show_report
        app = types.ModuleType("FreeCAD")
        app.GuiUp = False
        app.Console = types.SimpleNamespace(PrintMessage=Mock())
        with patch.dict("sys.modules", {"FreeCAD": app}):
            show_report({"ok": True, "losses": [{"code": "synthetic", "detail": "a loss"}]})
        summary = app.Console.PrintMessage.call_args.args[0]
        self.assertIn("Losses: 1", summary)
        self.assertEqual(len(summary.splitlines()), 4)

    def test_failure_shows_escaped_error_and_source_with_private_help_first(self):
        formatted = report.as_html({"ok": False, "source_name": "synthetic<cube>.f3d",
                                    "error": {"message": "Truncated <archive>"}})
        self.assertIn("synthetic&lt;cube&gt;.f3d", formatted)
        self.assertIn("Truncated &lt;archive&gt;", formatted)
        self.assertIn("Is there a problem? Is something missing?", formatted)
        self.assertLess(formatted.index("discord.gg"), formatted.index("github.com"))
        self.assertIn("DM Dutchy", formatted)

    def test_setup_problem_points_to_preferences_not_support(self):
        formatted = report.as_html({"ok": False, "setup_problem": True, "source_name": "a.f3d",
                                    "error": {"message": "Dutchman was not found."}})
        self.assertIn("Edit &gt; Preferences &gt; Dutchman", formatted)
        self.assertNotIn("discord.gg", formatted)

    def test_error_urls_are_clickable_and_escaped(self):
        formatted = report.as_html({"ok": False, "error": {"message": "see https://example.org/a?x=1&y=2."}})
        self.assertIn('<a href="https://example.org/a?x=1&amp;y=2">', formatted)

    def test_success_leads_with_headline_and_help_before_notes(self):
        formatted = report.as_html({"ok": True, "mode": "import", "saved_copy": "/tmp/out/a.FCStd",
                                    "verification": {"status": "not_applicable", "reason": "embedded STEP"},
                                    "losses": [{"code": "x", "detail": "a note"}]})
        self.assertIn("Imported as geometry only", formatted)
        self.assertNotIn("History:", formatted)
        self.assertIn("/tmp/out/a.FCStd", formatted)
        self.assertLess(formatted.index("Is there a problem?"), formatted.index("Notes (1)"))
        self.assertLess(formatted.index("Imported as geometry only"), formatted.index("Is there a problem?"))

    def test_full_history_counts_shown_when_history_exists(self):
        formatted = report.as_html({"ok": True, "history": {"mapped": 4, "rebuilt": 4, "total": 4}})
        self.assertIn("Imported with full feature history", formatted)
        self.assertIn("4 of 4 features rebuilt", formatted)

    def test_losses_links_and_escaping(self):
        payload = {"ok": True, "verification": {"status": "not_applicable", "reason": "embedded STEP"},
                   "losses": [{"code": "x", "detail": "<unsafe>", "docs_url": "https://example.org/docs"},
                              {"code": "y", "message": "fallback", "docs": "javascript:alert(1)"},
                              {"code": None, "message": "informational detail"}]}
        formatted = report.as_html(payload)
        self.assertIn("&lt;unsafe&gt;", formatted)
        self.assertIn('href="https://example.org/docs"', formatted)
        self.assertNotIn("javascript:", formatted)
        self.assertIn("embedded STEP", formatted)
        self.assertIn("y: fallback", formatted)
        self.assertIn("info: informational detail", formatted)


class MacroTests(unittest.TestCase):
    def test_macro_document_creation_is_redirected_without_global_patch(self):
        import types
        app = types.ModuleType("FreeCAD")
        app.newDocument = lambda name: self.fail("Must not create a second document")
        document = types.SimpleNamespace(Label="before")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.FCMacro"
            path.write_text("import FreeCAD as App\ndoc = App.newDocument('Dutchman')\ndoc.Label = 'imported'\n")
            with patch.dict("sys.modules", {"FreeCAD": app}):
                _execute_macro(path, app, document)
        self.assertEqual(document.Label, "imported")
        self.assertNotIn("ActiveDocument", vars(app))


if __name__ == "__main__":
    unittest.main()
