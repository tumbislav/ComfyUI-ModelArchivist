<script lang=ts>
    import ModelFilter from './ModelFilter.svelte'
    import ModelActions from './ModelActions.svelte'
    import ModelTable from './ModelTable.svelte'
    import ModelDetails from './ModelDetails.svelte'

    import { onMount } from "svelte";
    import {
        clone,
        getModels,
        saveModel,
        getModelsRescan,
        getTags,
        type PrimaryObjectType,
        type ModelRecord
        } from "$lib/api";

    let models: ModelRecord[] = $state([]);
    let selectedId: string | null = $state(null);
    let dirty = $state(false);
    let tags: str[] = $state([]);
    let models_error: string | null = $state(null);
    let tags_error: string | null = $state(null);
    let models_loading: boolean | null = $state(true);
    let tags_loading: boolean | null = $state(true);

    let selectedModel = $derived(models.find(m => m.id == selectedId) ?? null);



    function ifDiscardChanges() {
        return !dirty || confirm('The model is changed. Discard changes?');
    }

    function selectModel(id: string) {
        if (id == selectedId) return;

        if (!ifDiscardChanges()) return;

        selectedId = id;
        dirty = false;
    }

    function closeDetails() {
        if (!ifDiscardChanges()) return;
        selectedId = null;
        dirty = false;
    }

    function updateModel(updatedModel: ModelRecord) {
        saved = saveModel(updatedModel);
        models = models.map(m =>
          m.id === saved.id ? saved : m
        );

        selectedId = saved.id;
        dirty = false;
    }

    function handleOutsideTableClick(event: MouseEvent) {
        const target = event.target as HTMLElement;

        if ( target.closest('#model-table') || target.closest('#model-details') ) { return; }

        if (selectedId) closeDetails();
    }

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


<div class="three-panel" onclick={handleOutsideTableClick}>
    <ModelFilter tags={tags} error={tags_error} loading={tags_loading} on:submit={refreshFilter} />
    <div class="content-with-actions">
        <ModelActions/>
        <ModelTable {models} {selectedId} onSelect={selectModel} error={models_error} loading={models_loading} />
    </div>
    <ModelDetails
        model={draft}
        {dirty}
        {saving}
        onDirtyChange={(value) => dirty = value}
        onSave={updateModel}
        onClose={closeDetails} />
</div>


<style>

</style>