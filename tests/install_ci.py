# SPDX-License-Identifier: Apache-2.0
"""Fetch public upstream releases for CI; Dutchman uses the addon verifier."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from freecad.dutchman_freecad.binary import download_release


def main():
    tools = ROOT / ".ci-tools"
    tools.mkdir(exist_ok=True)
    download_release(tools / "bin")
    request = urllib.request.Request(
        "https://api.github.com/repos/FreeCAD/FreeCAD/releases/latest",
        headers={"User-Agent": "Dutchman-FreeCAD-CI"})
    with urllib.request.urlopen(request, timeout=120) as stream:
        release = json.load(stream)
    candidates = [asset for asset in release["assets"]
                  if asset["name"].lower().endswith(".appimage")
                  and any(arch in asset["name"].lower() for arch in ("x86_64", "x86-64"))]
    if not candidates:
        raise RuntimeError("Official FreeCAD release has no x86_64 AppImage")
    image = tools / "FreeCAD.AppImage"
    request = urllib.request.Request(candidates[0]["browser_download_url"],
                                     headers={"User-Agent": "Dutchman-FreeCAD-CI"})
    with urllib.request.urlopen(request, timeout=300) as source, image.open("wb") as target:
        shutil.copyfileobj(source, target)
    image.chmod(0o755)
    subprocess.run([str(image), "--appimage-extract"], cwd=tools, check=True,
                   stdout=subprocess.DEVNULL)
    mod = Path.home() / ".local" / "share" / "FreeCAD" / "Mod" / "Dutchman"
    mod.parent.mkdir(parents=True, exist_ok=True)
    mod.symlink_to(ROOT, target_is_directory=True)


if __name__ == "__main__":
    main()
