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
import { getServerStatus, type ActiveTab } from "$lib/admin";

let current_tab = $state<ActiveTab>( null );
let server_ready = $state( false );
let content_modal_open = $state(false);

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
            current_tab = 'models';
            return;
        }
    }, 1000);
    
    return () => clearInterval(polling_interval);
});
</script>

<heading class="page-header">
    <ArchivistHeader bind:current_tab navigationLocked={content_modal_open}/>
</heading>

<div class="page-contents">
    {#if !server_ready}
        <WaitingForStart />
    {:else if current_tab === 'models'}
        <ModelContents bind:multiEditorOpen={content_modal_open}/>
    {:else if current_tab === 'workflows'}
        <WorkflowContents bind:multiEditorOpen={content_modal_open}/>
    {:else if current_tab === 'collections'}
        <CollectionContents/>
    {/if}
</div>

<ConfirmBox />

<style>
</style>
