<script lang=ts>
    import ModelFilter from './ModelFilter.svelte'
    import ModelActions from './ModelActions.svelte'
    import ModelTable from './ModelTable.svelte'
    import ModelDetails from './ModelDetails.svelte'


    import { onMount } from "svelte";
    import { getModels, getModelsRescan, type ModelRecord } from "$lib/api";

    let models: ModelRecord[] = $state([]);
    let error: string | null = $state(null);
    let loading = $state(true);

    async function refresh() {
        loading = true;
        error = null;
        try {
            models = await getModels();
        } catch (e) {
            error = e instanceof Error ? e.message : String(e);
        } finally {
            loading = false;
        }
    }

    async function updateFilter() {
        loading = true;
        error = null;
        try {
            models = await getModelsRescan();
        } catch (e) {
            error = e instanceof Error ? e.message : String(e);
        } finally {
            loading = false;
        }
    }

    onMount(refresh);
</script>


<div class="three-panel">
    <ModelFilter loading = { false } on:submit={ updateFilter } />
    <div class="content-with-actions">
        <ModelActions />
        <ModelTable models={ models } error={ error } loading={ loading }/>
    </div>
    <ModelDetails />
</div>


<style>

</style>