/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: test/frontend/user-multi-edit.test.mjs
 * purpose: Multi-object editing isolation, preflight, and partial failure handling
 * ---------------------------------------------------------------------------*/

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';

const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
const ts = require('typescript');
const source = readFileSync(new URL('../../frontend/src/lib/components/user-objects/MultiUserObjectEditor.svelte', import.meta.url), 'utf8');
const script = source.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1].replace(/import [\s\S]*?;\s*/g, '');
const code = ts.transpileModule(script + `
    exports.editor = {
        prepare(add = [], remove = []) { addTags = add; removeTags = remove; loading = false; blocked = false; },
        perform,
        get error() { return error; },
        get busy() { return busy; }
    };
`, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;

function editor(objects, update) {
    let refreshed = 0;
    const context = {
        exports: {}, $state: value => value, $derived: value => value, onMount() {},
        $props: () => ({ ids: objects.map(item => item.id), onClose() {}, onChanged: async () => { refreshed++; } }),
        statusMonitor: { operation: null },
        getUserObject: async id => ({ ok: true, data: structuredClone(objects.find(item => item.id === id)) }),
        updateUserObject: update,
        locale: {
            t: (key, parameters = {}) => {
                if (key === 'ui.multi_user_object_editor.some_selected_objects_are_read_only') {
                    return 'Some selected objects are read-only.';
                }
                if (key === 'messages.partial_objects_updated') {
                    return `${parameters.completed} of ${parameters.total} objects updated. ${parameters.error}`;
                }

                return key;
            },
            plural: (key, count) => key === 'messages.updated_objects'
                ? `Updated ${count} objects.` : `${count} objects`
        },
        console
    };
    runInNewContext(code, context);
    return { api: context.exports.editor, refreshed: () => refreshed };
}

const objects = () => [
    { id: 'a', display_name: 'A', purpose: 'Keep A', tags: ['old', 'keep'], read_only: false },
    { id: 'b', display_name: 'B', purpose: 'Keep B', tags: ['keep'], read_only: false }
];

test('bulk tags preserve names, purpose, and unrelated tags', async () => {
    const calls = [];
    const { api, refreshed } = editor(objects(), async item => { calls.push(item); return { ok: true }; });
    api.prepare(['new', 'keep'], ['old']);
    await api.perform('tags');
    assert.deepEqual(JSON.parse(JSON.stringify(calls.map(item => item.tags))), [['keep', 'new'], ['keep', 'new']]);
    assert.deepEqual(calls.map(item => item.purpose), ['Keep A', 'Keep B']);
    assert.equal(api.error, null);
    assert.equal(refreshed(), 1);
});

test('partial failure stops the batch and reports completed objects', async () => {
    let calls = 0;
    const { api, refreshed } = editor(objects(), async () => ++calls === 1
        ? { ok: true } : { ok: false, message: 'Denied' });
    api.prepare(['new']);
    await api.perform('tags');
    assert.equal(calls, 2);
    assert.match(api.error, /1 of 2 objects updated.*Denied/);
    assert.equal(api.busy, false);
    assert.equal(refreshed(), 1);
});

test('fresh read-only preflight prevents any edits', async () => {
    const data = objects();
    data[1].read_only = true;
    const { api } = editor(data, async () => assert.fail('must not edit'));
    api.prepare(['new']);
    await api.perform('tags');
    assert.match(api.error, /read-only/);
    assert.equal(api.busy, false);
});
