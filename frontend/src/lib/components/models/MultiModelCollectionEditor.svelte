<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: MultiModelCollectionEditor.svelte
 ! purpose: Edit collection membership for selected models
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

import addIcon from '$icons/actions/add16.png';
import removeIcon from '$icons/actions/remove16.png';

import CollectionPicker from '$lib/components/collections/CollectionPicker.svelte';
import { confirmBox } from '$lib/confirm.svelte';
import { createCollection, updateCollectionModels } from '$lib/collections';
import { type CollectionSummary, type Model } from '$lib/objects';

let { models, onChanged }: { models: Model[]; onChanged: () => Promise<void> } = $props();

let section: HTMLElement;
let addButton = $state<HTMLElement | null>(null);
let selected = $state<Set<string>>(new Set());
let popupOpen = $state(false);
let busy = $state(false);
let error = $state<string | null>(null);

let counts = $derived.by(() => {
    const result = new Map<string, {collection: CollectionSummary; count: number}>();
    for (const model of models) {
        for (const collection of model.collections) {
            const current = result.get(collection.id);
            result.set(collection.id, {
                collection,
                count: (current?.count ?? 0) + 1
            });
        }
    }
    return result;
});
let memberships = $derived([...counts.values()].sort((a, b) =>
    locale.compare(a.collection.name, b.collection.name)));
let modelIds = $derived(models.map(model => model.id));

function toggleSelected(id: string) {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    selected = next;
}

function openAdd() { popupOpen = true; }
function closePopup() { popupOpen = false; }

async function addTo(collectionId: string): Promise<string | null> {
    const envelope = await updateCollectionModels(collectionId, modelIds, true);
    if (!envelope.ok) {
        return envelope.message ?? locale.t('ui.multi_model_collection_editor.cannot_add_models_to_collection');
    }
    await onChanged();
    return null;
}

async function removeSelected() {
    if (selected.size === 0) return;
    const confirmed = await confirmBox({
        title: locale.t('ui.multi_model_collection_editor.remove_from_collections'),
        message: locale.plural('messages.remove_selected_models', selected.size),
        anchor: section
    });
    if (!confirmed) return;
    busy = true;
    for (const collectionId of selected) {
        const envelope = await updateCollectionModels(collectionId, modelIds, false);
        if (!envelope.ok) {
            error = envelope.message ?? locale.t('ui.multi_model_collection_editor.cannot_remove_models_from_collection');
            busy = false;
            return;
        }
    }
    selected = new Set();
    busy = false;
    await onChanged();
}

async function createNew(name: string): Promise<string | null> {
    const envelope = await createCollection({
        name, purpose: '', tags: [],
        models: modelIds, workflows: [], children: []
    });
    if (!envelope.ok) {
        return envelope.message ?? locale.t('ui.multi_model_collection_editor.cannot_create_collection');
    }
    await onChanged();
    return null;
}
</script>

<div class="space-below" bind:this={section}>
    <h2>{locale.t('ui.multi_model_collection_editor.collections')}</h2>
    <div class="collection-members">
        {#each memberships as membership (membership.collection.id)}
            <label>
                <input type="checkbox" checked={selected.has(membership.collection.id)}
                       disabled={busy} onchange={() => toggleSelected(membership.collection.id)} />
                <span>({membership.count} models) {membership.collection.name}</span>
            </label>
        {:else}
            <p class="annotation">{locale.t('ui.multi_model_collection_editor.not_in_a_collection')}</p>
        {/each}
    </div>
    {#if error && !popupOpen}<p class="error-message">{error}</p>{/if}
    <div class="spaced-horizontally">
        <button class="button-with-text" bind:this={addButton} disabled={busy} onclick={openAdd}>
            <img class="action-icon" alt={locale.t('ui.multi_model_collection_editor.add')} src={addIcon} />
            <span class="button-label">{locale.t('ui.multi_model_collection_editor.add_2')}</span>
        </button>
        <button class="button-with-text" disabled={busy || selected.size === 0}
                onclick={removeSelected}>
            <img class="action-icon" alt={locale.t('ui.multi_model_collection_editor.remove')} src={removeIcon} />
            <span class="button-label">{locale.t('ui.multi_model_collection_editor.remove_from')}</span>
        </button>
    </div>
</div>

{#if popupOpen && addButton}
    <CollectionPicker anchor={addButton}
                      title={locale.t('ui.multi_model_collection_editor.add_to_collection')}
                      optionLabel={(collection: CollectionSummary) =>
                          `(${counts.get(collection.id)?.count ?? 0} models) ${collection.name}`}
                      optionDisabled={(collection: CollectionSummary) =>
                          (counts.get(collection.id)?.count ?? 0) === models.length}
                      onAdd={addTo}
                      onCreate={createNew}
                      onClose={closePopup} />
{/if}

<style>
</style>
