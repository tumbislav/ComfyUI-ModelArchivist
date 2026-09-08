<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: RepositorySummary.svelte
 ! purpose: Live repository statistics and selective scans
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import { onMount } from 'svelte';
    import closeIcon from '$icons/actions/close8.png';
    import refreshIcon from '$icons/actions/refresh16.png';
    import { apiFetch, getUrl, parseResponse, serverUnresponsive } from '$lib/api';
    import { startScan, type ScanScope } from '$lib/admin';
    import type { Operation } from '$lib/models';
    import { statusMonitor } from '$lib/status.svelte';

    type Counts = { working: number; archive: number; synced: number; total: number; errors: number };
    type Summary = {
        sections: Record<string, Counts>;
        operation: Operation | null;
        can_scan: boolean;
    };

    let { onClose }: { onClose: () => void } = $props();
    let dialog = $state<HTMLDialogElement>();
    let summary = $state<Summary | null>(null);
    let error = $state<string | null>(null);
    let submitting = $state<ScanScope | null>(null);
    let operation = $derived(summary?.operation ?? null);
    let busy = $derived(submitting !== null || operation?.state === 'pending' || operation?.state === 'running');
    const sections = [
        { key: 'models', title: 'Models', individual: true },
        { key: 'workflows', title: 'Workflows', individual: false },
        { key: 'user_objects', title: 'User types', individual: true },
        { key: 'collections', title: 'Collections', individual: false }
    ] as const;

    function scanning(scope: string): boolean {
        if (submitting === scope) return true;
        if (!busy || operation?.type !== 'scan') return false;

        return operation.progress.scope === undefined || operation.progress.scope === 'all'
            || operation.progress.scope === scope;
    }

    onMount(() => {
        dialog?.showModal();
        let cancelled = false;
        let timer: ReturnType<typeof setTimeout>;

        async function refresh(): Promise<void> {
            try {
                const response = await apiFetch(getUrl('/repository-summary'));
                const result = await parseResponse<Summary>(response, value => value, 'repositorySummary');

                if (!cancelled && submitting === null) {
                    if (result.ok) {
                        summary = result.data;
                        error = null;
                    } else {
                        error = result.message ?? 'Cannot load repository summary';
                    }
                }
            } catch (cause) {
                if (!cancelled) {
                    error = cause instanceof Error ? cause.message : 'Cannot load repository summary';
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
                error = result.message ?? 'Cannot start scan';
            }
        } catch (cause) {
            error = cause instanceof Error ? cause.message : 'Cannot start scan';
        } finally {
            submitting = null;
        }
    }
</script>

<dialog class="repository-summary" bind:this={dialog} aria-label="Repository summary"
        oncancel={event => {
            event.preventDefault();
            onClose();
        }}>
    <header class="spaced-horizontally">
        <h2>Repository</h2>
        <button class="round" type="button" aria-label="Close repository summary" onclick={onClose}>
            <img class="action-icon" alt="" src={closeIcon} />
        </button>
    </header>

    {#if $serverUnresponsive}
        <p class="bold-text" role="alert">The server is not responding</p>
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
                                <div class="annotation repository-annotation">Individual types can be scanned from settings</div>
                            {/if}
                        </div>

                        {#if section.key !== 'collections'}
                            <button class="button-with-text" type="button"
                                    disabled={busy || !summary.can_scan}
                                    aria-label={`Refresh ${section.title}`}
                                    onclick={() => scan(section.key as ScanScope)}>
                                <img class="action-icon-small" alt="" src={refreshIcon} />
                                <span>{scanning(section.key) ? 'Scanning...' : 'Refresh'}</span>
                            </button>
                        {/if}

                    </section>
                {/each}
            {:else}
                <p>Loading repository summary...</p>
            {/if}
        </div>
    {/if}
</dialog>
