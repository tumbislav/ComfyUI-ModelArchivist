/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: test/frontend/column-filters.test.mjs
 * purpose: Column filtering, blank selections, and browser persistence regression tests
 * ---------------------------------------------------------------------------*/

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';

const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
const ts = require('typescript');
const stores = await import(pathToFileURL(require.resolve('svelte/store')).href);
const source = readFileSync(new URL('../../frontend/src/lib/column-filters.ts', import.meta.url), 'utf8');
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const plain = value => JSON.parse(JSON.stringify(value));

function filters(storage = new Map()) {
    const messages = {
        'common.blank': '(blank)', 'common.none': 'none', 'common.yes': 'yes',
        'common.no': 'no', 'common.filter_off': '(filter off)', 'common.no_filters': 'No filters'
    };
    const context = { exports: {}, require: name => name === 'svelte/store' ? stores
        : { locale: { t: key => messages[key] ?? key } }, localStorage: {
        getItem: key => storage.get(key) ?? null,
        setItem: (key, value) => storage.set(key, value),
        removeItem: key => storage.delete(key)
    } };
    runInNewContext(code, context);
    return context.exports;
}

const rows = [
    { id: 1, internal_name: 'Alpha', file_format: '', tag_values: [], error_values: [], deployment: 'working' },
    { id: 2, internal_name: 'alphabet', file_format: 'gguf', tag_values: ['portrait', 'favorite'], error_values: ['bad'], deployment: 'archive' },
    { id: 3, internal_name: 'Beta', file_format: 'gguf', tag_values: ['favorite'], error_values: [], deployment: 'synced' }
];

test('column rules combine with AND and prefixes are case insensitive and literal', () => {
    const api = filters();
    api.applyColumn('models', 'internal_name', 'ALP');
    api.applyColumn('models', 'tag_values', ['']);
    assert.deepEqual(api.filteredRows(rows, stores.get(api.filterStates).models).map(row => row.id), [1]);
    api.applyColumn('models', 'internal_name', 'A%');
    assert.equal(api.filteredRows(rows, stores.get(api.filterStates).models).length, 0);
});

test('blank, none, and unrestricted selections are distinct', () => {
    const api = filters();
    api.applyColumn('models', 'file_format', ['']);
    assert.deepEqual(api.filteredRows(rows, stores.get(api.filterStates).models).map(row => row.id), [1]);
    assert.match(api.filterSummary('models', stores.get(api.filterStates).models), /\(blank\)/);
    api.applyColumn('models', 'file_format', []);
    assert.equal(api.filteredRows(rows, stores.get(api.filterStates).models).length, 0);
    api.applyColumn('models', 'file_format', null);
    assert.equal(api.filteredRows(rows, stores.get(api.filterStates).models).length, 3);
});

test('error values and rows without errors can be selected', () => {
    const api = filters();
    api.applyColumn('models', 'error_values', ['bad']);
    assert.deepEqual(api.filteredRows(rows, stores.get(api.filterStates).models).map(row => row.id), [2]);
    api.applyColumn('models', 'error_values', ['']);
    assert.deepEqual(api.filteredRows(rows, stores.get(api.filterStates).models).map(row => row.id), [1, 3]);
});

test('toggle bypasses filtering without discarding rules or affecting other tabs', () => {
    const api = filters();
    api.applyColumn('models', 'tag_values', ['portrait']);
    api.toggleFilters('models');
    assert.equal(api.filteredRows(rows, stores.get(api.filterStates).models).length, 3);
    api.toggleFilters('models');
    assert.equal(api.filteredRows(rows, stores.get(api.filterStates).models).length, 1);
    assert.deepEqual(plain(stores.get(api.filterStates).workflows.columns), {});
});

test('remember option persists current state, changes, and disabled filters for every tab', () => {
    const storage = new Map();
    const api = filters(storage);
    for (const tab of ['models', 'workflows', 'user', 'collections']) {
        api.applyColumn(tab, 'tag_values', ['favorite']);
    }
    assert.equal(storage.has('archivist.columnFilters'), false);
    api.setRememberFilters(true);
    api.toggleFilters('models');
    const restored = filters(storage);
    assert.deepEqual(plain(stores.get(restored.filterStates)), plain(stores.get(api.filterStates)));
    api.setRememberFilters(false);
    assert.equal(storage.has('archivist.columnFilters'), false);
    assert.deepEqual(plain(stores.get(filters(storage).filterStates).models.columns), {});
});

test('invalid storage and obsolete column rules are safely ignored', () => {
    const storage = new Map([['archivist.rememberFilters', 'true'], ['archivist.columnFilters', '{broken']]);
    assert.equal(stores.get(filters(storage).filterStates).models.enabled, false);
    const api = filters();
    const states = api.validateFilters({models: {enabled: true, columns: {
        has_tags: false, file_format: [], deployment: [null], unknown: 'bad', internal_name: 12
    }}});
    assert.deepEqual(plain(states.models.columns), {file_format: []});
});

test('multi-value columns match any selected value and preserve blanks', () => {
    const api = filters();
    api.applyColumn('models', 'tag_values', ['portrait']);
    assert.deepEqual(api.filteredRows(rows, stores.get(api.filterStates).models).map(row => row.id), [2]);
    api.applyColumn('models', 'tag_values', ['favorite']);
    assert.deepEqual(api.filteredRows(rows, stores.get(api.filterStates).models).map(row => row.id), [2, 3]);
    api.applyColumn('models', 'tag_values', ['']);
    assert.deepEqual(api.filteredRows(rows, stores.get(api.filterStates).models).map(row => row.id), [1]);
});
