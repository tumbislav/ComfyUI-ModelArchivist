<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: FirstRunModal.svelte
 ! purpose: Explain required repository setup on the first application run
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import confirmIcon from '$icons/actions/confirm16.png';
    import helpIcon from '$icons/actions/help16.png';
    import welcomeLogo from '$lib/assets/images/logo/Welcome-logo.png';

    import { locale } from '$lib/locale.svelte';
    import { modalControl } from '$lib/modal-control';
    import { getRepositorySettings, acknowledgeFirstRun } from '$lib/settings';
    import { onMount } from 'svelte';

    let { onContinue }: { onContinue: () => void } = $props();
    let workingRoots = $state('');
    let archiveRoots = $state('');
    let loading = $state(true);
    let saving = $state(false);
    let error = $state<string | null>(null);
    let mode = $state<'standalone' | 'comfyui'>('standalone');

    onMount(async () => {
        try {
            const result = await getRepositorySettings();
            if (!result.ok) {
                error = result.message ?? locale.t('ui.first_run.load_failed');
                return;
            }
            mode = result.data.mode;
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
        saving = true;
        error = null;
        try {
            const result = await acknowledgeFirstRun();
            if (!result.ok) {
                error = result.message ?? locale.t('ui.first_run.acknowledge_failed');
                return;
            }
            onContinue();
        } catch (cause) {
            error = cause instanceof Error ? cause.message : locale.t('ui.first_run.acknowledge_failed');
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
                {#each locale.paragraphs(`ui.first_run.roots_instructions_${mode}`) as paragraph}
                    <p>{paragraph}</p>
                {/each}
            </div>
        </div>
    </div>

    {#if mode === 'comfyui'}
        <div class="dialog-label">
            <span id="first-run-working-roots">{locale.t('filesystem.working_roots')}</span>
            <!-- svelte-ignore a11y_no_noninteractive_tabindex (Keyboard users must be able to focus and scroll the root list.) -->
            <div class="text-input first-run-roots" tabindex="0" role="region"
                 aria-labelledby="first-run-working-roots">{workingRoots}</div>
        </div>

        <div class="dialog-label">
            <span id="first-run-archive-roots">{locale.t('filesystem.archive_roots')}</span>
            <!-- svelte-ignore a11y_no_noninteractive_tabindex (Keyboard users must be able to focus and scroll the root list.) -->
            <div class="text-input first-run-roots" tabindex="0" role="region"
                 aria-labelledby="first-run-archive-roots">{archiveRoots}</div>
        </div>
    {/if}

    {#if error}
        <p class="error-message" role="alert">{error}</p>
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
            <img class="action-icon" alt="" src={confirmIcon} />
            <span>{locale.t('ui.first_run.open_settings')}</span>
        </button>
    </div>
</dialog>
