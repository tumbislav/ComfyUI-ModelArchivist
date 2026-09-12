<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: UserObjectCollectionEditor.svelte
 ! purpose: Edit collection membership for one user-defined object
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

import addIcon from '$icons/actions/add16.png';
import removeIcon from '$icons/actions/remove16.png';
import closeIcon from '$icons/actions/close8.png';
import confirmIcon from '$icons/actions/confirm16.png';
import { confirmBox, sideDialogPosition } from '$lib/confirm.svelte';
import { modalControl } from '$lib/modal-control';
import { unsavedChangesBox } from '$lib/unsaved-changes.svelte';
import { createCollection, getCollections, updateCollectionUserObjects } from '$lib/collections';
import type { CollectionSummary, UserObject } from '$lib/objects';

let { item, onChanged }: {item: UserObject; onChanged: () => Promise<void>} = $props();
let section: HTMLElement;
let collections = $state<CollectionSummary[]>([]), selected = $state(new Set<string>()); let popupOpen = $state(false), busy = $state(false), error = $state<string | null>(null);
let popupPosition = $state(''), newName = $state(''), newPurpose = $state('');
let memberIds = $derived(new Set(item.collections.map(collection => collection.id)));
let dirty = $derived(newName !== '' || newPurpose !== '');
function toggle(id: string) { const next = new Set(selected); next.has(id) ? next.delete(id) : next.add(id); selected = next; }
async function openAdd() {
    const result = await getCollections();
    if (!result.ok) { error = result.message ?? locale.t('ui.user_object_collection_editor.cannot_load_collections'); return; }
    collections = result.data; popupPosition = sideDialogPosition(section); popupOpen = true;
    newName = ''; newPurpose = ''; error = null;
}
function closeNow() { popupOpen = false; newName = ''; newPurpose = ''; error = null; }
async function closePopup() {
    if (dirty) {
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
    closeNow();
}
async function change(collectionId: string, add: boolean) {
    busy = true;
    const result = await updateCollectionUserObjects(collectionId, [item.id], add);
    busy = false;
    if (!result.ok) { error = result.message ?? locale.t('ui.user_object_collection_editor.cannot_update_collection'); return false; }
    await onChanged(); return true;
}
async function addTo(id: string) { if (await change(id, true)) closeNow(); }
async function removeSelected() {
    if (!await confirmBox({title: locale.t('ui.user_object_collection_editor.remove_from_collections'),
        message: locale.plural('messages.remove_object_collections', selected.size), anchor: section})) return;
    for (const id of selected) if (!await change(id, false)) return;
    selected = new Set();
}
async function createNew() {
    busy = true;
    const result = await createCollection({name: newName.trim(), purpose: newPurpose, tags: [],
        models: [], workflows: [], user_objects: [item.id], children: []});
    busy = false;
    if (!result.ok) { error = result.message ?? locale.t('ui.user_object_collection_editor.cannot_create_collection'); return; }
    await onChanged(); closeNow();
}
</script>

<div class="space-below" bind:this={section}>
    <h2 class="tight-vertical">{locale.t('ui.user_object_collection_editor.collections')}</h2>
    <div class="collection-members">
        {#each item.collections as collection (collection.id)}
            <label><input type="checkbox" checked={selected.has(collection.id)} disabled={busy}
                onchange={() => toggle(collection.id)} /><span>{collection.name}</span></label>
        {:else}<p class="annotation">{locale.t('ui.user_object_collection_editor.not_in_a_collection')}</p>{/each}
    </div>
    {#if error && !popupOpen}<p class="error-message">{error}</p>{/if}
    <div class="spaced-horizontally">
        <button class="button-with-text" disabled={busy || item.read_only} onclick={openAdd}>
            <img class="action-icon" alt={locale.t('ui.user_object_collection_editor.add')} src={addIcon} /><span class="button-label">{locale.t('ui.user_object_collection_editor.add_2')}</span></button>
        <button class="button-with-text" disabled={busy || item.read_only || !selected.size}
            onclick={removeSelected}><img class="action-icon" alt={locale.t('ui.user_object_collection_editor.remove')} src={removeIcon} />
            <span class="button-label">{locale.t('ui.user_object_collection_editor.remove_from')}</span></button>
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

            <div class="spaced-horizontally"><h2 class="tight-vertical">{locale.t('ui.user_object_collection_editor.add_to_collection')}</h2>
                <button disabled={busy} class="round" aria-label={locale.t('ui.user_object_collection_editor.close_collection_picker')} onclick={() => void closePopup()}>
                    <img class="action-icon" alt="" src={closeIcon} /></button></div>
            {#if error}<p class="error-message">{error}</p>{/if}
            <div class="dialog-section collection-create"><h3>{locale.t('ui.user_object_collection_editor.new_collection')}</h3>
                <label class="dialog-label">{locale.t('ui.user_object_collection_editor.name')}<input disabled={busy} class="text-input full-width" bind:value={newName} /></label>
                <label class="dialog-label">{locale.t('ui.user_object_collection_editor.purpose')}<textarea disabled={busy} class="text-input full-width" bind:value={newPurpose}></textarea></label>
                <button class="button-with-text" disabled={busy || !newName.trim()} onclick={createNew}>
                    <img class="action-icon" alt={locale.t('ui.user_object_collection_editor.create')} src={confirmIcon} />
                    <span class="button-label">{locale.t('ui.user_object_collection_editor.create_and_close')}</span></button></div>
            <div class="collection-options">{#each collections as collection (collection.id)}
                <button class="blank-button" disabled={busy || memberIds.has(collection.id)}
                    onclick={() => addTo(collection.id)}>{collection.name}</button>{/each}</div>

    </dialog>
{/if}
