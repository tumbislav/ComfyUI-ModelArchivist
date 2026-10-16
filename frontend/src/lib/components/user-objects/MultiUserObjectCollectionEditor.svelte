<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: MultiUserObjectCollectionEditor.svelte
 ! purpose: Edit collection membership for selected user-defined objects
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';
    import addIcon from '$icons/actions/add16.png';
    import removeIcon from '$icons/actions/remove16.png';
    import CollectionPicker from '$components/collections/CollectionPicker.svelte';
    import { confirmBox } from '$lib/confirm.svelte';
    import { createCollection, updateCollectionUserObjects } from '$lib/collections';
    import type { CollectionSummary, UserObject } from '$lib/objects';

    let { items, disabled = false, busy = $bindable(false), onChanged }: {
        items: UserObject[];
        disabled?: boolean;
        busy?: boolean;
        onChanged: () => Promise<void>;
    } = $props();

    let section: HTMLElement;
    let addButton = $state<HTMLElement | null>(null);
    let selected = $state(new Set<string>());
    let popupOpen = $state(false);
    let error = $state<string | null>(null);
    let blocked = $derived(disabled || busy || items.length === 0 || items.some(item => item.read_only));
    let objectIds = $derived(items.map(item => item.id));
    let counts = $derived.by(() => {
        const result = new Map<string, {collection: CollectionSummary; count: number}>();
        for (const item of items) {
            for (const collection of item.collections) {
                const current = result.get(collection.id);
                result.set(collection.id, {collection, count: (current?.count ?? 0) + 1});
            }
        }
        return result;
    });
    let memberships = $derived([...counts.values()].sort((a, b) =>
        locale.compare(a.collection.name, b.collection.name)));

    function toggleSelected(id: string): void {
        const next = new Set(selected);
        next.has(id) ? next.delete(id) : next.add(id);
        selected = next;
    }

    function optionLabel(collection: CollectionSummary): string {
        return locale.plural('messages.collection_object_count', counts.get(collection.id)?.count ?? 0,
            {name: collection.name});
    }

    function optionDisabled(collection: CollectionSummary): boolean {
        return blocked || (counts.get(collection.id)?.count ?? 0) === items.length;
    }

    function openAdd(): void {
        if (!blocked) {
            error = null;
            popupOpen = true;
        }
    }

    async function addTo(collectionId: string): Promise<string | null> {
        if (blocked || (counts.get(collectionId)?.count ?? 0) === items.length) {
            return locale.t('ui.multi_user_object_editor.cannot_update_collection');
        }
        busy = true;
        try {
            const result = await updateCollectionUserObjects(collectionId, objectIds, true);
            if (!result.ok) return result.message
                ?? locale.t('ui.multi_user_object_editor.cannot_update_collection');
            await onChanged();
            return null;
        } finally {
            busy = false;
        }
    }

    async function createNew(name: string): Promise<string | null> {
        if (blocked) return locale.t('ui.multi_user_object_editor.cannot_update_collection');
        busy = true;
        try {
            const result = await createCollection({
                name, purpose: '', tags: [], models: [], workflows: [], children: [],
                user_objects: objectIds
            });
            if (!result.ok) return result.message
                ?? locale.t('ui.user_object_collection_editor.cannot_create_collection');
            await onChanged();
            return null;
        } finally {
            busy = false;
        }
    }

    async function removeSelected(): Promise<void> {
        if (blocked || selected.size === 0) return;
        const confirmed = await confirmBox({
            title: locale.t('ui.user_object_collection_editor.remove_from_collections'),
            message: locale.plural('messages.remove_selected_objects', selected.size),
            anchor: section
        });
        if (!confirmed || blocked) return;
        busy = true;
        error = null;
        try {
            for (const collectionId of selected) {
                const result = await updateCollectionUserObjects(collectionId, objectIds, false);
                if (!result.ok) {
                    error = result.message ?? locale.t('ui.multi_user_object_editor.cannot_update_collection');
                    return;
                }
            }
            selected = new Set();
        } finally {
            try {
                await onChanged();
            } finally {
                busy = false;
            }
        }
    }
</script>

<div class="space-below" bind:this={section}>
    <h2>{locale.t('ui.user_object_collection_editor.collections')}</h2>
    <div class="collection-members">
        {#each memberships as membership (membership.collection.id)}
            <label>
                <input type="checkbox"
                       checked={selected.has(membership.collection.id)}
                       disabled={blocked}
                       onchange={() => toggleSelected(membership.collection.id)} />
                <span>{optionLabel(membership.collection)}</span>
            </label>
        {:else}
            <p class="annotation">{locale.t('ui.user_object_collection_editor.not_in_a_collection')}</p>
        {/each}
    </div>
    {#if error && !popupOpen}
        <p class="error-message" role="alert">{error}</p>
    {/if}
    <div class="spaced-horizontally">
        <button class="button-with-text" bind:this={addButton} disabled={blocked} onclick={openAdd}>
            <img class="action-icon" alt={locale.t('ui.user_object_collection_editor.add')} src={addIcon} />
            <span class="button-label">{locale.t('ui.user_object_collection_editor.add_2')}</span>
        </button>
        <button class="button-with-text" disabled={blocked || selected.size === 0} onclick={removeSelected}>
            <img class="action-icon" alt={locale.t('ui.user_object_collection_editor.remove')} src={removeIcon} />
            <span class="button-label">{locale.t('ui.user_object_collection_editor.remove_from')}</span>
        </button>
    </div>
</div>

{#if popupOpen && addButton}
    <CollectionPicker anchor={addButton}
                      title={locale.t('ui.user_object_collection_editor.add_to_collection')}
                      {optionLabel}
                      {optionDisabled}
                      onAdd={addTo}
                      onCreate={createNew}
                      onClose={() => popupOpen = false} />
{/if}
