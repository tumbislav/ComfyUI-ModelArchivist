# Model Archivist
What do you do when the number of models in your ComfyUI setup becomes unmanageable and your drop-downs extend over the edge of the screen? You off-load those that you're not using to a separate drive, of course. But then you have to keep track of those that you've moved and make sure you always have the set that you need.

This is the tool that lets you keep the chaos under control.

# Configuration and operating modes
The file `config.toml` is typically located in the root folder. It contains only the
bootstrap settings required before the repository database can be opened: the SQLite
database path, web server settings, and logging settings. Repository behavior, model
types, accepted extensions, and working/archive location mappings are stored in SQLite.
A new database starts in setup mode and is not scanned until the required mappings have
been saved.

In standalone mode, Archivist manages the working locations and permits exactly one
working/archive pair for each model type and one pair for workflows. ComfyUI's
`extra_model_paths.yaml` mechanism is deliberately not supported in standalone mode.

When installed as a ComfyUI custom node, Archivist discovers model working directories
and accepted extensions through ComfyUI's live `folder_paths` registry, including extra
model paths, and discovers workflows below the ComfyUI user directory. Those working
paths remain owned by ComfyUI; Archivist stores only their archive mappings and its own
display settings. A ComfyUI action-bar button opens `/model-archivist/` on the ComfyUI
origin. ComfyUI proxies that path to Archivist's internal FastAPI server, so browser
traffic uses the same host and port as ComfyUI. No ComfyUI execution nodes are registered.
Mutable embedded runtime data is kept outside the installed custom-node directory, in
`<ComfyUI user directory>/_archivist/`. This directory contains the SQLite database and
log file. Standalone mode continues to use the paths specified in `config.toml`.

# Assumptions

- ModelArchivist is a single-user application using SQLite.
- If any configured model or workflow folder is inaccessible, the application runs read-only and does not scan files.
- Every configured working directory has exactly one archive counterpart, and neither directory may be reused in another pair.
- A model or workflow has at most one working component set and one archive component set. Missing sides have no component set; their prospective paths are derived from the configured pair.
- A workflow is identified by a UUID in its top-level `id` field. JSON files without a usable UUID are ignored.
- Workflow IDs uniquely identify one relative filename across working and archive storage.
- A model is identified by the SHA-256 hash of its main weights file.
- Normal scans trust a usable cached SHA-256 from Archivist or LoraManager metadata and hash weights only when no usable cached hash exists.
- User-requested rehash scans calculate hashes from every weights file, including archived files on slow storage.
- The risk of stale cached hashes and files changing during a scan is accepted. Users can request a manual rescan or rehash.
- Other applications may rename files in the working set. The working filename is authoritative and metadata can be updated later.
- Invalid third-party metadata is treated like an unreadable sidecar. Third-party and Archivist metadata are not reconciled.
- Orphaned sidecars and orphaned example directories are ignored.

## User-defined types

User-defined types (UDTs) extend the archive beyond models and workflows. Intended uses
include datasets (either directory trees or individual Parquet files), training sets that
are archived between sessions, wildcard files used by ComfyUI workflows, ControlNet
reference files, and groups of outputs that together form a single opus.

A user-defined type contains user-defined objects. Its definition has a unique name, a
short navigation name of at most eight characters, a
file-or-folder class, optional accepted filename extensions for file types, paired
working and archive locations, an icon, a purpose, and a configurable hard object-size
limit initially set to 10 MB. File objects may be stored in nested relative directories.
A folder and its complete recursive contents form one object. UDT metadata is stored
only in the database; file contents are not inspected to verify their claimed format.
Folder objects may neither overlap nor nest.

Synchronization mirrors the selected object: matching files are overwritten and
destination entries absent from the source are removed. Filesystem failures are reported
as warnings rather than aborting the complete multi-object operation, but an incomplete
object is not marked synchronized and a move does not delete its source. An object over
its type's size limit is omitted by initial discovery, and its move or synchronization
fails with a warning instructing the user to increase the limit manually. A previously
known object that grows beyond the limit remains in the database and its collections,
but is marked stale and treated as read-only until a later scan succeeds. A small object
has a maximum size of 1 MiB, and operations on an individual small object are synchronous.

Type definitions may be deleted after two explicit confirmations; their objects are
removed from every collection, but files and directories on disk remain untouched.
Changing a populated type between file and folder class is prohibited.
