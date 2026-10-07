<!-- -------------------------------------------------------------------------
system: ModelArchivist
file: LOCALIZATION.md
purpose: Languages
---------------------------------------------------------------------------- -->

# Localization

Version 1.0 supports four languages: English, which is the default, Slovenian, French and Spanish. English is the original, the other three are machine translations, which means that they need work. The following table summarizes the current status of the localizations along **three** dimensions:

* Completeness: how many strings are translated and how many default to English,
* Labels: how many screen labels are reviewed for correctness,
* Fonts: how do fonts match the requirements of the language,
* Help: how much of the help is translated and **checked by a human**,
* Vignettes: librarian vignettes need more than just a correctness check,
* Layout: labels that overflow their space can break the screen layout

| Dimension    | English | Slovenian | French | Spanish |
| ------------ | ------- | --------- | ------ | ------- |
| Completeness | 100%    | 100%      | 100%   | 100%    |
| Labels       | 100%    | 50%       | 10%    | 10%     |
| Fonts        | 100%    | 100%      | 100%   | 100%    |
| Help         | 40%     | 0%        | 0%     | 0%      |
| Vignettes    | 100%    | 100%      | 0%     | 0%      |
| Layout       | 80%     | 20%       | 30%    | 10%     |

## Help wanted

You can help with any of those categories. See the [locale catalog guide](../frontend/src/lib/locales/README.md) for details.

For minor corrections that do not warrant a pull request, let me know in [GitHub Discussions](https://github.com/tumbislav/ComfyUI-ModelArchivist/discussions).

You can also help by adding a new translation. Since much of the community is Chinese, both **traditional and simplified Chinese** translations are desired, but **any language is welcome**. For languages that are not familiar to me, I will probably ask for a second (human) opinion to confirm that the translation is of adequate quality. Machine generated translations without a human review will be viewed with scepticism.
