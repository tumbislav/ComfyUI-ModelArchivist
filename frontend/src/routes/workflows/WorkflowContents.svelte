<script lang=ts>
    import WorkflowFilter from './WorkflowFilter.svelte'
    import WorkflowActions from './WorkflowActions.svelte'
    import WorkflowTable from './WorkflowTable.svelte'
    import WorkflowDetails from './WorkflowDetails.svelte'

    import { onMount } from "svelte";
    import { getWorkflows, getTags, type PrimaryObjectType, type WorkflowRecord } from "$lib/api";

    let workflows: WorkflowRecord[] = $state([]);
    let tags: str[] = $state([]);
    let workflows_error: string | null = $state(null);
    let tags_error: string | null = $state(null);
    let workflows_loading: boolean | null = $state(true);
    let tags_loading: boolean | null = $state(true);

    async function loadWorkflows() {
        workflows_loading = true;
        workflows_error = null;
        try {
            workflows = await getWorkflows();
        } catch (e) {
            workflows_error = e instanceof Error ? e.message : String(e);
        } finally {
            workflows_loading = false;
        }
    }

    async function loadTags() {
        tags_loading = true;
        tags_error = null;
        try {
            tags = await getTags("workflows");
        } catch (e) {
            tags_error = e instanceof Error ? e.message : String(e);
        } finally {
            tags_loading = false;
        }
    }

    async function refreshFilter() {
        loading = true;
        error = null;
        try {
            models = await getWorkflows();
        } catch (e) {
            error = e instanceof Error ? e.message : String(e);
        } finally {
            loading = false;
        }
    }

    onMount(async () => {
        loadWorkflows();
        loadTags();
    })

</script>

<div class="three-panel">
    <WorkflowFilter tags={tags} error={tags_error} loading={tags_loading} on:submit={refreshFilter} />
    <div class="content-with-actions">
        <WorkflowActions/>
        <WorkflowTable workflows={ workflows } error={ workflows_error } loading={ workflows_loading }/>
    </div>
    <WorkflowDetails/>
</div>


<style>

</style>