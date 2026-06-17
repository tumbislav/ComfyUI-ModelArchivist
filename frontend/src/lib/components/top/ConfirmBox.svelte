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
                <button class="simple-button"
                        onclick={() => close(true)} >
                    <span class="button-text">Ok</span>
                </button>
                <button class="simple-button"
                        onclick={() => close(false)} >
                    <span class="button-text">Cancel</span>
                </button>
            </div>
        </div>
    </div>
{/if}

<style>

</style>