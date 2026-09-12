<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: UserObjectContents.svelte
 ! purpose: Container for browsing and editing objects of the active UDT
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

import { untrack } from 'svelte';
import { fly } from 'svelte/transition';
import FilterActions from '$components/controls/FilterActions.svelte';
import MultiUserObjectEditor from '$components/user-objects/MultiUserObjectEditor.svelte';
import UserObjectTable from '$components/user-objects/UserObjectTable.svelte';
import UserObjectDetails from '$components/user-objects/UserObjectDetails.svelte';
import { sidebar_in_out } from '$lib/common';
import { confirmBox } from '$lib/confirm.svelte';
import { unsavedChangesBox } from '$lib/unsaved-changes.svelte';
import { statusMonitor } from '$lib/status.svelte';
import { userTypeState } from '$lib/user-types.svelte';
import { getUserObject, getUserObjects, isLongOperation, moveUserObject, syncUserObject,
    updateUserObject, getUserObjectRelativePaths, relocateUserObjects,
    type UserObjectDestination } from '$lib/user-objects';
import type { UserObject, UserObjectSummary } from '$lib/objects';

let { multiEditorOpen=$bindable(false), remapBlocked=$bindable(false), tagRevision=0 }: {
    multiEditorOpen?: boolean;
    remapBlocked?: boolean;
    tagRevision?: number;
} = $props();

$effect(() => {
    remapBlocked = changed || saving || operating || multiEditorOpen;
});

$effect(() => {
    if (tagRevision > 0) {
        untrack(() => {
            void refresh();
            if (activeId) void refreshActive();
        });
    }
});

let objects = $state<UserObjectSummary[]>([]), error = $state<string | null>(null); let selectedId = $state<string | null>(null), selectedIds = $state(new Set<string>()); let activeId = $state<string | null>(null), active = $state<UserObject | null>(null); let snapshot = $state(''), saving = $state(false), operating = $state(false); let operationError = $state<string | null>(null), loadedTypeId = $state<string | null>(null); let relativePaths = $state<string[]>([]);
// svelte-ignore non_reactive_update
let sidebar: HTMLElement;
let multiSidebar = $state<HTMLElement>();
let multiEditor = $state<{requestClose: () => Promise<void>}>();
let changed = $derived(active !== null && snapshot !== JSON.stringify({name: active.display_name,
    purpose: active.purpose, tags: active.tags}));

$effect(() => {
    const typeId = userTypeState.active?.id ?? null;
    if (typeId !== loadedTypeId) { loadedTypeId = typeId; void changeType(typeId); }
});
$effect(() => { if (!multiEditorOpen && selectedId && selectedId !== activeId) void openDetails(selectedId); });
$effect(() => { if (active && sidebar) sidebar.focus(); });
$effect(() => { if (multiEditorOpen && multiSidebar) multiSidebar.focus(); });

const makeSnapshot = (item: UserObject) => JSON.stringify({name: item.display_name,
    purpose: item.purpose, tags: item.tags});
async function changeType(typeId: string | null) {
    await closeDetails(); selectedIds = new Set(); objects = [];
    if (typeId === null) return;
    await refresh();
    const paths = await getUserObjectRelativePaths(typeId);
    if (paths.ok) relativePaths = paths.data;
}
async function refresh() {
    if (!loadedTypeId) return false;
    const result = await getUserObjects(loadedTypeId);
    if (!result.ok) { error = result.message ?? locale.t('ui.user_object_contents.cannot_load_objects'); return false; }
    objects = result.data; error = null; return true;
}
async function openDetails(id: string) {
    if (!await closeDetails()) return;
    const result = await getUserObject(id);
    if (!result.ok) { error = result.message ?? locale.t('ui.user_object_contents.cannot_load_object'); return; }
    active = result.data; activeId = id; selectedId = id; snapshot = makeSnapshot(result.data);
}
async function closeDetails(): Promise<boolean> {
    if (changed) {
        const result = await unsavedChangesBox({
            message: locale.t('ui.user_object_contents.save_object_changes_before_continuing')
        });

        if (result === 'cancel' || (result === 'save' && !await save())) {
            selectedId = activeId;
            return false;
        }
    }
    selectedId = null; activeId = null; active = null; snapshot = ''; operationError = null; return true;
}
async function save(): Promise<boolean> {
    if (!active) return false; saving = true; operationError = null;
    const result = await updateUserObject(active); saving = false;
    if (!result.ok) { operationError = result.message ?? locale.t('ui.user_object_contents.cannot_save_object'); return false; }
    active = result.data; snapshot = makeSnapshot(result.data); await refresh();
    return true;
}
async function runOperation(destination: UserObjectDestination | null) {
    if (!active) return; operating = true; operationError = null; const id = active.id;
    try {
        const result = destination === null ? await syncUserObject(id) : await moveUserObject(id, destination);
        if (!result.ok) { operationError = result.message ?? locale.t('ui.user_object_contents.cannot_perform_object_operation'); return; }
        if (isLongOperation(result.data)) {
            const completed = await statusMonitor.waitForOperation(result.data);
            if (!completed.ok || completed.data.state === 'failed') {
                operationError = completed.ok ? completed.data.error?.message ?? locale.t('ui.user_object_contents.object_operation_failed')
                    : completed.message ?? locale.t('ui.user_object_contents.cannot_retrieve_object_operation'); return;
            }
        } else if (!result.data.allowed) {
            operationError = result.data.errors?.join('; ') ?? locale.t('ui.user_object_contents.operation_is_not_allowed'); return;
        }
        await refreshActive();
    } finally { operating = false; }
}
async function relocate(destination: string) {
    if (!active || operating) return;
    if (!await confirmBox({
        message: locale.t('messages.move_object', {
            destination: destination || locale.t('dynamic.repository_root').toLocaleLowerCase(locale.language)
        })})) return;
    operating = true;
    operationError = null;
    const preview = await relocateUserObjects([active.id], destination, true);
    const result = preview.ok && preview.data.allowed
        ? await relocateUserObjects([active.id], destination, false) : preview;
    operating = false;
    if (!result.ok || !result.data.allowed) {
        operationError = result.ok
            ? result.data.errors?.map((issue: {message: string}) => issue.message).join('; ')
            : result.message ?? locale.t('ui.user_object_contents.cannot_move_object');
        return;
    }
    await refreshActive();
}
async function refreshActive() {
    if (!activeId) return;
    const result = await getUserObject(activeId);
    if (!result.ok) { operationError = result.message ?? locale.t('ui.user_object_contents.cannot_refresh_object'); return; }
    active = result.data; snapshot = makeSnapshot(result.data); await refresh();
}
async function handleEscape(event: KeyboardEvent) { if (event.key === 'Escape') await closeDetails(); }
async function clickOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;

    if (multiEditorOpen) {
        if (!target.closest('[data-user-multi]')) {
            await multiEditor?.requestClose();
        }
        return;
    }

    if (target.closest('[data-user-object-table]') || target.closest('[data-user-object-details]') || target.closest('[data-filter-actions]')) return;
    await closeDetails();
}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="object-view" onclick={clickOutside}>
    <FilterActions tab="user" selectedCount={selectedIds.size} onOpenMulti={async () => {
        if (selectedIds.size >= 2 && await closeDetails()) multiEditorOpen = true;
    }} />
    {#if userTypeState.active}
        <div class="object-results"><main><UserObjectTable type={userTypeState.active} {objects} {error}
            disabled={multiEditorOpen}
            bind:selectedId bind:selectedIds /></main></div>
    {/if}
    {#if active}
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <aside class="right-sidebar" data-user-object-details tabindex="-1" onkeydown={handleEscape}
            bind:this={sidebar} transition:fly={sidebar_in_out}>
            <UserObjectDetails bind:item={active} {changed} {saving} {operating} {operationError}
                onSave={save} onClose={closeDetails} onSync={() => runOperation(null)} onMove={runOperation}
                onRelocate={relocate} {relativePaths}
                onCollectionsChanged={refreshActive} />
        </aside>
    {/if}
    {#if multiEditorOpen}
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <aside class="right-sidebar"
               data-user-multi
               tabindex="-1"
               aria-label={locale.t('ui.multi_user_object_editor.edit_selected_user_objects')}
               bind:this={multiSidebar}
               onkeydown={(event) => {
                   if (event.key === 'Escape') void multiEditor?.requestClose();
               }}
               transition:fly={sidebar_in_out}>
            <MultiUserObjectEditor
                bind:this={multiEditor}
                ids={[...selectedIds]}
                onClose={() => multiEditorOpen = false}
                onChanged={async () => { await refresh(); }} />
        </aside>
    {/if}
</div>
