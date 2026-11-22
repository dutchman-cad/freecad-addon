# SPDX-License-Identifier: Apache-2.0
"""Discover import filters while preserving FreeCAD's native readers."""

import json
import re
import subprocess

NATIVE = {"fcstd", "step", "stp", "iges", "igs", "brep", "brp", "stl", "obj"}
FALLBACK = [
    ("Autodesk Fusion", ["f3d", "f3z"]),
    ("Autodesk Inventor", ["ipt", "iam"]),
    ("SOLIDWORKS", ["sldprt", "sldasm"]),
    ("CATIA", ["CATPart", "CATProduct"]),
    ("Rhinoceros", ["3dm"]),
]


def parse_formats(payload):
    if not payload.get("ok") or not isinstance(payload.get("formats"), list):
        raise ValueError("Invalid Dutchman format report")
    result = []
    for item in payload["formats"]:
        # Releases expose readable formats using can_read (or read/readable).
        readable = item.get("can_read", item.get("readable", item.get("read", True)))
        if not readable or item.get("status") == "not_supported":
            continue
        extensions = item.get("extensions", [])
        if isinstance(extensions, str):
            extensions = [extensions]
        extensions = [ext.lstrip("*.") for ext in extensions if isinstance(ext, str)]
        extensions = [ext for ext in extensions if re.fullmatch(r"[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*", ext)
                      and ext.lower() not in NATIVE]
        if extensions:
            result.append((item.get("name", item.get("id", "CAD")), extensions))
    return result


def discover(binary=None):
    if binary:
        try:
            process = subprocess.run([binary, "formats", "--json"], capture_output=True,
                                     text=True, timeout=20, check=True)
            return parse_formats(json.loads(process.stdout))
        except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
            pass
    return FALLBACK


def register(app):
    from .binary import BinaryError, PARAM_GROUP, resolve
    from pathlib import Path
    try:
        binary = resolve(app.ParamGet(PARAM_GROUP).GetString("BinaryPath", ""),
                         Path(app.getUserAppDataDir()) / "Dutchman" / "bin")
    except BinaryError:
        binary = None
    for program, extensions in discover(binary):
        patterns = " ".join("*." + ext for ext in extensions)
        app.addImportType("Dutchman: {} ({})".format(program, patterns),
                          "freecad.dutchman_freecad.importer")
