<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: MultiModelEditor.svelte
 ! purpose: Modal editor for multiple selected models
 ! -------------------------------------------------->

<script lang="ts">
let {
    onClose
}: {
    onClose: () => void;
} = $props();
</script>

<div class="content-modal-backdrop">
    <section class="multi-model-editor" role="dialog"
             aria-modal="true" aria-label="Edit selected models">
        <div class="dialog-section spaced-horizontally">
            <div></div>
            <button type="button" class="round" onclick={onClose}>×</button>
        </div>
    </section>
</div>

<style>
</style>
