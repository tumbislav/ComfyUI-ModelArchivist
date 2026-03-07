<script lang=ts>
    import WorkflowFilter from './WorkflowFilter.svelte'
    import WorkflowActions from './WorkflowActions.svelte'
    import WorkflowTable from './WorkflowTable.svelte'
    import WorkflowDetails from './WorkflowDetails.svelte'

    let { workflows } = $state([]);
    let { error } = $state(false);
    let { loading } = $state(false);
</script>

<div class="three-panel">
    <WorkflowFilter loading={ false }/>
    <div class="content-with-actions">
        <WorkflowActions/>
        <WorkflowTable workflows={ workflows } error={ error } loading={ loading }/>
    </div>
    <WorkflowDetails/>
</div>


<style>

</style>