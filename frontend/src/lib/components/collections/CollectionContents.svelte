<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: CollectionContents.svelte
 ! purpose: Collection browsing, membership changes, and transitive operations
 ! -------------------------------------------------->

<script lang="ts">
import { onMount, tick, untrack } from 'svelte';
import { fly } from 'svelte/transition';
import CollectionTable from '$components/collections/CollectionTable.svelte';
import CollectionDetails from '$components/collections/CollectionDetails.svelte';
import { sidebar_in_out } from '$lib/common';
import { confirmBox, confirmState } from '$lib/confirm.svelte';
import { statusMonitor } from '$lib/status.svelte';
import { collectionInput, getCollection, getCollections, getCollectionMembers, updateCollection,
    operateCollection, type MemberSegment, type CollectionMember, type CollectionOperationResult } from '$lib/collections';
import type { Collection, CollectionOverview } from '$lib/objects';

let {navigationLocked=$bindable(false), remapBlocked=$bindable(false), tagRevision=0}: {
    navigationLocked?: boolean;
    remapBlocked?: boolean;
    tagRevision?: number;
} = $props();

$effect(() => {
    remapBlocked = navigationLocked;
});

$effect(() => {
    if (tagRevision > 0) {
        untrack(() => {
            void refresh();
            if (active) void refreshActive();
        });
    }
});
let collections = $state<CollectionOverview[]>([]), active = $state<Collection | null>(null);
let segments = $state<MemberSegment[]>([]), selectedIds = $state(new Set<string>());
let snapshot = $state(''), busy = $state(false), loading = $state(false);
let error = $state<string | null>(null), detailError = $state<string | null>(null);
let warning = $state<string | null>(null), popup = $state<MemberSegment | null>(null);
let search = $state('');
let sidebar = $state<HTMLElement>();
let dialog = $state<HTMLDialogElement>();
const metadata = (item: Collection) => ({name: item.name, purpose: item.purpose, tags: [...item.tags]});
let changed = $derived(active !== null && JSON.stringify(metadata(active)) !== snapshot);
let candidates = $derived((popup?.candidates ?? []).filter(item => item.name.toLocaleLowerCase().includes(search.toLocaleLowerCase())));
$effect(() => {navigationLocked = changed || busy || loading || popup !== null || confirmState.open;});
$effect(() => {if (popup && dialog && !dialog.open) dialog.showModal();});
onMount(() => {void refresh();});

async function refresh() {
    try {
        const result = await getCollections();
        if (!result.ok) {error = result.message ?? 'Cannot load collections'; return;}
        collections = result.data;
        selectedIds = new Set([...selectedIds].filter(id => collections.some(item => item.id === id)));
        error = null;
    } catch (cause) {error = message(cause);}
}
function message(cause: unknown) {return cause instanceof Error ? cause.message : 'Request failed';}
async function mayClose() {
    return !changed || await confirmBox({title: 'Unsaved changes', message: 'Discard collection metadata changes?'});
}
async function close() {
    if (busy || loading || popup || !await mayClose()) return;
    active = null; snapshot = ''; detailError = null; warning = null;
}
async function open(id: string) {
    if (busy || loading || popup || active?.id === id) return;
    loading = true;
    try {
        if (!await mayClose()) return;
        const [result, members] = await Promise.all([getCollection(id), getCollectionMembers(id)]);
        if (!result.ok) {error = result.message ?? 'Cannot load collection'; return;}
        if (!members.ok) {error = members.message ?? 'Cannot load members'; return;}
        active = result.data; segments = members.data; snapshot = JSON.stringify(metadata(active));
        detailError = null; warning = null; await tick(); sidebar?.focus();
    } catch (cause) {error = message(cause);} finally {loading = false;}
}
async function refreshActive(preserveDraft = false) {
    if (!active) return;
    const draft = preserveDraft && changed ? metadata(active) : null;
    const [result, members] = await Promise.all([getCollection(active.id), getCollectionMembers(active.id)]);
    if (!result.ok) throw new Error(result.message ?? 'Cannot refresh collection');
    if (!members.ok) throw new Error(members.message ?? 'Cannot refresh members');
    active = result.data; snapshot = JSON.stringify(metadata(active)); segments = members.data;
    if (draft) active = {...active, ...draft};
    await refresh();
}
async function save() {
    if (!active || busy) return;
    busy = true; detailError = null;
    try {
        // Retrieve current membership so a metadata save does not replace newer links.
        const current = await getCollection(active.id);
        if (!current.ok) throw new Error(current.message ?? 'Cannot load collection');
        const result = await updateCollection(active.id, {...collectionInput(current.data), ...metadata(active)});
        if (!result.ok) throw new Error(result.message ?? 'Cannot save collection');
        await refreshActive();
    } catch (cause) {detailError = message(cause);} finally {busy = false;}
}
async function changeMember(segment: MemberSegment, member: CollectionMember, add: boolean) {
    if (!active || busy) return;
    busy = true; detailError = null;
    try {
        const current = await getCollection(active.id);
        if (!current.ok) throw new Error(current.message ?? 'Cannot load collection');
        const input = collectionInput(current.data);
        const ids = input[segment.field] ?? [];
        input[segment.field] = add ? [...ids, member.id] : ids.filter(id => id !== member.id);
        const result = await updateCollection(active.id, input);
        if (!result.ok) throw new Error(result.message ?? 'Cannot change membership');
        closePopup(); await refreshActive(true);
    } catch (cause) {detailError = message(cause);} finally {busy = false;}
}
async function remove(segment: MemberSegment, member: CollectionMember) {
    if (await confirmBox({title: 'Remove member', message: `Remove ${member.name} from this collection? Files and nested collection contents will remain unchanged.`})) {
        await changeMember(segment, member, false);
    }
}
async function openAdd(segment: MemberSegment) {
    if (!active || busy) return;
    busy = true; detailError = null;
    try {
        const result = await getCollectionMembers(active.id);
        if (!result.ok) throw new Error(result.message ?? 'Cannot load candidates');
        segments = result.data; search = ''; popup = segments.find(item => item.id === segment.id) ?? null;
    } catch (cause) {detailError = message(cause);} finally {busy = false;}
}
function closePopup() {dialog?.close(); popup = null; search = '';}
function operationMessages(result: CollectionOperationResult, field: 'errors' | 'warnings'): string[] {
    return [...(result[field] ?? []).map(issue => issue.message),
        ...(result.members ?? []).flatMap(member => operationMessages(member, field))];
}
async function operate(destination: 'working' | 'archive' | null) {
    if (!active || changed || busy) return;
    busy = true; detailError = null; warning = null;
    try {
        const result = await operateCollection(active.id, destination);
        if (!result.ok) throw new Error(result.message ?? 'Cannot perform collection operation');
        let plan: CollectionOperationResult;
        if ('state' in result.data) {
            const completed = await statusMonitor.waitForOperation(result.data);
            if (!completed.ok) throw new Error(completed.message ?? 'Cannot retrieve operation');
            if (completed.data.state === 'failed') throw new Error(completed.data.error?.message ?? 'Collection operation failed');
            plan = completed.data.result as CollectionOperationResult;
            if (!plan) throw new Error('Collection operation returned no result');
        } else {plan = result.data;}
        const errors = operationMessages(plan, 'errors');
        if (!plan.allowed || !plan.performed) detailError = errors.join('\n') || 'Collection operation did not complete.';
        warning = [...new Set(operationMessages(plan, 'warnings'))].join('\n') || null;
    } catch (cause) {detailError = message(cause);} finally {
        // Partial operations may already have changed some members.
        try {await refreshActive();} catch (cause) {detailError = [detailError, message(cause)].filter(Boolean).join('\n');}
        busy = false;
    }
}
function escape(event: KeyboardEvent) {
    if (event.key === 'Escape' && !popup && !confirmState.open) {event.stopPropagation(); void close();}
}
</script>

<div class="object-view">
    {#if error}<p class="error-message">{error} <button class="blank-button" onclick={refresh}>Retry</button></p>{/if}
    <div class="object-results"><main><CollectionTable {collections} selectedId={active?.id ?? null}
        bind:selectedIds disabled={busy || loading || popup !== null} onOpen={open} /></main></div>
    {#if active}
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <aside class="right-sidebar" data-collection-details tabindex="-1" bind:this={sidebar}
            onkeydown={escape} transition:fly={sidebar_in_out}>
            <CollectionDetails bind:item={active} {segments} {changed} busy={busy || loading}
                error={detailError} {warning} onClose={close} onSave={save}
                onRemove={remove} onAdd={openAdd} onOperate={operate} />
        </aside>
    {/if}
</div>
{#if popup}
    <dialog class="collection-member-picker" bind:this={dialog} aria-labelledby="collection-picker-title"
        oncancel={event => {event.preventDefault(); if (!busy) closePopup();}}>
        <h2 id="collection-picker-title">Add: {popup.name}</h2>
        {#if detailError}<p class="error-message">{detailError}</p>{/if}

            <label class="dialog-label">Search names<input disabled={busy} class="text-input full-width" bind:value={search} /></label>
            <div class="collection-options">
                {#each candidates as member (member.id)}
                    <button disabled={busy} class="blank-button" title={member.name}
                        onclick={() => {if (popup) void changeMember(popup, member, true);}}>{member.name}</button>
                {:else}<p class="annotation">No available members match.</p>{/each}
            </div>
            <button disabled={busy} class="button-with-text" onclick={closePopup}>Cancel</button>

    </dialog>
{/if}
