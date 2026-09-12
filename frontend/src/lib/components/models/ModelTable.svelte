<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ModelTable.svelte
 ! purpose: Central component for models with model table
 ! -------------------------------------------------->

<script lang=ts>
    import { locale } from '$lib/locale.svelte';

import ColumnFilter from '$components/controls/ColumnFilter.svelte';
import { filteredRows, filterStates } from '$lib/column-filters';
import { type ModelSummary } from "$lib/objects";
import tagIcon from '$icons/indicators/tag16.png';
import noTagIcon from '$icons/indicators/no-tag16.png';
import collectionIcon from '$icons/indicators/collection16.png';
import noCollectionIcon from '$icons/indicators/no-collection16.png';

let {
    models: allRows,
    error,
    disabled = false,
    selected_id=$bindable(),
    selected_ids=$bindable(),
} : {
    models: ModelSummary[],
    error: string | null,
    disabled?: boolean,
    selected_id: string | null,
    selected_ids: Set<string>,
} = $props();

let models = $derived(filteredRows(allRows, $filterStates.models));

let allVisibleSelected = $derived(
    models.length > 0 && models.every((model) => selected_ids.has(model.id)) ); let closedTypes = $state(new Set<string>());
let sections = $derived.by(() => {
    const grouped = new Map<string, ModelSummary[]>();
    for (const model of models) {
        const section = grouped.get(model.type);
        section ? section.push(model) : grouped.set(model.type, [model]);
    }
    return [...grouped.entries()];
});

function toggleSelected(modelId: string) {
    if (disabled) return;

    const next = new Set(selected_ids);
    next.has(modelId) ? next.delete(modelId) : next.add(modelId);
    selected_ids = next;
}

function toggleAllVisible() {
    if (disabled) return;

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
            <th class="clear selection-column" id="header">
                <input type="checkbox" class="selector"
                       disabled={disabled}
                       checked={allVisibleSelected}
                       onclick={(event) => event.stopPropagation()}
                       onchange={toggleAllVisible}>
            </th>
            <th>
                <ColumnFilter tab="models" columnKey="internal_name" rows={allRows}>
                    {locale.t('ui.model_table.model')}
                </ColumnFilter>
            </th>
            <th>
                <ColumnFilter tab="models" columnKey="relative_path" rows={allRows}>
                    {locale.t('ui.model_table.relative_path')}
                </ColumnFilter>
            </th>
            <th>
                <ColumnFilter tab="models" columnKey="file_format" rows={allRows}>
                    {locale.t('ui.model_table.format')}
                </ColumnFilter>
            </th>
            <th class="base-model-column">
                <ColumnFilter tab="models" columnKey="base_model_abbreviation" rows={allRows}>
                    {locale.t('ui.model_table.base')}
                </ColumnFilter>
            </th>
            <th class="indicator-column">
                <ColumnFilter tab="models" columnKey="tag_values" rows={allRows}>
                    <img class="indicator-icon action-icon" src={tagIcon} alt={locale.t('ui.model_table.does_the_model_have_tags')}>
                </ColumnFilter>
            </th>
            <th class="indicator-column">
                <ColumnFilter tab="models" columnKey="collection_names" rows={allRows}>
                    <img class="indicator-icon action-icon" src={collectionIcon} alt={locale.t('ui.model_table.is_the_model_in_collection_s')}>
                </ColumnFilter>
            </th>
            <th>
                <ColumnFilter tab="models" columnKey="deployment" rows={allRows}>
                    {locale.t('ui.model_table.location')}
                </ColumnFilter>
            </th>
            <th class="error-column">
                <ColumnFilter tab="models" columnKey="error_values" rows={allRows}>
                    {locale.t('ui.model_table.e')}
                </ColumnFilter>
            </th>
        </tr>
        </thead>
        {#each sections as [type, sectionModels] (type)}
            <tbody>
                <tr class="table-section model-section">
                    <td colspan=9>
                        <button type="button"
                                class="table-section-header"
                                aria-expanded={!closedTypes.has(type)}
                                onclick={() => toggleSection(type)}>
                            <span class="section-marker" aria-hidden="true">
                                {closedTypes.has(type) ? '▸' : '▾'}
                            </span>
                            <span class="dialog-label">{type} ({sectionModels.length})</span>
                        </button>
                    </td>
                </tr>
                {#if !closedTypes.has(type)}
                    {#each sectionModels as model (model.id)}
                        <tr class:table-clickable={!disabled}
                            aria-selected={selected_id === model.id}
                            aria-disabled={disabled}
                            onclick={() => { if (!disabled) selected_id = model.id; }} >
                            <td class="clear selection-column" id="{model.id}">
                                <input type="checkbox"
                                       disabled={disabled}
                                       checked={selected_ids.has(model.id)}
                                       onclick={(event) => event.stopPropagation()}
                                       onchange={() => toggleSelected(model.id)}>
                            </td>
                            <td class="ellipsized-cell" title={model.internal_name}>
                                {model.internal_name}
                            </td>
                            <td class="ellipsized-cell" title={model.relative_path}>
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
                                     alt={locale.t(model.has_tags ? 'dynamic.has_tags' : 'dynamic.no_tags')}>
                            </td>
                            <td class="indicator-column">
                                <img class="indicator-icon action-icon"
                                     src={model.has_collections ? collectionIcon : noCollectionIcon}
                                     alt={locale.t(model.has_collections ? 'dynamic.in_collections' : 'dynamic.not_in_collection')}>
                            </td>
                            <td>{model.deployment}</td>
                            <td class="error-column">
                                {#if model.read_only}<span class="error-message">{locale.t('ui.model_table.e')}</span>{/if}
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
