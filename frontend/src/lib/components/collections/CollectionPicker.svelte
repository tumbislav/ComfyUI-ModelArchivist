<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: CollectionPicker.svelte
 ! purpose: Select or create a collection for repository objects
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import { onMount } from 'svelte';

    import closeIcon from '$icons/actions/close8.png';

    import { getCollections } from '$lib/collections';
    import { sideDialogPosition } from '$lib/confirm.svelte';
    import { locale } from '$lib/locale.svelte';
    import { modalControl } from '$lib/modal-control';
    import type { CollectionSummary } from '$lib/objects';
    import { unsavedChangesBox } from '$lib/unsaved-changes.svelte';

    let {
        anchor,
        title,
        optionLabel = (collection: CollectionSummary) => collection.name,
        optionDisabled = () => false,
        onAdd,
        onCreate,
        onClose
    }: {
        anchor: HTMLElement;
        title: string;
        optionLabel?: (collection: CollectionSummary) => string;
        optionDisabled?: (collection: CollectionSummary) => boolean;
        onAdd: (collectionId: string) => Promise<string | null>;
        onCreate: (name: string) => Promise<string | null>;
        onClose: () => void;
    } = $props();

    let collections = $state<CollectionSummary[]>([]);
    let position = $state('');
    let newName = $state('');
    let busy = $state(false);
    let error = $state<string | null>(null);

    onMount(async () => {
        position = sideDialogPosition(anchor, 'bottom');

        const envelope = await getCollections();
        if (!envelope.ok) {
            error = envelope.message ?? locale.t('ui.collection_picker.cannot_load_collections');
            return;
        }

        collections = envelope.data;
    });

    async function finish(action: () => Promise<string | null>) {
        busy = true;
        error = null;

        try {
            error = await action();
            if (!error) onClose();
        } finally {
            busy = false;
        }
    }

    async function addTo(collectionId: string) {
        await finish(() => onAdd(collectionId));
    }

    async function createAndAdd() {
        const name = newName.trim();
        if (!name) return;

        await finish(() => onCreate(name));
    }

    async function close() {
        if (newName !== '') {
            const result = await unsavedChangesBox({
                message: locale.t('messages.save_new_collection_before_continuing'),
                anchor,
                saveDisabled: !newName.trim()
            });

            if (result === 'cancel') return;
            if (result === 'save') {
                await createAndAdd();
                return;
            }
        }

        onClose();
    }
</script>

<dialog class="collection-picker"
        style={position}
        use:modalControl
        oncancel={(event) => {
            event.preventDefault();
            void close();
        }}>
    <div class="spaced-horizontally">
        <h2 class="tight-vertical">{title}</h2>
        <button disabled={busy}
                type="button"
                class="round"
                aria-label={locale.t('ui.collection_picker.close')}
                onclick={() => void close()}>
            <img class="action-icon" alt="" src={closeIcon} />
        </button>
    </div>

    {#if error}
        <p class="error-message">{error}</p>
    {/if}

    <div class="input-with-action collection-create">
        <input disabled={busy}
               class="text-input"
               aria-label={locale.t('ui.collection_picker.new_collection')}
               placeholder={locale.t('ui.collection_picker.new_collection')}
               bind:value={newName} />
        <button type="button"
                class="button-with-text"
                disabled={busy || !newName.trim()}
                onclick={createAndAdd}>
            <span class="button-label">{locale.t('ui.collection_picker.create_and_add')}</span>
        </button>
    </div>

    <div class="collection-options">
        {#each collections as collection (collection.id)}
            <button type="button"
                    class="blank-button"
                    disabled={busy || optionDisabled(collection)}
                    onclick={() => addTo(collection.id)}>
                {optionLabel(collection)}
            </button>
        {/each}
    </div>
</dialog>
