<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: RepositorySummary.svelte
 ! purpose: Live repository statistics and selective scans
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

    import { onMount } from 'svelte';
    import closeIcon from '$icons/actions/close8.png';
    import refreshIcon from '$icons/actions/refresh16.png';
    import { apiFetch, getUrl, parseResponse, serverUnresponsive } from '$lib/api';
    import { startScan, type ScanScope } from '$lib/admin';
    import type { Operation } from '$lib/models';
    import { statusMonitor } from '$lib/status.svelte';
    import { modalDialog } from '$lib/modal-dialog';

    type Counts = { working: number; archive: number; synced: number; total: number; errors: number };
    type Summary = {
        sections: Record<string, Counts>;
        operation: Operation | null;
        can_scan: boolean;
    };

    let { onClose }: { onClose: () => void } = $props();
    let summary = $state<Summary | null>(null); let error = $state<string | null>(null); let submitting = $state<ScanScope | null>(null);
    let operation = $derived(summary?.operation ?? null);
    let busy = $derived(submitting !== null || operation?.state === 'pending' || operation?.state === 'running');
    const sections = [
        { key: 'models', title: locale.t('ui.repository_summary.models'), individual: true },
        { key: 'workflows', title: locale.t('ui.repository_summary.workflows'), individual: false },
        { key: 'user_objects', title: locale.t('ui.repository_summary.user_types'), individual: true },
        { key: 'collections', title: locale.t('ui.repository_summary.collections'), individual: false }
    ] as const;

    function scanning(scope: string): boolean {
        if (submitting === scope) return true;
        if (!busy || operation?.type !== 'scan') return false;

        return operation.progress.scope === undefined || operation.progress.scope === 'all'
            || operation.progress.scope === scope;
    }

    onMount(() => {
        let cancelled = false;
        let timer: ReturnType<typeof setTimeout>; async function refresh(): Promise<void> {
            try {
                const response = await apiFetch(getUrl('/repository-summary'));
                const result = await parseResponse<Summary>(response, value => value, 'repositorySummary');

                if (!cancelled && submitting === null) {
                    if (result.ok) {
                        summary = result.data;
                        error = null;
                    } else {
                        error = result.message ?? locale.t('ui.repository_summary.cannot_load_repository_summary');
                    }
                }
            } catch (cause) {
                if (!cancelled) {
                    error = cause instanceof Error ? cause.message : locale.t('ui.repository_summary.cannot_load_repository_summary');
                }
            }

            if (!cancelled) {
                timer = setTimeout(() => void refresh(), 500);
            }
        }

        void refresh();

        return () => {
            cancelled = true;
            clearTimeout(timer);
        };
    });

    async function scan(scope: ScanScope): Promise<void> {
        if (busy || !summary?.can_scan) return;
        submitting = scope;
        error = null;

        try {
            const result = await startScan(false, scope);

            if (result.ok) {
                summary.operation = result.data;
                statusMonitor.track(result.data);
            } else {
                error = result.message ?? locale.t('ui.repository_summary.cannot_start_scan');
            }
        } catch (cause) {
            error = cause instanceof Error ? cause.message : locale.t('ui.repository_summary.cannot_start_scan');
        } finally {
            submitting = null;
        }
    }
</script>

<dialog class="nav-dialog repository-summary" use:modalDialog aria-label={locale.t('ui.repository_summary.repository_summary')}
        oncancel={event => {
            event.preventDefault();
            onClose();
        }}>
    <header class="dialog-header spaced-horizontally">
        <h2>{locale.t('ui.repository_summary.repository')}</h2>
        <button class="round" type="button" aria-label={locale.t('ui.repository_summary.close_repository_summary')} onclick={onClose}>
            <img class="action-icon" alt="" src={closeIcon} />
        </button>
    </header>

    {#if $serverUnresponsive}
        <p class="bold-text" role="alert">{locale.t('ui.repository_summary.the_server_is_not_responding')}</p>
    {:else}
        {#if error}
            <p class="error-details" role="alert">{error}</p>
        {/if}

        <div class="repository-sections">
            {#if summary}
                {#each sections as section}
                    {@const counts = summary.sections[section.key]}
                    <section class="repository-section">
                        <div>
                            <h2>{section.title}</h2>
                            <div>{counts.working} in working set</div>
                            <div>{counts.archive} in archive</div>
                            <div>{counts.synced} synchronized</div>
                            <div class="bold-text">{counts.total} in total</div>
                            <div class:error-details={counts.errors > 0}>{counts.errors} errors</div>

                            {#if section.individual}
                                <div class="annotation repository-annotation">
                                    {locale.t('ui.repository_summary.individual_types_can_be_scanned_from_the_settings_dialog')}
                                </div>
                            {/if}
                        </div>

                        {#if section.key !== 'collections'}
                            <button class="button-with-text" type="button"
                                    disabled={busy || !summary.can_scan}
                                    aria-label={locale.t('messages.refresh_section', {section: section.title})}
                                    onclick={() => scan(section.key as ScanScope)}>
                                <img class="action-icon-small" alt="" src={refreshIcon} />
                                <span>{locale.t(scanning(section.key) ? 'dynamic.scanning' : 'dynamic.refresh')}</span>
                            </button>
                        {/if}

                    </section>
                {/each}
            {:else}
                <p>{locale.t('ui.repository_summary.loading_repository_summary')}</p>
            {/if}
        </div>
    {/if}
</dialog>
