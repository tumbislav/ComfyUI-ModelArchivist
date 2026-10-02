<!-- -------------------------------------------------------------------------
system: ModelArchivist
file: ROADMAP.md
purpose: Release checklist, planned cleanup, and future ideas
---------------------------------------------------------------------------- -->

# Model Archivist roadmap

This roadmap records current plans rather than promises. Priorities can change as
the application is tested in real installations.

## Post-release work
Some issues were identified in testing but will be fixed after initial release.
- Button layout and table headings must be fixed for French and Spanish translations.
- The label "Working root" in the settings menu is not translated.
- Do more Linux and macOS testing
- Test with more browsers

## Ideas for a later version

The following ideas are unconfirmed and need design work before implementation:

- Support models packaged as a Hugging Face directory rather than a single file.
- Support separate workspaces for different users.
- Extend model metadata and retrieve it from sources such as Civitai, Hugging Face,
  LoraManager, or rgthree sidecars.
- Add a first-class base-model attribute to models.
- Add project collections that can establish a complete environment by:
  - defining the object types the project controls;
  - archiving working objects that are not part of the project;
  - automatically including new objects that match rules such as a regular
    expression; and
  - optionally running a setup script.

## Suggest an addition

Use [GitHub Discussions](https://github.com/tumbislav/ComfyUI-ModelArchivist/discussions)
to propose or develop roadmap ideas. A concrete proposal should explain the user
problem, give an example, and describe how the result should behave.
