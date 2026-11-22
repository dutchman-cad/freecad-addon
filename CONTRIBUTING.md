# Contributing

Report reproducible problems through the repository's issue tracker. Include
FreeCAD and Dutchman versions, the import format, and relevant report entries.
Use synthetic examples that you have permission to share; remove private names,
paths, and identifiers before posting. Send security concerns through the process
in [SECURITY.md](SECURITY.md).

Use Python 3 and FreeCAD's PySide wrapper. Keep conversion in Dutchman and this
addon focused on integration. Place runtime code under `freecad/dutchman_freecad`
and avoid modifying Python's import path, other workbenches, menus, or toolbars.
Use standard-library helpers where possible and declare necessary built-in
FreeCAD module dependencies in `package.xml`. Do not vendor Python packages.

Run `python3 -m unittest discover -s tests -p 'test_*.py' -v` for unit coverage.
Run the synthetic FreeCAD import test described in README when changing import
behavior. Update the user documentation and changelog with behavior changes.

Before requesting Addon Index inclusion, gather user feedback, confirm current
FreeCAD compatibility, and satisfy the Academy review checklist. Maintain a
stable published branch, increment the manifest version and date for every
published change, and tag reviewed releases. The initial manifest tracks `main`;
use a separate development branch for ongoing work before indexing. Repository
topics should include `freecad`, `addon`, `import`, `parametric`, and `python`.
