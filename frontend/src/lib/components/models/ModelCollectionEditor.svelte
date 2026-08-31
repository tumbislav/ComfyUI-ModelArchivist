<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ModelCollectionEditor.svelte
 ! purpose: Edit collection membership for one model
 ! -------------------------------------------------->

<script lang="ts">
import addIcon from '$icons/actions/add16.png';
import removeIcon from '$icons/actions/remove16.png';
import cancelIcon from '$icons/actions/cancel16.png';
import confirmIcon from '$icons/actions/confirm16.png';

import { confirmBox, sideDialogPosition } from '$lib/confirm.svelte';
import {
    addModelToCollection,
    createCollection,
    getCollections,
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
let selected = $state<Set<string>>(new Set());
let collections = $state<CollectionSummary[]>([]);
let popupOpen = $state(false);
let creating = $state(false);
let busy = $state(false);
let error = $state<string | null>(null);
let popupPosition = $state('');
let newName = $state('');
let newPurpose = $state('');

let memberIds = $derived(new Set(model.collections.map((collection) => collection.id)));

function toggleSelected(id: string) {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    selected = next;
}

async function openAdd() {
    error = null;
    const envelope = await getCollections();
    if (!envelope.ok) {
        error = envelope.message ?? 'Cannot load collections';
        return;
    }
    collections = envelope.data;
    popupPosition = sideDialogPosition(section);
    popupOpen = true;
    creating = false;
}

function closePopup() {
    popupOpen = false;
    creating = false;
    newName = '';
    newPurpose = '';
    error = null;
}

async function addTo(collectionId: string) {
    busy = true;
    error = null;
    try {
        const envelope = await addModelToCollection(collectionId, model.id);
        if (!envelope.ok) {
            error = envelope.message ?? 'Cannot add model to collection';
            return;
        }
        await onChanged();
        closePopup();
    } finally {
        busy = false;
    }
}

async function createNew() {
    if (!newName.trim()) return;
    busy = true;
    error = null;
    try {
        const envelope = await createCollection({
            name: newName.trim(),
            purpose: newPurpose,
            tags: [],
            models: [model.id],
            workflows: [],
            children: []
        });
        if (!envelope.ok) {
            error = envelope.message ?? 'Cannot create collection';
            return;
        }
        await onChanged();
        closePopup();
    } finally {
        busy = false;
    }
}

async function removeSelected() {
    if (selected.size === 0) return;
    const names = model.collections
        .filter((collection) => selected.has(collection.id))
        .map((collection) => collection.name)
        .join(', ');
    const confirmed = await confirmBox({
        title: 'Remove from collections',
        message: `Remove this model from ${names}?`,
        anchor: section
    });
    if (!confirmed) return;

    busy = true;
    error = null;
    try {
        for (const collectionId of selected) {
            const envelope = await removeModelFromCollection(collectionId, model.id);
            if (!envelope.ok) {
                error = envelope.message ?? 'Cannot remove model from collection';
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

<div class="dialog-section" bind:this={section}>
    <p class="dialog-label">Collections</p>
    <div class="collection-members">
        {#each model.collections as collection (collection.id)}
            <label>
                <input type="checkbox"
                       checked={selected.has(collection.id)}
                       disabled={busy}
                       onchange={() => toggleSelected(collection.id)} />
                <span class="text-compact">{collection.name}</span>
            </label>
        {:else}
            <p class="annotation">Not in a collection.</p>
        {/each}
    </div>

    {#if error && !popupOpen}
        <p class="error-message">{error}</p>
    {/if}

    <div class="spaced-horizontally">
        <button class="button-with-text" disabled={busy} onclick={openAdd}>
            <img class="action-icon" alt="add" src={addIcon} />
            <span>Add</span>
        </button>
        <button class="button-with-text"
                disabled={busy || selected.size === 0}
                onclick={removeSelected}>
            <img class="action-icon" alt="remove" src={removeIcon} />
            <span>Remove from</span>
        </button>
    </div>
</div>

{#if popupOpen}
    <div class="modal-backdrop">
        <div class="modal-dialog collection-picker" style={popupPosition}>
            {#if error}
                <p class="error-message">{error}</p>
            {/if}

            <fieldset class="nested-modal-parent" disabled={creating || busy}>
                <div class="spaced-horizontally">
                    <h2>Add to collection</h2>
                    <button type="button" class="round" onclick={closePopup}>×</button>
                </div>

                <div class="collection-options">
                    {#each collections as collection (collection.id)}
                        <button type="button" class="blank-button"
                                disabled={memberIds.has(collection.id)}
                                onclick={() => addTo(collection.id)}>
                            {collection.name}
                        </button>
                    {:else}
                        <p class="annotation">No collections exist yet.</p>
                    {/each}
                </div>

                {#if !creating}
                    <div class="spaced-horizontally">
                        <button class="button-with-text" onclick={() => creating = true}>
                            <img class="action-icon" alt="add" src={addIcon} />
                            <span>New collection</span>
                        </button>
                        <button class="button-with-text" onclick={closePopup}>
                            <img class="action-icon" alt="cancel" src={cancelIcon} />
                            <span>Cancel</span>
                        </button>
                    </div>
                {/if}
            </fieldset>

            {#if creating}
                <div class="raised-section collection-create">
                    <label class="dialog-label" for="new-collection-name">Name</label>
                    <input id="new-collection-name" class="text-input full-width" bind:value={newName} />
                    <label class="dialog-label" for="new-collection-purpose">Purpose</label>
                    <textarea id="new-collection-purpose" class="text-input full-width" bind:value={newPurpose}></textarea>
                    <div class="spaced-horizontally">
                        <button class="button-with-text"
                                disabled={busy || !newName.trim()}
                                onclick={createNew}>
                            <img class="action-icon" alt="create" src={confirmIcon} />
                            <span>Create and close</span>
                        </button>
                        <button class="button-with-text" disabled={busy} onclick={() => creating = false}>
                            <img class="action-icon" alt="cancel" src={cancelIcon} />
                            <span>Cancel</span>
                        </button>
                    </div>
                </div>
            {/if}
        </div>
    </div>
{/if}

<style>
</style>
