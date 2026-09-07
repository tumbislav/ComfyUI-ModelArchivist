<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: UserObjectCollectionEditor.svelte
 ! purpose: Edit collection membership for one user-defined object
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
import addIcon from '$icons/actions/add16.png';
import removeIcon from '$icons/actions/remove16.png';
import closeIcon from '$icons/actions/close8.png';
import confirmIcon from '$icons/actions/confirm16.png';
import { confirmBox, sideDialogPosition } from '$lib/confirm.svelte';
import { createCollection, getCollections, updateCollectionUserObjects } from '$lib/collections';
import type { CollectionSummary, UserObject } from '$lib/objects';

let { item, onChanged }: {item: UserObject; onChanged: () => Promise<void>} = $props();
let section: HTMLElement;
let collections = $state<CollectionSummary[]>([]), selected = $state(new Set<string>());
let popupOpen = $state(false), busy = $state(false), error = $state<string | null>(null);
let popupPosition = $state(''), newName = $state(''), newPurpose = $state('');
let memberIds = $derived(new Set(item.collections.map(collection => collection.id)));
let dirty = $derived(newName !== '' || newPurpose !== '');
function toggle(id: string) { const next = new Set(selected); next.has(id) ? next.delete(id) : next.add(id); selected = next; }
async function openAdd() {
    const result = await getCollections();
    if (!result.ok) { error = result.message ?? 'Cannot load collections'; return; }
    collections = result.data; popupPosition = sideDialogPosition(section); popupOpen = true;
    newName = ''; newPurpose = ''; error = null;
}
function closeNow() { popupOpen = false; newName = ''; newPurpose = ''; error = null; }
async function closePopup() {
    if (dirty && !await confirmBox({title: 'Discard new collection?',
        message: 'Discard the unsaved new collection?', anchor: section})) return;
    closeNow();
}
async function change(collectionId: string, add: boolean) {
    busy = true;
    const result = await updateCollectionUserObjects(collectionId, [item.id], add);
    busy = false;
    if (!result.ok) { error = result.message ?? 'Cannot update collection'; return false; }
    await onChanged(); return true;
}
async function addTo(id: string) { if (await change(id, true)) closeNow(); }
async function removeSelected() {
    if (!await confirmBox({title: 'Remove from collections',
        message: `Remove this object from ${selected.size} collection(s)?`, anchor: section})) return;
    for (const id of selected) if (!await change(id, false)) return;
    selected = new Set();
}
async function createNew() {
    busy = true;
    const result = await createCollection({name: newName.trim(), purpose: newPurpose, tags: [],
        models: [], workflows: [], user_objects: [item.id], children: []});
    busy = false;
    if (!result.ok) { error = result.message ?? 'Cannot create collection'; return; }
    await onChanged(); closeNow();
}
</script>

<div class="space-below" bind:this={section}>
    <h2 class="tight-vertical">Collections</h2>
    <div class="collection-members">
        {#each item.collections as collection (collection.id)}
            <label><input type="checkbox" checked={selected.has(collection.id)} disabled={busy}
                onchange={() => toggle(collection.id)} /><span>{collection.name}</span></label>
        {:else}<p class="annotation">Not in a collection.</p>{/each}
    </div>
    {#if error && !popupOpen}<p class="error-message">{error}</p>{/if}
    <div class="spaced-horizontally">
        <button class="button-with-text" disabled={busy || item.read_only} onclick={openAdd}>
            <img class="action-icon" alt="add" src={addIcon} /><span class="button-label">Add</span></button>
        <button class="button-with-text" disabled={busy || item.read_only || !selected.size}
            onclick={removeSelected}><img class="action-icon" alt="remove" src={removeIcon} />
            <span class="button-label">Remove from</span></button>
    </div>
</div>
{#if popupOpen}
    <div class="modal-backdrop"><div class="modal-dialog collection-picker" style={popupPosition}>

            <div class="spaced-horizontally"><h2 class="tight-vertical">Add to collection</h2>
                <button disabled={busy} class="round" aria-label="Close collection picker" onclick={() => void closePopup()}>
                    <img class="action-icon" alt="" src={closeIcon} /></button></div>
            {#if error}<p class="error-message">{error}</p>{/if}
            <div class="dialog-section collection-create"><h3>New collection</h3>
                <label class="dialog-label">Name<input disabled={busy} class="text-input full-width" bind:value={newName} /></label>
                <label class="dialog-label">Purpose<textarea disabled={busy} class="text-input full-width" bind:value={newPurpose}></textarea></label>
                <button class="button-with-text" disabled={busy || !newName.trim()} onclick={createNew}>
                    <img class="action-icon" alt="create" src={confirmIcon} />
                    <span class="button-label">Create and close</span></button></div>
            <div class="collection-options">{#each collections as collection (collection.id)}
                <button class="blank-button" disabled={busy || memberIds.has(collection.id)}
                    onclick={() => addTo(collection.id)}>{collection.name}</button>{/each}</div>

    </div></div>
{/if}
