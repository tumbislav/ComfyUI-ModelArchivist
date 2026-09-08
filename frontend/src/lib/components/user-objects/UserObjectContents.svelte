<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: UserObjectContents.svelte
 ! purpose: Container for browsing and editing objects of the active UDT
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
import { untrack } from 'svelte';
import { fly } from 'svelte/transition';
import FilterActions from '$components/controls/FilterActions.svelte';
import MultiUserObjectEditor from '$components/user-objects/MultiUserObjectEditor.svelte';
import UserObjectTable from '$components/user-objects/UserObjectTable.svelte';
import UserObjectDetails from '$components/user-objects/UserObjectDetails.svelte';
import { sidebar_in_out } from '$lib/common';
import { confirmBox } from '$lib/confirm.svelte';
import { statusMonitor } from '$lib/status.svelte';
import { userTypeState } from '$lib/user-types.svelte';
import { getUserObject, getUserObjects, isLongOperation, moveUserObject, syncUserObject,
    updateUserObject, type UserObjectDestination } from '$lib/user-objects';
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

let objects = $state<UserObjectSummary[]>([]), error = $state<string | null>(null);
let selectedId = $state<string | null>(null), selectedIds = $state(new Set<string>());
let activeId = $state<string | null>(null), active = $state<UserObject | null>(null);
let snapshot = $state(''), saving = $state(false), operating = $state(false);
let operationError = $state<string | null>(null), loadedTypeId = $state<string | null>(null);
// svelte-ignore non_reactive_update
let sidebar: HTMLElement;
let changed = $derived(active !== null && snapshot !== JSON.stringify({name: active.display_name,
    purpose: active.purpose, tags: active.tags}));

$effect(() => {
    const typeId = userTypeState.active?.id ?? null;
    if (typeId !== loadedTypeId) { loadedTypeId = typeId; void changeType(typeId); }
});
$effect(() => { if (selectedId && selectedId !== activeId) void openDetails(selectedId); });
$effect(() => { if (active && sidebar) sidebar.focus(); });

const makeSnapshot = (item: UserObject) => JSON.stringify({name: item.display_name,
    purpose: item.purpose, tags: item.tags});
async function changeType(typeId: string | null) {
    await closeDetails(); selectedIds = new Set(); objects = [];
    if (typeId === null) return;
    await refresh();
}
async function refresh() {
    if (!loadedTypeId) return false;
    const result = await getUserObjects(loadedTypeId);
    if (!result.ok) { error = result.message ?? 'Cannot load objects'; return false; }
    objects = result.data; error = null; return true;
}
async function openDetails(id: string) {
    if (!await closeDetails()) return;
    const result = await getUserObject(id);
    if (!result.ok) { error = result.message ?? 'Cannot load object'; return; }
    active = result.data; activeId = id; selectedId = id; snapshot = makeSnapshot(result.data);
}
async function closeDetails(): Promise<boolean> {
    if (changed && !await confirmBox({title: 'Unsaved changes', message: 'Discard object changes?'})) {
        selectedId = activeId; return false;
    }
    selectedId = null; activeId = null; active = null; snapshot = ''; operationError = null; return true;
}
async function save() {
    if (!active) return; saving = true; operationError = null;
    const result = await updateUserObject(active); saving = false;
    if (!result.ok) { operationError = result.message ?? 'Cannot save object'; return; }
    active = result.data; snapshot = makeSnapshot(result.data); await refresh();
}
async function runOperation(destination: UserObjectDestination | null) {
    if (!active) return; operating = true; operationError = null; const id = active.id;
    try {
        const result = destination === null ? await syncUserObject(id) : await moveUserObject(id, destination);
        if (!result.ok) { operationError = result.message ?? 'Cannot perform object operation'; return; }
        if (isLongOperation(result.data)) {
            const completed = await statusMonitor.waitForOperation(result.data);
            if (!completed.ok || completed.data.state === 'failed') {
                operationError = completed.ok ? completed.data.error?.message ?? 'Object operation failed'
                    : completed.message ?? 'Cannot retrieve object operation'; return;
            }
        } else if (!result.data.allowed) {
            operationError = result.data.errors?.join('; ') ?? 'Operation is not allowed'; return;
        }
        await refreshActive();
    } finally { operating = false; }
}
async function refreshActive() {
    if (!activeId) return;
    const result = await getUserObject(activeId);
    if (!result.ok) { operationError = result.message ?? 'Cannot refresh object'; return; }
    active = result.data; snapshot = makeSnapshot(result.data); await refresh();
}
async function handleEscape(event: KeyboardEvent) { if (event.key === 'Escape') await closeDetails(); }
async function clickOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (target.closest('[data-user-object-table]') || target.closest('[data-user-object-details]') || target.closest('[data-filter-actions]') || target.closest('[data-user-multi]')) return;
    await closeDetails();
}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="object-view" onclick={clickOutside}>
    <FilterActions tab="user" selectedCount={selectedIds.size} onOpenMulti={async () => {
        if (selectedIds.size >= 2 && await closeDetails()) multiEditorOpen = true;
    }} />
    {#if multiEditorOpen}
        <MultiUserObjectEditor ids={[...selectedIds]} onClose={() => multiEditorOpen = false}
            onChanged={async () => { await refresh(); }} />
    {/if}
    {#if userTypeState.active}
        <div class="object-results"><main><UserObjectTable type={userTypeState.active} {objects} {error}
            bind:selectedId bind:selectedIds /></main></div>
    {/if}
    {#if active}
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <aside class="right-sidebar" data-user-object-details tabindex="-1" onkeydown={handleEscape}
            bind:this={sidebar} transition:fly={sidebar_in_out}>
            <UserObjectDetails bind:item={active} {changed} {saving} {operating} {operationError}
                onSave={save} onClose={closeDetails} onSync={() => runOperation(null)} onMove={runOperation}
                onCollectionsChanged={refreshActive} />
        </aside>
    {/if}
</div>
