<!-- -------------------------------------------------------------------------
system: ModelArchivist
file: frontend/src/lib/locales/README.md
purpose: Planned frontend localization catalog conventions
---------------------------------------------------------------------------- -->

# Locale catalogs

Localization support will be introduced near release, after user-interface wording has
stabilized. Catalogs will be JSON files in this directory, named with BCP 47 language
tags such as `en.json`, `de.json`, and `sl.json`.

Catalogs will use stable semantic keys rather than English source strings. English will
be the complete fallback catalog. Parameters will be explicit values supplied by the
caller, while plural selection and locale-sensitive formatting will use JavaScript
`Intl` APIs.

Backend API errors should provide stable error codes and structured parameters so the
frontend can map them to catalog entries. English backend messages remain available as
a fallback and for logs. No runtime localization framework is intentionally selected or
installed yet.
