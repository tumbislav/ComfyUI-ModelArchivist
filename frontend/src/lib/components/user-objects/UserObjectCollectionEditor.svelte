<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: UserObjectCollectionEditor.svelte
 ! purpose: Edit collection membership for one user-defined object
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

import addIcon from '$icons/actions/add16.png';
import removeIcon from '$icons/actions/remove16.png';
import CollectionPicker from '$lib/components/collections/CollectionPicker.svelte';
import { confirmBox } from '$lib/confirm.svelte';
import { createCollection, updateCollectionUserObjects } from '$lib/collections';
import type { CollectionSummary, UserObject } from '$lib/objects';

let { item, onChanged }: {item: UserObject; onChanged: () => Promise<void>} = $props();
let section: HTMLElement;
let addButton = $state<HTMLElement | null>(null);
let selected = $state(new Set<string>());
let popupOpen = $state(false), busy = $state(false), error = $state<string | null>(null);
let memberIds = $derived(new Set(item.collections.map(collection => collection.id)));
function toggle(id: string) { const next = new Set(selected); next.has(id) ? next.delete(id) : next.add(id); selected = next; }
function openAdd() { popupOpen = true; }
function closePopup() { popupOpen = false; }
async function change(collectionId: string, add: boolean) {
    busy = true;
    const result = await updateCollectionUserObjects(collectionId, [item.id], add);
    busy = false;
    if (!result.ok) { error = result.message ?? locale.t('ui.user_object_collection_editor.cannot_update_collection'); return false; }
    await onChanged(); return true;
}
async function addTo(id: string): Promise<string | null> {
    return await change(id, true) ? null : error;
}
async function removeSelected() {
    if (!await confirmBox({title: locale.t('ui.user_object_collection_editor.remove_from_collections'),
        message: locale.plural('messages.remove_object_collections', selected.size), anchor: section})) return;
    for (const id of selected) if (!await change(id, false)) return;
    selected = new Set();
}
async function createNew(name: string): Promise<string | null> {
    const result = await createCollection({name, purpose: '', tags: [],
        models: [], workflows: [], user_objects: [item.id], children: []});
    if (!result.ok) return result.message ?? locale.t('ui.user_object_collection_editor.cannot_create_collection');
    await onChanged(); return null;
}
</script>

<div class="space-below" bind:this={section}>
    <h2 class="tight-vertical">
        {locale.t('ui.user_object_collection_editor.collections')}
    </h2>
    <div class="collection-members">
        {#each item.collections as collection (collection.id)}
            <label>
                <input type="checkbox"
                       checked={selected.has(collection.id)}
                       disabled={busy}
                       onchange={() => toggle(collection.id)} />
                <span>{collection.name}</span>
            </label>
        {:else}
            <p class="annotation">{locale.t('ui.user_object_collection_editor.not_in_a_collection')}</p>
        {/each}
    </div>
    {#if error && !popupOpen}
        <p class="error-message">{error}</p>
    {/if}
    <div class="spaced-horizontally">
        <button class="button-with-text"
                bind:this={addButton}
                disabled={busy || item.read_only}
                onclick={openAdd}>
            <img class="action-icon" alt={locale.t('ui.user_object_collection_editor.add')} src={addIcon} />
            <span class="button-label">{locale.t('ui.user_object_collection_editor.add_2')}</span>
        </button>
        <button class="button-with-text"
                disabled={busy || item.read_only || !selected.size}
                onclick={removeSelected}>
            <img class="action-icon" alt={locale.t('ui.user_object_collection_editor.remove')} src={removeIcon} />
            <span class="button-label">{locale.t('ui.user_object_collection_editor.remove_from')}</span>
        </button>
    </div>
</div>
{#if popupOpen && addButton}
    <CollectionPicker anchor={addButton}
                      title={locale.t('ui.user_object_collection_editor.add_to_collection')}
                      optionDisabled={(collection: CollectionSummary) => memberIds.has(collection.id)}
                      onAdd={addTo}
                      onCreate={createNew}
                      onClose={closePopup} />
{/if}
