<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: WorkflowTable.svelte
 ! purpose: Workflow table and selection
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

import ColumnFilter from '$components/controls/ColumnFilter.svelte';
import { filteredRows, filterStates } from '$lib/column-filters';
import { type WorkflowSummary } from '$lib/objects';
import tagIcon from '$icons/indicators/tag16.png';
import noTagIcon from '$icons/indicators/no-tag16.png';
import collectionIcon from '$icons/indicators/collection16.png';
import noCollectionIcon from '$icons/indicators/no-collection16.png';
let { workflows: allRows, error, disabled=false, selected_id=$bindable(), selected_ids=$bindable() }: {
    workflows: WorkflowSummary[]; error: string | null; selected_id: string | null;
    selected_ids: Set<string>; disabled?: boolean;
} = $props();

let workflows = $derived(filteredRows(allRows, $filterStates.workflows));
let allVisibleSelected = $derived(workflows.length > 0 &&
    workflows.every(workflow => selected_ids.has(workflow.id)));
function toggleSelected(id: string) {
    if (disabled) return;

    const next = new Set(selected_ids); next.has(id) ? next.delete(id) : next.add(id);
    selected_ids = next;
}
function toggleAllVisible() {
    if (disabled) return;

    const next = new Set(selected_ids);
    workflows.forEach(workflow => allVisibleSelected ? next.delete(workflow.id) : next.add(workflow.id));
    selected_ids = next;
}

</script>

{#if error}<div class="message-container error-message"><p>Error loading workflows: {error}</p></div>
{:else}
<table class="main-table workflow-table" data-workflow-table>
    <thead><tr class="table-head table-section">
        <th class="clear selection-column"><input type="checkbox" checked={allVisibleSelected} disabled={disabled}
            onclick={event => event.stopPropagation()} onchange={toggleAllVisible} /></th>
        <th>
            <ColumnFilter tab="workflows" columnKey="internal_name" rows={allRows}>
                {locale.t('ui.workflow_table.name')}
            </ColumnFilter>
        </th>
        <th>{locale.t('ui.workflow_table.purpose')}</th>
        <th>
            <ColumnFilter tab="workflows" columnKey="relative_path" rows={allRows}>
                {locale.t('ui.workflow_table.relative_path')}
            </ColumnFilter>
        </th>
        <th class="indicator-column">
            <ColumnFilter tab="workflows" columnKey="tag_values" rows={allRows}>
                <img class="indicator-icon action-icon" src={tagIcon}
                alt={locale.t('ui.workflow_table.does_the_workflow_have_tags')}>
            </ColumnFilter>
        </th>
        <th class="indicator-column">
            <ColumnFilter tab="workflows" columnKey="collection_names" rows={allRows}>
                <img class="indicator-icon action-icon" src={collectionIcon}
                alt={locale.t('ui.workflow_table.is_the_workflow_in_collection_s')}>
            </ColumnFilter>
        </th>
        <th>
            <ColumnFilter tab="workflows" columnKey="deployment" rows={allRows}>
                {locale.t('ui.workflow_table.location')}
            </ColumnFilter>
        </th>
        <th class="error-column">
            <ColumnFilter tab="workflows" columnKey="error_values" rows={allRows}>
                {locale.t('ui.workflow_table.e')}
            </ColumnFilter>
        </th>
    </tr></thead>
    <tbody>{#each workflows as workflow (workflow.id)}
        <tr class:table-clickable={!disabled} aria-selected={selected_id === workflow.id}
            aria-disabled={disabled}
            onclick={() => { if (!disabled) selected_id = workflow.id; }}>
            <td class="clear selection-column"><input type="checkbox" checked={selected_ids.has(workflow.id)} disabled={disabled}
                onclick={event => event.stopPropagation()} onchange={() => toggleSelected(workflow.id)} /></td>
            <td>{workflow.internal_name}</td>
            <td class="ellipsized-cell" title={workflow.purpose}>{workflow.purpose}</td>
            <td class="ellipsized-cell" title={workflow.relative_path}>{workflow.relative_path}</td>
            <td class="indicator-column">
                <img class="indicator-icon action-icon"
                     src={workflow.has_tags ? tagIcon : noTagIcon}
                     alt={locale.t(workflow.has_tags ? 'dynamic.has_tags' : 'dynamic.no_tags')}>
            </td>
            <td class="indicator-column">
                <img class="indicator-icon action-icon"
                     src={workflow.has_collections ? collectionIcon : noCollectionIcon}
                     alt={locale.t(workflow.has_collections ? 'dynamic.in_collections' : 'dynamic.not_in_collection')}>
            </td>
            <td>{workflow.deployment}</td>
            <td class="error-column">
                {#if workflow.read_only}
                    <span class="error-message">{locale.t('ui.workflow_table.e')}</span>
                {/if}
            </td>
        </tr>
    {/each}</tbody>
</table>
{/if}
