<!-- -------------------------------------------------------------------------
system: ModelArchivist
file: HELP.md
purpose: User guide and documentation entry point
---------------------------------------------------------------------------- -->

# Model Archivist

You have dozens of checkpoints, hundreds of LoRAs, a pile of workflows, training data, wildcards, pose 
references, prompt collections, samples, works in progress. Some of that stuff belongs on fast storage so
ComfyUI, Kohya, Musubi and whatever other tool you are using can get at it quickly. The rest
belongs in an archive, from which it can be quickly moved to its working location. Moving all those files
to where they are needed, not forgetting anything and keeping things tidy remains a pile of work that
could better be user actually doing something creative.

Hence, Model Archivist. It won't change you into an organizing genius. The author can attest to that from his
own experience. But it will help.

Originally, this was meant to be a fork of LoraManager (which you should be using, it's great), but it quickly 
became clear that we're solving a very different problem, so Archivist became an independent application.

> [!note]
> About using AI to develop this: yes, I let Codex write a lot of the code. I even let it write the the first draft of
> this help file. The em-dashes, however, are all mine, because, dammit,  proper punctuation matters!

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
- most importantly, **organize related items into collections** and handle entire collections with one click.

A collection can represent a complete working set for a project. Depending on what you are doing, it
could contain a checkpoint, several LoRAs, two or three workflows, a prompt collection, a dozen controlnet 
references, or it could be a training dataset with configuration scripts and intermediate builds. Anything, really.

Bringing the collection into the working set makes all of those parts available together; archiving it moves them 
out together to give you room to work with something else.

Important to understand: Model Archivist does not store your files in its database. It catalogs
them and moves them (very carefully), but it doesn't prevent you from moving files on your own. This
means that its catalog can get out of sync. Depending on how you set things up, this can happen every time you
run a Comfy workflow. This isn't a problem, re-scanning your folders is quick and painless. More on that later.

## How to set it up

Model Archivist can be set up in one of two ways: as a standalone application or as a ComfyUI 
extension. See [Installation and setup](INSTALLATION.md) for instructions how to do one or the other.

On first run, Archivist doesn't yet know where you want to put your archive. If you're running it
from ComfyUI, it knows where Comfy expects its models and workflows to be, but if it's standalone, it
doesn't even know that. So you're going to see a friendly splash screen that will give you a starting
hint on how to set things ups. This won't open again, unless you do something drastic like deleting the
database.

## How to use it

### Meet the nav bar

The central part contains the tabs: **Models**, **Workflows**, your user-defined types, and **Collections**. This 
is where you select what you're currently working on. User-defined types is actually a tab of tabs—you can
pick any of the types you defined, or define another one.

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

## About and the librarians

The tiny image at the left of the menu bar opens the About box and lets you meet [the librarians](LIBRARIANS.md).

## How you can help

### Add or improve a translation

Read more about it [here](LOCALIZATION.md).

### Introduce a new librarian

Introduce a new [librarian](LIBRARIANS.md) to us.

### Suggest an idea or report a problem

Use [GitHub Discussions](https://github.com/tumbislav/ComfyUI-ModelArchivist/discussions) for ideas, questions, and early proposals. Use [GitHub Issues](https://github.com/tumbislav/ComfyUI-ModelArchivist/issues) for a
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

The current  [development roadmap](ROADMAP.md) is just a collection of ideas and cleanup work that 
has already been identified. New proposals are welcome in [GitHub Discussions](https://github.com/tumbislav/ComfyUI-ModelArchivist/discussions).

## Filesystem access restrictions

Location fields accept absolute paths on the server. Settings shows the permitted
working/archive roots, excluded subtrees, and any blocked configured mappings.
Permissions are edited in `config.toml` on disk and take effect after a restart;
the browser cannot grant itself access. See the
[filesystem setup guide](INSTALLATION.md#filesystem-permissions) for defaults and examples.

In ComfyUI mode, initial working permissions include every directory registered
in ComfyUI's live folder registry. Other custom nodes can register their own
directories there, so their resource folders may also appear in the generated
filesystem configuration. This is expected; review `config.toml` after the
first startup if you want a narrower boundary.

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
