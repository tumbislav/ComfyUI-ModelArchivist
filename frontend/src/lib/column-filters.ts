/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: column-filters.ts
 * purpose: Shared column filters and optional browser persistence
 * ---------------------------------------------------------------------------*/

import { writable, get } from 'svelte/store';

export type FilterTab = 'models' | 'workflows' | 'user' | 'collections';
export type ColumnRule = string | string[] | boolean;
export type FilterState = { enabled: boolean; columns: Record<string, ColumnRule> };
export type FilterColumn = {
    key: string;
    label: string;
    kind: 'prefix' | 'multi' | 'boolean';
    positive?: string;
    negative?: string;
};
const booleanLabels: Record<string, [string, string]> = {
    has_tags: ['Has tags', 'Does not have tags'],
    has_collections: ['In collection', 'Not in collection'],
    errors: ['Has errors', 'No errors'],
    has_models: ['Contains models', 'No models'],
    has_workflows: ['Contains workflows', 'No workflows'],
    has_user_objects: ['Contains user object', 'No user objects'],
    has_children: ['Contains collections', 'No collections']
};
const column = (key: string, label: string, kind: FilterColumn['kind']): FilterColumn => ({
    key, label, kind,
    positive: booleanLabels[key]?.[0],
    negative: booleanLabels[key]?.[1]
});
const common = [column('relative_path', 'Relative path', 'multi'),
    column('has_tags', 'Tags', 'boolean'), column('has_collections', 'Collections', 'boolean'),
    column('deployment', 'Location', 'multi'), column('errors', 'Error', 'boolean')];
export const filterColumns: Record<FilterTab, FilterColumn[]> = {
    models: [column('internal_name', 'Model name', 'prefix'), common[0],
        column('file_format', 'Format', 'multi'), column('base_model_abbreviation', 'Base', 'multi'), ...common.slice(1)],
    workflows: [column('internal_name', 'Name', 'prefix'), ...common],
    user: [column('display_name', 'Name', 'prefix'), ...common],
    collections: [column('name', 'Name', 'prefix'), column('deployment', 'Location', 'multi'),
        ...['has_tags', 'has_models', 'has_workflows', 'has_user_objects', 'has_children', 'errors'].map((key, i) =>
            column(key, ['Tags', 'Models', 'Workflows', 'User types', 'Collections', 'Error'][i], 'boolean'))]
};
const preferenceKey = 'archivist.rememberFilters';
const stateKey = 'archivist.columnFilters';
const emptyStates = () => Object.fromEntries(Object.keys(filterColumns).map(tab =>
    [tab, { enabled: false, columns: {} }])) as Record<FilterTab, FilterState>;

function stored(key: string): string | null {
    try { return localStorage.getItem(key); } catch { return null; }
}

export function validateFilters(value: unknown): Record<FilterTab, FilterState> {
    const result = emptyStates();
    if (!value || typeof value !== 'object') return result;
    for (const tab of Object.keys(filterColumns) as FilterTab[]) {
        const state = (value as Record<string, any>)[tab];
        if (!state || typeof state !== 'object') continue;
        result[tab].enabled = state.enabled === true;
        for (const column of filterColumns[tab]) {
            const rule = state.columns?.[column.key];
            if ((column.kind === 'prefix' && typeof rule === 'string' && rule !== '') ||
                (column.kind === 'boolean' && typeof rule === 'boolean') ||
                (column.kind === 'multi' && Array.isArray(rule) && rule.every(item => typeof item === 'string'))) {
                result[tab].columns[column.key] = rule;
            }
        }
    }
    return result;
}

function restore(): Record<FilterTab, FilterState> {
    if (stored(preferenceKey) !== 'true') return emptyStates();
    try { return validateFilters(JSON.parse(stored(stateKey) ?? 'null')); } catch { return emptyStates(); }
}

export const rememberFilters = writable(stored(preferenceKey) === 'true');
export const filterStates = writable(restore());
export const openFilter = writable<string | null>(null);

filterStates.subscribe(states => {
    if (get(rememberFilters)) {
        try { localStorage.setItem(stateKey, JSON.stringify(states)); } catch { /* Storage may be unavailable. */ }
    }
});

export function setRememberFilters(enabled: boolean): void {
    localStorage.setItem(preferenceKey, String(enabled));
    if (enabled) localStorage.setItem(stateKey, JSON.stringify(get(filterStates)));
    else localStorage.removeItem(stateKey);
    rememberFilters.set(enabled);
}

export function applyColumn(tab: FilterTab, key: string, rule: ColumnRule | null): void {
    filterStates.update(states => {
        const columns = { ...states[tab].columns };
        if (rule === null || rule === '') delete columns[key];
        else columns[key] = rule;
        return { ...states, [tab]: { enabled: Object.keys(columns).length > 0, columns } };
    });
}

export function toggleFilters(tab: FilterTab): void {
    filterStates.update(states => ({ ...states, [tab]: { ...states[tab], enabled: !states[tab].enabled } }));
}

export function columnValue(row: object, key: string): string | boolean {
    const data = row as Record<string, any>;
    if (key === 'errors') {
        if (typeof data.error_count === 'number') return data.error_count > 0;
        return typeof data.read_only === 'boolean' ? data.read_only : (data.errors?.length ?? 0) > 0;
    }
    if (key.startsWith('has_')) return Boolean(data[key]);
    return String(data[key] ?? '');
}

export function filteredRows<T extends object>(rows: T[], state: FilterState): T[] {
    if (!state.enabled) return rows;
    return rows.filter(row => Object.entries(state.columns).every(([key, rule]) => {
        const value = columnValue(row, key);
        if (Array.isArray(rule)) return rule.includes(String(value));
        if (typeof rule === 'boolean') return value === rule;
        return String(value).toLocaleLowerCase().startsWith(rule.toLocaleLowerCase());
    }));
}

export function filterSummary(tab: FilterTab, state: FilterState): string {
    const parts = filterColumns[tab].filter(column => column.key in state.columns).map(column => {
        const rule = state.columns[column.key];
        const value = Array.isArray(rule) ? (rule.length ? rule.map(value => value || '(blank)').join(', ') : 'none')
            : typeof rule === 'boolean' ? (rule ? 'yes' : 'no') : rule;
        return `${column.label}: ${value}`;
    });
    return parts.length ? `${state.enabled ? '' : '(filter off) '}${parts.join('; ')}` : 'No filters';
}
