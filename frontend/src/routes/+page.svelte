<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: +page.svelte
 ! purpose: Svelte entry point
 ! -------------------------------------------------->

<script lang=ts>
    import ArchivistHeader from '$components/top/ArchivistHeader.svelte'
    import WaitingForStart from '$components/top/WaitingForStart.svelte'
    import ConfirmBox from '$components/top/ConfirmBox.svelte'
    import ModelContents from '$components/models/ModelContents.svelte'
    import WorkflowContents from '$components/workflows/WorkflowContents.svelte'
    import CollectionContents from '$components/collections/CollectionContents.svelte'

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

<ConfirmBox />

<style>
</style>