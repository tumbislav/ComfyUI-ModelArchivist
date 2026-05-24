<script lang=ts>
    import ArchivistHeader from './top/ArchivistHeader.svelte'
    import WaitingForStart from './top/WaitingForStart.svelte'
    import ModelContents from './models/ModelContents.svelte'
    import WorkflowContents from './workflows/WorkflowContents.svelte'
    import CollectionContents from './collections/CollectionContents.svelte'

    import { onMount } from 'svelte';
    import { getServerStatus } from "$lib/admin";
    import { type ApiResult } from "$lib/api";

    let current_contents = $state( 'models' );
    let server_ready = $state( false );

    function selectMainContents(new_contents) {
        current_contents = new_contents;
    }

    onMount(() => {
        async function checkStatus() {
            const status = await getServerStatus();
            server_ready = status.ok && status.data.ready;
        }

        checkStatus();

        const polling_interval = setInterval(async () => {
            checkStatus();

            if (server_ready) {
                clearInterval(polling_interval);
                return;
            }
        }, 1000);

        return () => clearInterval(polling_interval);
    });
</script>

<heading class="page-header">
    <ArchivistHeader selectContents={ selectMainContents }/>
</heading>

<div class="page-contents">
    {#if !server_ready}
    <WaitingForStart />
    {:else if current_contents === 'models'}
    <ModelContents/>
    {:else if current_contents === 'workflows'}
    <WorkflowContents/>
    {:else if current_contents === 'collections'}
    <CollectionContents/>
    {/if}
</div>

<style>
    .page-header {
        position: fixed;
        top: 0;
        z-index: 100;
        background: #ffffff;
        border-bottom: 1px solid #e0e0e0;
        height: var(--nav-height);
        width: 100%;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    .page-contents {
        position:fixed;
        height: calc(100vh - var(--nav-height));
        top: var(--nav-height);
        width: 100%;
        overflow-x: hidden;
        overflow-y: hidden;
    }
</style>