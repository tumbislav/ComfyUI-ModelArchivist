<script lang=ts>
    import ModelFilter from './ModelFilter.svelte'
    import ModelActions from './ModelActions.svelte'
    import ModelTable from './ModelTable.svelte'
    import ModelDetails from './ModelDetails.svelte'

    import { onMount } from "svelte";
    import { getModels, getModelsRescan, getTags, type PrimaryObjectType, type ModelRecord } from "$lib/api";

    let models: ModelRecord[] = $state([]);
    let tags: str[] = $state([]);
    let models_error: string | null = $state(null);
    let tags_error: string | null = $state(null);
    let models_loading = $state(true);
    let tags_loading = $state(true);

    async function loadModels() {
        models_loading = true;
        models_error = null;
        try {
            models = await getModels();
        } catch (e) {
            models_error = e instanceof Error ? e.message : String(e);
        } finally {
            models_loading = false;
        }
    }

    async function loadTags() {
        tags_loading = true;
        tags_error = null;
        try {
            tags = await getTags("models");
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
            models = await getModels();
        } catch (e) {
            error = e instanceof Error ? e.message : String(e);
        } finally {
            loading = false;
        }
    }

    onMount(async () => {
        loadModels();
        loadTags();
    })
</script>


<div class="three-panel">
    <ModelFilter tags={tags} error={tags_error} loading={tags_loading} on:submit={refreshFilter}/>
    <div class="content-with-actions">
        <ModelActions/>
        <ModelTable models={models} error={models_error} loading={models_loading}/>
    </div>
    <ModelDetails/>
</div>


<style>

</style>