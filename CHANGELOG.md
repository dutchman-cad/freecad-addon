# Changelog

## 0.1.6

- A failed Dutchman download (no connection, interrupted transfer) now says so in plain words and points to Edit > Preferences > Dutchman, instead of showing a raw network error.
- A failed import no longer repeats the full error in the dialog and the report panel; the dialog gives the short reason.
- The report panel lists at most three notes, each shortened, instead of every note in full.
- A freshly opened file no longer shows `*` (unsaved) in its tab.

## 0.1.5

- When the download offer is turned off, the missing-Dutchman message no longer suggests downloading.

## 0.1.4

- Fit the model to the 3D view after the report panel opens, so a new import is not hidden under it.

## 0.1.3

- A failed import opens an error dialog naming the file; the report panel keeps the full error with clickable links.
- A missing Dutchman is offered as a checksum-verified download on first use (on by default), with a progress window and Cancel, or the preferences page.
- The report panel leads with a plain headline, shows the help prompt before the notes, hides history counts when there is no history, and says where the saved copy went.
- Preferences: browse buttons for the executable and the copy folder, with descriptions.
- README leads with a quick start; the custom-repository name and `file://` behaviour are explained.

## 0.1.2

- Show the source filename and error for failed imports, including a missing executable and rebuild failures.
- Replace a stale successful report when a later import fails, and offer private support from the report panel.
- Add the public maintainer contact to package metadata and support documentation.

## 0.1.0

- Import CAD files through Dutchman in FreeCAD without adding a workbench.
- Review history coverage, verification results, and conversion losses after import.
- Configure the executable, verified release downloads, and saved document copies.
