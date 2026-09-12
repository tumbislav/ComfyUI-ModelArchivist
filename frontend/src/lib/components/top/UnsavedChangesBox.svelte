<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: UnsavedChangesBox.svelte
 ! purpose: Native modal control for resolving unsaved changes
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import cancelIcon from '$icons/actions/cancel16.png';
    import resetIcon from '$icons/actions/reset16.png';
    import saveIcon from '$icons/actions/save16.png';

    import { locale } from '$lib/locale.svelte';
    import { modalControl } from '$lib/modal-control';
    import {
        unsavedChangesState,
        type UnsavedChangesResult
    } from '$lib/unsaved-changes.svelte';

    function close(result: UnsavedChangesResult): void {
        unsavedChangesState.open = false;
        unsavedChangesState.response?.(result);
        unsavedChangesState.response = undefined;
    }
</script>

{#if unsavedChangesState.open}
    <dialog class="modal-control unsaved-changes-box"
            style={unsavedChangesState.position}
            use:modalControl
            aria-labelledby="unsaved-changes-title"
            oncancel={(event) => {
                event.preventDefault();
                close('cancel');
            }}>
        <h2 id="unsaved-changes-title">{unsavedChangesState.title}</h2>

        <p>{unsavedChangesState.message}</p>

        <div class="spaced-horizontally">
            <button class="button-with-text" onclick={() => close('cancel')}>
                <img class="action-icon" alt="" src={cancelIcon} />
                <span class="button-label">{locale.t('common.cancel')}</span>
            </button>
            <button class="button-with-text" onclick={() => close('discard')}>
                <img class="action-icon" alt="" src={resetIcon} />
                <span class="button-label">{locale.t('common.discard')}</span>
            </button>
            <button class="button-with-text"
                    disabled={unsavedChangesState.saveDisabled}
                    onclick={() => close('save')}>
                <img class="action-icon" alt="" src={saveIcon} />
                <span class="button-label">{locale.t('common.save')}</span>
            </button>
        </div>
    </dialog>
{/if}
