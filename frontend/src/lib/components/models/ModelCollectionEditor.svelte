<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ModelCollectionEditor.svelte
 ! purpose: Edit collection membership for one model
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
let selected = $state<Set<string>>(new Set()); let collections = $state<CollectionSummary[]>([]); let popupOpen = $state(false); let busy = $state(false); let error = $state<string | null>(null);
let popupPosition = $state('');
let newName = $state('');
let newPurpose = $state('');

let memberIds = $derived(new Set(model.collections.map((collection) => collection.id)));
let newCollectionDirty = $derived(newName !== '' || newPurpose !== '');

function toggleSelected(id: string) {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    selected = next;
}

async function openAdd() {
    error = null;
    const envelope = await getCollections();
    if (!envelope.ok) {
        error = envelope.message ?? locale.t('ui.model_collection_editor.cannot_load_collections');
        return;
    }
    collections = envelope.data;
    popupPosition = sideDialogPosition(section);
    popupOpen = true;
    newName = '';
    newPurpose = '';
}

function closePopupNow() {
    popupOpen = false;
    newName = '';
    newPurpose = '';
    error = null;
}

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

async function addTo(collectionId: string) {
    busy = true;
    error = null;
    try {
        const envelope = await addModelToCollection(collectionId, model.id);
        if (!envelope.ok) {
            error = envelope.message ?? locale.t('ui.model_collection_editor.cannot_add_model_to_collection');
            return;
        }
        await onChanged();
        closePopupNow();
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
            error = envelope.message ?? locale.t('ui.model_collection_editor.cannot_create_collection');
            return;
        }
        await onChanged();
        closePopupNow();
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
    <h2 class="tight-vertical">{locale.t('ui.model_collection_editor.collections')}</h2>
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
            <p class="annotation">{locale.t('ui.model_collection_editor.not_in_a_collection')}</p>
        {/each}
    </div>

    {#if error && !popupOpen}
        <p class="error-message">{error}</p>
    {/if}

    <div class="spaced-horizontally">
        <button class="button-with-text" disabled={busy} onclick={openAdd}>
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

{#if popupOpen}
    <dialog class="collection-picker"
            style={popupPosition}
            use:modalControl
            oncancel={(event) => {
                event.preventDefault();
                void closePopup();
            }}>
            {#if error}
                <p class="error-message">{error}</p>
            {/if}


                <div class="spaced-horizontally">
                    <h2 class="tight-vertical">{locale.t('ui.model_collection_editor.add_to_collection')}</h2>
                    <button disabled={busy} type="button" class="round" aria-label={locale.t('ui.model_collection_editor.close_collection_picker')}
                            onclick={() => void closePopup()}>
                        <img class="action-icon" alt="" src={closeIcon} />
                    </button>
                </div>

                <div class="dialog-section collection-create">
                    <h3>{locale.t('ui.model_collection_editor.new_collection')}</h3>
                    <label class="dialog-label" for="new-collection-name">{locale.t('ui.model_collection_editor.name')}</label>
                    <input disabled={busy} id="new-collection-name" class="text-input full-width" bind:value={newName} />
                    <label class="dialog-label" for="new-collection-purpose">{locale.t('ui.model_collection_editor.purpose')}</label>
                    <textarea disabled={busy} id="new-collection-purpose" class="text-input full-width" bind:value={newPurpose}></textarea>
                    <button class="button-with-text" disabled={busy || !newName.trim()} onclick={createNew}>
                        <img class="action-icon" alt={locale.t('ui.model_collection_editor.create')} src={confirmIcon} />
                        <span class="button-label">{locale.t('ui.model_collection_editor.create_and_close')}</span>
                    </button>
                </div>

                <div class="collection-options">
                    {#each collections as collection (collection.id)}
                        <button type="button" class="blank-button"
                                disabled={busy || memberIds.has(collection.id)}
                                onclick={() => addTo(collection.id)}>
                            {collection.name}
                        </button>
                    {/each}
                </div>

                <button disabled={busy} class="button-with-text" onclick={() => void closePopup()}>
                    <img class="action-icon" alt={locale.t('ui.model_collection_editor.cancel')} src={cancelIcon} />
                    <span class="button-label">{locale.t('ui.model_collection_editor.cancel_2')}</span>
                </button>

    </dialog>
{/if}

<style>
</style>
