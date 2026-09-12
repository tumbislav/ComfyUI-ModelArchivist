<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: UserObjectTable.svelte
 ! purpose: Accordion table of objects belonging to a user-defined type
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
import { locale } from '$lib/locale.svelte';
import ColumnFilter from '$components/controls/ColumnFilter.svelte';

import tagIcon from '$icons/indicators/tag16.png';
import noTagIcon from '$icons/indicators/no-tag16.png';
import collectionIcon from '$icons/indicators/collection16.png';
import noCollectionIcon from '$icons/indicators/no-collection16.png';

import { filteredRows, filterStates } from '$lib/column-filters';
import type { UserDefinedType, UserObjectSummary } from '$lib/objects';

let { type, objects: allRows, error, disabled=false, selectedId=$bindable(), selectedIds=$bindable() }: {
    type: UserDefinedType;
    objects: UserObjectSummary[];
    error: string | null;
    disabled?: boolean;
    selectedId: string | null;
    selectedIds: Set<string>;
} = $props();

let objects = $derived(filteredRows(allRows, $filterStates.user));

let allSelected = $derived(objects.length > 0 && objects.every(item => selectedIds.has(item.id)));
function toggleSelected(id: string) {
    if (disabled) return;

    const next = new Set(selectedIds); next.has(id) ? next.delete(id) : next.add(id); selectedIds = next;
}
function toggleAll() {
    if (disabled) return;

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
                <th class="clear selection-column"><input type="checkbox" checked={allSelected} disabled={disabled}
                    onclick={(event) => event.stopPropagation()} onchange={toggleAll} /></th>
                <th>
                    <ColumnFilter tab="user" columnKey="display_name" rows={allRows}>
                        {locale.t('ui.user_object_table.name')}
                    </ColumnFilter>
                </th>
                <th>
                    <ColumnFilter tab="user" columnKey="relative_path" rows={allRows}>
                        {locale.t('ui.user_object_table.relative_path')}
                    </ColumnFilter>
                </th>
                <th class="indicator-column">
                    <ColumnFilter tab="user" columnKey="tag_values" rows={allRows}>
                        <img class="indicator-icon action-icon"
                        src={tagIcon} alt={locale.t('ui.user_object_table.does_the_object_have_tags')} />
                    </ColumnFilter>
                </th>
                <th class="indicator-column">
                    <ColumnFilter tab="user" columnKey="collection_names" rows={allRows}>
                        <img class="indicator-icon action-icon"
                        src={collectionIcon} alt={locale.t('ui.user_object_table.is_the_object_in_collection_s')} />
                    </ColumnFilter>
                </th>
                <th>
                    <ColumnFilter tab="user" columnKey="deployment" rows={allRows}>
                        {locale.t('ui.user_object_table.location')}
                    </ColumnFilter>
                </th>
                <th class="error-column">
                    <ColumnFilter tab="user" columnKey="error_values" rows={allRows}>
                        {locale.t('ui.user_object_table.e')}
                    </ColumnFilter>
                </th>
            </tr>
        </thead>
        <tbody>
            {#each objects as item (item.id)}
                <tr class:table-clickable={!disabled} aria-selected={selectedId === item.id}
                    aria-disabled={disabled}
                    onclick={() => { if (!disabled) selectedId = item.id; }}>
                    <td class="clear selection-column"><input type="checkbox" checked={selectedIds.has(item.id)} disabled={disabled}
                        onclick={(event) => event.stopPropagation()}
                        onchange={() => toggleSelected(item.id)} /></td>
                    <td class="ellipsized-cell" title={item.display_name}>{item.display_name}</td>
                    <td class="ellipsized-cell" title={item.relative_path}>{item.relative_path}</td>
                    <td class="indicator-column"><img class="indicator-icon action-icon"
                        src={item.has_tags ? tagIcon : noTagIcon}
                        alt={locale.t(item.has_tags ? 'dynamic.has_tags' : 'dynamic.no_tags')} /></td>
                    <td class="indicator-column"><img class="indicator-icon action-icon"
                        src={item.has_collections ? collectionIcon : noCollectionIcon}
                        alt={locale.t(item.has_collections ? 'dynamic.in_collections' : 'dynamic.not_in_collection')} /></td>
                    <td>{item.deployment}</td>
                    <td class="error-column">{#if item.read_only}<span class="error-message">{locale.t('ui.user_object_table.e')}</span>{/if}</td>
                </tr>
            {/each}
        </tbody>
    </table>
{/if}
