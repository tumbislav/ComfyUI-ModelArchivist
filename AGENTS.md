<!-- -------------------------------------------------------------------------
system: ModelArchivist
file: AGENTS.md
purpose: Repository guidance for contributors and coding agents
---------------------------------------------------------------------------- -->

# Model Archivist contributor guidance

## Project structure

Model Archivist is a single-user SQLite application with a Python backend and a
Svelte frontend. It runs either as a standalone application or as a ComfyUI custom
node. In ComfyUI mode, the public `/model-archivist/` subtree is proxied from ComfyUI's
origin to Archivist's internal FastAPI server. It does not register ComfyUI execution
nodes.

The principal directories are:

- `backend/`: configuration, repository, scanning, file operations, dispatcher, and API.
- `frontend/src/`: Svelte application source and shared styles.
- `alembic/`: database schema migrations.
- `test/backend/`: backend unit tests.
- `web/`: ComfyUI browser extension entrypoint.

Read `README.md` for the user-facing overview and
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) before changing repository semantics.
Its Assumptions section records accepted constraints and deliberate tradeoffs;
it also documents runtime behavior, endpoint security, builds, and publication.

## Maintenance workflow

Version 1.0.2 is the current release. Maintenance mode begins once reviewers confirm
that the reported vulnerabilities are fixed; do not assume that confirmation has
already happened.

- In maintenance mode, make all changes on a separate branch and merge them through
  a pull request. Do not edit, commit, or push changes directly on `master`.
- Protect `master` on GitHub against direct pushes when maintenance mode begins.
- Before making changes, check the current branch. If it is `master`, remind the user
  of this policy and move the work to a separate branch before editing. Apply this
  reminder immediately to future tasks, including before maintenance mode begins.
- Associate every maintenance change with a release number or a higher-level version
  increase, and keep a one-line entry for every change in `docs/CHANGES.md` under the
  corresponding version.
- The user's own branches typically follow `YYYY-MM-YY-tumbislav`. Preserve a branch
  name supplied by the user; treat this pattern as their naming preference.

## Operating modes and configuration

`config.toml` contains bootstrap configuration and disk-owned filesystem permissions:
SQLite path, logging, web-server settings, permitted roots, and exclusions. Repository
options, model definitions, and working/archive mappings belong in SQLite.

- Standalone mode does not use ComfyUI's `extra_model_paths` mechanism. It permits one
  working/archive pair per model type and one workflow pair.
- ComfyUI mode discovers working model locations and extensions from `folder_paths`.
  Working model paths supplied by ComfyUI are not editable by Archivist. Each discovered
  working path may have an Archivist-managed archive mapping.
- Workflow folders default to ComfyUI's selected public profile directory but remain
  editable within the filesystem policy. Saved workflow mappings belong to Archivist.
- A new database starts in setup mode and must not scan before at least one complete
  model, workflow, or user-type mapping exists. Each category is optional. Unmapped
  discoveries must not affect readiness; scan cleanup is limited to configured targets.
- ComfyUI mode stores its SQLite database and log in the ComfyUI user root's
  `_archivist` directory. Standalone mode honors the bootstrap paths in `config.toml`.
- Filesystem inaccessibility makes the application read-only and prevents scanning or
  file operations.

Keep ComfyUI imports confined to the custom-node entrypoint or environment adapter so
the backend remains importable in standalone development and test environments.

Preserve saved model extension lists. Initial ComfyUI proposals combine discovered
extensions with `.sft`, `.safetensors`, `.pt`, `.pth`, and `.gguf`; discovery must not
overwrite saved choices or recreate types that the user removed. Removing a model
type removes its database mappings and catalog links, never model files or sidecars.
Model and workflow settings saves must preserve each other's configuration.

Allow only one long-running operation at a time. UDP directory-tree transfers must
include filesystem planning in background execution, regardless of the Small setting.
Report partial transfer failures and reconcile deployment state with the remaining
files. Preserve records outside selected scan targets and after incomplete scans.

## Data identity and accepted constraints

- ModelArchivist is a single-user application using SQLite.
- If any configured model or workflow folder is inaccessible, the application runs read-only and does not scan files.
- Every configured working directory has exactly one archive counterpart, and neither directory may be reused in another pair.
- A model or workflow has at most one working component set and one archive component set. Missing sides have no component set; their prospective paths are derived from the configured pair.
- A workflow is identified by a UUID in its top-level `id` field. JSON files without a usable UUID are ignored.
- Workflow IDs uniquely identify one relative filename across working and archive storage.
- Workflow details offers “Fix it” for duplicate working or archive IDs. It assigns a
  new UUID to each relative filename within a configured pair, keeping matching
  working/archive copies together. Each resulting workflow retains collection
  memberships. Avoid saving an already-open ComfyUI workflow over a repaired file,
  as that can restore its old ID.
- A model is identified by the SHA-256 hash of its main weights file.
- Normal scans trust a usable cached SHA-256 from Archivist or LoraManager metadata and hash weights only when no usable cached hash exists.
- User-requested rehash scans calculate hashes from every weights file, including archived files on slow storage.
- The risk of stale cached hashes and files changing during a scan is accepted. Users can request a manual rescan or rehash.
- Other applications may rename files in the working set. The working filename is authoritative and metadata can be updated later.
- Invalid third-party metadata is treated like an unreadable sidecar. Third-party and Archivist metadata are not reconciled.
- Orphaned sidecars and orphaned example directories are ignored.

## Database policy

Use SQLModel models in `backend/repository/tables.py`. Schema changes require an Alembic
migration and proportionate startup/migration tests. Do not silently mutate an
unversioned database.

During the current pre-release phase, a task may explicitly authorize replacing the
baseline and rebuilding development databases. Otherwise, preserve migration history
and assume databases contain user data.

## API and localization conventions

Register every new public API path and method in `backend/server/public_routes.py`.
Preserve exact frontend asset routes and the absence of catch-all routes. Keep the
embedded listener on `127.0.0.1` and its proxy token private to the proxy. Browser
requests must remain same-origin and carry the Archivist request header. Do not
treat ComfyUI profile names or the `Comfy-User` header as authentication.

Enforce filesystem policy for mappings, previews, scans, metadata edits, and transfers,
and repeat checks near file operations. No API may change disk-owned filesystem
permissions. Reject links, junctions, and multiple hard links; preserve blocked
mappings and incomplete-scan records. Endpoint protection does not replace path checks.

API clients must not rely on English exception text as an identifier. New API errors
should expose a stable semantic code, an English fallback message, and structured
interpolation parameters where applicable. User-interface localization belongs in the
frontend; backend logs and low-level filesystem errors remain in English.

Future locale catalogs live in `frontend/src/lib/locales/`. Use semantic keys such as
`settings.models.archive_folder`, keep English complete as the fallback, and format
dates, numbers, byte sizes, and plurals with the JavaScript `Intl` APIs. Do not build
sentences by concatenating translated fragments.

## Frontend organization

Keep HTML/Svelte markup and JavaScript/TypeScript code clearly indented and nested for
readability, with blank lines between logical blocks. Avoid compressing nested markup
or multiple statements onto one line. Use `TagEditor.svelte` and `ModelDetails.svelte`
as formatting examples for subsequent changes.

All CSS belongs in `frontend/src/lib/styles/`, including private component layouts.
Do not add or retain `<style>` blocks in Svelte components. Consolidate rules into
existing files such as `panels.css`, `controls.css`, `text.css`, and `dialogs.css`;
use a component-dedicated CSS file there when warranted and import it from `app.css`.
Scope component-specific selectors with a component class. Inline styles are allowed
only for values computed at runtime, such as dialog positions or tree indentation.
Avoid duplicating the same visual contract. Preserve keyboard access, labels, focus behavior, modal
boundaries, and narrow-screen wrapping when changing controls.

Place contextual help buttons at the top-right of the section they explain. Help for an
individual control belongs at the right edge of that control's row.

Browser-persistent preferences, such as theme and future language selection, belong in
frontend storage. Repository configuration belongs in the backend database.

## Dependencies and packaging

Runtime dependencies must be declared consistently in both `pyproject.toml` and
`requirements.txt`. ComfyUI Manager installs `requirements.txt`; `pyproject.toml` is the
authoritative Python package metadata. Development-only dependencies belong in the
`dev` optional dependency group.

Avoid depending accidentally on packages bundled by ComfyUI. Declare every third-party
package imported directly by Archivist unless the import is deliberately an integration
point supplied by ComfyUI itself, such as `folder_paths` or `PromptServer`.

Follow [build and release procedures](docs/DEVELOPMENT.md#frontend-production-build)
when preparing a release. Generate frontend output with the build scripts, include
the entire build and its manifest when committing a build, and verify committed
freshness before publication. Rebuild and commit before tagging. Publication is
manual; tags must match package metadata and be reachable from `master`. Do not
assume that pushing creates tags, releases, or Registry publications.

## File headers

Every new source, test, configuration, documentation, or asset-description file must
start with the project header used by neighboring files. Use the language-appropriate
comment form: `#` for Python/TOML/requirements, `/* */` for TypeScript/JavaScript/CSS,
and `<!-- -->` for Markdown/Svelte markup. Include system, file, and purpose fields.

## Verification

Run backend tests from the repository root:

```powershell
.venv\Scripts\python.exe -m pytest test/backend -q
```

Run frontend checks from `frontend/`:

```powershell
npm run check
```

Run frontend regression tests from the repository root:

```powershell
node --test "test/frontend/*.test.mjs"
```

Pytest isolates temporary runs and caches by process account under `test/temp/`.
Preserve that isolation; do not replace it with a shared directory that is deleted
for each run. See [verification details](docs/DEVELOPMENT.md#development-verification)
for supported temporary-directory and cache overrides.

Also run `git diff --check`. Add focused regression tests for behavioral changes rather
than relying only on the full suite.

## Agent filesystem access

If a task requires filesystem access beyond the active project policy, tell the user
the exact paths, whether read or write access is needed, and why. Wait for the user to
update the project filesystem policy before proceeding with work that needs that
access. Do not request one-time access grants or attempt workarounds.

## Generated and user-owned files

Do not edit `frontend/build/`, `frontend/.svelte-kit/`, Python cache directories, test
temporary directories, database files, or log files as source. Preserve unrelated
working-tree changes. Never delete or replace a database, migration history, or user
filesystem content unless the task explicitly authorizes it.
