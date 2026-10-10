<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: FirstRunModal.svelte
 ! purpose: Explain required repository setup on the first application run
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import settingsIcon from '$icons/actions/settings16.png';
    import helpIcon from '$icons/actions/help16.png';
    import welcomeLogo from '$lib/assets/images/logo/Welcome-logo.png';

    import { locale } from '$lib/locale.svelte';
    import { modalControl } from '$lib/modal-control';
    import { getRepositorySettings, saveInitialFilesystemRoots, type FilesystemIssue } from '$lib/settings';
    import { onMount } from 'svelte';

    let { onContinue }: { onContinue: () => void } = $props();
    let workingRoots = $state('');
    let archiveRoots = $state('');
    let loading = $state(true);
    let saving = $state(false);
    let error = $state<string | null>(null);
    let warnings = $state<FilesystemIssue[]>([]);
    let warnedRoots = $state('');

    const roots = (value: string) => value.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
    let rootValues = $derived(JSON.stringify([roots(workingRoots), roots(archiveRoots)]));
    let showWarnings = $derived(warnings.length > 0 && warnedRoots === rootValues);

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
        if (loading || saving) {
            return;
        }
        if (roots(workingRoots).length === 0 || roots(archiveRoots).length === 0) {
            error = locale.t('errors.filesystem_roots_required');
            return;
        }
        saving = true;
        error = null;
        try {
            const result = await saveInitialFilesystemRoots(
                roots(workingRoots), roots(archiveRoots), showWarnings);
            if (!result.ok) {
                error = result.message ?? locale.t('ui.first_run.save_failed');
                return;
            }
            if (result.data.warnings?.length) {
                warnings = result.data.warnings;
                warnedRoots = rootValues;
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
    <div class="first-run-introduction">
        <img class="first-run-logo" src={welcomeLogo} width="200" height="300" alt="" />

        <div class="first-run-text">
            <h1 id="first-run-title">{locale.t('ui.first_run.welcome')}</h1>

            <div class="multi-paragraph">
                {#each locale.paragraphs('ui.first_run.roots_instructions') as paragraph}
                    <p>{paragraph}</p>
                {/each}
            </div>
        </div>
    </div>

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

    {#if showWarnings}
        <div class="first-run-warnings" role="alert">
            {#each warnings as warning}
                <p>{locale.t('ui.first_run.inaccessible_directory', warning.params)}</p>
            {/each}
        </div>
    {/if}

    <div class="first-run-actions">
        <button class="button-with-text" type="button"
                onclick={() => window.open(
                    'https://github.com/tumbislav/ComfyUI-ModelArchivist/blob/master/docs/INSTALLATION.md',
                    '_blank', 'noopener,noreferrer')}>
            <img class="action-icon" alt="" src={helpIcon} />
            <span>{locale.t('ui.first_run.help')}</span>
        </button>
        <button class="button-with-text" type="button" disabled={loading || saving} onclick={continueSetup}>
            <img class="action-icon" alt="" src={settingsIcon} />
            <span>{locale.t(showWarnings ? 'ui.first_run.continue_anyway' : 'ui.first_run.open_settings')}</span>
        </button>
    </div>
</dialog>
