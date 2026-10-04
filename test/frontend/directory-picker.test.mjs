/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: test/frontend/directory-picker.test.mjs
 * purpose: Picker navigation, stale responses, selection and lifecycle regressions
 * ---------------------------------------------------------------------------*/

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';

const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
const ts = require('typescript');
const source = readFileSync(new URL('../../frontend/src/lib/components/controls/DirectoryPicker.svelte', import.meta.url), 'utf8');
const script = source.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1].replace(/import [\s\S]*?;\s*/g, '');
const code = ts.transpileModule(script + `
    exports.actions = { navigate, select,
        get current() { return current; }, get error() { return error; },
        get busy() { return busy; }, get expanded() { return expanded; }
    };
`, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;

function listing(path, ancestors = [path]) {
    return { ok: true, data: { path, ancestors, directories: [], omitted: 0,
        parent: ancestors.length > 1 ? ancestors.at(-2) : null } };
}

function picker(getDirectories, initialPath = '') {
    let mount;
    const selected = [];
    const calls = [];
    const context = {
        exports: {},
        $props: () => ({ role: 'archive', initialPath, onSelect: path => selected.push(path), onClose() {} }),
        $state: value => value,
        $derived: { by: callback => callback() },
        locale: { t: key => key, error: issue => issue.message },
        onMount: callback => mount = callback,
        tick: async () => {},
        getDirectoryRoots: async role => {
            assert.equal(role, 'archive');
            return { ok: true, data: [{ name: '/archive', path: '/archive', issue: null }] };
        },
        getDirectories: (path, role) => {
            calls.push(path);
            assert.equal(role, 'archive');
            return getDirectories(path);
        }
    };
    runInNewContext(code, context);
    return { actions: context.exports.actions, selected, calls, mount: () => mount() };
}

test('initial selection expands only its ancestors and preserves archive context', async () => {
    const view = picker(async path => listing(path,
        path === '/archive/models/nested' ? ['/archive', '/archive/models', path] : [path]),
        '/archive/models/nested');
    view.mount();
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(view.calls, ['/archive/models/nested', '/archive', '/archive/models']);
    assert.equal(view.actions.current.path, '/archive/models/nested');
    assert.deepEqual([...view.actions.expanded], ['/archive', '/archive/models', '/archive/models/nested']);
    assert.deepEqual(view.selected, []);
});

test('late navigation responses cannot replace the latest selected directory', async () => {
    let finishOld;
    const view = picker(path => path === '/archive/old'
        ? new Promise(resolve => finishOld = resolve) : Promise.resolve(listing(path)));
    const old = view.actions.navigate('/archive/old');
    await view.actions.navigate('/archive/new');
    finishOld(listing('/archive/old'));
    await old;
    assert.equal(view.actions.current.path, '/archive/new');
    assert.equal(view.actions.busy, false);
});

test('selection is revalidated and denial prevents returning a stale location', async () => {
    let denied = false;
    const view = picker(async path => denied ? { ok: false, message: 'Excluded now' } : listing(path));
    await view.actions.navigate('/archive');
    denied = true;
    await view.actions.select();
    assert.deepEqual(view.selected, []);
    assert.equal(view.actions.current, null);
    assert.equal(view.actions.error, 'Excluded now');
});

test('successful explicit selection returns the server path without saving settings', async () => {
    const view = picker(async path => listing(path));
    await view.actions.navigate('/archive');
    assert.deepEqual(view.selected, []);
    await view.actions.select();
    assert.deepEqual(view.selected, ['/archive']);
    assert.deepEqual(view.calls, ['/archive', '/archive']);
});

test('closing during initial loading prevents late updates and further navigation', async () => {
    const view = picker(async path => listing(path));
    const destroy = view.mount();
    destroy();
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(view.calls, []);
    assert.equal(view.actions.current, null);
});
