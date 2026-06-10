/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/common.ts
 * purpose: General helpers
 * ---------------------------------------------------------------------------*/

/* Date and time
 * ---------------------------------------------------------------------------*/

export const system_locale = new Intl.DateTimeFormat().resolvedOptions().locale;

export const short_date: Intl.DateTimeFormatOptions = {
    dateStyle: 'short'
};

export const timestamp: Intl.DateTimeFormatOptions = {
    dateStyle: 'short',
    timeStyle: 'short'
}

export function shortDate(d: Date): string {
    const formatter = new Intl.DateTimeFormat(system_locale, short_date);
    return formatter.format(d);
}

/* Paths
 * ---------------------------------------------------------------------------*/

export function joinPath(root: string, subdir: string | null): string {
    return subdir === '.' ? root : [root, subdir].join('/');
}

/* Transitions
 * ---------------------------------------------------------------------------*/

export const sidebar_in_out = {
    x: 400,
    duration: 300
}