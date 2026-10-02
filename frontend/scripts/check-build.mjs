/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/scripts/check-build.mjs
 * purpose: Reject stale, incomplete, or uncommitted production builds
 * ---------------------------------------------------------------------------*/

import { readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { fingerprintInputs, fingerprintOutputs, manifestName } from './build.mjs';

function differences(expected, actual, label) {
    const problems = [];
    for (const name of new Set([...Object.keys(expected), ...Object.keys(actual)])) {
        if (!(name in actual)) problems.push(`${label} missing: ${name}`);
        else if (!(name in expected)) problems.push(`${label} added: ${name}`);
        else if (expected[name] !== actual[name]) problems.push(`${label} changed: ${name}`);
    }
    return problems;
}

export async function checkBuild(root, committed = false) {
    const manifest = JSON.parse(await readFile(path.join(root, 'build', manifestName), 'utf8'));
    if (manifest.schemaVersion !== 1 || manifest.algorithm !== 'sha256'
        || manifest.inputTextNormalization !== 'CRLF to LF'
        || !manifest.inputs?.files || !manifest.outputs) {
        throw new Error('Unsupported or invalid build manifest.');
    }
    const inputs = await fingerprintInputs(root);
    const outputs = await fingerprintOutputs(root);
    const problems = [
        ...differences(manifest.inputs.files, inputs.files, 'Input'),
        ...differences(manifest.outputs, outputs, 'Output')
    ];
    if (manifest.inputs.fingerprint !== inputs.fingerprint) {
        problems.unshift('The build input fingerprint does not match.');
    }
    if (committed) {
        const repo = path.dirname(root);
        const tracked = new Set(execFileSync('git', ['ls-files', '-z', '--', 'frontend'],
            { cwd: repo, encoding: 'utf8' }).split('\0'));
        const required = [
            ...Object.keys(inputs.files).map(name => `frontend/${name}`),
            ...Object.keys(outputs).map(name => `frontend/build/${name}`),
            `frontend/build/${manifestName}`
        ];
        for (const file of required) {
            if (!tracked.has(file)) problems.push(`Not tracked by Git: ${file}`);
        }
        const status = execFileSync('git', ['status', '--porcelain', '--untracked-files=all',
            '--', ...required], { cwd: repo, encoding: 'utf8' }).trim();
        if (status) problems.push(`Uncommitted frontend inputs or output:\n${status}`);
    }
    if (problems.length) throw new Error(problems.join('\n'));
    return Object.keys(outputs).length;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
    const args = process.argv.slice(2);
    const root = fileURLToPath(new URL('../', import.meta.url));
    Promise.resolve().then(() => {
        if (args.some(arg => arg !== '--committed')) throw new Error('Usage: npm run check:build -- [--committed]');
        return checkBuild(root, args.includes('--committed'));
    }).then(count => console.log(`Frontend build is current and complete (${count} files).`))
        .catch(error => {
            console.error(`Build verification failed: ${error.message}`);
            console.error('Run npm run build from frontend/. For a committed build, stage and commit all inputs and frontend/build/.');
            process.exitCode = 1;
        });
}
