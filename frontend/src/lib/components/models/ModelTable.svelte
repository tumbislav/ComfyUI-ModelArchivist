<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ModelTable.svelte
 ! purpose: Central component for models with model table
 ! -------------------------------------------------->

<script lang=ts>
import { type ModelSummary } from "$lib/objects";
import tagIcon from '$icons/indicators/tag16.png';
import noTagIcon from '$icons/indicators/no-tag16.png';
import collectionIcon from '$icons/indicators/collection16.png';
import noCollectionIcon from '$icons/indicators/no-collection16.png';

let {
    models,
    error,
    selected_id=$bindable(),
    selected_ids=$bindable(),
} : {
    models: ModelSummary[],
    error: string | null,
    selected_id: string | null,
    selected_ids: Set<string>,
} = $props();

let allVisibleSelected = $derived(
    models.length > 0 && models.every((model) => selected_ids.has(model.id))
);
let closedTypes = $state(new Set<string>());
let sections = $derived.by(() => {
    const grouped = new Map<string, ModelSummary[]>();
    for (const model of models) {
        const section = grouped.get(model.type);
        section ? section.push(model) : grouped.set(model.type, [model]);
    }
    return [...grouped.entries()];
});

function toggleSelected(modelId: string) {
    const next = new Set(selected_ids);
    next.has(modelId) ? next.delete(modelId) : next.add(modelId);
    selected_ids = next;
}

function toggleAllVisible() {
    const next = new Set(selected_ids);
    if (allVisibleSelected) {
        models.forEach((model) => next.delete(model.id));
    } else {
        models.forEach((model) => next.add(model.id));
    }
    selected_ids = next;
}

function toggleSection(type: string) {
    const next = new Set(closedTypes);
    next.has(type) ? next.delete(type) : next.add(type);
    closedTypes = next;
}
</script>

{#if error}
    <div class="message-container error-message">
        <p>Error loading models: {error}</p>
        <pre>{ JSON.stringify(models, null, 2) }</pre>
    </div>
{:else}

    <table class="main-table model-table">
        <thead>
        <tr class="table-head table-section">
            <th class="clear" id="header">
                <input type="checkbox" class="selector"
                       checked={allVisibleSelected}
                       onclick={(event) => event.stopPropagation()}
                       onchange={toggleAllVisible}>
            </th>
            <th>Model</th>
            <th>Relative path</th>
            <th>Format</th>
            <th class="base-model-column">Base</th>
            <th class="indicator-column">
                <img class="indicator-icon action-icon" src={tagIcon} alt="Does the model have tags?">
            </th>
            <th class="indicator-column">
                <img class="indicator-icon action-icon" src={collectionIcon} alt="Is the model in collection(s)?">
            </th>
            <th>Location</th>
            <th class="error-column">E</th>
        </tr>
        </thead>
        {#each sections as [type, sectionModels] (type)}
            <tbody>
                <tr class="table-section model-section">
                    <td colspan=9>
                        <button type="button"
                                aria-expanded={!closedTypes.has(type)}
                                onclick={() => toggleSection(type)}>
                            <span class="section-marker" aria-hidden="true">
                                {closedTypes.has(type) ? '▸' : '▾'}
                            </span>
                            <span>{type} ({sectionModels.length})</span>
                        </button>
                    </td>
                </tr>
                {#if !closedTypes.has(type)}
                    {#each sectionModels as model (model.id)}
                        <tr class="table-clickable"
                            aria-selected={selected_id === model.id}
                            onclick={() => selected_id = model.id} >
                            <td class="clear" id="{model.id}">
                                <input type="checkbox"
                                       checked={selected_ids.has(model.id)}
                                       onclick={(event) => event.stopPropagation()}
                                       onchange={() => toggleSelected(model.id)}>
                            </td>
                            <td class="model-name" title={model.internal_name}>
                                {model.internal_name}
                            </td>
                            <td class="relative-path" title={model.relative_path}>
                                {model.relative_path}
                            </td>
                            <td>{model.file_format}</td>
                            <td class="base-model-column"
                                title={model.base_model_abbreviation}>
                                {model.base_model_abbreviation}
                            </td>
                            <td class="indicator-column">
                                <img class="indicator-icon action-icon"
                                     src={model.has_tags ? tagIcon : noTagIcon}
                                     alt={model.has_tags ? 'Has tags' : 'No tags'}>
                            </td>
                            <td class="indicator-column">
                                <img class="indicator-icon action-icon"
                                     src={model.has_collections ? collectionIcon : noCollectionIcon}
                                     alt={model.has_collections ? 'In collections' : 'Not in a collection'}>
                            </td>
                            <td>{model.deployment}</td>
                            <td class="error-column">
                                {#if model.read_only}<span class="error-message">E</span>{/if}
                            </td>
                        </tr>
                    {/each}
                {/if}
            </tbody>
        {/each}
    </table>
{/if}

<style>

</style>
