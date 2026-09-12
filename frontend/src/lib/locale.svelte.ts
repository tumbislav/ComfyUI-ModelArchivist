/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: locale.svelte.ts
 * purpose: Reactive localization, formatting, and locale asset initialization
 * ---------------------------------------------------------------------------*/

import config from '$lib/locales/config.json';
import english from '$lib/locales/en.json';
import spanish from '$lib/locales/es.json';
import french from '$lib/locales/fr.json';
import slovenian from '$lib/locales/sl.json';

type Catalog = Record<string, unknown>;
type Direction = 'ltr' | 'rtl';

export type LocaleMetadata = {
    name: string;
    direction: Direction;
    font: keyof typeof config.fonts;
};

const catalogs: Record<string, Catalog> = {
    en: english,
    es: spanish,
    fr: french,
    sl: slovenian
};
const languageStorageKey = 'archivist.language';
const reportedMissingKeys = new Set<string>();

function catalogValue(catalog: Catalog, key: string): unknown {
    return key.split('.').reduce<unknown>((value, part) => {
        if (typeof value !== 'object' || value === null || !(part in value)) return undefined;

        return (value as Catalog)[part];
    }, catalog);
}

function interpolate(value: string, parameters: Record<string, string | number>): string {
    return value.replace(/\{([A-Za-z0-9_]+)\}/g,
        (match, name: string) => name in parameters ? String(parameters[name]) : match);
}

function storedLanguage(): string | null {
    try {
        return localStorage.getItem(languageStorageKey);
    } catch {
        return null;
    }
}

function browserLanguage(): string {
    const supported = Object.keys(config.locales);

    for (const requested of navigator.languages) {
        const normalized = requested.toLowerCase();
        const exact = supported.find(language => language.toLowerCase() === normalized);
        const base = supported.find(language => language.toLowerCase() === normalized.split('-')[0]);

        if (exact ?? base) return (exact ?? base)!;
    }

    return config.default;
}

class LocaleState {
    language = $state(config.default);

    get available(): { code: string; metadata: LocaleMetadata }[] {
        return Object.entries(config.locales).map(([code, metadata]) => ({
            code,
            metadata: metadata as LocaleMetadata
        }));
    }

    initialize(): void {
        const stored = storedLanguage();
        this.set(stored && stored in config.locales ? stored : browserLanguage(), false);
    }

    set(language: string, persist = true): void {
        if (!(language in config.locales)) language = config.default;
        this.language = language;

        const metadata = config.locales[language as keyof typeof config.locales];
        const font = config.fonts[metadata.font as keyof typeof config.fonts];
        document.documentElement.lang = language;
        document.documentElement.dir = metadata.direction;
        document.documentElement.style.setProperty('--app-font-family', font.family);

        if (persist) {
            try {
                localStorage.setItem(languageStorageKey, language);
            } catch {
                // Language switching remains available when browser storage is blocked.
            }
        }
    }

    t(key: string, parameters: Record<string, string | number> = {}): string {
        const selected = catalogValue(catalogs[this.language] ?? {}, key);
        const fallback = catalogValue(english, key);

        if (fallback === undefined && import.meta.env.DEV && !reportedMissingKeys.has(key)) {
            reportedMissingKeys.add(key);
            console.warn(`Missing English locale key: ${key}`);
        }

        const value = typeof selected === 'string' ? selected
            : typeof fallback === 'string' ? fallback : key;

        return interpolate(value, parameters);
    }

    plural(key: string, count: number,
           parameters: Record<string, string | number> = {}): string {
        const category = new Intl.PluralRules(this.language).select(count);
        const candidate = `${key}.${category}`;
        const fallback = `${key}.other`;

        return this.t(catalogValue(catalogs[this.language] ?? {}, candidate) === undefined
            && catalogValue(english, candidate) === undefined ? fallback : candidate,
        { count, ...parameters });
    }

    number(value: number): string {
        return new Intl.NumberFormat(this.language).format(value);
    }

    date(value: Date | number | string, options: Intl.DateTimeFormatOptions): string {
        return new Intl.DateTimeFormat(this.language, options).format(new Date(value));
    }

    compare(left: string, right: string): number {
        return left.localeCompare(right, this.language);
    }
}

export const locale = new LocaleState();
