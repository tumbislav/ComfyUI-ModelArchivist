<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ModelCollectionEditor.svelte
 ! purpose: Edit collection membership for one model
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

import addIcon from '$icons/actions/add16.png';
import removeIcon from '$icons/actions/remove16.png';

import CollectionPicker from '$lib/components/collections/CollectionPicker.svelte';
import { confirmBox } from '$lib/confirm.svelte';
import {
    addModelToCollection,
    createCollection,
    removeModelFromCollection
} from '$lib/collections';
import { type CollectionSummary, type Model } from '$lib/objects';

let {
    model,
    onChanged
}: {
    model: Model;
    onChanged: () => Promise<void>;
} = $props();

let section: HTMLElement;
let addButton = $state<HTMLElement | null>(null);
let selected = $state<Set<string>>(new Set());
let popupOpen = $state(false);
let busy = $state(false);
let error = $state<string | null>(null);

let memberIds = $derived(new Set(model.collections.map((collection) => collection.id)));

function toggleSelected(id: string) {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    selected = next;
}

function openAdd() {
    popupOpen = true;
}

function closePopup() {
    popupOpen = false;
}

async function addTo(collectionId: string): Promise<string | null> {
    const envelope = await addModelToCollection(collectionId, model.id);
    if (!envelope.ok) {
        return envelope.message ?? locale.t('ui.model_collection_editor.cannot_add_model_to_collection');
    }

    await onChanged();
    return null;
}

async function createNew(name: string): Promise<string | null> {
    const envelope = await createCollection({
        name,
        purpose: '',
        tags: [],
        models: [model.id],
        workflows: [],
        children: []
    });
    if (!envelope.ok) {
        return envelope.message ?? locale.t('ui.model_collection_editor.cannot_create_collection');
    }

    await onChanged();
    return null;
}

async function removeSelected() {
    if (selected.size === 0) return;
    const names = model.collections
        .filter((collection) => selected.has(collection.id))
        .map((collection) => collection.name)
        .join(', ');
    const confirmed = await confirmBox({
        title: locale.t('ui.model_collection_editor.remove_from_collections'),
        message: locale.t('messages.remove_model_collections', {collections: names}),
        anchor: section
    });
    if (!confirmed) return;

    busy = true;
    error = null;
    try {
        for (const collectionId of selected) {
            const envelope = await removeModelFromCollection(collectionId, model.id);
            if (!envelope.ok) {
                error = envelope.message ?? locale.t('ui.model_collection_editor.cannot_remove_model_from_collection');
                return;
            }
        }
        selected = new Set();
        await onChanged();
    } finally {
        busy = false;
    }
}
</script>

<div class="space-below" bind:this={section}>
    <h2 class="tight-vertical">
        {locale.t('ui.model_collection_editor.collections')}
    </h2>
    <div class="collection-members">
        {#each model.collections as collection (collection.id)}
            <label>
                <input type="checkbox"
                       checked={selected.has(collection.id)}
                       disabled={busy}
                       onchange={() => toggleSelected(collection.id)} />
                <span>{collection.name}</span>
            </label>
        {:else}
            <p class="annotation">
                {locale.t('ui.model_collection_editor.not_in_a_collection')}
            </p>
        {/each}
    </div>

    {#if error && !popupOpen}
        <p class="error-message">{error}</p>
    {/if}

    <div class="spaced-horizontally">
        <button class="button-with-text" bind:this={addButton} disabled={busy} onclick={openAdd}>
            <img class="action-icon" alt={locale.t('ui.model_collection_editor.add')} src={addIcon} />
            <span class="button-label">{locale.t('ui.model_collection_editor.add_2')}</span>
        </button>
        <button class="button-with-text"
                disabled={busy || selected.size === 0}
                onclick={removeSelected}>
            <img class="action-icon" alt={locale.t('ui.model_collection_editor.remove')} src={removeIcon} />
            <span class="button-label">{locale.t('ui.model_collection_editor.remove_from')}</span>
        </button>
    </div>
</div>

{#if popupOpen && addButton}
    <CollectionPicker anchor={addButton}
                      title={locale.t('ui.model_collection_editor.add_to_collection')}
                      optionDisabled={(collection: CollectionSummary) => memberIds.has(collection.id)}
                      onAdd={addTo}
                      onCreate={createNew}
                      onClose={closePopup} />
{/if}
