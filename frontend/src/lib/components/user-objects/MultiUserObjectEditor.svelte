<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: MultiUserObjectEditor.svelte
 ! purpose: Bulk tags, collection membership, and deployment for user-defined objects
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import { onMount } from 'svelte';
    import TagEditor from '$components/controls/TagEditor.svelte';
    import closeIcon from '$icons/actions/close8.png';
    import saveIcon from '$icons/actions/save16.png';
    import { getUserObject, updateUserObject, syncUserObject, moveUserObject, isLongOperation,
        type UserObjectDestination } from '$lib/user-objects';
    import { getCollections, updateCollectionUserObjects } from '$lib/collections';
    import { statusMonitor } from '$lib/status.svelte';
    import type { UserObject, CollectionOverview } from '$lib/objects';

    let { ids, onClose, onChanged }: {
        ids: string[]; onClose: () => void; onChanged: () => Promise<void>;
    } = $props();
    let dialog: HTMLDialogElement;
    let items = $state<UserObject[]>([]);
    let collections = $state<CollectionOverview[]>([]);
    let collectionId = $state('');
    let addTags = $state<string[]>([]);
    let removeTags = $state<string[]>([]);
    let busy = $state(false);
    let loading = $state(true);
    let error = $state<string | null>(null);
    let outcome = $state('');
    let blocked = $derived(busy || loading || items.length !== ids.length || items.some(item => item.read_only)
        || statusMonitor.operation?.state === 'pending' || statusMonitor.operation?.state === 'running');
    let removableTags = $derived([...new Set(items.flatMap(item => item.tags))].sort());

    async function load(): Promise<boolean> {
        const results = await Promise.all(ids.map(getUserObject));
        const failed = results.find(result => !result.ok);
        if (failed && !failed.ok) {
            error = failed.message ?? 'Cannot load selected objects';
            return false;
        }
        items = results.flatMap(result => result.ok ? [result.data] : []);
        return true;
    }

    onMount(() => {
        dialog.showModal();
        void (async () => {
            await load();
            const result = await getCollections();
            if (result.ok) collections = result.data;
            else error = result.message ?? 'Cannot load collections';
            loading = false;
        })();
    });

    function close(): void {
        if (busy) return;
        if ((addTags.length || removeTags.length) && !confirm('Discard unsaved tag changes?')) return;
        onClose();
    }

    async function perform(action: 'tags' | 'add' | 'remove' | 'sync' | UserObjectDestination): Promise<void> {
        if (blocked) return;
        busy = true;
        error = null;
        outcome = '';
        let completed = 0;
        try {
            if (!await load()) return;
            if (items.some(item => item.read_only)) throw new Error('Some selected objects are read-only.');
            if (action === 'add' || action === 'remove') {
                const result = await updateCollectionUserObjects(collectionId, ids, action === 'add');
                if (!result.ok) throw new Error(result.message ?? 'Cannot update collection');
                completed = ids.length;
            } else {
                for (const item of items) {
                    if (action === 'tags') {
                        const tags = [...new Set([...item.tags.filter(tag => !removeTags.includes(tag)), ...addTags])];
                        const result = await updateUserObject({ ...item, tags });
                        if (!result.ok) throw new Error(result.message ?? 'Cannot update tags');
                    } else {
                        const result = action === 'sync' ? await syncUserObject(item.id) : await moveUserObject(item.id, action);
                        if (!result.ok) throw new Error(result.message ?? 'Cannot perform operation');
                        if (isLongOperation(result.data)) {
                            const done = await statusMonitor.waitForOperation(result.data);
                            if (!done.ok || done.data.state !== 'succeeded') {
                                throw new Error(done.ok ? done.data.error?.message ?? 'Operation failed' : done.message);
                            }
                        } else if (!result.data.allowed) {
                            throw new Error(result.data.errors?.join('; ') ?? 'Operation rejected');
                        }
                    }
                    completed++;
                }
                if (action === 'tags') { addTags = []; removeTags = []; }
            }
            outcome = `Updated ${completed} objects.`;
        } catch (cause) {
            error = `${completed} of ${ids.length} objects updated. ${cause instanceof Error ? cause.message : 'Operation failed'}`;
        } finally {
            try {
                await load();
                await onChanged();
            } finally {
                busy = false;
            }
        }
    }
</script>

<dialog class="user-multi-dialog" bind:this={dialog} data-user-multi aria-label="Edit selected user objects"
        oncancel={event => { event.preventDefault(); close(); }}>
    <header class="spaced-horizontally">
        <h2>Edit selected objects</h2>
        <button class="round" aria-label="Close multi-edit" disabled={busy} onclick={close}>
            <img class="action-icon" src={closeIcon} alt="" />
        </button>
    </header>
    <p>{ids.length} objects selected</p>
    <div class="multi-model-list">{#each items as item}<p>{item.display_name}</p>{/each}</div>
    {#if error}<p class="error-details" role="alert">{error}</p>{/if}
    {#if outcome}<p role="status">{outcome}</p>{/if}
    {#if items.some(item => item.read_only)}<p class="error-details">Some selected objects are read-only.</p>{/if}
    <TagEditor title="Add tags" tags={addTags} disabled={blocked} editable={true} onChanged={tags => addTags = tags} />
    <TagEditor title="Remove tags" tags={removeTags} availableTags={removableTags}
        disabled={blocked} editable={false} onChanged={tags => removeTags = tags} />
    <button class="button-with-text" disabled={blocked || (!addTags.length && !removeTags.length)} onclick={() => perform('tags')}>
        <img class="action-icon" src={saveIcon} alt="" />Apply tags
    </button>
    <div class="settings-actions space-below">
        <button class="button-with-text" disabled={blocked} onclick={() => perform('working')}>To working set</button>
        <button class="button-with-text" disabled={blocked} onclick={() => perform('sync')}>Sync</button>
        <button class="button-with-text" disabled={blocked} onclick={() => perform('archive')}>To archive</button>
    </div>
    <label>Collection
        <select class="text-input" bind:value={collectionId} disabled={blocked}>
            <option value="">Select collection</option>
            {#each collections as collection}<option value={collection.id}>{collection.name}</option>{/each}
        </select>
    </label>
    <div class="settings-actions">
        <button class="button-with-text" disabled={blocked || !collectionId} onclick={() => perform('add')}>Add to collection</button>
        <button class="button-with-text" disabled={blocked || !collectionId} onclick={() => perform('remove')}>Remove from collection</button>
    </div>
</dialog>
