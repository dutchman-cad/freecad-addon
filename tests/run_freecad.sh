#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
python3 -m unittest discover -s tests -p 'test_*.py' -v
log=$(mktemp)
trap 'rm "$log"' EXIT
DUTCHMAN_BIN="${DUTCHMAN_BIN:-dutchman}" flatpak run --no-documents-portal --filesystem=host --command=FreeCADCmd org.freecad.FreeCAD tests/freecad_import_test.py 2>&1 | tee "$log"
python3 - "$log" <<'PY'
from pathlib import Path
import sys
assert 'Namespaced FreeCAD import and insert integration tests passed' in Path(sys.argv[1]).read_text(), 'FreeCAD did not execute the integration assertions'
PY
