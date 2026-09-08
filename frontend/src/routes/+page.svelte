<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: +page.svelte
 ! purpose: Svelte entry point
 ! -------------------------------------------------->

<script lang=ts>
import ArchivistHeader from '$components/top/ArchivistHeader.svelte'
import ConfirmBox from '$components/top/ConfirmBox.svelte'
import ModelContents from '$components/models/ModelContents.svelte'
import WorkflowContents from '$components/workflows/WorkflowContents.svelte'
import UserObjectContents from '$components/user-objects/UserObjectContents.svelte'
import CollectionContents from '$components/collections/CollectionContents.svelte'

import { onMount } from 'svelte';
import { getServerStatus, startScan, type ActiveTab } from "$lib/admin";
import { initialTab, saveLastTab, scanAtStartup } from '$lib/preferences';
import { statusMonitor } from '$lib/status.svelte';
import { apiFetch, getUrl, parseResponse, serverUnresponsive } from '$lib/api';
import { type Operation } from '$lib/models';

let current_tab = $state<ActiveTab>( null );
let server_ready = $state( false );
let content_modal_open = $state(false);
let remapBlocked = $state(false);
let tagRevision = $state(0);
let startupError = $state<string | null>(null);

$effect(() => {
    if (server_ready && current_tab !== null) {
        saveLastTab(current_tab);
    }
});

onMount(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let startupChecked = false;
    let scanId: string | null = null;

    async function checkStatus(): Promise<void> {
        try {
            const status = await getServerStatus();

            if (cancelled) return;

            if (status.ok && status.data.started) {
                if (!startupChecked) {
                    startupChecked = true;

                    if (scanAtStartup() && !status.data.setup_required && !status.data.read_only) {
                        const scan = await startScan(true);

                        if (cancelled) return;

                        if (scan.ok) {
                            scanId = scan.data.id;
                            statusMonitor.track(scan.data);
                        } else if ($serverUnresponsive) {
                            startupChecked = false;
                        } else {
                            startupError = scan.message ?? 'Cannot start startup scan';
                        }
                    }
                }

                if (scanId !== null) {
                    const response = await apiFetch(getUrl(`/operations/${scanId}`));
                    const operation = await parseResponse<Operation>(response,
                        value => value, 'startupScan');

                    if (cancelled) return;

                    if (!operation.ok) {
                        if (!$serverUnresponsive) {
                            startupError = operation.message ?? 'Cannot retrieve startup scan';
                            scanId = null;
                        }
                    } else if (operation.data.state === 'failed') {
                        startupError = operation.data.error?.message ?? 'Startup scan failed';
                        scanId = null;
                    } else if (operation.data.state === 'succeeded') {
                        scanId = null;
                    }
                }

                if (startupChecked && scanId === null && status.data.ready) {
                    server_ready = true;
                    current_tab = initialTab();
                    return;
                }
            }
        } catch (error) {
            if (!cancelled) {
                startupError = error instanceof Error ? error.message : 'Cannot contact server';
            }
        }

        if (!cancelled) {
            timer = setTimeout(() => void checkStatus(), 1000);
        }
    }

    void checkStatus();

    return () => {
        cancelled = true;
        clearTimeout(timer);
    };
});
</script>

<heading class="page-header">
    <ArchivistHeader bind:current_tab navigationLocked={content_modal_open} serverReady={server_ready}
        {remapBlocked} onTagsRemapped={() => tagRevision += 1} />
</heading>

<div class="page-contents">
    {#if startupError && !$serverUnresponsive}
        <p role="alert">{startupError}</p>
    {/if}

    {#if server_ready && current_tab === 'models'}
        <ModelContents bind:multiEditorOpen={content_modal_open} bind:remapBlocked {tagRevision} />
    {:else if server_ready && current_tab === 'workflows'}
        <WorkflowContents bind:multiEditorOpen={content_modal_open} bind:remapBlocked {tagRevision} />
    {:else if server_ready && current_tab === 'user'}
        <UserObjectContents bind:multiEditorOpen={content_modal_open} bind:remapBlocked {tagRevision} />
    {:else if server_ready && current_tab === 'collections'}
        <CollectionContents bind:navigationLocked={content_modal_open} bind:remapBlocked {tagRevision} />
    {/if}
</div>

<ConfirmBox />

<style>
</style>
