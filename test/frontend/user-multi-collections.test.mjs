/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: test/frontend/user-multi-collections.test.mjs
 * purpose: Verify bulk UDP collection membership, picker rules, and failure handling
 * ---------------------------------------------------------------------------*/

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';

const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
const ts = require('typescript');
const source = readFileSync(new URL(
    '../../frontend/src/lib/components/user-objects/MultiUserObjectCollectionEditor.svelte',
    import.meta.url), 'utf8');
const script = source.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1]
    .replace(/import [\s\S]*?;\s*/g, '');
const code = ts.transpileModule(script + `
    exports.editor = {
        openAdd, addTo, createNew, removeSelected, toggleSelected, optionDisabled,
        get memberships() { return memberships; },
        get popupOpen() { return popupOpen; },
        get busy() { return busy; },
        get error() { return error; },
        get selected() { return selected; }
    };
`, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText;

const collections = [
    {id: 'all', name: 'All objects'},
    {id: 'some', name: 'Some objects'},
    {id: 'none', name: 'No objects'}
];
const objects = () => [
    {id: 'a', read_only: false, collections: [collections[0], collections[1]]},
    {id: 'b', read_only: false, collections: [collections[0]]}
];

function editor({items = objects(), disabled = false, update, confirmed = true} = {}) {
    const calls = [];
    let refreshed = 0;
    const derived = value => value;
    derived.by = callback => callback();
    const context = {
        exports: {}, $state: value => value, $derived: derived, $bindable: value => value,
        $props: () => ({items, disabled, onChanged: async () => { refreshed++; }}),
        locale: {
            t: key => key,
            compare: (a, b) => a.localeCompare(b),
            plural: (key, count) => `${key}:${count}`
        },
        confirmBox: async () => confirmed,
        updateCollectionUserObjects: async (...args) => {
            calls.push(args);
            return update ? update(...args) : {ok: true};
        },
        createCollection: async input => {
            calls.push(input);
            return {ok: true};
        }
    };
    runInNewContext(code, context);
    return {api: context.exports.editor, calls, refreshed: () => refreshed};
}

test('Add opens without choosing a collection and picker disables only full memberships', () => {
    const {api} = editor();
    api.openAdd();
    assert.equal(api.popupOpen, true);
    assert.equal(api.optionDisabled(collections[0]), true);
    assert.equal(api.optionDisabled(collections[1]), false);
    assert.equal(api.optionDisabled(collections[2]), false);
    assert.deepEqual(Array.from(api.memberships, value => value.count), [2, 1]);
});

test('add includes all selected object IDs and refreshes membership data', async () => {
    const {api, calls, refreshed} = editor();
    assert.equal(await api.addTo('some'), null);
    assert.deepEqual(JSON.parse(JSON.stringify(calls)), [['some', ['a', 'b'], true]]);
    assert.equal(refreshed(), 1);
    assert.equal(api.busy, false);
});

test('create includes selected UDPs without adding models or workflows', async () => {
    const {api, calls, refreshed} = editor();
    assert.equal(await api.createNew('Training'), null);
    assert.deepEqual(JSON.parse(JSON.stringify(calls[0])), {
        name: 'Training', purpose: '', tags: [], models: [], workflows: [], children: [],
        user_objects: ['a', 'b']
    });
    assert.equal(refreshed(), 1);
});

test('remove requires selected memberships and confirmation', async () => {
    const {api, calls, refreshed} = editor();
    await api.removeSelected();
    assert.equal(calls.length, 0);
    api.toggleSelected('all');
    api.toggleSelected('some');
    await api.removeSelected();
    assert.deepEqual(JSON.parse(JSON.stringify(calls)), [
        ['all', ['a', 'b'], false], ['some', ['a', 'b'], false]
    ]);
    assert.equal(api.selected.size, 0);
    assert.equal(refreshed(), 1);

    const cancelled = editor({confirmed: false});
    cancelled.api.toggleSelected('all');
    await cancelled.api.removeSelected();
    assert.equal(cancelled.calls.length, 0);
});

test('partial removal reports error, refreshes completed changes, and releases busy state', async () => {
    const {api, calls, refreshed} = editor({update: async id => id === 'some'
        ? {ok: false, message: 'Denied'} : {ok: true}});
    api.toggleSelected('all');
    api.toggleSelected('some');
    await api.removeSelected();
    assert.equal(calls.length, 2);
    assert.equal(api.error, 'Denied');
    assert.equal(api.busy, false);
    assert.equal(refreshed(), 1);
});

test('unavailable selections cannot open the picker or change memberships', async () => {
    for (const options of [{disabled: true}, {items: []},
        {items: [{...objects()[0], read_only: true}]}]) {
        const {api, calls} = editor(options);
        api.openAdd();
        assert.equal(api.popupOpen, false);
        assert.equal(api.optionDisabled(collections[2]), true);
        await api.addTo('none');
        await api.createNew('Training');
        assert.equal(calls.length, 0);
    }
});
