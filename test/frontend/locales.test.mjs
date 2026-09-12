/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: test/frontend/locales.test.mjs
 * purpose: Validate locale catalogs, metadata, parameters, and About captions
 * ---------------------------------------------------------------------------*/

import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';

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
