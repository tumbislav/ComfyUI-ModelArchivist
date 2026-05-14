<script lang="ts">
    import { type ModelRecord } from "$lib/api";
    let {
        model,
        dirty,
        saving,
        onDirtyChange,
        onSave,
        onClose
    }: {
        model: ModelRecord;
        dirty: boolean;
        saving: boolean;
        onDirtyChange: (dirty: boolean) => void;
        onSave: (model: ModelRecord) => void | Promise<void>;
        onClose: () => void | Promise<void>;
    } = $props();

    function markDirty() {
        if (!dirty) {
            onDirtyChange(true);
        }
    }
</script>

<aside class="right-sidebar" id="model-details">

    <section class="details">
        <header>
            <h2>Model details</h2>
            <button type="button" onclick={onClose}>Close</button>
        </header>

        <label>
            Name
            <input
                    bind:value={model.name}
                    oninput={markDirty}
            />
        </label>

<!--        <label>
            Description
            <textarea
                    bind:value={object.description}
                    oninput={markDirty}
            />
        </label> -->

        <footer>
            <button
                    type="button"
                    disabled={!dirty || saving}
                    onclick={()
            => onSave(model)}
            >
            {saving ? 'Saving…' : 'Save'}
            </button>
        </footer>
    </section>

</aside>

<style>

</style>