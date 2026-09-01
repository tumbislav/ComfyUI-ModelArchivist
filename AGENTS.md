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

Read `README.md` before changing repository semantics. Its Assumptions section records
accepted constraints and deliberate tradeoffs.

## Operating modes and configuration

`config.toml` is bootstrap configuration only: SQLite path, logging, and web-server
settings. Repository options, model definitions, and filesystem mappings belong in
SQLite.

- Standalone mode does not use ComfyUI's `extra_model_paths` mechanism. It permits one
  working/archive pair per model type and one workflow pair.
- ComfyUI mode discovers working model locations and extensions from `folder_paths`.
  Working paths supplied by ComfyUI are not editable by Archivist. Each discovered
  working path may have an Archivist-managed archive mapping.
- A new database starts in setup mode and must not scan before required mappings exist.
- ComfyUI mode stores its SQLite database and log in the ComfyUI user root's
  `_archivist` directory. Standalone mode honors the bootstrap paths in `config.toml`.
- Filesystem inaccessibility makes the application read-only and prevents scanning or
  file operations.

Keep ComfyUI imports confined to the custom-node entrypoint or environment adapter so
the backend remains importable in standalone development and test environments.

## Database policy

Use SQLModel models in `backend/repository/tables.py`. Schema changes require an Alembic
migration and proportionate startup/migration tests. Do not silently mutate an
unversioned database.

During the current pre-release phase, a task may explicitly authorize replacing the
baseline and rebuilding development databases. Otherwise, preserve migration history
and assume databases contain user data.

## API and localization conventions

API clients must not rely on English exception text as an identifier. New API errors
should expose a stable semantic code, an English fallback message, and structured
interpolation parameters where applicable. User-interface localization belongs in the
frontend; backend logs and low-level filesystem errors remain in English.

Future locale catalogs live in `frontend/src/lib/locales/`. Use semantic keys such as
`settings.models.archive_folder`, keep English complete as the fallback, and format
dates, numbers, byte sizes, and plurals with the JavaScript `Intl` APIs. Do not build
sentences by concatenating translated fragments.

## Frontend organization

Reusable design rules belong in `frontend/src/lib/styles/`; avoid duplicating the same
visual contract in multiple Svelte components. Component-local CSS is appropriate only
for genuinely private layout. Preserve keyboard access, labels, focus behavior, modal
boundaries, and narrow-screen wrapping when changing controls.

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

Also run `git diff --check`. Add focused regression tests for behavioral changes rather
than relying only on the full suite.

## Generated and user-owned files

Do not edit `frontend/build/`, `frontend/.svelte-kit/`, Python cache directories, test
temporary directories, database files, or log files as source. Preserve unrelated
working-tree changes. Never delete or replace a database, migration history, or user
filesystem content unless the task explicitly authorizes it.
