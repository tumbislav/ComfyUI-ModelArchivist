/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: test/frontend/api.test.mjs
 * purpose: API timeout, connectivity, and recovery regressions
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
const source = readFileSync(new URL('../../frontend/src/lib/api.ts', import.meta.url), 'utf8');
const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS }
}).outputText;

function client(fetch) {
    const timers = new Map();
    let nextTimer = 0;
    const context = {
        exports: {}, Response, AbortController, DOMException, URL, fetch,
        require: name => {
            if (name === 'svelte/store') return stores;
            if (name === '$lib/locale.svelte') return { locale: { t: key => ({
                'errors.request_cancelled': 'Request cancelled',
                'errors.server_unresponsive': 'The server is not responding'
            })[key] } };

            assert.fail(`Unexpected module ${name}`);
        },
        setTimeout: (callback, delay) => {
            assert.equal(delay, 3000);
            timers.set(++nextTimer, callback);
            return nextTimer;
        },
        clearTimeout: id => timers.delete(id)
    };
    runInNewContext(code, context);
    return { api: context.exports, timers, context };
}

function stalled(signal) {
    if (signal.aborted) return Promise.reject(signal.reason);

    return new Promise((resolve, reject) => {
        signal.addEventListener('abort', () => reject(signal.reason), { once: true });
    });
}

for (const phase of ['headers', 'body']) {
    test(`three-second timeout includes stalled ${phase} and later requests recover`, async () => {
        const { api, timers, context } = client(async (url, { signal }) => {
            if (phase === 'headers') return stalled(signal);
            return { arrayBuffer: () => stalled(signal) };
        });
        const pending = api.apiFetch('/test');
        await Promise.resolve();
        [...timers.values()][0]();
        const result = await api.parseResponse(await pending, value => value, 'test');
        assert.equal(result.ok, false);
        assert.equal(result.message, 'The server is not responding');
        assert.equal(stores.get(api.serverUnresponsive), true);
        assert.equal(timers.size, 0);

        context.fetch = async () => Response.json({ ready: true });
        const recovered = await api.parseResponse(await api.apiFetch('/test'), value => value, 'test');
        assert.equal(recovered.data.ready, true);
        assert.equal(stores.get(api.serverUnresponsive), false);
    });
}

test('network failures and gateway timeouts are distinguished from application rejections', async () => {
    const { api, context } = client(async () => { throw new TypeError('network unavailable'); });
    await api.apiFetch('/test');
    assert.equal(stores.get(api.serverUnresponsive), true);

    for (const status of [408, 502, 503, 504]) {
        context.fetch = async () => new Response('Unavailable', { status });
        await api.apiFetch('/test');
        assert.equal(stores.get(api.serverUnresponsive), true);
    }

    context.fetch = async () => Response.json({ detail: 'Busy' }, { status: 409 });
    const result = await api.parseResponse(await api.apiFetch('/test'), value => value, 'test');
    assert.equal(result.message, 'Busy');
    assert.equal(stores.get(api.serverUnresponsive), false);
});

test('an older response cannot clear a newer timeout', async () => {
    let finishOld;
    const { api, context } = client(() => new Promise(resolve => { finishOld = resolve; }));
    const old = api.apiFetch('/old');
    context.fetch = async () => { throw new TypeError('offline'); };
    await api.apiFetch('/new');
    finishOld(Response.json({}));
    await old;
    assert.equal(stores.get(api.serverUnresponsive), true);
});

test('intentional cancellation does not mark the server unresponsive', async () => {
    const { api, timers } = client((url, { signal }) => stalled(signal));
    const controller = new AbortController();
    const pending = api.apiFetch('/test', { signal: controller.signal });
    controller.abort();
    assert.equal((await pending).status, 499);
    assert.equal(stores.get(api.serverUnresponsive), false);
    assert.equal(timers.size, 0);
});

test('interactive requests can wait without triggering the server timeout', async () => {
    let finish;
    const { api, timers } = client(() => new Promise(resolve => { finish = resolve; }));

    const pending = api.apiFetch('/picker', {}, null);
    assert.equal(timers.size, 0);
    assert.equal(stores.get(api.serverUnresponsive), false);
    finish(Response.json({path: 'C:\\models'}));
    assert.equal((await pending).status, 200);
});

test('all frontend API callers use the timeout wrapper', async () => {
    const { readdir } = await import('node:fs/promises');
    const root = new URL('../../frontend/src/', import.meta.url);
    for (const name of await readdir(root, { recursive: true })) {
        if (!/\.(ts|svelte)$/.test(name) || name.replaceAll('\\', '/') === 'lib/api.ts') continue;
        assert.doesNotMatch(readFileSync(new URL(name.replaceAll('\\', '/'), root), 'utf8'), /\bfetch\(/, name);
    }
});
