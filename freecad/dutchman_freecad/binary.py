# SPDX-License-Identifier: Apache-2.0
"""Resolve Dutchman and install only checksum-verified release executables."""

import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile

RELEASE_API = "https://api.github.com/repos/dutchman-cad/dutchman/releases/latest"
PARAM_GROUP = "User parameter:BaseApp/Preferences/Mod/Dutchman"


class BinaryError(RuntimeError):
    pass


class BinaryNotFound(BinaryError):
    """No usable executable was found; `declined` means the user refused a download."""

    def __init__(self, message, declined=False):
        super().__init__(message)
        self.declined = declined


class DownloadFailed(BinaryNotFound):
    """The network, not the release, failed; the user can retry or install by hand."""


def executable_name():
    return "dutchman.exe" if platform.system() == "Windows" else "dutchman"


def _executable(path):
    return bool(path and Path(path).is_file() and os.access(path, os.X_OK))


def resolve(configured="", install_dir=None, auto_download=False, confirm=None, progress=None):
    """Environment override, preferences, PATH, then managed installation.

    Automatic installation requires a GUI callback explicitly approving it.
    """
    override = os.environ.get("DUTCHMAN_BIN", "")
    if override:
        if not _executable(override):
            raise BinaryError("DUTCHMAN_BIN does not point to an executable file")
        return str(Path(override).resolve())
    if configured:
        if not _executable(configured):
            raise BinaryError("The configured Dutchman path is not executable")
        return str(Path(configured).resolve())
    found = shutil.which("dutchman")
    if found:
        return found
    if install_dir:
        managed = Path(install_dir) / executable_name()
        if _executable(managed):
            return str(managed)
    declined = False
    if auto_download and install_dir and confirm:
        if confirm():
            return str(download_release(install_dir, progress=progress))
        declined = True
    if auto_download:
        message = ("Dutchman was not found. Download it, or set the path to an existing copy, "
                   "in Edit > Preferences > Dutchman.")
    else:
        message = ("Dutchman was not found. Set the path to an existing copy, or turn on the "
                   "download offer, in Edit > Preferences > Dutchman.")
    raise BinaryNotFound(message, declined)


def _read(url, progress=None, label=""):
    """Fetch url; report (label, bytes_done, bytes_total_or_0) to progress as it arrives.

    The progress callback may raise to cancel the transfer.
    """
    request = urllib.request.Request(url, headers={"User-Agent": "Dutchman-FreeCAD/0.1.6"})
    try:
        response = urllib.request.urlopen(request, timeout=120)
    except (urllib.error.URLError, OSError) as error:
        reason = getattr(error, "reason", error)
        raise DownloadFailed(
            "Dutchman could not be downloaded ({}). Check your internet connection and try "
            "again, or install Dutchman yourself and set its path in Edit > Preferences > "
            "Dutchman.".format(reason)) from error
    with response:
        total = int(response.headers.get("Content-Length") or 0)
        chunks, done = [], 0
        if progress:
            progress(label, 0, total)
        while True:
            try:
                chunk = response.read(1 << 20)
            except OSError as error:
                raise DownloadFailed(
                    "The Dutchman download was interrupted ({}). Try again, or install it "
                    "yourself and set its path in Edit > Preferences > Dutchman."
                    .format(error)) from error
            if not chunk:
                break
            chunks.append(chunk)
            done += len(chunk)
            if progress:
                progress(label, done, total)
        return b"".join(chunks)


def select_asset(assets, system=None, machine=None):
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    arches = {"amd64": ("x86_64", "amd64"), "x86_64": ("x86_64", "amd64"),
              "arm64": ("aarch64", "arm64"), "aarch64": ("aarch64", "arm64")}
    operating_systems = {"Linux": ("linux",), "Darwin": ("darwin", "macos"),
                         "Windows": ("windows", "pc-windows")}
    if machine not in arches or system not in operating_systems:
        raise BinaryError("No supported Dutchman release for this OS/architecture")
    matches = []
    for asset in assets:
        name = asset["name"].lower()
        if (any(a in name for a in arches[machine])
                and any(s in name for s in operating_systems[system])
                and name.endswith((".tar.gz", ".tgz", ".tar.xz", ".zip"))):
            matches.append(asset)
    if not matches:
        raise BinaryError("No Dutchman release archive for this OS/architecture")
    # Prefer the conventional glibc build over musl when both are provided.
    return sorted(matches, key=lambda a: ("musl" in a["name"], a["name"]))[0]


def _expected_checksum(contents, archive_name, single=False):
    for line in contents.decode("utf-8").splitlines():
        fields = line.strip().split(maxsplit=1)
        if not fields or not re.fullmatch(r"[0-9a-fA-F]{64}", fields[0]):
            continue
        if len(fields) == 1 and single:
            return fields[0].lower()
        if len(fields) == 2 and fields[1].lstrip("*").removeprefix("./") == archive_name:
            return fields[0].lower()
    raise BinaryError("Release checksum file does not contain the selected archive")


def _unpack_executable(data, archive_name):
    """Read only the regular executable member; never extract archive paths."""
    expected = executable_name()
    if archive_name.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = [m for m in archive.infolist() if Path(m.filename).name == expected
                       and not m.is_dir() and not stat.S_ISLNK(m.external_attr >> 16)]
            if len(members) == 1:
                return archive.read(members[0])
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
            members = [m for m in archive.getmembers()
                       if Path(m.name).name == expected and m.isfile()]
            if len(members) == 1:
                with archive.extractfile(members[0]) as stream:
                    return stream.read()
    raise BinaryError("Release archive must contain exactly one regular Dutchman executable")


def download_release(install_dir, api_url=RELEASE_API, system=None, machine=None, progress=None):
    """Verify the archive before unpacking; atomically publish the executable."""
    release = json.loads(_read(api_url, progress, "Looking up the latest Dutchman release"))
    assets = release.get("assets", [])
    archive = select_asset(assets, system, machine)
    checksum_assets = [a for a in assets if a["name"].upper() == "SHA256SUMS"]
    if not checksum_assets:
        checksum_assets = sorted(
            [a for a in assets if a["name"].lower().endswith(".sha256")],
            key=lambda a: a["name"] != archive["name"] + ".sha256")
    if not checksum_assets:
        raise BinaryError("Release has no SHA256SUMS or archive .sha256 file; download refused")
    expected = None
    for checksum_asset in checksum_assets:
        try:
            expected = _expected_checksum(
                _read(checksum_asset["browser_download_url"], progress, "Downloading checksums"),
                archive["name"],
                checksum_asset["name"] == archive["name"] + ".sha256")
            break
        except BinaryError:
            continue
    if expected is None:
        raise BinaryError("Release checksum file does not contain the selected archive")
    data = _read(archive["browser_download_url"], progress, "Downloading Dutchman")
    if hashlib.sha256(data).hexdigest() != expected:
        raise BinaryError("Dutchman archive SHA-256 checksum mismatch; download refused")
    payload = _unpack_executable(data, archive["name"])
    destination = Path(install_dir)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / executable_name()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
        temporary.chmod(0o755)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target


def resolve_freecad():
    import FreeCAD
    params = FreeCAD.ParamGet(PARAM_GROUP)
    from .gui import confirm_download, download_progress
    progress = download_progress() if FreeCAD.GuiUp else None
    try:
        return resolve(params.GetString("BinaryPath", ""),
                       Path(FreeCAD.getUserAppDataDir()) / "Dutchman" / "bin",
                       params.GetBool("AutoDownload", True),
                       confirm_download if FreeCAD.GuiUp else None, progress)
    finally:
        if progress:
            progress.close()
