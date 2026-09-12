/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: test/frontend/settings-save.test.mjs
 * purpose: Settings save actions preserve unrelated drafts and select scan targets
 * ---------------------------------------------------------------------------*/

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';

const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
const ts = require('typescript');
const source = readFileSync(new URL('../../frontend/src/lib/components/top/SettingsModal.svelte', import.meta.url), 'utf8');
const script = source.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
const imports = [...script.matchAll(/import (\w+) from/g)].map(match => match[1]);
const code = ts.transpileModule(script.replace(/import [\s\S]*?;\s*/g, '') + `
    exports.actions = {
        seed(config, saved, users = []) {
            settings = config;
            savedModels = saved;
            savedWorkflows = structuredClone(config.workflow_locations);
            userTypes = users;
            savedUserTypes = structuredClone(users);
            rememberModelNames();
            modelsDirty = settings.model_types.some(modelDirty);
            workflowsDirty = false;
            editingLocked = false;
        },
        runSave, modelDirty, userDirty,
        get settings() { return settings; },
        get users() { return userTypes; },
        get error() { return error; }
    };
`, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;

function harness(overrides = {}) {
    const scans = [];
    const context = {
        exports: {}, structuredClone, console,
        ...Object.fromEntries(imports.map(name => [name, 'icon'])),
        $state: value => value, $derived: value => value,
        $props: () => ({ onClose() {} }), onMount() {}, SvelteMap: Map,
        $serverUnresponsive: false, statusMonitor: { operation: null, track() {} },
        startScan: async (...args) => { scans.push(args); return { ok: true, data: { id: 'scan' } }; },
        userTypeState: { load: async () => {} },
        ...overrides
    };
    runInNewContext(code, context);
    return { actions: context.exports.actions, scans };
}

const model = name => ({ name, display_name: name, extensions: ['.bin'], locations: [] });
const config = models => ({ model_types: models, workflow_locations: [{ working_dir: 'w', archive_dir: 'a' }] });
const plain = value => JSON.parse(JSON.stringify(value));

test('individual model save preserves other model and workflow drafts', async () => {
    const saved = [model('a'), model('b')];
    const drafts = structuredClone(saved);
    drafts[0].display_name = 'Changed A';
    drafts[1].display_name = 'Unsaved B';
    const { actions, scans } = harness({
        saveModelType: async (type, original) => {
            assert.equal(original, 'a');
            return { ok: true, data: config([structuredClone(type), saved[1]]) };
        }
    });
    actions.seed(config(drafts), saved);
    actions.settings.workflow_locations[0].working_dir = 'unsaved workflow';
    assert.equal(await actions.runSave('models', true, drafts[0]), true);
    assert.equal(actions.settings.model_types[1].display_name, 'Unsaved B');
    assert.equal(actions.modelDirty(drafts[1]), true);
    assert.equal(actions.modelDirty(drafts[0]), false);
    assert.equal(actions.settings.workflow_locations[0].working_dir, 'unsaved workflow');
    assert.deepEqual(plain(scans), [[false, 'models', ['a']]]);
});

test('whole-tab save scans only changed models, while clean Refresh skips saving', async () => {
    const saved = [model('a'), model('b'), model('c')];
    const drafts = structuredClone(saved);
    drafts[0].display_name = 'New A';
    drafts[2].display_name = 'New C';
    let saves = 0;
    const { actions, scans } = harness({
        saveModelSettings: async types => { saves++; return { ok: true, data: config(structuredClone(types)) }; },
        saveModelType: () => assert.fail('clean Refresh must not save')
    });
    actions.seed(config(drafts), saved);
    assert.equal(await actions.runSave('models', true), true);
    assert.deepEqual(plain(scans[0]), [false, 'models', ['a', 'c']]);
    assert.equal(await actions.runSave('models', true, actions.settings.model_types[1]), true);
    assert.deepEqual(plain(scans[1]), [false, 'models', ['b']]);
    assert.equal(saves, 1);
});

test('individual user-type save preserves unrelated drafts and uses its saved ID', async () => {
    const users = [{ id: 'a', name: 'A' }, { id: 'b', name: 'B' }];
    const { actions, scans } = harness({
        updateUserType: async type => ({ ok: true, data: structuredClone(type) })
    });
    actions.seed(config([]), [], users);
    users[0].name = 'Changed A';
    users[1].name = 'Unsaved B';
    assert.equal(await actions.runSave('user-types', true, undefined, users[0]), true);
    assert.equal(actions.userDirty(users[0]), false);
    assert.equal(actions.userDirty(users[1]), true);
    assert.deepEqual(plain(scans), [[false, 'user_objects', ['a']]]);
});

test('failed save does not launch a scan', async () => {
    const saved = [model('a')];
    const drafts = structuredClone(saved);
    drafts[0].display_name = 'Changed';
    const { actions, scans } = harness({ saveModelType: async () => ({ ok: false, message: 'Rejected' }) });
    actions.seed(config(drafts), saved);
    assert.equal(await actions.runSave('models', true, drafts[0]), false);
    assert.equal(actions.modelDirty(drafts[0]), true);
    assert.equal(scans.length, 0);
    assert.equal(actions.error, 'Rejected');
});
