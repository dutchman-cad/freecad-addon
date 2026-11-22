#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
export DUTCHMAN_BIN="$PWD/.ci-tools/bin/dutchman"
export ADDON_ROOT="$PWD"
export QTWEBENGINE_DISABLE_SANDBOX=1
if [ "${1:-}" = gui ]; then
    timeout 5m xvfb-run -a .ci-tools/squashfs-root/AppRun tests/gui_screenshot.FCMacro < /dev/null
    test -s out/dutchman-report.png
else
    log=$(mktemp)
    trap 'rm "$log"' EXIT
    QT_QPA_PLATFORM=offscreen timeout 5m .ci-tools/squashfs-root/AppRun --console tests/freecad_import_test.py < /dev/null 2>&1 | tee "$log"
    python3 - "$log" <<'PYCODE'
from pathlib import Path
import sys
assert 'Namespaced FreeCAD import and insert integration tests passed' in Path(sys.argv[1]).read_text(), 'FreeCAD did not execute the integration assertions'
PYCODE
fi
