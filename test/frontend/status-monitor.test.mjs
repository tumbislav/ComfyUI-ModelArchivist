/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: test/frontend/status-monitor.test.mjs
 * purpose: Operation-only polling, final results, and transient failure regressions
 * ---------------------------------------------------------------------------*/

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';

const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
const ts = require('typescript');
const source = readFileSync(new URL('../../frontend/src/lib/status.svelte.ts', import.meta.url), 'utf8');
const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS }
}).outputText;
const operation = state => ({ id: 'scan-1', type: 'scan', state, progress: {} });

function monitor(request) {
    const timers = new Map();
    const calls = [];
    let nextTimer = 0;
    const context = {
        exports: {},
        $state: value => value,
        require: name => {
            if (name === '$lib/locale.svelte') return { locale: { t: key => key } };
            if (name === '$lib/api') return {
                getUrl: path => path,
                apiFetch: async path => {
                    calls.push(path);
                    return request(path);
                },
                parseResponse: async result => result,
            };
            assert.fail(`Unexpected module ${name}`);
        },
        setTimeout: (callback, delay) => {
            timers.set(++nextTimer, { callback, delay });
            return nextTimer;
        },
        clearTimeout: id => timers.delete(id),
    };
    runInNewContext(code, context);
    return {
        status: context.exports.statusMonitor, calls, timers,
        async tick() {
            const [id, timer] = timers.entries().next().value;
            timers.delete(id);
            timer.callback();
            await settle();
        },
    };
}

async function settle() {
    await new Promise(resolve => setImmediate(resolve));
}

test('initial idle status is fetched once with no recurring timer', async () => {
    const client = monitor(() => ({ ok: true, data: { counts: {}, operation: null } }));
    const stop = client.status.start();
    await settle();
    assert.deepEqual(client.calls, ['/repository-status']);
    assert.equal(client.timers.size, 0);
    stop();
});

for (const finalState of ['succeeded', 'failed']) {
    test(`tracked operation retrieves ${finalState} result and stops polling`, async () => {
        let state = 'running';
        const client = monitor(path => ({ ok: true, data: path.startsWith('/operations/')
            ? operation(state) : { counts: {}, operation: null } }));
        client.status.start();
        await settle();
        client.status.track(operation('pending'));
        await client.tick();
        assert.equal(client.status.operation.state, 'running');
        assert.equal(client.timers.size, 1);
        state = finalState;
        await client.tick();
        assert.equal(client.status.operation.state, finalState);
        assert.equal(client.status.scanRevision, 1);
        assert.equal(client.timers.size, 0);
        assert.equal(client.calls.filter(path => path === '/operations/scan-1').length, 2);
    });
}

test('transient failure retains tracked operation until recovery and completion', async () => {
    let broken = false;
    const client = monitor(path => broken
        ? { ok: false, status: 503, message: 'Unavailable' }
        : { ok: true, data: path.startsWith('/operations/')
            ? operation('succeeded') : { counts: {}, operation: null } });
    client.status.start();
    await settle();
    broken = true;
    client.status.track(operation('running'));
    await client.tick();
    assert.equal(client.status.operation.state, 'running');
    assert.equal(client.status.scanRevision, 0);
    assert.equal(client.status.error, 'Unavailable');
    assert.equal(client.timers.size, 1);
    broken = false;
    await client.tick();
    assert.equal(client.status.operation.state, 'succeeded');
    assert.equal(client.status.scanRevision, 1);
    assert.equal(client.status.error, null);
    assert.equal(client.timers.size, 0);
});

test('repeated scan results refresh once while each new completed scan refreshes again', async () => {
    let id = 'scan-1';
    const client = monitor(path => ({ ok: true, data: path.startsWith('/operations/')
        ? { ...operation('succeeded'), id } : { counts: {}, operation: null } }));
    client.status.start();
    await settle();

    for (const nextId of ['scan-1', 'scan-1', 'scan-2']) {
        id = nextId;
        client.status.track({ ...operation('pending'), id });
        await client.tick();
        assert.equal(client.status.scanRevision, id === 'scan-1' ? 1 : 2);
    }
});

test('completed non-scan operations do not request a scan refresh', async () => {
    const move = { ...operation('succeeded'), type: 'model_move' };
    const client = monitor(path => ({ ok: true, data: path.startsWith('/operations/')
        ? move : { counts: {}, operation: null } }));
    client.status.start();
    await settle();
    client.status.track({ ...move, state: 'pending' });
    await client.tick();
    assert.equal(client.status.scanRevision, 0);
});

test('a scan discovered through repository status refreshes partial results and retains its error', async () => {
    let state = 'running';
    const failure = { type: 'ScanError', message: 'Some folders could not be read' };
    const client = monitor(() => ({ ok: true, data: {
        counts: {}, operation: { ...operation(state), error: state === 'failed' ? failure : null }
    } }));
    client.status.start();
    await settle();
    assert.equal(client.status.scanRevision, 0);
    state = 'failed';
    await client.tick();
    assert.equal(client.status.scanRevision, 1);
    assert.equal(client.status.operation.error, failure);
    assert.equal(client.timers.size, 0);
});

test('an operation submitted during initial status fetch is not lost', async () => {
    let release;
    const initial = new Promise(resolve => { release = resolve; });
    let first = true;
    const client = monitor(path => {
        if (first) {
            first = false;
            return initial;
        }
        return { ok: true, data: path.startsWith('/operations/')
            ? operation('succeeded') : { counts: {}, operation: null } };
    });
    client.status.start();
    client.status.track(operation('pending'));
    await client.tick();
    release({ ok: true, data: { counts: {}, operation: null } });
    await settle();
    assert.equal(client.status.operation.state, 'pending');
    await client.tick();
    assert.equal(client.status.operation.state, 'succeeded');
    assert.equal(client.timers.size, 0);
});
