<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: UserObjectTable.svelte
 ! purpose: Accordion table of objects belonging to a user-defined type
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
import ColumnFilter from '$components/controls/ColumnFilter.svelte';
import { filteredRows, filterStates } from '$lib/column-filters';
import type { UserDefinedType, UserObjectSummary } from '$lib/objects';
import tagIcon from '$icons/indicators/tag16.png';
import noTagIcon from '$icons/indicators/no-tag16.png';
import collectionIcon from '$icons/indicators/collection16.png';
import noCollectionIcon from '$icons/indicators/no-collection16.png';

let { type, objects: allRows, error, selectedId=$bindable(), selectedIds=$bindable() }: {
    type: UserDefinedType;
    objects: UserObjectSummary[];
    error: string | null;
    selectedId: string | null;
    selectedIds: Set<string>;
} = $props();

let objects = $derived(filteredRows(allRows, $filterStates.user));

let closed = $state(false);
let allSelected = $derived(objects.length > 0 && objects.every(item => selectedIds.has(item.id)));
function toggleSelected(id: string) {
    const next = new Set(selectedIds); next.has(id) ? next.delete(id) : next.add(id); selectedIds = next;
}
function toggleAll() {
    const next = new Set(selectedIds);
    objects.forEach(item => allSelected ? next.delete(item.id) : next.add(item.id));
    selectedIds = next;
}

</script>

{#if error}
    <div class="message-container error-message"><p>Error loading objects: {error}</p></div>
{:else}
    <table class="main-table user-object-table" data-user-object-table>
        <thead>
            <tr class="table-head table-section">
                <th class="clear"><input type="checkbox" checked={allSelected}
                    onclick={(event) => event.stopPropagation()} onchange={toggleAll} /></th>
                <th>
                    <ColumnFilter tab="user" columnKey="display_name" rows={allRows}>
                        Name
                    </ColumnFilter>
                </th>
                <th>
                    <ColumnFilter tab="user" columnKey="relative_path" rows={allRows}>
                        Relative path
                    </ColumnFilter>
                </th>
                <th class="indicator-column">
                    <ColumnFilter tab="user" columnKey="tag_values" rows={allRows}>
                        <img class="indicator-icon action-icon"
                        src={tagIcon} alt="Does the object have tags?" />
                    </ColumnFilter>
                </th>
                <th class="indicator-column">
                    <ColumnFilter tab="user" columnKey="collection_names" rows={allRows}>
                        <img class="indicator-icon action-icon"
                        src={collectionIcon} alt="Is the object in collection(s)?" />
                    </ColumnFilter>
                </th>
                <th>
                    <ColumnFilter tab="user" columnKey="deployment" rows={allRows}>
                        Location
                    </ColumnFilter>
                </th>
                <th class="error-column">
                    <ColumnFilter tab="user" columnKey="error_values" rows={allRows}>
                        E
                    </ColumnFilter>
                </th>
            </tr>
        </thead>
        <tbody>
            <tr class="table-section user-object-section">
                <td colspan="7">
                    <button type="button" aria-expanded={!closed} onclick={() => closed = !closed}>
                        <span class="section-marker" aria-hidden="true">{closed ? '▸' : '▾'}</span>
                        <span>{type.name} ({objects.length})</span>
                    </button>
                </td>
            </tr>
            {#if !closed}
                {#each objects as item (item.id)}
                    <tr class="table-clickable" aria-selected={selectedId === item.id}
                        onclick={() => selectedId = item.id}>
                        <td class="clear"><input type="checkbox" checked={selectedIds.has(item.id)}
                            onclick={(event) => event.stopPropagation()}
                            onchange={() => toggleSelected(item.id)} /></td>
                        <td class="object-name" title={item.display_name}>{item.display_name}</td>
                        <td class="relative-path" title={item.relative_path}>{item.relative_path}</td>
                        <td class="indicator-column"><img class="indicator-icon action-icon"
                            src={item.has_tags ? tagIcon : noTagIcon}
                            alt={item.has_tags ? 'Has tags' : 'No tags'} /></td>
                        <td class="indicator-column"><img class="indicator-icon action-icon"
                            src={item.has_collections ? collectionIcon : noCollectionIcon}
                            alt={item.has_collections ? 'In collections' : 'Not in a collection'} /></td>
                        <td>{item.deployment}</td>
                        <td class="error-column">{#if item.read_only}<span class="error-message">E</span>{/if}</td>
                    </tr>
                {/each}
            {/if}
        </tbody>
    </table>
{/if}
