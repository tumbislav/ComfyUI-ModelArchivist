<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: WorkflowCollectionEditor.svelte
 ! purpose: Edit collection membership for one workflow
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

import addIcon from '$icons/actions/add16.png';
import removeIcon from '$icons/actions/remove16.png';
import cancelIcon from '$icons/actions/cancel16.png';
import confirmIcon from '$icons/actions/confirm16.png';
import closeIcon from '$icons/actions/close8.png';
import { confirmBox, sideDialogPosition } from '$lib/confirm.svelte';
import { modalControl } from '$lib/modal-control';
import { unsavedChangesBox } from '$lib/unsaved-changes.svelte';
import { createCollection, getCollections, updateCollectionWorkflows } from '$lib/collections';
import { type CollectionSummary, type Workflow } from '$lib/objects';
let { workflow, onChanged }: { workflow: Workflow; onChanged: () => Promise<void> } = $props();
let section: HTMLElement;
let selected = $state<Set<string>>(new Set()); let collections = $state<CollectionSummary[]>([]); let popupOpen = $state(false), busy = $state(false); let error = $state<string | null>(null), popupPosition = $state('');
let newName = $state(''), newPurpose = $state('');
let newCollectionDirty = $derived(newName !== '' || newPurpose !== '');
let memberIds = $derived(new Set(workflow.collections.map(collection => collection.id)));
function toggleSelected(id: string) {
    const next = new Set(selected); next.has(id) ? next.delete(id) : next.add(id); selected = next;
}
async function openAdd() {
    const result = await getCollections();
    if (!result.ok) { error = result.message ?? locale.t('ui.workflow_collection_editor.cannot_load_collections'); return; }
    collections = result.data; popupPosition = sideDialogPosition(section);
    popupOpen = true; newName = ''; newPurpose = ''; error = null;
}
function closePopupNow() { popupOpen = false; newName = ''; newPurpose = ''; error = null; }
async function closePopup() {
    if (newCollectionDirty) {
        const result = await unsavedChangesBox({
            message: locale.t('messages.save_new_collection_before_continuing'),
            anchor: section,
            saveDisabled: !newName.trim()
        });
        if (result === 'cancel') return;
        if (result === 'save') {
            await createNew();
            return;
        }
    }
    closePopupNow();
}
async function addTo(id: string) {
    busy = true; const result = await updateCollectionWorkflows(id, [workflow.id], true); busy = false;
    if (!result.ok) { error = result.message ?? locale.t('ui.workflow_collection_editor.cannot_add_workflow_to_collection'); return; }
    await onChanged(); closePopupNow();
}
async function removeSelected() {
    if (!await confirmBox({title: locale.t('ui.workflow_collection_editor.remove_from_collections'),
        message: locale.plural('messages.remove_workflow_collections', selected.size), anchor: section})) return;
    busy = true;
    for (const id of selected) {
        const result = await updateCollectionWorkflows(id, [workflow.id], false);
        if (!result.ok) { error = result.message ?? locale.t('ui.workflow_collection_editor.cannot_remove_workflow'); busy = false; return; }
    }
    selected = new Set(); busy = false; await onChanged();
}
async function createNew() {
    busy = true;
    const result = await createCollection({name: newName.trim(), purpose: newPurpose, tags: [],
        models: [], workflows: [workflow.id], children: []});
    busy = false;
    if (!result.ok) { error = result.message ?? locale.t('ui.workflow_collection_editor.cannot_create_collection'); return; }
    await onChanged(); closePopupNow();
}
</script>

<div class="space-below" bind:this={section}>
    <h2>{locale.t('ui.workflow_collection_editor.collections')}</h2>
    <div class="collection-members">{#each workflow.collections as collection (collection.id)}
        <label>
            <input type="checkbox" checked={selected.has(collection.id)} disabled={busy}
                onchange={() => toggleSelected(collection.id)} />
            <span>{collection.name}</span>
        </label>
    {:else}
        <p class="annotation">{locale.t('ui.workflow_collection_editor.not_in_a_collection')}</p>{/each}
    </div>
    {#if error && !popupOpen}
        <p class="error-message">{error}</p>
    {/if}
    <div class="spaced-horizontally">
        <button class="button-with-text" disabled={busy} onclick={openAdd}>
            <img class="action-icon" alt={locale.t('ui.workflow_collection_editor.add')} src={addIcon} />
            <span class="button-label">{locale.t('ui.workflow_collection_editor.add_2')}</span>
        </button>
        <button class="button-with-text" disabled={busy || !selected.size} onclick={removeSelected}>
            <img class="action-icon" alt={locale.t('ui.workflow_collection_editor.remove')} src={removeIcon} />
            <span class="button-label">{locale.t('ui.workflow_collection_editor.remove_from')}</span>
        </button>
    </div>
</div>
    {#if popupOpen}
        <dialog class="collection-picker"
                style={popupPosition}
                use:modalControl
                oncancel={(event) => {
                    event.preventDefault();
                    void closePopup();
                }}>
            {#if error}<p class="error-message">{error}</p>{/if}

                    <div class="spaced-horizontally">
                        <h2>{locale.t('ui.workflow_collection_editor.add_to_collection')}</h2>
                        <button disabled={busy} class="round" aria-label={locale.t('ui.workflow_collection_editor.close_collection_picker')}
                                onclick={() => void closePopup()}>
                            <img class="action-icon" alt="" src={closeIcon} />
                        </button>
                    </div>
                    <div class="dialog-section collection-create">
                        <h3>{locale.t('ui.workflow_collection_editor.new_collection')}</h3>
                        <label class="dialog-label" for="workflow-collection-name">{locale.t('ui.workflow_collection_editor.name')}</label>
                        <input disabled={busy} id="workflow-collection-name" class="text-input full-width" bind:value={newName} />
                        <label class="dialog-label" for="workflow-collection-purpose">{locale.t('ui.workflow_collection_editor.purpose')}</label>
                        <textarea disabled={busy} id="workflow-collection-purpose" class="text-input full-width" bind:value={newPurpose}></textarea>
                        <button class="button-with-text" disabled={busy || !newName.trim()} onclick={createNew}>
                            <img class="action-icon" alt={locale.t('ui.workflow_collection_editor.create')} src={confirmIcon} />
                            <span class="button-label">{locale.t('ui.workflow_collection_editor.create_and_close')}</span>
                        </button>
                    </div>
                    <div class="collection-options">
                        {#each collections as collection (collection.id)}
                            <button class="blank-button" disabled={busy || memberIds.has(collection.id)}
                                    onclick={() => addTo(collection.id)}>
                                {collection.name}
                            </button>
                        {/each}</div>
                    <button disabled={busy} class="button-with-text" onclick={() => void closePopup()}>
                        <img class="action-icon" alt={locale.t('ui.workflow_collection_editor.cancel')} src={cancelIcon} />
                        <span class="button-label">{locale.t('ui.workflow_collection_editor.cancel_2')}</span>
                    </button>

        </dialog>
{/if}
