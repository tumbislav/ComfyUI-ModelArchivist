/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: test/frontend/locales.test.mjs
 * purpose: Validate locale catalogs, metadata, parameters, and About captions
 * ---------------------------------------------------------------------------*/

import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';

const root = process.cwd();
const localeDirectory = path.join(root, 'frontend', 'src', 'lib', 'locales');
const logoDirectory = path.join(root, 'frontend', 'src', 'lib', 'assets', 'images', 'logo');

const readJson = async file => JSON.parse(await readFile(path.join(localeDirectory, file), 'utf8'));

function leaves(value, prefix = '', result = new Map()) {
    for (const [key, child] of Object.entries(value)) {
        const path = prefix ? `${prefix}.${key}` : key;

        if (child !== null && typeof child === 'object') leaves(child, path, result);
        else result.set(path, child);
    }

    return result;
}

function parameters(value) {
    return [...String(value).matchAll(/\{([A-Za-z0-9_]+)\}/g)].map(match => match[1]).sort();
}

test('configured locales mirror the complete English catalog', async () => {
    const config = await readJson('config.json');
    const english = leaves(await readJson('en.json'));

    for (const [language, metadata] of Object.entries(config.locales)) {
        assert.match(language, /^[a-z]{2,3}(?:-[A-Za-z0-9]+)*$/);
        assert.ok(['ltr', 'rtl'].includes(metadata.direction));
        assert.ok(metadata.font in config.fonts);

        const catalog = leaves(await readJson(`${language}.json`));
        assert.deepEqual([...catalog.keys()], [...english.keys()], `${language} catalog keys`);

        for (const [key, value] of catalog) {
            if (value !== null) {
                assert.equal(typeof value, 'string', `${language}:${key} must be text or null`);
                assert.deepEqual(parameters(value), parameters(english.get(key)),
                    `${language}:${key} parameters`);
            }
        }
    }
});

test('English contains one About caption entry for every Library image', async () => {
    const english = await readJson('en.json');
    const images = (await readdir(logoDirectory))
        .filter(file => /^Library-.*\.png$/.test(file))
        .map(file => file.replace(/\.png$/, ''))
        .sort();

    assert.deepEqual(Object.keys(english.about.captions).sort(), images);
    assert.equal((await readdir(logoDirectory)).some(file => /^Library-.*\.html$/.test(file)), false);
});


test('every stored object error and operation rejection has a display message', async () => {
    const english = await readJson('en.json');
    const tables = await readFile(path.join(root, 'backend/repository/tables.py'), 'utf8');
    const enums = [...tables.matchAll(/class (?:Model|Workflow|UserObject)Error\(StrEnum\):([\s\S]*?)(?=\n\n)/g)];
    const repository = await readFile(path.join(root, 'backend/repository/repository.py'), 'utf8');
    const codes = [
        ...enums.flatMap(match => [...match[1].matchAll(/= '([^']+)'/g)].map(value => value[1])),
        ...[...repository.matchAll(/(?:reject|OperationIssue)\(\s*'([^']+)'/g)].map(match => match[1])
    ];

    for (const code of codes) {
        assert.equal(typeof english.errors[code], 'string', code);
        assert.notEqual(english.errors[code], code);
    }
});

test('error display resolves codes, falls back to English, and retains unknown details', async () => {
    const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
    const ts = require('typescript');
    const source = (await readFile(path.join(root, 'frontend/src/lib/locale.svelte.ts'), 'utf8'))
        .replace('import.meta.env.DEV', 'false');
    const catalogs = Object.fromEntries(await Promise.all(
        ['config', 'en', 'es', 'fr', 'sl'].map(async name => [name, await readJson(`${name}.json`)])));
    const context = {
        exports: {}, $state: value => value,
        require: name => ({ default: catalogs[name.split('/').at(-1).replace('.json', '')] })
    };
    runInNewContext(ts.transpileModule(source, {
        compilerOptions: { module: ts.ModuleKind.CommonJS }
    }).outputText, context);
    const { locale } = context.exports;

    for (const language of ['en', 'es', 'fr', 'sl']) {
        locale.language = language;
        assert.equal(locale.error('location_mismatch'), catalogs.en.errors.location_mismatch);
        assert.equal(locale.error('unrecognized_code'), 'unrecognized_code');
        assert.equal(locale.error({ code: 'future_error', message: 'Original detail' }), 'Original detail');
        assert.equal(locale.error({ code: 'location_mismatch' }), catalogs.en.errors.location_mismatch);
        assert.match(locale.error({ code: 'filesystem_error', message: '/private/file: denied' }),
            /\/private\/file: denied/);
    }
});
