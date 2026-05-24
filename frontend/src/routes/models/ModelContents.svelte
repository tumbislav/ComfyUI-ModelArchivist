<script lang=ts>
    import ModelFilter from './ModelFilter.svelte'
    import ModelActions from './ModelActions.svelte'
    import ModelTable from './ModelTable.svelte'
    import ModelDetails from './ModelDetails.svelte'

    import { onMount } from "svelte";
    import {
        clone,
        PrimaryObjectType,
        type Model,
        type ModelSummary,
        type Tag } from "$lib/objects";
    import { getModels } from "$lib/models";
    import { getTags } from "$lib/tags";
    import { type ApiResult } from "$lib/api";

    let models: ApiResult<ModelSummary[]> = $state( { ok: false } );

    let tags: ApiResult<string[]> = $state( { ok: false } );

    async function refreshFilter() {
        models = await getModels();
    }

    onMount(async () => {
        models = await getModels();
        tags = await getTags();
    });
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="three-panel" >
    <ModelFilter tags={tags} />
    <div class="content-with-actions">
        <ModelActions />
        <ModelTable { models } />
    </div>
    <ModelDetails />
</div>


<style>

</style>