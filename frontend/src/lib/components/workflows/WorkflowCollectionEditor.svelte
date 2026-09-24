<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: WorkflowCollectionEditor.svelte
 ! purpose: Edit collection membership for one workflow
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

import addIcon from '$icons/actions/add16.png';
import removeIcon from '$icons/actions/remove16.png';
import CollectionPicker from '$lib/components/collections/CollectionPicker.svelte';
import { confirmBox } from '$lib/confirm.svelte';
import { createCollection, updateCollectionWorkflows } from '$lib/collections';
import { type CollectionSummary, type Workflow } from '$lib/objects';
let { workflow, onChanged }: { workflow: Workflow; onChanged: () => Promise<void> } = $props();
let section: HTMLElement;
let addButton = $state<HTMLElement | null>(null);
let selected = $state<Set<string>>(new Set());
let popupOpen = $state(false);
let busy = $state(false);
let error = $state<string | null>(null);
let memberIds = $derived(new Set(workflow.collections.map(collection => collection.id)));
function toggleSelected(id: string) {
    const next = new Set(selected); next.has(id) ? next.delete(id) : next.add(id); selected = next;
}
function openAdd() { popupOpen = true; }
function closePopup() { popupOpen = false; }
async function addTo(id: string): Promise<string | null> {
    const result = await updateCollectionWorkflows(id, [workflow.id], true);
    if (!result.ok) return result.message ?? locale.t('ui.workflow_collection_editor.cannot_add_workflow_to_collection');
    await onChanged(); return null;
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
async function createNew(name: string): Promise<string | null> {
    const result = await createCollection({name, purpose: '', tags: [],
        models: [], workflows: [workflow.id], children: []});
    if (!result.ok) return result.message ?? locale.t('ui.workflow_collection_editor.cannot_create_collection');
    await onChanged(); return null;
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
        <button class="button-with-text" bind:this={addButton} disabled={busy} onclick={openAdd}>
            <img class="action-icon" alt={locale.t('ui.workflow_collection_editor.add')} src={addIcon} />
            <span class="button-label">{locale.t('ui.workflow_collection_editor.add_2')}</span>
        </button>
        <button class="button-with-text" disabled={busy || !selected.size} onclick={removeSelected}>
            <img class="action-icon" alt={locale.t('ui.workflow_collection_editor.remove')} src={removeIcon} />
            <span class="button-label">{locale.t('ui.workflow_collection_editor.remove_from')}</span>
        </button>
    </div>
</div>
    {#if popupOpen && addButton}
        <CollectionPicker anchor={addButton}
                          title={locale.t('ui.workflow_collection_editor.add_to_collection')}
                          optionDisabled={(collection: CollectionSummary) => memberIds.has(collection.id)}
                          onAdd={addTo}
                          onCreate={createNew}
                          onClose={closePopup} />
{/if}
