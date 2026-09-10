<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: CollectionTable.svelte
 ! purpose: Collection overview with direct membership and aggregate status
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
import ColumnFilter from '$components/controls/ColumnFilter.svelte';
import { filteredRows, filterStates } from '$lib/column-filters';
import type { CollectionOverview } from '$lib/objects';
import tagIcon from '$icons/indicators/tag16.png';
import noTagIcon from '$icons/indicators/no-tag16.png';
import modelIcon from '$icons/indicators/model16.png';
import noModelIcon from '$icons/indicators/no-model16.png';
import workflowIcon from '$icons/indicators/workflow16.png';
import noWorkflowIcon from '$icons/indicators/no-workflow16.png';
import udtIcon from '$icons/indicators/udt16.png';
import noUdtIcon from '$icons/indicators/no-udt16.png';
import collectionIcon from '$icons/indicators/collection16.png';
import noCollectionIcon from '$icons/indicators/no-collection16.png';

let {collections: allRows, selectedId, disabled=false, onOpen}: {
    collections: CollectionOverview[]; selectedId: string | null;
    disabled?: boolean; onOpen: (id: string) => Promise<void>;
} = $props();
const indicators = [
    {key: 'tag_values', present: 'has_tags', name: 'Tags', yes: tagIcon, no: noTagIcon},
    {key: 'model_names', present: 'has_models', name: 'Direct models', yes: modelIcon, no: noModelIcon},
    {key: 'workflow_names', present: 'has_workflows', name: 'Direct workflows', yes: workflowIcon, no: noWorkflowIcon},
    {key: 'user_object_names', present: 'has_user_objects', name: 'Direct UDT objects', yes: udtIcon, no: noUdtIcon},
    {key: 'child_collection_names', present: 'has_children', name: 'Direct collections', yes: collectionIcon, no: noCollectionIcon}
] as const;
let collections = $derived(filteredRows(allRows, $filterStates.collections));
</script>

<table class="main-table collection-table" data-collection-table>
    <thead><tr class="table-head table-section">
        <th>
            <ColumnFilter tab="collections" columnKey="name" rows={allRows}>
                Name
            </ColumnFilter>
        </th>
        <th>Purpose</th>
        {#each indicators as indicator}
            <th class="indicator-column">
                <ColumnFilter tab="collections" columnKey={indicator.key} rows={allRows}>
                    <img class="indicator-icon action-icon"
                    src={indicator.yes} alt={indicator.name} title={indicator.name} />
                </ColumnFilter>
            </th>
        {/each}
        <th class="location-column">
            <ColumnFilter tab="collections" columnKey="deployment" rows={allRows}>
                Location
            </ColumnFilter>
        </th>
        <th class="error-column">
            <ColumnFilter tab="collections" columnKey="error_values" rows={allRows}>
                E
            </ColumnFilter>
        </th>
    </tr></thead>
    <tbody>
        {#each collections as item (item.id)}
            <tr class="table-clickable" aria-selected={selectedId === item.id}
                tabindex={disabled ? -1 : 0}
                onkeydown={event => {
                    if (event.target === event.currentTarget && !disabled && ['Enter', ' '].includes(event.key)) {
                        event.preventDefault(); void onOpen(item.id);
                    }
                }}
                onclick={() => { if (!disabled) void onOpen(item.id); }}>
                <td class="ellipsized-cell" title={item.name}>{item.name}</td>
                <td class="ellipsized-cell" title={item.purpose}>{item.purpose}</td>
                {#each indicators as indicator}
                    <td class="indicator-column"><img class="indicator-icon action-icon"
                        src={item[indicator.present] ? indicator.yes : indicator.no}
                        alt={`${indicator.name}: ${item[indicator.present] ? 'yes' : 'no'}`} /></td>
                {/each}
                <td>{item.deployment}</td>
                <td class="error-column">{#if item.error_count > 0}
                    <span class="error-message" title={`${item.error_count} members have errors`}>E</span>
                {/if}</td>
            </tr>
        {:else}<tr><td colspan="9">No collections.</td></tr>{/each}
    </tbody>
</table>
