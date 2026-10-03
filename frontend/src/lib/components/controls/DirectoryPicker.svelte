<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: DirectoryPicker.svelte
 ! purpose: Lazy, policy-confined server directory selection
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import { onMount, tick } from 'svelte';
    import { modalDialog } from '$lib/modal-dialog';
    import { locale } from '$lib/locale.svelte';
    import { getDirectories, getDirectoryRoots, type DirectoryEntry,
        type DirectoryListing, type DirectoryRole } from '$lib/settings';

    let { role, initialPath, onSelect, onClose }: {
        role: DirectoryRole;
        initialPath: string;
        onSelect: (path: string) => void;
        onClose: () => void;
    } = $props();

    let roots = $state<DirectoryEntry[]>([]);
    let listings = $state<Record<string, DirectoryListing>>({});
    let expanded = $state<string[]>([]);
    let current = $state<DirectoryListing | null>(null);
    let error = $state('');
    let busy = $state(true);
    let focused = $state('');
    let tree: HTMLElement;
    let alive = true;
    let sequence = 0;

    type Row = DirectoryEntry & { depth: number; parent: string | null };
    let rows = $derived.by(() => {
        const result: Row[] = [];
        function visit(entries: DirectoryEntry[], depth: number, parent: string | null) {
            for (const entry of entries) {
                result.push({ ...entry, depth, parent });
                if (expanded.includes(entry.path)) {
                    visit(listings[entry.path]?.directories ?? [], depth + 1, entry.path);
                }
            }
        }
        visit(roots, 1, null);
        return result;
    });

    // Keep the nested modal outside the location field's enclosing label/fieldset.
    function dialog(node: HTMLDialogElement) {
        const previous = document.activeElement as HTMLElement | null;
        document.body.append(node);
        const action = modalDialog(node);
        return { destroy() {
            action.destroy();
            node.remove();
            previous?.focus();
        } };
    }

    async function navigate(path: string, reveal = false): Promise<void> {
        const request = ++sequence;
        busy = true;
        error = '';
        current = null;
        const result = await getDirectories(path, role);
        if (!alive || request !== sequence) return;
        if (!result.ok) {
            error = result.message ?? locale.t('picker.failed');
            busy = false;
            return;
        }
        const listing = result.data;
        if (reveal) {
            for (const ancestor of listing.ancestors.slice(0, -1)) {
                const parent = await getDirectories(ancestor, role);
                if (!alive || request !== sequence) return;
                if (!parent.ok) {
                    error = parent.message ?? locale.t('picker.failed');
                    busy = false;
                    return;
                }
                listings[ancestor] = parent.data;
                if (!expanded.includes(ancestor)) expanded = [...expanded, ancestor];
            }
        }
        listings[listing.path] = listing;
        if (!expanded.includes(listing.path)) expanded = [...expanded, listing.path];
        current = listing;
        focused = listing.path;
        busy = false;
        await focusRow(listing.path);
    }

    async function focusRow(path: string) {
        focused = path;
        await tick();
        const index = rows.findIndex(row => row.path === path);
        tree?.querySelectorAll<HTMLElement>('[role="treeitem"]')[index]?.focus();
    }

    async function keydown(event: KeyboardEvent, row: Row) {
        const index = rows.findIndex(item => item.path === row.path);
        const commands = ['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight', 'Home', 'End', 'Enter', ' '];
        if (!commands.includes(event.key)) return;
        event.preventDefault();
        if (event.key === 'ArrowDown') await focusRow(rows[Math.min(index + 1, rows.length - 1)].path);
        else if (event.key === 'ArrowUp') await focusRow(rows[Math.max(index - 1, 0)].path);
        else if (event.key === 'Home') await focusRow(rows[0].path);
        else if (event.key === 'End') await focusRow(rows[rows.length - 1].path);
        else if (event.key === 'ArrowLeft') {
            if (expanded.includes(row.path)) expanded = expanded.filter(path => path !== row.path);
            else if (row.parent) await focusRow(row.parent);
        } else if (event.key === 'ArrowRight' && expanded.includes(row.path)) {
            const child = listings[row.path]?.directories[0];
            if (child) await focusRow(child.path);
        } else if (!busy) {
            if (row.issue) {
                current = null;
                error = locale.error(row.issue);
            }
            else {
                await navigate(row.path);
                await focusRow(row.path);
            }
        }
    }

    async function select() {
        if (!current || busy) return;
        const path = current.path;
        const request = ++sequence;
        busy = true;
        const result = await getDirectories(path, role);
        if (!alive || request !== sequence) return;
        busy = false;
        if (result.ok) onSelect(result.data.path);
        else {
            current = null;
            error = result.message ?? locale.t('picker.failed');
        }
    }

    onMount(() => {
        void (async () => {
            const result = await getDirectoryRoots(role);
            if (!alive) return;
            busy = false;
            if (!result.ok) {
                error = result.message ?? locale.t('picker.failed');
                return;
            }
            roots = result.data;
            focused = roots[0]?.path ?? '';
            if (initialPath.trim()) await navigate(initialPath, true);
            else if (roots.find(root => !root.issue)) {
                await navigate(roots.find(root => !root.issue)!.path);
            }
        })();
        return () => { alive = false; sequence++; };
    });
</script>

<dialog use:dialog class="directory-picker" aria-label={locale.t(`picker.${role}`)}
        oncancel={event => { event.preventDefault(); onClose(); }}>
    <header class="dialog-header">
        <h2>{locale.t(`picker.${role}`)}</h2>
        <button type="button" onclick={onClose} aria-label={locale.t('picker.cancel')}>×</button>
    </header>
    <p>{locale.t('picker.help')}</p>
    <div class="picker-location">
        <button type="button" disabled={busy || !current?.parent}
                onclick={() => current?.parent && navigate(current.parent)}>{locale.t('picker.up')}</button>
        <output aria-live="polite">{current?.path ?? locale.t('picker.choose')}</output>
    </div>
    <div class="picker-panels" aria-busy={busy}>
        <div class="picker-tree" role="tree" aria-label={locale.t('picker.roots')} bind:this={tree}>
            {#each rows as row}
                <div role="treeitem" aria-level={row.depth}
                     aria-selected={current?.path === row.path}
                     aria-expanded={expanded.includes(row.path)}
                     tabindex={focused === row.path ? 0 : -1}
                     style:padding-left={`${(row.depth - 1) * 1.1 + 0.3}rem`}
                     onfocus={() => focused = row.path}
                     onkeydown={event => keydown(event, row)}
                     onclick={() => {
                         if (busy) return;
                         if (row.issue) {
                             current = null;
                             error = locale.error(row.issue);
                         } else {
                             void navigate(row.path);
                         }
                     }}>
                    <button type="button" tabindex="-1" disabled={busy || !!row.issue}
                            aria-label={locale.t(expanded.includes(row.path) ? 'picker.collapse' : 'picker.expand')}
                            onclick={event => {
                                event.stopPropagation();
                                if (expanded.includes(row.path)) expanded = expanded.filter(path => path !== row.path);
                                else void navigate(row.path);
                            }}>{expanded.includes(row.path) ? '▾' : '▸'}</button>
                    <span>{row.name}{row.issue ? ' ⚠' : ''}</span>
                </div>
            {/each}
            {#if !busy && roots.length === 0}<p>{locale.t('picker.no_roots')}</p>{/if}
        </div>
        <section class="picker-folders" aria-label={locale.t('picker.folders')}>
            {#if busy}<p role="status">{locale.t('picker.loading')}</p>{/if}
            {#if error}<p class="error-message" role="alert">{error}</p>{/if}
            {#if current && !busy}
                {#each current.directories as folder (folder.path)}
                    <button type="button" class="picker-folder" onclick={() => navigate(folder.path, true)}>
                        <span aria-hidden="true">▸</span> {folder.name}
                    </button>
                {:else}
                    <p>{locale.t('picker.empty')}</p>
                {/each}
                {#if current.omitted}<p>{locale.t('picker.omitted')}</p>{/if}
            {/if}
        </section>
    </div>
    <footer class="picker-actions">
        <button type="button" onclick={onClose}>{locale.t('picker.cancel')}</button>
        <button type="button" disabled={busy || !current} onclick={select}>{locale.t('picker.use')}</button>
    </footer>
</dialog>

<style>
    .directory-picker {
        width: 54rem;
        max-width: 95vw;
        max-height: 90vh;
        overflow: auto;
    }
    .directory-picker::backdrop {
        background: rgb(0 0 0 / 35%);
    }
    .picker-location {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        margin-block: 0.6rem;
    }
    output {
        overflow-wrap: anywhere;
        min-width: 0;
    }
    .picker-panels {
        display: grid;
        grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
        height: 20rem;
        border: var(--solid-border);
    }
    .picker-tree, .picker-folders {
        overflow: auto;
        padding: 0.4rem;
        min-width: 0;
    }
    .picker-tree {
        border-right: var(--solid-border);
    }
    [role="treeitem"] {
        display: flex;
        align-items: center;
        cursor: pointer;
        overflow-wrap: anywhere;
        min-height: 2rem;
    }
    [role="treeitem"][aria-selected="true"] {
        background: var(--bg-accent);
    }
    [role="treeitem"]:focus-visible {
        outline: 2px solid currentColor;
        outline-offset: -2px;
    }
    [role="treeitem"] button {
        flex-shrink: 0;
        width: 1.5rem;
        padding: 0;
    }
    .picker-folder {
        display: block;
        width: 100%;
        text-align: start;
        overflow-wrap: anywhere;
        margin-bottom: 0.3rem;
    }
    .picker-actions {
        display: flex;
        justify-content: flex-end;
        gap: 0.6rem;
        margin-top: 0.8rem;
    }
    @media (max-width: 600px) {
        .picker-panels {
            grid-template-columns: 1fr;
            grid-template-rows: 1fr 1fr;
            height: 45vh;
        }
        .picker-tree {
            border-right: 0;
            border-bottom: var(--solid-border);
        }
    }
</style>
