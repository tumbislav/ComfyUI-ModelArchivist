/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: test/frontend/preferences.test.mjs
 * purpose: Regression tests for browser preference persistence and defaults
 * ---------------------------------------------------------------------------*/

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';

const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
const ts = require('typescript');
const source = readFileSync(new URL('../../frontend/src/lib/preferences.ts', import.meta.url), 'utf8');
const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS }
}).outputText;

function browser(storage = new Map()) {
    const context = {
        exports: {},
        localStorage: {
            getItem: key => storage.get(key) ?? null,
            setItem: (key, value) => storage.set(key, value)
        }
    };
    runInNewContext(code, context);
    return context.exports;
}

test('tab restoration is opt-in and persists all four tabs across reloads', () => {
    const storage = new Map();
    const preferences = browser(storage);
    assert.equal(preferences.rememberLastTab(), false);
    assert.equal(preferences.initialTab(), 'models');

    preferences.saveRememberLastTab(true);
    for (const tab of ['models', 'workflows', 'user', 'collections']) {
        preferences.saveLastTab(tab);
        assert.equal(browser(storage).initialTab(), tab);
    }

    preferences.saveRememberLastTab(false);
    assert.equal(browser(storage).initialTab(), 'models');
    preferences.saveRememberLastTab(true);
    storage.set('archivist.lastTab', 'invalid');
    assert.equal(browser(storage).initialTab(), 'models');
});

test('theme persists independently of the tab option and accepts only known values', () => {
    const storage = new Map();
    const preferences = browser(storage);
    assert.equal(preferences.savedTheme(), 'light');

    for (const theme of ['dark', 'light']) {
        preferences.saveTheme(theme);
        assert.equal(browser(storage).savedTheme(), theme);
    }

    storage.set('theme', 'invalid');
    assert.equal(browser(storage).savedTheme(), 'light');
});

test('blocked storage leaves navigation and theme usable with defaults', () => {
    const preferences = browser({
        get() { throw new Error('blocked'); },
        set() { throw new Error('blocked'); }
    });
    assert.equal(preferences.initialTab(), 'models');
    assert.equal(preferences.savedTheme(), 'light');
    assert.doesNotThrow(() => preferences.saveLastTab('collections'));
    assert.doesNotThrow(() => preferences.saveTheme('dark'));
});
