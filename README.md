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

The backend initializes without scanning. General settings contains “Always run a full
scan at startup”, enabled by default and saved in this browser's local storage. When
enabled, opening Archivist requests one startup scan per backend run; refreshing or
opening another tab does not repeat it. Disabling it opens the existing repository
immediately. Manual scans remain available from the header. Setup mode and read-only
repositories do not request startup scans.

The Repository button shows “Wait...” until startup completes. All frontend API
requests have a 3000 ms timeout, including their response bodies. A timeout or lost
connection changes the button to “Server...”; its dialog reports that the server is
not responding. Background polling continues and restores normal status when the
server responds again.

The Repository dialog shows counts by location for models, workflows, user-defined
objects, and collections. Working, archive, and synchronized counts are disjoint;
mixed or mismatched locations remain included in the total. Errors count objects with
errors, and collections with errors among their transitive members. Collections have
statistics only. The other sections can refresh independently, with statistics updated
every 500 ms while the dialog is open. Only one long-running operation can run at once.

Selective scans use `/scan?scope=models`, `scope=workflows`, or `scope=user_objects`.
An optional `type_id` selects a model type by name or a user type by ID, ready for
individual-type actions in Settings. A JSON body with `type_ids` selects a batch of
model or user types. Scanning and cleanup are both restricted to the
selected scope; other types and their records are preserved.

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

## Tags

New tags are case-sensitive Python-style Unicode names, extended to allow leading ASCII
digits (0–9), ordinary spaces after the first character, and internal ASCII colons (`:`)
and dashes (`-`). Colons and dashes cannot start or end a tag; their Unicode equivalents
are not accepted. Python keywords are allowed. Leading spaces, tabs, newlines,
and other punctuation outside the identifier character set are invalid. Trailing spaces are
removed and new values are normalized to Unicode NFKC. Existing imported tags remain
available until explicitly removed or remapped.

The header's tag editor shows direct usage counts for models, workflows, user-defined
objects, and collections. Remapping applies all substitutions simultaneously: `A → B`
and `B → C` move original A assignments to B and original B assignments to C. Merging
tags removes duplicate assignments. Blank and invalid targets are skipped.

Remapping updates SQLite, model `.archivist.json` sidecars, and workflow JSON tag fields.
Third-party sidecars are untouched. Affected objects and files are checked before
writing; read-only objects block the batch. Execution failures roll back the database
and attempt to restore files already written, reporting any restoration failures.

# Pre-release testing

Before publishing Model Archivist:

- Set up a Linux virtual machine and perform thorough end-to-end user testing,
  including standalone operation, filesystem permissions, network shares, directory
  selection, scanning, synchronization, and moves.
- Determine a practical macOS testing strategy. Automated tests can cover much of the
  backend, but the native directory picker and full user workflow still require testing
  on actual macOS hardware or a legitimately hosted macOS environment.

# Deferred work

Items deliberately postponed during the current implementation pass:

- Add internationalization and localization support once interface text stabilizes.
- Complete visual/CSS cleanup and final icon coverage.
- Rebuild the Alembic baseline after the pre-release database schema stabilizes.

# Roadmap V2

Optional, unconfirmed extensions to be considered for V2:

* Support for models packaged as a Huggingface directory rather than a single file
* Separate workspaces per user
* Extend model metadata
  * Retrieve metadata from Civitai and Huggingface
  * Retrieve metadata from LoraManager and/or rgthree sidecars
* Project-type collections that set up the entire user's environment:
  * collection defines the object types that it cares about
  * when brought to working set, it archives all objects that are not part of it
  * automatically adds new working set objects that match pre-defined criteria, e.g. a regexp
  * runs a set-up script (???)
* Add a base model attribute to models

## Scanning from Settings

Models and User types offer per-type Save and Save and scan buttons. For a saved,
unchanged type, Save and scan becomes Refresh. The tab-level Save and scan saves
all pending changes in that tab and scans only its changed types. Workflows has the
same Save and scan/Refresh action for its single configuration. Saving one type
preserves unsaved edits to other types and tabs. While an operation is running,
configuration editing and additional scans are blocked; Settings tabs and Close
remain available.

## Column filters

Click a filterable column header to edit its filter. Name columns use a case-insensitive
literal prefix; categorical columns offer checkboxes including `(blank)`; indicator
columns offer all, present, or absent. Apply commits the draft. Clicking the header
again, pressing Escape, or clicking outside cancels it. Clear removes that column's
filter. Filters combine across columns, and the action-bar toggle suspends them without
losing their values. Choices are drawn from the complete loaded table, including rows
currently filtered out. Purpose columns have no filter.

General settings offers “Remember last used filters”, off by default. When enabled,
all four tabs' filters and their enabled states are stored in this browser. Otherwise,
filters are retained only while the app remains open. Collections has no row selection
or multi-editor. User types supports multi-editing tags, collection membership, and
working/archive deployment. Bulk user-object changes run sequentially and report how
many objects completed if an operation fails; completed changes are preserved.
