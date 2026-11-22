# SPDX-License-Identifier: Apache-2.0
"""Widget-driven import cases, run inside the isolated FreeCAD process."""
import os
from pathlib import Path


def cases(app, gui, core, widgets, out, root, shot, action):
    fixtures = Path(os.environ['WALK_PRIVATE']) / 'fixtures'

    def dialog():
        matches = [w for w in widgets.QApplication.topLevelWidgets()
                   if isinstance(w, widgets.QFileDialog) and w.isVisible()]
        assert len(matches) == 1, 'Expected a single visible file dialog'
        return matches[0]

    def report(name, success):
        from freecad.dutchman_freecad import importer
        payload = importer.LAST_REPORT
        assert payload is not None, 'No import report'
        if success is not None:
            assert bool(payload.get('ok')) == success, payload
        assert gui.getMainWindow().findChild(widgets.QDockWidget, 'DutchmanReport').isVisible()
        (out / (name + '-report.json')).write_text(__import__('json').dumps(payload, indent=2))
        browser = gui.getMainWindow().findChild(widgets.QDockWidget, 'DutchmanReport').findChild(widgets.QTextBrowser)
        if browser is not None:
            (out / (name + '-panel.txt')).write_text(browser.toPlainText())
        shot(name)
        return payload

    # All opens go through the actual File > Open dialog, using the registered filter.
    for index, filename in enumerate(('generated_unit_cube.f3d', 'synthetic_cube.ipt',
                                      'solidworks_cube.sldprt'), 10):
        core.QTimer.singleShot(0, lambda: action('Std_Open'))
        yield 2
        chooser = dialog()
        candidates = [f for f in chooser.nameFilters()
                      if f.startswith('Dutchman') and '*.' + Path(filename).suffix[1:] in f]
        assert candidates, 'No Dutchman filter for ' + filename
        chooser.selectNameFilter(candidates[0])
        chooser.selectFile(str(fixtures / filename))
        shot(str(index) + '-open-dialog')
        yield 2
        chooser.accept()
        yield 3
        payload = report(str(index) + '-report', True if index == 10 else None)
        yield 2
        if payload.get('ok'):
            solids = [obj.Shape for obj in app.ActiveDocument.Objects
                      if hasattr(obj, 'Shape') and obj.Shape.Solids]
            assert solids, 'Expected a solid cube'
            assert any(abs(shape.Volume - 1000) < 1 for shape in solids), 'Expected 1000 mm³'

    core.QTimer.singleShot(0, lambda: action('Std_DlgPreferences'))
    yield 2
    trees = [w for w in widgets.QApplication.allWidgets()
             if isinstance(w, widgets.QTreeWidget) and w.isVisible()]
    selected = False
    for tree in trees:
        it = widgets.QTreeWidgetItemIterator(tree)
        while it.value():
            item = it.value()
            if item.text(0).replace('&', '') == 'Dutchman':
                tree.setCurrentItem(item)
                tree.expandItem(item)
                if item.childCount():
                    tree.setCurrentItem(item.child(0))
                selected = True
                break
            it += 1
    assert selected, 'Dutchman preferences category is absent'
    yield 2
    field = next(w for w in widgets.QApplication.allWidgets()
                 if w.objectName() == 'outputFolder' and w.isVisible())
    shot('14-preferences')
    yield 2
    field.setText(str(Path(os.environ['WALK_PRIVATE']) / 'converted'))
    shot('15-output-folder')
    yield 2
    prefs = field.window()
    buttons = prefs.findChild(widgets.QDialogButtonBox)
    assert buttons is not None, 'Preferences buttons missing'
    buttons.button(widgets.QDialogButtonBox.Ok).click()
    yield 2
    assert app.ParamGet('User parameter:BaseApp/Preferences/Mod/Dutchman').GetString('OutputFolder') == str(Path(os.environ['WALK_PRIVATE']) / 'converted')

    core.QTimer.singleShot(0, lambda: action('Std_Open'))
    yield 2
    chooser = dialog()
    chooser.selectNameFilter(next(f for f in chooser.nameFilters() if f.startswith('Dutchman') and '*.f3d' in f))
    chooser.selectFile(str(fixtures / 'truncated.f3d'))
    chooser.accept()
    yield 3
    report('16-truncated-file-message', False)
    yield 2

    target = app.ActiveDocument
    documents = set(app.listDocuments())
    before = len(target.Objects)
    core.QTimer.singleShot(0, lambda: action('Std_Import'))
    yield 2
    chooser = dialog()
    chooser.selectNameFilter(next(f for f in chooser.nameFilters() if f.startswith('Dutchman') and '*.f3d' in f))
    chooser.selectFile(str(fixtures / 'generated_unit_cube.f3d'))
    shot('17-import-dialog')
    yield 2
    chooser.accept()
    yield 3
    assert set(app.listDocuments()) == documents, 'Import created another document'
    assert len(target.Objects) > before, 'Import did not insert into the target'
    assert list((Path(os.environ['WALK_PRIVATE']) / 'converted').glob('*.FCStd')), 'Converted copy not saved'
    report('18-import-report', True)
    yield 2


def missing_binary(app, gui, core, widgets, out, root, shot, action):
    old_binary = os.environ.pop('DUTCHMAN_BIN', None)
    old_path = os.environ.get('PATH', '')
    os.environ['PATH'] = str(Path(os.environ['WALK_PRIVATE']) / 'stubs')
    params = app.ParamGet('User parameter:BaseApp/Preferences/Mod/Dutchman')
    old_configured = params.GetString('BinaryPath', '')
    params.SetString('BinaryPath', '')
    params.SetBool('AutoDownload', False)
    core.QTimer.singleShot(0, lambda: action('Std_Open'))
    yield 2
    chooser = next(w for w in widgets.QApplication.topLevelWidgets()
                   if isinstance(w, widgets.QFileDialog) and w.isVisible())
    chooser.selectNameFilter(next(f for f in chooser.nameFilters() if f.startswith('Dutchman') and '*.f3d' in f))
    chooser.selectFile(str(Path(os.environ['WALK_PRIVATE']) / 'fixtures' / 'generated_unit_cube.f3d'))
    chooser.accept()
    yield 2
    from freecad.dutchman_freecad import importer
    assert importer.LAST_REPORT and not importer.LAST_REPORT.get('ok')
    assert 'Preferences' in importer.LAST_REPORT['error']['message']
    shot('19-missing-binary-default')
    yield 2
    params.SetBool('AutoDownload', True)
    core.QTimer.singleShot(0, lambda: action('Std_Open'))
    yield 2
    chooser = next(w for w in widgets.QApplication.topLevelWidgets()
                   if isinstance(w, widgets.QFileDialog) and w.isVisible())
    chooser.selectFile(str(Path(os.environ['WALK_PRIVATE']) / 'fixtures' / 'generated_unit_cube.f3d'))
    chooser.selectNameFilter(next(f for f in chooser.nameFilters() if f.startswith('Dutchman') and '*.f3d' in f))
    # accept enters the modal download offer. Schedule the next coroutine step first.
    core.QTimer.singleShot(0, chooser.accept)
    yield 2
    offer = next(w for w in widgets.QApplication.topLevelWidgets()
                 if isinstance(w, widgets.QMessageBox) and w.isVisible()
                 and w.windowTitle() == 'Download Dutchman')
    shot('20-download-offer')
    yield 2
    offer.button(widgets.QMessageBox.No).click()
    yield 2
    from freecad.dutchman_freecad import importer
    assert importer.LAST_REPORT and not importer.LAST_REPORT.get('ok')
    assert 'Preferences' in importer.LAST_REPORT['error']['message']
    shot('21-missing-binary-report')
    yield 2
    params.SetBool('AutoDownload', False)
    params.SetString('BinaryPath', old_configured)
    os.environ['PATH'] = old_path
    if old_binary:
        os.environ['DUTCHMAN_BIN'] = old_binary
