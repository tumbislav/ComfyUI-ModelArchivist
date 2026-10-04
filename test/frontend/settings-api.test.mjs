/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: test/frontend/settings-api.test.mjs
 * purpose: Settings API request behavior regressions
 * ---------------------------------------------------------------------------*/

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';

const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
const ts = require('typescript');
const source = readFileSync(new URL('../../frontend/src/lib/settings.ts', import.meta.url), 'utf8');
const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS }
}).outputText;

function client() {
    const calls = [];
    const context = {
        exports: {}, Response,
        require: name => {
            if (name === '$lib/api') return {
                apiFetch: async (...args) => {
                    calls.push(args);
                    return Response.json([]);
                },
                getUrl: path => path,
                parseResponse: async response => ({ ok: true, data: await response.json() })
            };

            assert.fail(`Unexpected module ${name}`);
        }
    };
    runInNewContext(code, context);
    return { settings: context.exports, calls };
}

test('model mapping discovery is not cancelled by the generic API timeout', async () => {
    const { settings, calls } = client();

    await settings.previewModelMappings('C:\\models', 'C:\\archive', ['.safetensors']);

    assert.equal(calls.length, 1);
    assert.equal(calls[0][0], '/config/model-mapping-preview');
    assert.equal(calls[0][2], null);
});
