<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ConfirmBox.svelte
 ! purpose: Confirmation dialog
 ! -------------------------------------------------->

<script lang="ts">
    import confirmIcon from '$icons/confirm16.png';
    import cancelIcon from '$icons/cancel16.png';
    import { confirmState } from '$lib/confirm.svelte';
    
    function close(result: boolean) {
        confirmState.open = false;
        confirmState.response?.(result);
    }
</script>

{#if confirmState.open}
    <div class="modal-backdrop">
        <div class="modal-dialog" style={confirmState.position}>
            <h2>{confirmState.title}</h2>
            
            <p class="text-compact">{confirmState.message}</p>
            
            <div class="dialog-section spaced-horizontally">
                <button class="button-with-text"
                        onclick={() => close(true)} >
                    <img class="action-icon" alt="confirm" src={confirmIcon} />
                    <span>Ok</span>
                </button>
                <button class="button-with-text"
                        onclick={() => close(false)} >
                    <img class="action-icon" alt="cancel" src={cancelIcon} />
                    <span>Cancel</span>
                </button>
            </div>
        </div>
    </div>
{/if}

<style>

</style>
