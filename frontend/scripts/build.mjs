/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/scripts/build.mjs
 * purpose: Build the frontend and record input and output fingerprints
 * ---------------------------------------------------------------------------*/

import { createHash } from 'node:crypto';
import { readdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

export const manifestName = 'build-manifest.json';
const frontend = fileURLToPath(new URL('../', import.meta.url));
const requiredInputs = [
    'package.json', 'package-lock.json', 'svelte.config.js', 'vite.config.ts', 'tsconfig.json'
];
const textExtensions = /\.(?:[cm]?[jt]sx?|svelte|json|css|html|svg|md|txt|ya?ml|toml)$/i;

function hash(value) {
    return createHash('sha256').update(value).digest('hex');
}

async function inventory(root, directory) {
    const result = [];
    for (const entry of await readdir(path.join(root, directory), { withFileTypes: true })) {
        const relative = directory ? `${directory}/${entry.name}` : entry.name;
        if (entry.isDirectory()) result.push(...await inventory(root, relative));
        else if (entry.isFile()) result.push(relative);
        else throw new Error(`Unsupported build input/output entry: ${relative}`);
    }
    return result;
}

async function checksums(root, files, normalizeText = false) {
    const result = {};
    for (const file of [...new Set(files)].sort()) {
        let content = await readFile(path.join(root, file));
        // Git checkouts may use CRLF on Windows and LF in CI.
        if (normalizeText && (textExtensions.test(file) || path.basename(file).startsWith('.env')
            || path.basename(file) === '.npmrc')) {
            content = content.toString('utf8').replace(/\r\n/g, '\n');
        }
        result[file] = hash(content);
    }
    return result;
}

export async function fingerprintInputs(root) {
    const files = [...requiredInputs];
    for (const directory of ['src', 'static', 'scripts']) {
        files.push(...await inventory(root, directory));
    }
    for (const entry of await readdir(root, { withFileTypes: true })) {
        if (entry.isFile() && (entry.name.startsWith('.env') || entry.name === '.npmrc')) {
            files.push(entry.name);
        }
    }
    const inputs = await checksums(root, files, true);
    return { fingerprint: hash(JSON.stringify(inputs)), files: inputs };
}

export async function fingerprintOutputs(root) {
    const outputDirectory = path.join(root, 'build');
    const files = (await inventory(outputDirectory, '')).filter(file => file !== manifestName);
    if (!files.includes('index.html')) throw new Error('Build output is missing index.html.');
    return checksums(outputDirectory, files);
}

export async function writeManifest(root, inputsBeforeBuild) {
    const inputs = await fingerprintInputs(root);
    if (inputs.fingerprint !== inputsBeforeBuild.fingerprint) {
        throw new Error('Frontend inputs changed during the build. Run npm run build again.');
    }
    const outputDirectory = path.join(root, 'build');
    const manifest = {
        schemaVersion: 1,
        algorithm: 'sha256',
        inputTextNormalization: 'CRLF to LF',
        nodeVersion: process.version,
        inputs,
        outputs: await fingerprintOutputs(root)
    };
    await writeFile(path.join(outputDirectory, manifestName), JSON.stringify(manifest, null, 2) + '\n');
    return manifest;
}

async function build() {
    if (process.argv.length > 2) {
        throw new Error('The manifest build uses the standard production configuration; custom Vite arguments are not supported.');
    }
    // A failed build must never leave a previous manifest appearing current.
    await rm(path.join(frontend, 'build', manifestName), { force: true });
    const inputs = await fingerprintInputs(frontend);
    const code = await new Promise((resolve, reject) => {
        const child = spawn(process.execPath,
            [path.join(frontend, 'node_modules/vite/bin/vite.js'), 'build'],
            { cwd: frontend, stdio: 'inherit' });
        child.on('error', reject);
        child.on('exit', code => resolve(code ?? 1));
    });
    if (code !== 0) {
        process.exitCode = code;
        return;
    }
    const manifest = await writeManifest(frontend, inputs);
    console.log(`Build manifest saved: ${Object.keys(manifest.outputs).length} output files.`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
    build().catch(error => {
        console.error(error.message);
        process.exitCode = 1;
    });
}
