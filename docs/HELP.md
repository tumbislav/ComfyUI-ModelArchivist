<!-- -------------------------------------------------------------------------
system: ModelArchivist
file: HELP.md
purpose: User guide and documentation entry point
---------------------------------------------------------------------------- -->

# Model Archivist

You have dozens of checkpoints, hundreds of LoRAs, a pile of workflows, and
perhaps training data, wildcards, pose references, prompt collections, samples,
and works in progress. Some of them belong on fast storage where ComfyUI can use
them. Others can wait in an archive until you need them again.

Model Archivist helps you keep track of all of it.

Originally intended as an extension to LoraManager, Model Archivist grew into a
separate application because it solves a different problem: organizing complete
working and archival sets rather than managing model metadata alone.

## What it does

Model Archivist keeps a catalog of your models, workflows, and other files. For
each kind of object, you give it a **working folder** and an **archive folder**.
The working folder is where ComfyUI or another program expects to find the files.
The archive can be on slower or less expensive storage.

You can then:

- see what is in the working set, what is archived, and what exists in both;
- move an object between working and archive storage without losing track of it;
- keep working and archival copies synchronized;
- add names, descriptions, base-model information, and tags;
- organize related items into collections; and
- move or synchronize an entire collection at once.

A collection can represent a complete working set for a project. For example, it
can contain a checkpoint, several LoRAs, workflows, wildcards, and reference
images. Bringing the collection into the working set makes all of those parts
available together; archiving it moves them out together when the project is
finished.

Model Archivist does not store your large files in its database. It catalogs
them and performs requested file operations between the folders you configure.

## How to set it up

See [Installation and setup](INSTALLATION.md) for ComfyUI and standalone
installation instructions, the first-run folder setup, and update notes.

## How to use it

### Learn the main screen

Use the tabs in the header to switch among **Models**, **Workflows**, your
user-defined object types, and **Collections**.

The remaining header controls let you:

- run a full repository scan;
- open the repository summary;
- edit and remap tags;
- open Settings; and
- switch between light and dark themes.

The Repository button also shows the current long-running operation. It reads
**Wait...** while the application starts and changes to **Scanning...**,
**Moving...**, or **Syncing...** while work is in progress. If the backend stops
responding, it reads **Server...** and opens a dialog with connection details.

### Scan your folders

Run a scan after adding, removing, renaming, or changing files outside Model
Archivist. Use the scan button in the header to scan the complete repository.

For a smaller scan, open **Settings** and select **Models**, **Workflows**, or
**User types**. Each saved type has a **Refresh** action. After changing a type,
the same action becomes **Save & scan** and scans that type after saving it.

Normal scans reuse trustworthy stored hashes where possible and hash a model's
weights when no usable stored hash exists.

### Find and select objects

Each main tab presents a table. Click a row to open its details in the sidebar.
Models, workflows, and user-defined objects can also be selected for bulk edits.

Click a filterable column heading to filter that column. Text filters match the
start of a name without regard to case. Other columns offer choices such as
location, tags, collections, or error state. Filters from different columns are
combined. The filter button above the table temporarily switches all filters on
or off without discarding them.

In **Settings → General**, enable **Remember last used filters** to retain them in
this browser. You can also remember the last open tab.

### Edit an object

Select a model, workflow, or user-defined object to open its details. Depending
on the object type, you can edit its display information, relative folder, tags,
base model, and collection membership. Save metadata changes before starting a
file operation.

Use the action buttons at the bottom of the details panel:

- **To working set** moves the object and its associated files to the configured
  working folder.
- **To archive** moves them to the configured archive folder.
- **Sync** copies the working version to the archive when a working version is
  present. If the object exists only in the archive, it copies the archived
  version to the working set. Files missing from the source are removed from the
  destination copy so the two sides match.

When an object exists on both sides but the copies do not agree, Model Archivist
marks it as mismatched. Synchronize it before attempting other changes.

### Organize with tags

Add tags in an object's details panel. Tags are shared across models, workflows,
user-defined objects, and collections.

A new tag may start with a letter, an underscore, or an ASCII digit. It can use
Unicode name characters and ordinary spaces, with an ASCII colon or dash inside
the tag. Colons and dashes cannot be the first or last character. Tags are
case-sensitive.

Open the tag editor from the header to see where tags are used, remove unused
tags, or remap one tag to another. Remapping changes all selected assignments at
once and can merge several tags into one. It also updates Model Archivist model
sidecars and workflow metadata where applicable.

### Create and use collections

Open **Collections** and create a collection with a name and optional purpose.
Add models, workflows, user-defined objects, or other collections as members.
Collections may contain other collections, but Model Archivist prevents cycles.

Use **To working set**, **To archive**, or **Sync** in the collection details to
apply that action to all transitive members. This is the quickest way to bring a
complete project environment online or put it away again.

Removing something from a collection changes only its membership. It does not
delete or move the underlying files.

### Add other kinds of files

Use **Settings → User types → Add type** to catalog files beyond models and
workflows. Examples include datasets, training sets, wildcards, ControlNet
references, groups of outputs, or any other project assets you want to move as a
unit.

Each user type defines what one object means. A file type treats every matching
file as a separate object, even when the files are stored in subdirectories. A
folder type treats a directory and everything below it as one object. Folder
objects cannot overlap or be nested inside one another.

Give the type a name, a short name for its navigation tab, an icon, and an
optional description. Choose its working and archive folders and, for a file
type, the accepted filename extensions. After saving and scanning the type, its
objects appear in their own main-screen tab. From there they can be tagged, added
to collections, moved between working and archive storage, or synchronized just
like models and workflows.

Deleting a user-defined type removes its objects from the catalog and from
collections. It does not delete the files themselves.

The **size limit** is a safety boundary for each individual object. A mistakenly
chosen folder can contain far more data than intended, and a folder object may
represent an entire directory tree. The limit stops Model Archivist from
cataloging and later copying or synchronizing such an unexpectedly large object.
The default is 10 MiB and can be raised for types that are deliberately larger.
Objects over the limit are skipped during their first scan. If an object already
in the catalog later grows beyond the limit, it remains visible but becomes
read-only until you raise the limit and scan it successfully.

Enable **Small object type** when every object is at most 1 MiB. This fixes the
limit at 1 MiB and allows operations on one object to complete immediately;
larger operations run as background repository operations with progress reporting.

### Check repository health

Open **Repository** to see counts for working, archived, synchronized, and
errored objects. Models, workflows, and user-defined types can be refreshed
independently from this dialog.

An **E** in a table row means that Model Archivist found a problem. Select the row
to see the localized error description. Common causes include a missing file, an
unreadable folder, duplicate copies, or working and archive copies stored at
different relative paths.

If any configured model or workflow folder is inaccessible, Model Archivist
switches the repository to read-only mode. Restore access to the folder and scan
again before attempting file operations.

## About the librarians

There is a tiny image at the left of the menu bar. Click it and meet one of the
librarians. In the About dialog, use the Left and Right arrow keys or click the
outer edges of the image to browse. Click the center of the image to open the
full-size illustration in a new browser tab.

_The full story of the librarians will be added here._

## How you can help

### Improve a translation

The non-English text includes machine translations. Some will need corrections.
You can review an existing language or add a new one by following the
[locale catalog guide](../frontend/src/lib/locales/README.md).

If you are not comfortable preparing a pull request, describe the correction in
[GitHub Discussions](https://github.com/tumbislav/ComfyUI-ModelArchivist/discussions).

### Introduce a new librarian

New librarians need an image and a short caption or story. Start a
[Discussion](https://github.com/tumbislav/ComfyUI-ModelArchivist/discussions) with
the proposed material and its source or licensing information.

### Suggest an idea or report a problem

Use [GitHub Discussions](https://github.com/tumbislav/ComfyUI-ModelArchivist/discussions)
for ideas, questions, and early proposals. Use
[GitHub Issues](https://github.com/tumbislav/ComfyUI-ModelArchivist/issues) for a
specific reproducible problem.

When reporting a problem, include your operating system, whether you use the
ComfyUI or standalone version, what you did, what you expected, and what happened.
Remove private paths or other sensitive information from logs before attaching
them.

### Contribute code or documentation

Fork the repository, make one focused change, run the relevant checks described
in [README.md](../README.md), and open a pull request. It is a good idea to discuss
larger features before implementing them.

## Roadmap

See the [Model Archivist roadmap](ROADMAP.md) for release work, planned cleanup,
and ideas being considered for later versions. New proposals are welcome in
[GitHub Discussions](https://github.com/tumbislav/ComfyUI-ModelArchivist/discussions).

## Filesystem access restrictions

Location fields accept absolute paths on the server. Settings shows the permitted
working/archive roots, excluded subtrees, and any blocked configured mappings.
Permissions are edited in `config.toml` on disk and take effect after a restart;
the browser cannot grant itself access. See the
[filesystem setup guide](INSTALLATION.md#filesystem-permissions) for defaults and examples.

Links and junctions are blocked. Files with multiple hard links are also blocked;
use independent copies if you want Archivist to manage them. Network shares and
mounted volumes can be allowed explicitly. Existing mappings are retained when
blocked, and the repository becomes read-only until the settings are corrected.
The browse button beside editable location fields opens the server directory picker.
Expand permitted roots in the left tree or open subfolders in the right panel.
**Use this folder** fills the field; save Settings to apply the change. Cancel or
Escape leaves the field unchanged. Arrow keys navigate the tree and Enter opens a
folder. Only immediate children load, and Up never goes beyond a permitted root.
Blocked entries are hidden with an explanatory notice. You can still type a path;
the picker selects existing directories and does not create or modify them.
