<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ConfirmBox.svelte
 ! purpose: Confirmation dialog
 ! -------------------------------------------------->

<script lang="ts">
    import { confirmState } from '$lib/confirm.svelte';

    function close(result: boolean) {
        confirmState.open = false;
        confirmState.response?.(result);
    }
</script>

{#if confirmState.open}
    <div class="modal-backdrop">
        <div class="modal-dialog">
            <h2>{confirmState.title}</h2>

            <p class="text-compact">{confirmState.message}</p>

            <div class="dialog-section spaced-horizontally">
                <button class="simple-button action-button"
                        onclick={() => close(true)} >
                    <span class="actions-label button-text">Ok</span>
                </button>
                <button class="simple-button action-button"
                        onclick={() => close(false)} >
                    <span class="actions-label button-text">Cancel</span>
                </button>
            </div>
        </div>
    </div>
{/if}

<style>
.modal-backdrop {
    backdrop-filter: blur(2px);
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
}

.modal-dialog {
    position: fixed;
    top: 20vh;
    left: 50%;
    transform: translate(-50%);
    padding: var(--gap-mid);
    min-width: var(--min-width-right);
    z-index: var(--z-popup);
    background: var(--bg-color);
    border-radius: var(--radius-mid);
    border: var(--solid-border);
    box-shadow: var(--shadow-right);
}
</style>