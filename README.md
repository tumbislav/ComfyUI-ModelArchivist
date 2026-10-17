<!-- -------------------------------------------------------------------------
system: ModelArchivist
file: README.md
purpose: Project overview and contributor reference
---------------------------------------------------------------------------- -->

# Model Archivist

What do you do when the number of models in your ComfyUI setup becomes
unmanageable and your drop-downs extend over the edge of the screen? You move
the models you are not using to separate storage. Then you need to remember what
you moved and restore the complete set needed by each project. 

Model Archivist helps keep that chaos under control. It catalogs models,
workflows, and user-defined files; moves them between working and archive
storage; and groups them into collections that can be moved as a unit.

- [User guide](docs/HELP.md)
- [Installation and setup](docs/INSTALLATION.md)
- [Roadmap](docs/ROADMAP.md)
- [Development and technical reference](docs/DEVELOPMENT.md)

# Configuration and operating modes
The file `config.toml` is typically located in the root folder. It contains the
minimal settings needed to start: the database path, web server settings, 
logging settings, and disk-owned filesystem permissions. Repository behavior, model
types, accepted extensions, and working/archive location mappings are stored in the database.
A new database starts in setup mode and is not scanned until at least one complete
model, workflow, or user-defined type mapping has been saved. Each category is optional.
Scans visit only configured mappings, and cleanup preserves records outside the scan's
configured targets. Unmapped ComfyUI discoveries do not affect filesystem readiness.

By default, the backend initializes without scanning your disk, because scanning large
model files can take a while. General settings contains the option “Always run a full
scan at startup” where you can change this. These settings are stored in your browser
storage, not in the repository. Manual scans remain available from the header. Setup 
mode and read-only repositories do not request startup scans.

When a scan finishes, the active content tab refreshes its list without reloading
the page or resetting filters, selections, or editor drafts. Failed scans also
refresh the list so any objects discovered before the failure become visible.
Scan errors give the Repository button a red outline. The affected sections in its
dialog contain expandable “Scan errors” lists with codes, messages, and parameters.
These diagnostics remain for the current browser session until that section has a
clean scan. Missing metadata is generated for recognized model files; auxiliary-only
file groups are skipped without scan errors.

The Repository button shows “Wait...” until startup completes. A timeout or lost
connection changes the button to “Server...”; its dialog reports that the server is
not responding. All frontend requests have a 3s timeout, so slow connection or an 
overloaded CPU can cause false timeout messages. 
Opening its dialog or clicking Retry checks connectivity again.
After startup, the server is assumed available until a request fails. Repository
status polling runs only while a long-running operation is being tracked and stops
after its final result is retrieved.

# Release planning

The pre-release checklist, cleanup work, platform testing, and possible later
features are maintained in [docs/ROADMAP.md](docs/ROADMAP.md).
