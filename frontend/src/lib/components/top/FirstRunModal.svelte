<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: FirstRunModal.svelte
 ! purpose: Explain required repository setup on the first application run
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import settingsIcon from '$icons/nav/settings24.png';

    import { locale } from '$lib/locale.svelte';
    import { modalControl } from '$lib/modal-control';

    let { onContinue }: { onContinue: () => void } = $props();
</script>

<dialog class="modal-control first-run-dialog"
        use:modalControl
        aria-labelledby="first-run-title"
        oncancel={event => event.preventDefault()}>
    <h1 id="first-run-title">{locale.t('ui.first_run.welcome')}</h1>

    <p>{locale.t('ui.first_run.setup_explanation')}</p>

    <div class="first-run-actions">
        <button class="button-with-text" type="button" onclick={onContinue}>
            <img class="action-icon" alt="" src={settingsIcon} />
            <span>{locale.t('ui.first_run.open_settings')}</span>
        </button>
    </div>
</dialog>

<style>
    .first-run-dialog {
        width: min(32rem, calc(100vw - 2 * var(--gap-medium)));
    }

    .first-run-actions {
        display: flex;
        justify-content: flex-end;
        margin-top: var(--gap-mid);
    }
</style>
