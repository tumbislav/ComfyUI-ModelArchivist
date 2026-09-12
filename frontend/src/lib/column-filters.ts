/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: column-filters.ts
 * purpose: Shared column filters and optional browser persistence
 * ---------------------------------------------------------------------------*/

import { writable, get } from 'svelte/store';
import { locale } from '$lib/locale.svelte';

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
    has_tags: ['filters.boolean.has_tags', 'filters.boolean.no_tags'],
    has_collections: ['filters.boolean.in_collection', 'filters.boolean.not_in_collection'],
    errors: ['filters.boolean.has_errors', 'filters.boolean.no_errors'],
    has_models: ['filters.boolean.has_models', 'filters.boolean.no_models'],
    has_workflows: ['filters.boolean.has_workflows', 'filters.boolean.no_workflows'],
    has_user_objects: ['filters.boolean.has_user_objects', 'filters.boolean.no_user_objects'],
    has_children: ['filters.boolean.has_collections', 'filters.boolean.no_collections']
};
const column = (key: string, labelKey: string, kind: FilterColumn['kind']): FilterColumn => ({
    key,
    get label() { return locale.t(labelKey); },
    kind,
    get positive() { return booleanLabels[key] ? locale.t(booleanLabels[key][0]) : undefined; },
    get negative() { return booleanLabels[key] ? locale.t(booleanLabels[key][1]) : undefined; }
});
const common = [column('relative_path', 'filters.labels.relative_path', 'multi'),
    column('tag_values', 'filters.labels.tags', 'multi'),
    column('collection_names', 'filters.labels.collections', 'multi'),
    column('deployment', 'filters.labels.location', 'multi'),
    column('error_values', 'filters.labels.error', 'multi')];
export const filterColumns: Record<FilterTab, FilterColumn[]> = {
    models: [column('internal_name', 'filters.labels.model_name', 'prefix'), common[0],
        column('file_format', 'filters.labels.format', 'multi'),
        column('base_model_abbreviation', 'filters.labels.base', 'multi'), ...common.slice(1)],
    workflows: [column('internal_name', 'filters.labels.name', 'prefix'), ...common],
    user: [column('display_name', 'filters.labels.name', 'prefix'), ...common],
    collections: [column('name', 'filters.labels.name', 'prefix'),
        column('deployment', 'filters.labels.location', 'multi'),
        ...['tag_values', 'model_names', 'workflow_names', 'user_object_names',
            'child_collection_names'].map((key, i) =>
            column(key, ['filters.labels.tags', 'filters.labels.models', 'filters.labels.workflows',
                'filters.labels.user_types', 'filters.labels.collections'][i], 'multi')),
        column('error_values', 'filters.labels.error', 'multi')]
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

export function columnValue(row: object, key: string): string | string[] | boolean {
    const data = row as Record<string, any>;
    if (key.startsWith('has_')) return Boolean(data[key]);
    if (Array.isArray(data[key])) return data[key].length > 0 ? data[key].map(String) : [''];
    return String(data[key] ?? '');
}

export function filteredRows<T extends object>(rows: T[], state: FilterState): T[] {
    if (!state.enabled) return rows;
    return rows.filter(row => Object.entries(state.columns).every(([key, rule]) => {
        const value = columnValue(row, key);
        if (Array.isArray(rule)) {
            const values = Array.isArray(value) ? value : [String(value)];
            return values.some(item => rule.includes(item));
        }
        if (typeof rule === 'boolean') return value === rule;
        return String(value).toLocaleLowerCase().startsWith(rule.toLocaleLowerCase());
    }));
}

export function filterSummary(tab: FilterTab, state: FilterState): string {
    const parts = filterColumns[tab].filter(column => column.key in state.columns).map(column => {
        const rule = state.columns[column.key];
        const value = Array.isArray(rule)
            ? (rule.length ? rule.map(value => value || locale.t('common.blank')).join(', ')
                : locale.t('common.none'))
            : typeof rule === 'boolean' ? locale.t(rule ? 'common.yes' : 'common.no') : rule;
        return `${column.label}: ${value}`;
    });
    return parts.length
        ? `${state.enabled ? '' : `${locale.t('common.filter_off')} `}${parts.join('; ')}`
        : locale.t('common.no_filters');
}
