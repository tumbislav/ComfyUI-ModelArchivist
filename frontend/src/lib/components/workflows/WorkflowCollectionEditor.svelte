<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: WorkflowCollectionEditor.svelte
 ! purpose: Edit collection membership for one workflow
 ! -------------------------------------------------->

<script lang="ts">
import addIcon from '$icons/actions/add16.png';
import removeIcon from '$icons/actions/remove16.png';
import cancelIcon from '$icons/actions/cancel16.png';
import confirmIcon from '$icons/actions/confirm16.png';
import closeIcon from '$icons/actions/close8.png';
import { confirmBox, sideDialogPosition } from '$lib/confirm.svelte';
import { createCollection, getCollections, updateCollectionWorkflows } from '$lib/collections';
import { type CollectionSummary, type Workflow } from '$lib/objects';
let { workflow, onChanged }: { workflow: Workflow; onChanged: () => Promise<void> } = $props();
let section: HTMLElement;
let selected = $state<Set<string>>(new Set());
let collections = $state<CollectionSummary[]>([]);
let popupOpen = $state(false), busy = $state(false);
let error = $state<string | null>(null), popupPosition = $state('');
let newName = $state(''), newPurpose = $state('');
let newCollectionDirty = $derived(newName !== '' || newPurpose !== '');
let memberIds = $derived(new Set(workflow.collections.map(collection => collection.id)));
function toggleSelected(id: string) {
    const next = new Set(selected); next.has(id) ? next.delete(id) : next.add(id); selected = next;
}
async function openAdd() {
    const result = await getCollections();
    if (!result.ok) { error = result.message ?? 'Cannot load collections'; return; }
    collections = result.data; popupPosition = sideDialogPosition(section);
    popupOpen = true; newName = ''; newPurpose = ''; error = null;
}
function closePopupNow() { popupOpen = false; newName = ''; newPurpose = ''; error = null; }
async function closePopup() {
    if (newCollectionDirty && !await confirmBox({title: 'Discard new collection?',
        message: 'Discard the unsaved new collection?', anchor: section})) return;
    closePopupNow();
}
async function addTo(id: string) {
    busy = true; const result = await updateCollectionWorkflows(id, [workflow.id], true); busy = false;
    if (!result.ok) { error = result.message ?? 'Cannot add workflow to collection'; return; }
    await onChanged(); closePopupNow();
}
async function removeSelected() {
    if (!await confirmBox({title: 'Remove from collections',
        message: `Remove this workflow from ${selected.size} collection(s)?`, anchor: section})) return;
    busy = true;
    for (const id of selected) {
        const result = await updateCollectionWorkflows(id, [workflow.id], false);
        if (!result.ok) { error = result.message ?? 'Cannot remove workflow'; busy = false; return; }
    }
    selected = new Set(); busy = false; await onChanged();
}
async function createNew() {
    busy = true;
    const result = await createCollection({name: newName.trim(), purpose: newPurpose, tags: [],
        models: [], workflows: [workflow.id], children: []});
    busy = false;
    if (!result.ok) { error = result.message ?? 'Cannot create collection'; return; }
    await onChanged(); closePopupNow();
}
</script>

<div class="space-below" bind:this={section}>
    <h2>Collections</h2>
    <div class="collection-members">{#each workflow.collections as collection (collection.id)}
        <label>
            <input type="checkbox" checked={selected.has(collection.id)} disabled={busy}
                onchange={() => toggleSelected(collection.id)} />
            <span>{collection.name}</span>
        </label>
    {:else}
        <p class="annotation">Not in a collection.</p>{/each}
    </div>
    {#if error && !popupOpen}
        <p class="error-message">{error}</p>
    {/if}
    <div class="spaced-horizontally">
        <button class="button-with-text" disabled={busy} onclick={openAdd}>
            <img class="action-icon" alt="add" src={addIcon} />
            <span class="button-label">Add</span>
        </button>
        <button class="button-with-text" disabled={busy || !selected.size} onclick={removeSelected}>
            <img class="action-icon" alt="remove" src={removeIcon} />
            <span class="button-label">Remove from</span>
        </button>
    </div>
</div>
    {#if popupOpen}
        <div class="modal-backdrop"><div class="modal-dialog collection-picker" style={popupPosition}>
            {#if error}<p class="error-message">{error}</p>{/if}
                <fieldset disabled={busy}>
                    <div class="spaced-horizontally">
                        <h2>Add to collection</h2>
                        <button class="round" aria-label="Close collection picker"
                                onclick={() => void closePopup()}>
                            <img class="action-icon" alt="" src={closeIcon} />
                        </button>
                    </div>
                    <div class="dialog-section collection-create">
                        <h3>New collection</h3>
                        <label class="dialog-label" for="workflow-collection-name">Name</label>
                        <input id="workflow-collection-name" class="text-input full-width" bind:value={newName} />
                        <label class="dialog-label" for="workflow-collection-purpose">Purpose</label>
                        <textarea id="workflow-collection-purpose" class="text-input full-width" bind:value={newPurpose}></textarea>
                        <button class="button-with-text" disabled={!newName.trim()} onclick={createNew}>
                            <img class="action-icon" alt="create" src={confirmIcon} />
                            <span class="button-label">Create and close</span>
                        </button>
                    </div>
                    <div class="collection-options">
                        {#each collections as collection (collection.id)}
                            <button class="blank-button" disabled={memberIds.has(collection.id)}
                                    onclick={() => addTo(collection.id)}>
                                {collection.name}
                            </button>
                        {/each}</div>
                    <button class="button-with-text" onclick={() => void closePopup()}>
                        <img class="action-icon" alt="cancel" src={cancelIcon} />
                        <span class="button-label">Cancel</span>
                    </button>
                </fieldset>
        </div>
    </div>
{/if}
