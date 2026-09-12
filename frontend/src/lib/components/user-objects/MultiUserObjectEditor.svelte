<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: MultiUserObjectEditor.svelte
 ! purpose: Sidebar editor for multiple user-defined objects
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

    import { onMount } from 'svelte';
    import TagEditor from '$components/controls/TagEditor.svelte';
    import RelativePathEditor from '$components/controls/RelativePathEditor.svelte';
    import closeIcon from '$icons/actions/close8.png';
    import saveIcon from '$icons/actions/save16.png';
    import { getUserObject, updateUserObject, syncUserObject, moveUserObject, isLongOperation,
        getUserObjectRelativePaths, relocateUserObjects,
        type UserObjectDestination } from '$lib/user-objects';
    import { getCollections, updateCollectionUserObjects } from '$lib/collections';
    import { statusMonitor } from '$lib/status.svelte';
    import type { UserObject, CollectionOverview } from '$lib/objects';
    import { confirmBox } from '$lib/confirm.svelte';
    import { unsavedChangesBox } from '$lib/unsaved-changes.svelte';

    let { ids, onClose, onChanged }: {
        ids: string[]; onClose: () => void; onChanged: () => Promise<void>;
    } = $props();
    let items = $state<UserObject[]>([]); let collections = $state<CollectionOverview[]>([]); let collectionId = $state(''); let addTags = $state<string[]>([]); let removeTags = $state<string[]>([]); let busy = $state(false); let loading = $state(true); let error = $state<string | null>(null); let outcome = $state(''); let relativePaths = $state<string[]>([]);
    let destinationPath = $state('');
    let blocked = $derived(busy || loading || items.length !== ids.length || items.some(item => item.read_only)
        || statusMonitor.operation?.state === 'pending' || statusMonitor.operation?.state === 'running');
    let removableTags = $derived([...new Set(items.flatMap(item => item.tags))].sort()); async function load(): Promise<boolean> {
        const results = await Promise.all(ids.map(getUserObject));
        const failed = results.find(result => !result.ok);
        if (failed && !failed.ok) {
            error = failed.message ?? locale.t('ui.multi_user_object_editor.cannot_load_selected_objects');
            return false;
        }
        items = results.flatMap(result => result.ok ? [result.data] : []);
        if (items.length > 0 && items[0].type?.id) {
            const paths = await getUserObjectRelativePaths(items[0].type.id);
            if (paths.ok) relativePaths = paths.data;
        }
        return true;
    }

    onMount(() => {
        void (async () => {
            await load();
            const result = await getCollections();
            if (result.ok) collections = result.data;
            else error = result.message ?? locale.t('ui.multi_user_object_editor.cannot_load_collections');
            loading = false;
        })();
    });

    export async function requestClose(): Promise<void> {
        if (busy) return;

        if (addTags.length || removeTags.length) {
            const result = await unsavedChangesBox({
                message: locale.t('messages.save_tag_changes_before_continuing')
            });
            if (result === 'cancel') return;
            if (result === 'save') {
                await perform('tags');
                if (addTags.length || removeTags.length) return;
            }
        }
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
            if (items.some(item => item.read_only)) throw new Error(locale.t('ui.multi_user_object_editor.some_selected_objects_are_read_only'));
            if (action === 'add' || action === 'remove') {
                const result = await updateCollectionUserObjects(collectionId, ids, action === 'add');
                if (!result.ok) throw new Error(result.message ?? locale.t('ui.multi_user_object_editor.cannot_update_collection'));
                completed = ids.length;
            } else {
                for (const item of items) {
                    if (action === 'tags') {
                        const tags = [...new Set([...item.tags.filter(tag => !removeTags.includes(tag)), ...addTags])];
                        const result = await updateUserObject({ ...item, tags });
                        if (!result.ok) throw new Error(result.message ?? locale.t('ui.multi_user_object_editor.cannot_update_tags'));
                    } else {
                        const result = action === 'sync' ? await syncUserObject(item.id) : await moveUserObject(item.id, action);
                        if (!result.ok) throw new Error(result.message ?? locale.t('ui.multi_user_object_editor.cannot_perform_operation'));
                        if (isLongOperation(result.data)) {
                            const done = await statusMonitor.waitForOperation(result.data);
                            if (!done.ok || done.data.state !== 'succeeded') {
                                throw new Error(done.ok ? done.data.error?.message ?? locale.t('ui.multi_user_object_editor.operation_failed') : done.message);
                            }
                        } else if (!result.data.allowed) {
                            throw new Error(result.data.errors?.join('; ') ?? locale.t('ui.multi_user_object_editor.operation_rejected'));
                        }
                    }
                    completed++;
                }
                if (action === 'tags') { addTags = []; removeTags = []; }
            }
            outcome = locale.plural('messages.updated_objects', completed);
        } catch (cause) {
            error = locale.t('messages.partial_objects_updated', {
                completed,
                total: ids.length,
                error: cause instanceof Error ? cause.message
                    : locale.t('ui.multi_user_object_editor.operation_failed')
            });
        } finally {
            try {
                await load();
                await onChanged();
            } finally {
                busy = false;
            }
        }
    }

    async function relocate(): Promise<void> {
        if (blocked) return;
        busy = true;
        error = null;
        const preview = await relocateUserObjects(ids, destinationPath, true);
        busy = false;
        if (!preview.ok || !preview.data.allowed) {
            error = preview.ok
                ? preview.data.errors?.map((issue: {message: string}) => issue.message).join('; ')
                : preview.message ?? locale.t('ui.multi_user_object_editor.cannot_move_objects');
            return;
        }
        if (!await confirmBox({
            message: locale.t('messages.move_selected_objects', {
                destination: destinationPath || locale.t('dynamic.repository_root').toLocaleLowerCase(locale.language)
            })})) return;
        const directories = items.map(item => item.relative_path.replace(/[/\\][^/\\]+$/, '')
            .replace(item.relative_path, ''));
        if (new Set(directories).size > 1 && !await confirmBox({
            message: locale.t('ui.multi_user_object_editor.the_objects_are_currently_in_different_subdirectories_are_you_sure_you_want_to_move_them_to_the_same_subdirectory')
        })) return;
        busy = true;
        const result = await relocateUserObjects(ids, destinationPath, false);
        busy = false;
        if (!result.ok || !result.data.allowed) {
            error = result.ok
                ? result.data.errors?.map((issue: {message: string}) => issue.message).join('; ')
                : result.message ?? locale.t('ui.multi_user_object_editor.cannot_move_objects');
            return;
        }
        await load();
        await onChanged();
    }
</script>

<header class="spaced-horizontally">
    <h2>{locale.t('ui.multi_user_object_editor.edit_selected_objects')}</h2>
    <button class="round"
            aria-label={locale.t('ui.multi_user_object_editor.close_multi_edit')}
            disabled={busy}
            onclick={() => void requestClose()}>
        <img class="action-icon" src={closeIcon} alt="" />
    </button>
</header>

<p>{ids.length} objects selected</p>

<div class="multi-model-list">
    {#each items as item}
        <p>{item.display_name}</p>
    {/each}
</div>

{#if error}
    <p class="error-details" role="alert">{error}</p>
{/if}
{#if outcome}
    <p role="status">{outcome}</p>
{/if}
{#if items.some(item => item.read_only)}
    <p class="error-details">
        {locale.t('ui.multi_user_object_editor.some_selected_objects_are_read_only')}
    </p>
{/if}

<TagEditor
    title={locale.t('ui.multi_user_object_editor.add_tags')}
    tags={addTags}
    disabled={blocked}
    editable={true}
    onChanged={tags => addTags = tags} />
<TagEditor
    title={locale.t('ui.multi_user_object_editor.remove_tags')}
    tags={removeTags}
    availableTags={removableTags}
    disabled={blocked}
    editable={false}
    onChanged={tags => removeTags = tags} />

<button class="button-with-text"
        disabled={blocked || (!addTags.length && !removeTags.length)}
        onclick={() => perform('tags')}>
    <img class="action-icon" src={saveIcon} alt="" />
    {locale.t('ui.multi_user_object_editor.apply_tags')}
</button>

<div class="settings-actions space-below">
    <button class="button-with-text" disabled={blocked} onclick={() => perform('working')}>
        {locale.t('ui.multi_user_object_editor.to_working_set')}
    </button>
    <button class="button-with-text" disabled={blocked} onclick={() => perform('sync')}>
        {locale.t('ui.multi_user_object_editor.sync')}
    </button>
    <button class="button-with-text" disabled={blocked} onclick={() => perform('archive')}>
        {locale.t('ui.multi_user_object_editor.to_archive')}
    </button>
</div>

<div class="space-below">
    <RelativePathEditor
        bind:value={destinationPath}
        options={relativePaths}
        disabled={blocked}
        onMove={relocate} />
</div>

<label>
    {locale.t('ui.multi_user_object_editor.collection')}
    <select class="text-input" bind:value={collectionId} disabled={blocked}>
        <option value="">{locale.t('ui.multi_user_object_editor.select_collection')}</option>
        {#each collections as collection}
            <option value={collection.id}>{collection.name}</option>
        {/each}
    </select>
</label>

<div class="settings-actions">
    <button class="button-with-text"
            disabled={blocked || !collectionId}
            onclick={() => perform('add')}>
        {locale.t('ui.multi_user_object_editor.add_to_collection')}
    </button>
    <button class="button-with-text"
            disabled={blocked || !collectionId}
            onclick={() => perform('remove')}>
        {locale.t('ui.multi_user_object_editor.remove_from_collection')}
    </button>
</div>
