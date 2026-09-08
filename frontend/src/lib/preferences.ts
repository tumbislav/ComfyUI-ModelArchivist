/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/preferences.ts
 * purpose: Browser-persistent startup, navigation, and theme preferences
 * ---------------------------------------------------------------------------*/

import type { ActiveTab } from './admin';

const startupScanKey = 'archivist.scanAtStartup';
const rememberTabKey = 'archivist.rememberLastTab';
const lastTabKey = 'archivist.lastTab';

function storedValue(key: string): string | null {
    try {
        return localStorage.getItem(key);
    } catch {
        return null;
    }
}

export function rememberLastTab(): boolean {
    return storedValue(rememberTabKey) === 'true';
}

export function saveRememberLastTab(enabled: boolean): void {
    localStorage.setItem(rememberTabKey, String(enabled));
}

export function initialTab(): Exclude<ActiveTab, null> {
    const tab = rememberLastTab() ? storedValue(lastTabKey) : null;

    return tab === 'workflows' || tab === 'user' || tab === 'collections'
        ? tab : 'models';
}

export function saveLastTab(tab: Exclude<ActiveTab, null>): void {
    try {
        localStorage.setItem(lastTabKey, tab);
    } catch {
        // Navigation remains available when browser storage is blocked.
    }
}

export function savedTheme(): 'light' | 'dark' {
    return storedValue('theme') === 'dark' ? 'dark' : 'light';
}

export function saveTheme(theme: 'light' | 'dark'): void {
    try {
        localStorage.setItem('theme', theme);
    } catch {
        // Theme switching remains available when browser storage is blocked.
    }
}

export function scanAtStartup(): boolean {
    try {
        return localStorage.getItem(startupScanKey) !== 'false';
    } catch {
        return true;
    }
}

export function saveScanAtStartup(enabled: boolean): void {
    localStorage.setItem(startupScanKey, String(enabled));
}
