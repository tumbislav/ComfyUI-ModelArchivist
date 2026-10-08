<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: FirstRunModal.svelte
 ! purpose: Explain required repository setup on the first application run
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import settingsIcon from '$icons/nav/settings24.png';

    import { locale } from '$lib/locale.svelte';
    import { modalControl } from '$lib/modal-control';
    import { getRepositorySettings, saveInitialFilesystemRoots } from '$lib/settings';
    import { onMount } from 'svelte';

    let { onContinue }: { onContinue: () => void } = $props();
    let workingRoots = $state('');
    let archiveRoots = $state('');
    let loading = $state(true);
    let saving = $state(false);
    let error = $state<string | null>(null);

    onMount(async () => {
        try {
            const result = await getRepositorySettings();
            if (!result.ok) {
                error = result.message ?? locale.t('ui.first_run.load_failed');
                return;
            }
            workingRoots = result.data.filesystem?.working_roots.join('\n') ?? '';
            archiveRoots = result.data.filesystem?.archive_roots.join('\n') ?? '';
            loading = false;
        } catch (cause) {
            error = cause instanceof Error ? cause.message : locale.t('ui.first_run.load_failed');
        }
    });

    async function continueSetup(): Promise<void> {
        if (loading || saving) return;
        saving = true;
        error = null;
        const roots = (value: string) => value.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
        try {
            const result = await saveInitialFilesystemRoots(roots(workingRoots), roots(archiveRoots));
            if (!result.ok) {
                error = result.message ?? locale.t('ui.first_run.save_failed');
                return;
            }
            onContinue();
        } catch (cause) {
            error = cause instanceof Error ? cause.message : locale.t('ui.first_run.save_failed');
        } finally {
            saving = false;
        }
    }
</script>

<dialog class="modal-control first-run-dialog"
        use:modalControl
        aria-labelledby="first-run-title"
        oncancel={event => event.preventDefault()}>
    <h1 id="first-run-title">{locale.t('ui.first_run.welcome')}</h1>

    <p>{locale.t('ui.first_run.setup_explanation')}</p>

    <p>{locale.t('ui.first_run.roots_instructions')}</p>

    <label class="dialog-label">
        {locale.t('filesystem.working_roots')}
        <textarea class="text-input" rows="5" bind:value={workingRoots}
                  disabled={loading || saving} spellcheck={false}></textarea>
    </label>

    <label class="dialog-label">
        {locale.t('filesystem.archive_roots')}
        <textarea class="text-input" rows="5" bind:value={archiveRoots}
                  disabled={loading || saving} spellcheck={false}></textarea>
    </label>

    {#if error}
        <p class="error-message" role="alert">{error}</p>
    {/if}

    <div class="first-run-actions">
        <button class="button-with-text" type="button" disabled={loading || saving} onclick={continueSetup}>
            <img class="action-icon" alt="" src={settingsIcon} />
            <span>{locale.t('ui.first_run.open_settings')}</span>
        </button>
    </div>
</dialog>

<style>
    .first-run-dialog {
        box-sizing: border-box;
        min-width: 0;
        width: min(32rem, calc(100vw - 2 * var(--gap-medium)));
        max-height: calc(100dvh - 2 * var(--gap-medium));
        overflow-y: auto;
    }

    .first-run-dialog .dialog-label {
        display: flex;
        flex-direction: column;
        gap: var(--gap-small);
        margin-top: var(--gap-mid);
    }

    .first-run-dialog textarea {
        box-sizing: border-box;
        width: 100%;
        resize: vertical;
    }

    .first-run-actions {
        display: flex;
        justify-content: flex-end;
        margin-top: var(--gap-mid);
    }
</style>
