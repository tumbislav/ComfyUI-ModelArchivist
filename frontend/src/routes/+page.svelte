<script lang=ts>
    import ArchivistHeader from './header/ArchivistHeader.svelte'
    import ModelContents from './models/ModelContents.svelte'
    import WorkflowContents from './workflows/WorkflowContents.svelte'
    import CollectionContents from './collections/CollectionContents.svelte'

    let currentContents = $state( 'models' );

    function selectContentsA(newContents) {
        console.log(newContents)
        currentContents = newContents;
    }


</script>

<heading class="page-header">
    <ArchivistHeader selectContents={ selectContentsA }/>
</heading>

<div class="page-contents">
    <!--
        <dialog>
        <fieldset>
        <label>
        <input>
        <legend>
        <optgroup>
        <option>
        <select>
        <textarea>

        <noscript>
    -->

    {#if currentContents === 'models'}
    <ModelContents/>
    {:else if currentContents === 'workflows'}
    <WorkflowContents/>
    {:else if currentContents === 'collections'}
    <WorkflowContents/>
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