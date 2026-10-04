/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: test/frontend/comfy-extension.test.mjs
 * purpose: Validate ComfyUI launcher assets and icon registration
 * ---------------------------------------------------------------------------*/

import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';

const root = process.cwd();

test('ComfyUI launcher embeds the Archivist SVG directly in the button', async () => {
    const extension = await readFile(path.join(root, 'web', 'archivist.js'), 'utf8');

    assert.match(extension, /const ICON_SVG = `<svg[\s\S]*<\/svg>`;/);
    assert.doesNotMatch(extension, /assets\/archivist-icon\.svg/);
    assert.doesNotMatch(extension, /data:image/);
    assert.match(extension, /icon: ICON_CLASS/);
    assert.match(extension, /template\.innerHTML = ICON_SVG/);
    assert.match(extension, /icon\.replaceWith\(svg\)/);
    assert.match(extension, /requestAnimationFrame\(\(\) => attachArchivistIcon\(\)\)/);
    assert.doesNotMatch(extension, /pi pi-box/);
});
