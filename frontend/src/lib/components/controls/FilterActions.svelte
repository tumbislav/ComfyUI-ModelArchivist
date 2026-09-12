<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: FilterActions.svelte
 ! purpose: Table selection action, filter toggle, and applied filter summary
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

    import filterIcon from '$icons/actions/filter16.png';
    import filterOffIcon from '$icons/actions/filter-off16.png';
    import openIcon from '$icons/actions/open16.png';
    import { filterStates, filterSummary, toggleFilters, type FilterTab } from '$lib/column-filters';

    let { tab, selectedCount = 0, onOpenMulti }: {
        tab: FilterTab; selectedCount?: number; onOpenMulti?: () => void | Promise<void>;
    } = $props();
</script>

<section class="filter-bar" data-filter-actions>
    {#if onOpenMulti}
        <div class="model-selection-actions">
            <button class="image-button" type="button" disabled={selectedCount < 2}
                    onclick={onOpenMulti} aria-label={locale.t('ui.filter_actions.edit_selected_objects')}>
                <img class="action-icon" src={openIcon} alt="" />
            </button>
        </div>
    {/if}
    <div class="filter-buttons">
        <button class="image-button" type="button" aria-label={locale.t('ui.filter_actions.filter_on_off')}
                aria-pressed={$filterStates[tab].enabled} onclick={() => toggleFilters(tab)}>
            <img class="action-icon" src={$filterStates[tab].enabled ? filterIcon : filterOffIcon} alt="" />
        </button>
    </div>
    <div class="filter-summary">{filterSummary(tab, $filterStates[tab])}</div>
</section>
