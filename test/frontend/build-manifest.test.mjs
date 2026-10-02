/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: test/frontend/build-manifest.test.mjs
 * purpose: Verify build freshness fingerprints and output integrity records
 * ---------------------------------------------------------------------------*/

import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fingerprintInputs, manifestName, writeManifest } from '../../frontend/scripts/build.mjs';
import { checkBuild } from '../../frontend/scripts/check-build.mjs';
import { execFileSync } from 'node:child_process';

async function fixture(t) {
    const root = await mkdtemp(path.join(os.tmpdir(), 'archivist-build-'));
    t.after(() => rm(root, { recursive: true, force: true }));
    for (const directory of ['src', 'static', 'scripts', 'build']) {
        await mkdir(path.join(root, directory));
    }
    for (const file of ['package.json', 'package-lock.json', 'svelte.config.js',
        'vite.config.ts', 'tsconfig.json', 'src/app.svelte']) {
        await writeFile(path.join(root, file), 'original\n');
    }
    await writeFile(path.join(root, 'build/index.html'), '<html></html>');
    return root;
}

test('input fingerprints detect additions, edits, and deletions but ignore checkout line endings', async t => {
    const root = await fixture(t);
    const original = await fingerprintInputs(root);
    await writeFile(path.join(root, 'src/app.svelte'), 'original\r\n');
    assert.deepEqual(await fingerprintInputs(root), original);
    await writeFile(path.join(root, 'static/new.png'), Buffer.from([0, 1, 2]));
    assert.notEqual((await fingerprintInputs(root)).fingerprint, original.fingerprint);
    await rm(path.join(root, 'static/new.png'));
    assert.deepEqual(await fingerprintInputs(root), original);
    await writeFile(path.join(root, 'package-lock.json'), 'changed\n');
    assert.notEqual((await fingerprintInputs(root)).fingerprint, original.fingerprint);
});

test('manifest records every output except itself and does not fingerprint generated files as inputs', async t => {
    const root = await fixture(t);
    const inputs = await fingerprintInputs(root);
    await writeFile(path.join(root, 'build/app.abc123.js'), 'console.log(1)');
    const manifest = await writeManifest(root, inputs);
    assert.deepEqual(Object.keys(manifest.outputs), ['app.abc123.js', 'index.html']);
    assert.deepEqual(JSON.parse(await readFile(path.join(root, 'build', manifestName))), manifest);
    assert.deepEqual(await fingerprintInputs(root), inputs);
    assert.deepEqual(await writeManifest(root, inputs), manifest);
    await writeFile(path.join(root, 'build/app.abc123.js'), 'console.log(2)');
    const changed = await writeManifest(root, inputs);
    assert.notEqual(changed.outputs['app.abc123.js'], manifest.outputs['app.abc123.js']);
});

test('changed sources during a build and missing output prevent a manifest being written', async t => {
    const root = await fixture(t);
    const inputs = await fingerprintInputs(root);
    await writeFile(path.join(root, 'src/app.svelte'), 'changed');
    await assert.rejects(writeManifest(root, inputs), /changed during the build/);
    await assert.rejects(readFile(path.join(root, 'build', manifestName)), { code: 'ENOENT' });
    await rm(path.join(root, 'build/index.html'));
    await assert.rejects(writeManifest(root, await fingerprintInputs(root)), /missing index.html/);
});

test('checker rejects missing, added, changed output and stale sources without rewriting the manifest', async t => {
    const root = await fixture(t);
    await writeManifest(root, await fingerprintInputs(root));
    assert.equal(await checkBuild(root), 1);
    const before = await readFile(path.join(root, 'build', manifestName), 'utf8');
    await writeFile(path.join(root, 'build/forgotten.js'), 'new chunk');
    await assert.rejects(checkBuild(root), /Output added: forgotten.js/);
    await rm(path.join(root, 'build/forgotten.js'));
    await writeFile(path.join(root, 'build/index.html'), 'changed');
    await assert.rejects(checkBuild(root), /Output changed: index.html/);
    await writeFile(path.join(root, 'build/index.html'), '<html></html>');
    await writeFile(path.join(root, 'src/app.svelte'), 'changed');
    await assert.rejects(checkBuild(root), /Input changed: src\/app.svelte/);
    assert.equal(await readFile(path.join(root, 'build', manifestName), 'utf8'), before);
    await rm(path.join(root, 'build/index.html'));
    await assert.rejects(checkBuild(root), /missing index.html/);
});

test('committed checker catches files omitted from Git and staged changes', async t => {
    const repo = await mkdtemp(path.join(os.tmpdir(), 'archivist-build-git-'));
    t.after(() => rm(repo, { recursive: true, force: true }));
    const source = await fixture(t);
    const { cp } = await import('node:fs/promises');
    const root = path.join(repo, 'frontend');
    await cp(source, root, { recursive: true });
    const git = (...args) => execFileSync('git', args, { cwd: repo, stdio: 'pipe' });
    git('init');
    git('config', 'user.name', 'Manifest test');
    git('config', 'user.email', 'manifest@example.invalid');
    git('config', 'core.autocrlf', 'false');
    git('config', 'commit.gpgsign', 'false');
    await writeManifest(root, await fingerprintInputs(root));
    git('add', '.');
    git('commit', '-m', 'Fixture');
    assert.equal(await checkBuild(root, true), 1);
    await writeFile(path.join(root, 'build/new.js'), 'new');
    await writeManifest(root, await fingerprintInputs(root));
    await assert.rejects(checkBuild(root, true), /Not tracked by Git: frontend\/build\/new.js/);
    git('add', '.');
    await assert.rejects(checkBuild(root, true), /Uncommitted frontend/);
    git('commit', '-m', 'Updated build');
    assert.equal(await checkBuild(root, true), 2);
});
