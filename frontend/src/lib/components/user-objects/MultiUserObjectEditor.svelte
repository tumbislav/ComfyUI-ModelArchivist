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
    import moveUpIcon from '$icons/actions/move-up16.png';
    import moveDownIcon from '$icons/actions/move-down16.png';
    import syncIcon from '$icons/actions/move-up-down16.png';
    import {
        getUserObject,
        updateUserObject,
        syncUserObject,
        moveUserObject,
        isLongOperation,
        getUserObjectRelativePaths,
        relocateUserObjects,
        type UserObjectDestination } from '$lib/user-objects';
    import MultiUserObjectCollectionEditor from '$components/user-objects/MultiUserObjectCollectionEditor.svelte';
    import { statusMonitor } from '$lib/status.svelte';
    import type { UserObject } from '$lib/objects';
    import { confirmBox } from '$lib/confirm.svelte';
    import { unsavedChangesBox } from '$lib/unsaved-changes.svelte';

    let {
            ids,
            onClose,
            onChanged
        }: {
            ids: string[];
            onClose: () => void;
            onChanged: () => Promise<void>;
        } = $props();
    let items = $state<UserObject[]>([]);
    let addTags = $state<string[]>([]);
    let removeTags = $state<string[]>([]);
    let busy = $state(false);
    let loading = $state(true);
    let error = $state<string | null>(null);
    let outcome = $state('');
    let relativePaths = $state<string[]>([]);
    let destinationPath = $state('');
    let blocked = $derived(
        busy || loading ||
        items.length !== ids.length || items.some(item => item.read_only) ||
        statusMonitor.operation?.state === 'pending' ||
        statusMonitor.operation?.state === 'running');
    let removableTags = $derived([...new Set(items.flatMap(item => item.tags))].sort());

    async function load(): Promise<boolean> {
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

    async function perform(action: 'tags' | 'sync' | UserObjectDestination): Promise<void> {
        if (blocked) return;
        busy = true;
        error = null;
        outcome = '';
        let completed = 0;
        try {
            if (!await load()) return;
            if (items.some(item => item.read_only)) throw new Error(locale.t('ui.multi_user_object_editor.some_selected_objects_are_read_only'));
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
                    } else if (!result.data.allowed || result.data.performed === false) {
                        throw new Error([...(result.data.errors ?? []), ...(result.data.warnings ?? [])]
                            .map(issue => locale.error(issue)).join('; ')
                            || locale.t('ui.multi_user_object_editor.operation_failed'));
                    }
                }
                completed++;
            }
            if (action === 'tags') {
                addTags = [];
                removeTags = [];
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

    async function refreshCollections(): Promise<void> {
        await load();
        await onChanged();
    }

    async function relocate(): Promise<void> {
        if (blocked) return;
        busy = true;
        error = null;
        const preview = await relocateUserObjects(ids, destinationPath, true);
        busy = false;
        if (!preview.ok || !preview.data.allowed) {
            error = preview.ok
                ? preview.data.errors?.map((issue: Parameters<typeof locale.error>[0]) => locale.error(issue)).join('; ')
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
                ? result.data.errors?.map((issue: Parameters<typeof locale.error>[0]) => locale.error(issue)).join('; ')
                : result.message ?? locale.t('ui.multi_user_object_editor.cannot_move_objects');
            return;
        }
        await load();
        await onChanged();
    }
</script>

<header class="sidebar-header spaced-horizontally">
    <div></div>
    <button class="round"
            aria-label={locale.t('ui.multi_user_object_editor.close_multi_edit')}
            disabled={busy}
            onclick={() => void requestClose()}>
        <img class="action-icon" src={closeIcon} alt="" />
    </button>
</header>

<div class="sidebar-body">
    <p>{ids.length} objects selected</p>

    <div class="multi-model-list space-below">
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

    <div class="dialog-section">
        <div class="space-below">
            <TagEditor
                title={locale.t('ui.multi_user_object_editor.add_tags')}
                tags={addTags}
                disabled={blocked}
                editable={true}
                onChanged={tags => addTags = tags} />
        </div>
        <div class="space-below">
            <TagEditor
                title={locale.t('ui.multi_user_object_editor.remove_tags')}
                tags={removeTags}
                availableTags={removableTags}
                disabled={blocked}
                editable={false}
                onChanged={tags => removeTags = tags} />
        </div>

        <div class="spaced-horizontally">
            <div></div>
            <button class="button-with-text"
                    disabled={blocked || (!addTags.length && !removeTags.length)}
                    onclick={() => perform('tags')}>
                <img class="action-icon" src={saveIcon} alt="" />
                {locale.t('ui.multi_user_object_editor.apply_tags')}
            </button>
        </div>
    </div>

    <div class="dialog-section space-below">
        <h2 class="tight-vertical">
            Archive and working locations
        </h2>
        <div class="spaced-horizontally">
            <button class="button-with-text" disabled={blocked} onclick={() => perform('working')}>
                <img class="action-icon" alt={locale.t('ui.multi_user_object_editor.to_working_set')} src={moveUpIcon} />
                <span class="button-label">{locale.t('ui.multi_user_object_editor.to_working_set')}</span>
            </button>
            <button class="button-with-text" disabled={blocked} onclick={() => perform('sync')}>
                <img class="action-icon" alt={locale.t('ui.multi_user_object_editor.sync')} src={syncIcon} />
                <span class="button-label">{locale.t('ui.multi_user_object_editor.sync')}</span>
            </button>
            <button class="button-with-text" disabled={blocked} onclick={() => perform('archive')}>
                <img class="action-icon" alt={locale.t('ui.multi_user_object_editor.to_archive')} src={moveDownIcon} />
                <span class="button-label">{locale.t('ui.multi_user_object_editor.to_archive')}</span>
            </button>
        </div>
    </div>

    <div class="dialog-section space-below">
        <div class="space-below">
            <RelativePathEditor
                bind:value={destinationPath}
                options={relativePaths}
                disabled={blocked}
                onMove={relocate} />
        </div>
    </div>

    {#if !loading && items.length === ids.length && items.length > 0}
        <div class="dialog-section">
            <MultiUserObjectCollectionEditor
                {items}
                disabled={blocked}
                bind:busy
                onChanged={refreshCollections} />
        </div>
    {/if}
</div>
