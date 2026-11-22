# Dutchman

Import CAD files and review what survived conversion. Dutchman performs the
conversion; this extension runs its rebuild macro in your document and shows
history coverage, verification, and losses. It adds no workbench.

## Quick start

1. Choose **File → Open** or **File → Import** and select a **Dutchman: …** file filter. If Dutchman is not installed, the first import offers a checksum-verified download; or select an existing copy under **Edit → Preferences → Dutchman** (a copy on PATH also works).
2. **Open** creates a document; **Import** inserts into the current document.
3. Read the **Dutchman import report** dock. Check the verification result and losses before relying on the converted model.
4. Optionally set **Save a FreeCAD copy to** in preferences; the report shows where each copy went.

## What to expect

Supported readers are discovered from the installed Dutchman release. Fallback
filters cover Fusion, Inventor, SOLIDWORKS, CATIA, and Rhino when Dutchman is not
installed. A filter alone does not guarantee conversion support in your release.
FreeCAD's existing native-format, STEP, IGES, BREP, STL, and OBJ readers stay in use.

Some models can rebuild full feature history, some rebuild partially, and others
retain geometry only. The report distinguishes these outcomes and shows
mapped/rebuilt/total counts. Success does not guarantee verified equivalence.
Failed imports show their filename and error in the report panel, with setup
instructions when Dutchman is missing. The help prompt offers a private DM to
Dutchy on Discord first, with public GitHub issues as an alternative. Opening a
help link does not send files or reports. Console-mode imports print a short
summary instead of opening a dock.

Requires FreeCAD 1.1 or later, Python 3.9 or later, and the built-in Part,
PartDesign, and Sketcher modules. No third-party Python packages are installed.

## Downloads and privacy

Automatic downloads are disabled initially. If enabled, an import with no
available executable asks before contacting GitHub for release metadata,
checksums, and the archive for your OS/architecture. The archive must pass SHA-256
verification before installation. Missing checksums stop the download.

The addon sends no CAD files or conversion reports to GitHub. It passes your
source file to your selected local Dutchman executable; review that program's
behavior separately. See the
[privacy details](https://github.com/dutchman-cad/freecad-addon/blob/main/PRIVACY.md).

Maintained by [Dutchman CAD](mailto:hello@dutchmancad.xyz).

[Usage and installation](https://github.com/dutchman-cad/freecad-addon/blob/main/README.md)
· [Report a problem](https://github.com/dutchman-cad/freecad-addon/issues)
· [License](https://github.com/dutchman-cad/freecad-addon/blob/main/LICENSE)
