<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ConfirmBox.svelte
 ! purpose: Confirmation dialog
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

    import confirmIcon from '$icons/actions/confirm16.png';
    import cancelIcon from '$icons/actions/cancel16.png';
    import { confirmState } from '$lib/confirm.svelte';
    import { modalControl } from '$lib/modal-control';
    
    function close(result: boolean) {
        confirmState.open = false;
        confirmState.response?.(result);
        confirmState.response = undefined;
    }
</script>

{#if confirmState.open}
    <dialog class="modal-control"
            style={confirmState.position}
            use:modalControl
            aria-labelledby="confirm-box-title"
            oncancel={(event) => {
                event.preventDefault();
                close(false);
            }}>
            <h2 id="confirm-box-title">{confirmState.title}</h2>
            
            <p>{confirmState.message}</p>
            
            <div class="space-below spaced-horizontally">
                <button class="button-with-text"
                        onclick={() => close(true)} >
                    <img class="action-icon" alt={locale.t('ui.confirm_box.confirm')} src={confirmIcon} />
                    <span>{locale.t('common.ok')}</span>
                </button>
                <button class="button-with-text"
                        onclick={() => close(false)} >
                    <img class="action-icon" alt={locale.t('ui.confirm_box.cancel')} src={cancelIcon} />
                    <span>{locale.t('common.cancel')}</span>
                </button>
            </div>
    </dialog>
{/if}

<style>

</style>
