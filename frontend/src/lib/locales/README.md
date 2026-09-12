<!-- -------------------------------------------------------------------------
system: ModelArchivist
file: frontend/src/lib/locales/README.md
purpose: Localization architecture and guidance for translators
---------------------------------------------------------------------------- -->

# Locale catalogs

Model Archivist keeps user-interface translations in this directory. Catalogs are
named with BCP 47 language tags. `en.json` is authoritative and complete; every
missing or invalid translated value falls back to English. `config.json` lists the
supported locales and the presentation metadata needed before the interface starts.

The visible **Model Archivist** title in the navigation bar is a product name and is
not translated. Translate its surrounding accessibility labels and all other
user-facing interface text.

## Translating a catalog

Preserve every semantic key, JSON structure, placeholder, and HTML element from the
English catalog. Translate values only. Do not assemble translated sentences from
fragments. Parameters use braces, for example `{name}` and `{count}`; their spelling
must remain unchanged.

New catalog templates use `null` for untranslated values. Leave a value as `null` to
use the English fallback, or replace it with translated text. This makes partially
translated catalogs safe to select while work is in progress.

Plural messages have keys named for the categories returned by `Intl.PluralRules`,
such as `one`, `few`, and `other`. Supply every category used by the language and
always supply `other`. Numbers, dates, byte sizes, comparisons, and plurals use the
selected locale at runtime.

Translate visible labels together with accessibility text, including ARIA labels,
tooltips, titles, placeholders, confirmations, progress descriptions, image text,
and screen-reader-only content. User-provided names, paths, tags, repository data,
technical identifiers, and raw filesystem details are not translated. Stable backend
error codes should map to localized messages; an unexpected backend message remains
available as the fallback detail.

About-carousel captions are trusted rich HTML stored under `about.captions`. Preserve
the structure, tooltip IDs, `aria-describedby` relationships, and link destinations.
Every `Library-*.png` image has a key derived from its filename. An empty caption is
valid. Catalog HTML is maintained with the application and must never contain
untrusted user content.

Test translations at the fixed 380 by 600 pixel Settings content size and throughout
the tables, buttons, dialogs, and narrow-screen layouts. Translated labels can be much
longer than English and should wrap without obscuring controls.

## Locale metadata and fonts

Each entry in `config.json` contains:

- `name`: the language name written in that language;
- `direction`: `ltr` or `rtl`;
- `font`: a key from the config's font registry.

The runtime applies the locale to the document's `lang` and `dir` attributes and sets
the configured font family before the interface is displayed. Open Sans is used for
Latin, Greek, and Cyrillic. Other scripts should use the appropriate script-specific
Noto Sans family. Keep font files and their licenses under `assets/fonts`; record
third-party attribution in the repository-level `ATTRIBUTIONS.md`.

Prefer CSS logical properties for layouts that must support both directions. Decide
whether an icon expresses physical direction or reading direction. Reading-direction
icons may be mirrored with CSS when their design permits it; culturally specific or
asymmetric alternatives belong in `assets/icons` and are selected through an asset
registry. Locale-specific font and icon modules may be loaded lazily and cached by the
browser rather than bundled into every initial view.

## Adding a language

1. Copy the complete structure of `en.json` to a file named with the language's BCP 47
   tag.
2. Translate the values and captions while preserving parameters and markup.
3. Add native language name, direction, and font metadata to `config.json`.
4. Add any required font or icon assets, licenses, and attributions.
5. Run the locale validation and frontend test suites.
6. Inspect dialogs, tables, keyboard navigation, focus behavior, RTL direction, and
   narrow-screen wrapping in the running application.

Missing keys are reported during development and fall back to English in production.
Invalid saved locale preferences fall back to browser language matching and then to
English. The language picker stores explicit choices in browser persistent storage and
updates the open interface without a reload.
