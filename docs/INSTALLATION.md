<!-- -------------------------------------------------------------------------
system: ModelArchivist
file: INSTALLATION.md
purpose: Installation and first-run setup guide
---------------------------------------------------------------------------- -->

# Installation and setup

Model Archivist requires Python 3.12 or newer. It can run inside ComfyUI or as a
standalone application.

## Install it in ComfyUI

Once Model Archivist is published in the Comfy Registry, install it through
ComfyUI Manager and restart ComfyUI. Manager installs the Python dependencies
listed in `requirements.txt` into the Python environment used by ComfyUI.

For a manual installation before Registry publication:

1. Clone or download the repository into ComfyUI's `custom_nodes` directory. The
   resulting directory should be named `ComfyUI-ModelArchivist`.
2. Install `requirements.txt` with the same Python interpreter that starts
   ComfyUI.
3. Restart ComfyUI.

For the Windows portable build, run this from the portable installation root:

```powershell
git clone https://github.com/tumbislav/ComfyUI-ModelArchivist.git ComfyUI/custom_nodes/ComfyUI-ModelArchivist
python_embeded/python.exe -m pip install -r ComfyUI/custom_nodes/ComfyUI-ModelArchivist/requirements.txt
```

For a venv-based ComfyUI installation, activate its environment first and run:

```shell
git clone https://github.com/tumbislav/ComfyUI-ModelArchivist.git ComfyUI/custom_nodes/ComfyUI-ModelArchivist
python -m pip install -r ComfyUI/custom_nodes/ComfyUI-ModelArchivist/requirements.txt
```

After restart, use the Model Archivist button in ComfyUI's action bar. It opens
the application under `/model-archivist/` on the same address as ComfyUI. Model
Archivist does not add execution nodes to the workflow editor.

In ComfyUI mode, model types, working folders, and accepted file extensions come
from ComfyUI's live configuration, including `extra_model_paths.yaml`. Model
Archivist stores its database and log in:

```text
<ComfyUI user directory>/_archivist/
```

The log records only the current application run. It is cleared when Model
Archivist starts.

## Install the standalone application

Clone the repository, create a virtual environment, and install the project. For
example, on Windows:

```powershell
git clone https://github.com/tumbislav/ComfyUI-ModelArchivist.git
cd ComfyUI-ModelArchivist
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install .
.venv/Scripts/python.exe -m backend
```

On Linux or macOS:

```shell
git clone https://github.com/tumbislav/ComfyUI-ModelArchivist.git
cd ComfyUI-ModelArchivist
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install .
.venv/bin/python -m backend
```

The application opens in your default browser. By default it listens only on
`127.0.0.1` at port `5173`.

### Choose another configuration file

The root `config.toml` contains only the settings needed before the repository
database can be opened: database path, web server address, logging, and filesystem
permissions. Start the
standalone application with another configuration file by passing its full path:

```powershell
.venv/Scripts/python.exe -m backend --config C:\path\to\config.toml
```

The `{$app}` placeholder in the supplied configuration means the repository or
installed application directory. Model types, extensions, repository behavior,
and working/archive mappings are configured in the application and stored in its
SQLite database.

## Filesystem permissions

On the first start without a `[filesystem]` section, Archivist appends one to the
configuration file it loaded, preserving the other settings and comments:

- Standalone: both working and archive roots default to the operating-system
  user's home directory (`%USERPROFILE%` on Windows, `$HOME` on Unix).
- ComfyUI: working roots default to ComfyUI's `models` directory and registered
  extra model paths; archive roots default to that operating-system user's home
  directory. Model-save paths injected below ComfyUI's output directory are excluded.
  Two or more distinct extra model folders with the same immediate parent grant
  that parent instead. This consolidation runs once and never climbs further up
  the directory tree; an extra folder without a sibling keeps its own root.
- Exclusions initially contain no paths.

Initialization happens only when the entire section is absent. Explicit empty root
lists deny all access for that role. Invalid or incomplete policy settings stop
startup rather than restoring permissive defaults. The configuration file must be
writable for this one-time initialization; alternatively, add the section yourself.

Edit the file on the server and restart Archivist to change permissions. For example
(replace these paths with your actual directories):

```toml
[filesystem]
working_roots = ['C:\ComfyUI\models', 'C:\ComfyUI\user\default\workflows']
archive_roots = ['D:\ModelArchive', '\\nas\models\archive']
exclusions = ['C:\ComfyUI\models\private', 'D:\ModelArchive\backups']
```

Use absolute literal paths. TOML single-quoted strings are useful for Windows
backslashes. Unix paths such as `/home/alex/models` or `/mnt/archive` work too.
Variables, `~`, `{$app}`, globs, and regular expressions are not expanded here.
Exclusions apply recursively and override every allowed root, including nested
roots. The settings screen shows the active permissions and configuration filename.

ComfyUI-discovered paths do **not** grant permission automatically. Explicitly add
extra model directories and the ComfyUI workflow directory to `working_roots` when
needed. Choose archive locations within the archive roots. User-defined types follow
the same rules. Model examples use the sibling `examples` directory; permit that
location too if your allowed root is narrower than its parent.

Symbolic links, junctions, and files with multiple hard links are blocked, even if
their other locations are permitted. Use actual directories and independent file
copies. Mounted volumes and network shares are supported as explicitly allowed
roots; a scan cannot silently cross into a mounted volume below another root.
File systems that cannot provide the required link information are denied.

After upgrading an existing installation, blocked mappings are preserved and
reported in Settings, and the repository becomes read-only. Amend the policy on
disk or correct the mappings, then restart as needed and rescan. Files are not moved
or deleted by this migration. A blocked scan reports an incomplete result and
preserves the existing index instead of deleting unseen records.

Use the browse button beside an editable location field to open the in-app directory
browser. Its tree starts at the permitted roots for that field (working or archive).
Expand a folder or open a subfolder to load its immediate children. The current path
is shown above the panels; Up stops at the permitted root. Existing allowed paths
open as the initial selection. Missing, inaccessible, or blocked paths show an error.

Choose **Use this folder** to fill the field, then save Settings separately. Cancel
or Escape leaves the field unchanged. Arrow keys navigate the tree; Enter opens the
focused folder. Links and excluded entries are hidden, with a notice when entries
were omitted. The browser does not create, rename, or delete directories. Manual
absolute path entry remains available, including for directories not yet created.
ComfyUI-owned working locations remain non-editable.

## Complete the first-run setup

A new database starts in setup mode and does not scan until the required folder
mappings have been saved.

1. Open **Settings**.
2. Under **Models**, pair every working model location with an archive location.
   In ComfyUI mode, the working locations and extensions are supplied by ComfyUI
   and cannot be changed in Model Archivist.
3. Under **Workflows**, choose the archive folder. In standalone mode, also choose
   the working folder.
4. Add any **User types** you want to manage. This step is optional.
5. Save the settings and run a scan.

Each working directory must have one archive counterpart. Do not reuse the same
directory in more than one pair. The same relative path is used on both sides, so
an object can move between working and archive storage without losing its place.

In standalone mode, each model type and workflows have one working/archive pair.
ComfyUI's `extra_model_paths.yaml` is used only in ComfyUI mode.

## Startup and browser preferences

Standalone startup opens a browser tab with access for the current backend run.
The launch URL briefly contains a secret after `#`; the frontend removes it and
keeps it in that tab's session storage. Do not share the launch URL. Refreshing the
tab retains access, but a bare bookmarked URL in a new tab does not grant access.
To regain access after closing the tab or restarting the backend, restart the
standalone application and use the tab it opens. If browser session storage is
blocked, access lasts only until that page is refreshed. The session is not a
remote-login mechanism; keep standalone binding at its default `127.0.0.1`.

In ComfyUI mode, open Archivist using its action-bar button so the selected Comfy
profile is carried into the new tab. Host middleware still applies. Named profiles
alone do not authenticate users or isolate the shared Archivist repository.
The private Archivist port always listens on loopback and cannot be used directly
without the server-only proxy credential.

**Settings → General** contains preferences stored in the current browser:

- **Always run a full scan at startup** requests one scan after each backend
  start. It is enabled by default.
- **Remember last open tab** restores the last main tab.
- **Remember last used filters** restores table filters and their enabled state.

Opening another tab or refreshing the page does not start another startup scan
for the same backend run. You can always start a manual scan from the header.

## Update the application

When installed through ComfyUI Manager, use Manager's update function and restart
ComfyUI.

For a manual Git installation, stop the application, pull the new version, update
its dependencies with the same Python interpreter, and restart it. Keep the
database and `_archivist` runtime directory in place; schema migrations run when
the application starts.

For standalone installations made with `pip install .`, reinstall the project
after pulling an update:

```powershell
git pull --ff-only
.venv/Scripts/python.exe -m pip install .
```
