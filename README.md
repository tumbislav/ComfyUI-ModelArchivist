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

# Configuration and operating modes
The file `config.toml` is typically located in the root folder. It contains only the
bootstrap settings required before the repository database can be opened: the SQLite
database path, web server settings, logging settings, and disk-owned filesystem permissions. Repository behavior, model
types, accepted extensions, and working/archive location mappings are stored in SQLite.
A new database starts in setup mode and is not scanned until at least one complete
model, workflow, or user-defined type mapping has been saved. Each category is optional.
Scans visit only configured mappings, and cleanup preserves records outside the scan's
configured targets. Unmapped ComfyUI discoveries do not affect filesystem readiness.

The backend initializes without scanning. General settings contains “Always run a full
scan at startup”, enabled by default and saved in this browser's local storage. When
enabled, opening Archivist requests one startup scan per backend run; refreshing or
opening another tab does not repeat it. Disabling it opens the existing repository
immediately. Manual scans remain available from the header. Setup mode and read-only
repositories do not request startup scans.

The Repository button shows “Wait...” until startup completes. All frontend API
requests have a 3000 ms timeout, including their response bodies. A timeout or lost
connection changes the button to “Server...”; its dialog reports that the server is
not responding. Opening its dialog or clicking Retry checks connectivity again.
After startup, the server is assumed available until a request fails. Repository
status polling runs only while a long-running operation is being tracked and stops
after its final result is retrieved.

The Repository dialog shows counts by location for models, workflows, user-defined
objects, and collections. Working, archive, and synchronized counts are disjoint;
mixed or mismatched locations remain included in the total. Errors count objects with
errors, and collections with errors among their transitive members. Collections have
statistics only. The other sections can refresh independently, with statistics updated
when the dialog opens, every 500 ms during operations, and once after completion.
The idle dialog does not poll. Only one long-running operation can run at once.

Selective scans use `/scan?scope=models`, `scope=workflows`, or `scope=user_objects`.
An optional `type_id` selects a model type by name or a user type by ID, ready for
individual-type actions in Settings. A JSON body with `type_ids` selects a batch of
model or user types. Scanning and cleanup are both restricted to the
selected scope; other types and their records are preserved.

In standalone mode, Archivist manages the working locations and permits at most one
working/archive pair for each model type and one pair for workflows. ComfyUI's
`extra_model_paths.yaml` mechanism is deliberately not supported in standalone mode.

When installed as a ComfyUI custom node, Archivist discovers model working directories
and initial extensions through ComfyUI's live `folder_paths` registry, including extra
model paths, and discovers workflows below the ComfyUI user directory. Those working
paths remain owned by ComfyUI; Archivist stores their archive mappings, editable
extension lists, and display settings. Empty ComfyUI extension lists default to
`.sft`, `.safetensors`, `.gguf`, `.pt`, `.pth`, `.ckpt`, and `.bin`. Saved extensions
are owned by Archivist and remain authoritative after restarting.
Model type settings start empty; users create them by adding and
saving mappings for discovered ComfyUI folders. Discovery alone does not create model
type entries. Mapping proposals include only registered folders that exist on disk.
Users can discard proposed types or individual unsaved mappings before saving;
startup does not create omitted model mappings. Model and workflow saves validate
and update only their own settings, preserving the other tab's stored mappings.
A ComfyUI action-bar button opens `/model-archivist/` on the ComfyUI
origin. ComfyUI proxies that path to Archivist's internal FastAPI server, so browser
traffic uses the same host and port as ComfyUI. No ComfyUI execution nodes are registered.
Mutable embedded runtime data is kept outside the installed custom-node directory, in
`<ComfyUI user directory>/_archivist/`. This directory contains the SQLite database and
log file. Standalone mode continues to use the paths specified in `config.toml`.

## Endpoint access

Public API paths and methods are explicitly listed in
`backend/server/public_routes.py`; new endpoints require updating that list.
Frontend files receive exact GET/HEAD routes from the configured build directory.
There is no catch-all proxy or static mount, and API documentation endpoints are disabled.

Standalone startup generates a random, process-lifetime session secret and passes
it to the locally opened browser in a URL fragment. The frontend immediately removes
the fragment, retains the session in tab-scoped session storage, and supplies it on
every API call. Restarting the backend invalidates previous sessions. No public
endpoint issues the secret. See the installation guide for reopening the application.

Embedded FastAPI always binds to `127.0.0.1`, regardless of `web.host`, and requires
a separate in-memory proxy token for every request. Only the aiohttp proxy knows
that token; it is not sent to the browser. Comfy routes remain within PromptServer's
middleware, and API requests are checked through its user manager. The launcher
preserves the selected Comfy profile. Upstream Comfy's named profiles and
`Comfy-User` header are not authentication; anonymous host access remains anonymous.
The host access adapter is the integration point for future verified authentication.
This does not implement cloud login, multiple-user repository isolation, or remote
standalone provisioning.

Browser API requests must be same-origin and carry an Archivist request header.
The internal listener does not trust forwarded headers, and the proxy strips host
credentials before forwarding. Other applications sharing the Comfy origin remain
in the same browser trust boundary. Endpoint protection does not replace filesystem
path restrictions.

## Filesystem permissions

The `[filesystem]` section of `config.toml` defines permitted working roots,
permitted archive roots, and exclusions. It is initialized on first startup and
can be reviewed and saved once in the first-run dialog, with one root per line.
Saving applies the roots immediately and closes this UI permission permanently.
Later changes require editing the file and restarting. Existing installations do
not gain this first-run permission during upgrades. See [filesystem setup](docs/INSTALLATION.md#filesystem-permissions) for
defaults, examples, and migration of existing installations.

Model, workflow, and user-type mappings, mapping previews, scans, metadata edits,
and transfers all enforce these boundaries. Links, junctions, and files with
multiple hard links are rejected. Blocked mappings remain visible and make the
repository read-only. Scans report blocked entries and preserve existing records
when a scan is incomplete. The native operating-system directory picker has been
replaced with an in-app directory browser that lists only permitted server folders.

Checks are repeated near file operations. This is not an OS sandbox and does not
claim protection against a privileged local process racing filesystem changes.
The database, logs, and shipped web assets use trusted bootstrap locations rather
than the content working/archive policy.

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

# Development verification

Backend tests use the repository virtual environment:
`.venv/Scripts/python.exe -m pytest test/backend -q`. Pytest temporary runs and its
cache live under `test/temp/account-<identity>/`, separated by the actual process
account (Windows SID or Unix UID). This avoids permission conflicts between a
developer and a sandbox account sharing the checkout. Temporary runs use pytest's
normal numbering, locking, and retention; they no longer share a fixed directory
that each run deletes. Explicit `--basetemp`, `PYTEST_DEBUG_TEMPROOT`, and
`-o cache_dir=...` overrides remain supported.

# Frontend production build

Run `npm ci` and then `npm run build` from `frontend/`. The build command runs
Vite and, only on success, writes `frontend/build/build-manifest.json` with SHA-256
fingerprints of source files, static assets, build scripts, configuration, the
dependency lockfile, and generated output files. Input text uses normalized line
endings so Windows and Linux checkouts can be compared. Generated output is hashed
as exact bytes. The manifest excludes its own file and records the Node.js version.
It also fingerprints local `.env*` and `.npmrc` files when present, but does not
record their contents or capture environment variables supplied by the shell.

The command fails if inputs change during the build. It does not stage files,
commit changes, or publish anything. When committing a build, include the entire
`frontend/build/` directory, including the manifest. Publication-time freshness
verification uses this manifest. Run `npm run check:build` from `frontend/` to
check local output, or `npm run check:build -- --committed` to also require that
the inputs, output, and manifest are tracked and committed. A failure lists the
files to rebuild or commit. Generated output is kept byte-for-byte by
`.gitattributes`; source text fingerprints tolerate Windows line endings.

## GitHub validation and publication

`.github/workflows/ci.yaml` runs on pull requests and pushes to `master`. It checks
the committed frontend build before installing dependencies or rebuilding, runs
frontend tests and Svelte checks, and builds and verifies fresh output. Separate
Python 3.12 jobs run backend tests and metadata checks on Windows and Linux.

`.github/workflows/publish.yaml` is manual only. After it is on `master`, select
**Actions → Publish to Comfy Registry → Run workflow**, leave the workflow branch
set to `master`, and supply an existing tag such as `v0.8.0`. The tag must match
`pyproject.toml` and point to a commit reachable from `master`. The workflow resolves
that tag to an exact commit, runs CI on it, and builds fresh frontend output for
the Registry package. Publishing requires the GitHub Actions secret
`REGISTRY_ACCESS_TOKEN`. The workflow does not create tags or GitHub Releases.
Enter the complete tag, including the leading `v`; entering only `0.8.0` is not
enough. A missing or malformed tag is rejected before checkout.

Before tagging, rebuild and commit all source and build changes, including
`frontend/build/build-manifest.json`. Publication never runs merely because a
workflow or metadata file was pushed. Repository secrets and branch protection
must be configured separately in GitHub.

# Release planning

The pre-release checklist, cleanup work, platform testing, and possible later
features are maintained in [docs/ROADMAP.md](docs/ROADMAP.md).
