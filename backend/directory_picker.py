# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: directory_picker.py
# purpose: Host-side directory selection
# ---------------------------------------------------------------------------

import base64
from pathlib import Path
import subprocess
import sys


class DirectoryPickerUnavailable(RuntimeError):
    pass


def pick_directory(_initial_path: str | None = None) -> str | None:
    """Open the host's native directory picker and return its selected path."""
    if sys.platform != 'win32':
        raise DirectoryPickerUnavailable('Host directory picker is currently available on Windows only')
    script = r"""
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$shell = New-Object -ComObject Shell.Application
$folder = $shell.BrowseForFolder(0, 'Select folder', 0)
if ($null -ne $folder) { [Console]::Out.Write($folder.Self.Path) }
"""
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    try:
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-STA', '-EncodedCommand', encoded],
            capture_output=True, text=True, encoding='utf-8', check=False)
    except OSError as error:
        raise DirectoryPickerUnavailable(str(error)) from error
    if result.returncode != 0:
        raise DirectoryPickerUnavailable(result.stderr.strip() or 'Directory picker failed')
    selected = result.stdout.strip()
    return str(Path(selected).resolve(strict=False)) if selected else None
