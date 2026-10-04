/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: test/frontend/session.test.mjs
 * purpose: Launcher handoff, tab sessions, and credential containment regressions
 * ---------------------------------------------------------------------------*/

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';

const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
const ts = require('typescript');
const source = readFileSync(new URL('../../frontend/src/lib/session.ts', import.meta.url), 'utf8');
const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS }
}).outputText;

function client(fragment = '', stored = new Map(), blocked = false) {
    const location = new URL(`http://localhost:8000/model-archivist/${fragment}`);
    const context = {
        exports: {}, URL, URLSearchParams, Headers, Request,
        window: {
            location,
            history: {
                state: {},
                replaceState(_state, _title, url) { location.href = new URL(url, location).href; }
            },
            sessionStorage: {
                getItem: key => stored.get(key) ?? null,
                setItem: (key, value) => {
                    if (blocked) throw new Error('Storage blocked');
                    stored.set(key, value);
                }
            }
        }
    };
    runInNewContext(code, context);
    return { ...context.exports, location, stored };
}

const path = '/model-archivist/api/health';

test('startup token is removed from URL and retained across tab reloads', () => {
    const first = client('#archivist-session=secret');
    assert.equal(first.location.hash, '');
    const headers = first.sessionHeaders(path, {});
    assert.equal(headers.get('X-Archivist-Session'), 'secret');
    assert.equal(headers.get('X-Archivist-Request'), '1');
    const reload = client('', first.stored);
    assert.equal(reload.sessionHeaders(path, {}).get('X-Archivist-Session'), 'secret');
    assert.equal(client().sessionHeaders(path, {}).get('X-Archivist-Session'), null);
});

test('Comfy launch replaces an old standalone session with the selected profile', () => {
    const first = client('#archivist-session=secret');
    const embedded = client('#comfy-user=named-profile', first.stored);
    const headers = embedded.sessionHeaders(path, { headers: {
        'X-Archivist-Internal': 'forged', 'X-Archivist-Session': 'stale', 'Content-Type': 'application/json'
    } });
    assert.equal(headers.get('Comfy-User'), 'named-profile');
    assert.equal(headers.get('X-Archivist-Session'), null);
    assert.equal(headers.get('X-Archivist-Internal'), null);
    assert.equal(headers.get('Content-Type'), 'application/json');
});

test('credentials cannot be sent to other origins, ports, or routes', () => {
    const session = client('#archivist-session=secret');
    for (const target of ['https://evil.example/model-archivist/api/health',
        'http://localhost:9000/model-archivist/api/health', '/other', '/model-archivist/api/../asset.js']) {
        assert.throws(() => session.sessionHeaders(target, {}), /same-origin API/);
    }
});

test('blocked storage keeps startup access in memory and still clears the URL', () => {
    const session = client('#archivist-session=secret', new Map(), true);
    assert.equal(session.location.hash, '');
    assert.equal(session.sessionHeaders(path, {}).get('X-Archivist-Session'), 'secret');
});
