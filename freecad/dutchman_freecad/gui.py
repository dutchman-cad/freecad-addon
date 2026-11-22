# SPDX-License-Identifier: Apache-2.0
"""GUI entry points; importing this module also works without Qt."""

_dock = None
REPORT_WIDTH = 440


def qt():
    from PySide import QtCore, QtWidgets
    return QtCore, QtWidgets


def confirm_download():
    """Ask before contacting GitHub. Nothing is fetched unless the user agrees."""
    import FreeCADGui
    _, widgets = qt()
    box = widgets.QMessageBox(widgets.QMessageBox.Question, "Dutchman is not installed",
                              "Dutchman converts your CAD files for this addon. Download it now?",
                              widgets.QMessageBox.NoButton, FreeCADGui.getMainWindow())
    box.setInformativeText(
        "• It comes from the public GitHub releases of dutchman-cad/dutchman, for this OS and architecture.\n"
        "• The download is checked against its published SHA-256 before it is used.\n"
        "• GitHub sees your IP address and this addon's name. No CAD files or reports are sent.\n"
        "• Already have Dutchman? Cancel and set its path in Edit > Preferences > Dutchman.")
    download = box.addButton("Download Dutchman", widgets.QMessageBox.AcceptRole)
    box.addButton(widgets.QMessageBox.Cancel)
    box.setDefaultButton(download)
    box.exec_()
    return box.clickedButton() is download


class _Progress:
    """Modal progress for the release download; Cancel aborts the transfer."""

    def __init__(self):
        self.dialog = None

    def __call__(self, label, done, total):
        from .binary import BinaryError
        import FreeCADGui
        _, widgets = qt()
        if self.dialog is None:
            self.dialog = widgets.QProgressDialog("", "Cancel", 0, 0, FreeCADGui.getMainWindow())
            self.dialog.setWindowTitle("Installing Dutchman")
            self.dialog.setMinimumDuration(0)
            self.dialog.setMinimumWidth(420)
            self.dialog.setAutoClose(False)
            self.dialog.setAutoReset(False)
            self.dialog.setWindowModality(qt()[0].Qt.WindowModal)
        text = label
        if total:
            text += ": {:.0f} of {:.0f} MB".format(done / 1e6, total / 1e6)
            self.dialog.setMaximum(total)
            self.dialog.setValue(done)
        else:
            self.dialog.setMaximum(0)
        self.dialog.setLabelText(text)
        widgets.QApplication.processEvents()
        if self.dialog.wasCanceled():
            raise BinaryError("Download cancelled")

    def close(self):
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None


def download_progress():
    return _Progress()


def open_preferences():
    import FreeCADGui
    for call in (lambda: FreeCADGui.showPreferencesByName("Dutchman", "Import settings"),
                 lambda: FreeCADGui.showPreferences("Dutchman")):
        try:
            call()
            return
        except Exception:
            continue


def show_failure(report, setup_problem=False):
    """Interrupt the user: a failed import must never look like a finished one."""
    import FreeCADGui
    from .report import error_message
    _, widgets = qt()
    name = report.get("source_name") or "the file"
    box = widgets.QMessageBox(widgets.QMessageBox.Critical, "Dutchman import failed",
                              "Dutchman could not import " + name + ".",
                              widgets.QMessageBox.Close, FreeCADGui.getMainWindow())
    message = error_message(report)
    if not setup_problem:
        # The full text, with its links, is in the report panel; say it once.
        first = message.split(". ")[0].rstrip(".")
        message = (first if len(first) < 240 else first[:240] + "…") + \
            ".\n\nThe full message is in the Dutchman import report panel."
    box.setInformativeText(message if len(message) < 600 else message[:600] + "…")
    prefs = box.addButton("Open Dutchman preferences", widgets.QMessageBox.ActionRole) if setup_problem else None
    box.exec_()
    if prefs is not None and box.clickedButton() is prefs:
        open_preferences()


def show_report(report):
    import FreeCAD
    from .report import as_html, lines
    if not FreeCAD.GuiUp:
        summary = lines(report)[:3] + ["Losses: {}".format(len(report.get("losses") or []))]
        if not report.get("ok"):
            from .report import error_message
            summary.append("Error: " + error_message(report))
        FreeCAD.Console.PrintMessage("\n".join(summary) + "\n")
        return
    import FreeCADGui
    global _dock
    core, widgets = qt()
    if _dock is None:
        _dock = widgets.QDockWidget("Dutchman import report", FreeCADGui.getMainWindow())
        _dock.setObjectName("DutchmanReport")
        browser = widgets.QTextBrowser()
        browser.setOpenExternalLinks(True)
        _dock.setWidget(browser)
        FreeCADGui.getMainWindow().addDockWidget(core.Qt.RightDockWidgetArea, _dock)
        FreeCADGui.getMainWindow().resizeDocks([_dock], [REPORT_WIDTH], core.Qt.Horizontal)
    _dock.widget().setHtml(as_html(report))
    _dock.show()
    _dock.raise_()
