<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: MultiModelCollectionEditor.svelte
 ! purpose: Edit collection membership for selected models
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
import { createCollection, getCollections, updateCollectionModels } from '$lib/collections';
import { type CollectionSummary, type Model } from '$lib/objects';

let { models, onChanged }: { models: Model[]; onChanged: () => Promise<void> } = $props();

let section: HTMLElement;
let selected = $state<Set<string>>(new Set()); let collections = $state<CollectionSummary[]>([]); let popupOpen = $state(false); let busy = $state(false); let error = $state<string | null>(null);
let popupPosition = $state('');
let newName = $state('');
let newPurpose = $state('');
let newCollectionDirty = $derived(newName !== '' || newPurpose !== '');

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

async function openAdd() {
    const envelope = await getCollections();
    if (!envelope.ok) {
        error = envelope.message ?? locale.t('ui.multi_model_collection_editor.cannot_load_collections');
        return;
    }
    collections = envelope.data;
    popupPosition = sideDialogPosition(section);
    popupOpen = true;
    newName = ''; newPurpose = '';
    error = null;
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
    const envelope = await updateCollectionModels(collectionId, modelIds, true);
    busy = false;
    if (!envelope.ok) {
        error = envelope.message ?? locale.t('ui.multi_model_collection_editor.cannot_add_models_to_collection');
        return;
    }
    await onChanged();
    closePopupNow();
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

async function createNew() {
    if (!newName.trim()) return;
    busy = true;
    const envelope = await createCollection({
        name: newName.trim(), purpose: newPurpose, tags: [],
        models: modelIds, workflows: [], children: []
    });
    busy = false;
    if (!envelope.ok) {
        error = envelope.message ?? locale.t('ui.multi_model_collection_editor.cannot_create_collection');
        return;
    }
    await onChanged();
    closePopupNow();
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
        <button class="button-with-text" disabled={busy} onclick={openAdd}>
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
                    <h2>{locale.t('ui.multi_model_collection_editor.add_to_collection')}</h2>
                    <button disabled={busy} type="button" class="round" aria-label={locale.t('ui.multi_model_collection_editor.close_collection_picker')}
                            onclick={() => void closePopup()}>
                        <img class="action-icon" alt="" src={closeIcon} />
                    </button>
                </div>
                <div class="dialog-section collection-create">
                    <h3>{locale.t('ui.multi_model_collection_editor.new_collection')}</h3>
                    <label class="dialog-label" for="multi-collection-name">{locale.t('ui.multi_model_collection_editor.name')}</label>
                    <input disabled={busy} id="multi-collection-name" class="text-input full-width" bind:value={newName} />
                    <label class="dialog-label" for="multi-collection-purpose">{locale.t('ui.multi_model_collection_editor.purpose')}</label>
                    <textarea disabled={busy} id="multi-collection-purpose" class="text-input full-width" bind:value={newPurpose}></textarea>
                    <button class="button-with-text" disabled={busy || !newName.trim()} onclick={createNew}>
                        <img class="action-icon" alt={locale.t('ui.multi_model_collection_editor.create')} src={confirmIcon} />
                        <span class="button-label">{locale.t('ui.multi_model_collection_editor.create_and_close')}</span>
                    </button>
                </div>
                <div class="collection-options">
                    {#each collections as collection (collection.id)}
                        {@const count = counts.get(collection.id)?.count ?? 0}
                        <button type="button" class="blank-button"
                                disabled={busy || count === models.length}
                                onclick={() => addTo(collection.id)}>
                            ({count} models) {collection.name}
                        </button>
                    {/each}
                </div>
                <button disabled={busy} class="button-with-text" onclick={() => void closePopup()}>
                    <img class="action-icon" alt={locale.t('ui.multi_model_collection_editor.cancel')} src={cancelIcon} />
                    <span class="button-label">{locale.t('ui.multi_model_collection_editor.cancel_2')}</span>
                </button>

    </dialog>
{/if}

<style>
</style>
