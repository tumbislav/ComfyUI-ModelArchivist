<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: MultiWorkflowCollectionEditor.svelte
 ! purpose: Edit collection membership for selected workflows
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

import addIcon from '$icons/actions/add16.png';
import removeIcon from '$icons/actions/remove16.png';
import CollectionPicker from '$lib/components/collections/CollectionPicker.svelte';
import { confirmBox } from '$lib/confirm.svelte';
import { createCollection, updateCollectionWorkflows } from '$lib/collections';
import { type CollectionSummary, type Workflow } from '$lib/objects';
let { workflows, onChanged }: { workflows: Workflow[]; onChanged: () => Promise<void> } = $props();
let section: HTMLElement;
let addButton = $state<HTMLElement | null>(null);
let selected = $state<Set<string>>(new Set());
let popupOpen = $state(false), busy = $state(false);
let error = $state<string | null>(null);
let counts = $derived.by(() => {
    const result = new Map<string, {collection: CollectionSummary; count: number}>();
    for (const workflow of workflows) for (const collection of workflow.collections) {
        const current = result.get(collection.id);
        result.set(collection.id, {collection, count: (current?.count ?? 0) + 1});
    }
    return result;
});
let memberships = $derived([...counts.values()].sort((a, b) =>
    locale.compare(a.collection.name, b.collection.name)));
let workflowIds = $derived(workflows.map(workflow => workflow.id));
function toggle(id: string) { const next = new Set(selected); next.has(id) ? next.delete(id) : next.add(id); selected = next; }
function openAdd() { popupOpen = true; }
function closePopup() { popupOpen = false; }
async function addTo(id: string): Promise<string | null> {
    const result = await updateCollectionWorkflows(id, workflowIds, true);
    if (!result.ok) return result.message ?? locale.t('ui.multi_workflow_collection_editor.cannot_add_workflows');
    await onChanged(); return null;
}
async function removeSelected() {
    if (!await confirmBox({title: locale.t('ui.multi_workflow_collection_editor.remove_from_collections'),
        message: locale.plural('messages.remove_selected_workflows', selected.size), anchor: section})) return;
    busy = true;
    for (const id of selected) {
        const result = await updateCollectionWorkflows(id, workflowIds, false);
        if (!result.ok) { error = result.message ?? locale.t('ui.multi_workflow_collection_editor.cannot_remove_workflows'); busy = false; return; }
    }
    selected = new Set(); busy = false; await onChanged();
}
async function createNew(name: string): Promise<string | null> {
    const result = await createCollection({name, purpose: '',
        tags: [], models: [], workflows: workflowIds, children: []});
    if (!result.ok) return result.message ?? locale.t('ui.multi_workflow_collection_editor.cannot_create_collection');
    await onChanged(); return null;
}
</script>

<div class="space-below" bind:this={section}>
    <h2>{locale.t('ui.multi_workflow_collection_editor.collections')}</h2>
    <div class="collection-members">
        {#each memberships as membership (membership.collection.id)}
            <label>
                <input type="checkbox" checked={selected.has(membership.collection.id)} disabled={busy}
                onchange={() => toggle(membership.collection.id)} />
                <span>({membership.count} workflows) {membership.collection.name}</span>
            </label>
        {:else}
            <p class="annotation">{locale.t('ui.multi_workflow_collection_editor.not_in_a_collection')}</p>
        {/each}
    </div>
    {#if error && !popupOpen}
        <p class="error-message">{error}</p>
    {/if}
    <div class="spaced-horizontally">
        <button class="button-with-text" bind:this={addButton} disabled={busy} onclick={openAdd}>
            <img class="action-icon" alt={locale.t('ui.multi_workflow_collection_editor.add')} src={addIcon} />
            <span class="button-label">{locale.t('ui.multi_workflow_collection_editor.add_2')}</span>
        </button>
        <button class="button-with-text" disabled={busy || !selected.size} onclick={removeSelected}>
            <img class="action-icon" alt={locale.t('ui.multi_workflow_collection_editor.remove')} src={removeIcon} />
            <span class="button-label">{locale.t('ui.multi_workflow_collection_editor.remove_from')}</span>
        </button>
    </div>
</div>
{#if popupOpen && addButton}
    <CollectionPicker anchor={addButton}
                      title={locale.t('ui.multi_workflow_collection_editor.add_to_collection')}
                      optionLabel={(collection: CollectionSummary) =>
                          `(${counts.get(collection.id)?.count ?? 0} workflows) ${collection.name}`}
                      optionDisabled={(collection: CollectionSummary) =>
                          (counts.get(collection.id)?.count ?? 0) === workflows.length}
                      onAdd={addTo}
                      onCreate={createNew}
                      onClose={closePopup} />
{/if}
