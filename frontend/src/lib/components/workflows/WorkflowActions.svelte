<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: WorkflowActions.svelte
 ! purpose: Workflow selection actions and expandable filtering panel
 ! -------------------------------------------------->

<script lang="ts">
import filterIcon from '$icons/actions/filter16.png';
import filterOffIcon from '$icons/actions/filter-off16.png';
import adjustIcon from '$icons/actions/adjust16.png';
import confirmIcon from '$icons/actions/confirm16.png';
import cancelIcon from '$icons/actions/cancel16.png';
import resetIcon from '$icons/actions/reset16.png';
import openIcon from '$icons/actions/open16.png';
import TagEditor from '$components/controls/TagEditor.svelte';
import { type WorkflowSearchCriteria } from '$lib/workflows';

let { selectedCount, onFilter, onOpenMulti }: {
    selectedCount: number;
    onFilter: (filter: WorkflowSearchCriteria) => Promise<boolean>;
    onOpenMulti: () => Promise<void>;
} = $props();
const emptyFilter = (): WorkflowSearchCriteria => ({required_tags: [], forbidden_tags: [], name_prefix: ''});
const copyFilter = (filter: WorkflowSearchCriteria): WorkflowSearchCriteria => ({
    required_tags: [...filter.required_tags], forbidden_tags: [...filter.forbidden_tags],
    name_prefix: filter.name_prefix
});
let expanded = $state(false);
let applied = $state(emptyFilter());
let draft = $state(emptyFilter());
let filterActive = $state(false);
let filterCount = $derived(applied.required_tags.length + applied.forbidden_tags.length +
    (applied.name_prefix ? 1 : 0));
function openEditor() { draft = copyFilter(applied); expanded = true; }
async function toggleFilter() {
    if (filterCount === 0) return openEditor();
    const next = !filterActive;
    if (await onFilter(next ? copyFilter(applied) : emptyFilter())) filterActive = next;
}
function cancel() { draft = copyFilter(applied); expanded = false; }
function clear() { draft = emptyFilter(); }
async function apply() {
    const next = copyFilter(draft);
    const active = !!next.name_prefix || next.required_tags.length > 0 || next.forbidden_tags.length > 0;
    if (await onFilter(active ? next : emptyFilter())) {
        applied = next; filterActive = active; expanded = false;
    }
}
</script>

<section class="filter-bar" data-workflow-actions>
    <div class="model-selection-actions">
        <button type="button" class="image-button" disabled={selectedCount < 2}
                onclick={onOpenMulti} aria-label="edit selected workflows">
            <img class="action-icon" alt="edit selected workflows" src={openIcon} />
        </button>
    </div>
    {#if !expanded}
        <div class="filter-buttons">
            <button type="button" class="image-button" onclick={toggleFilter}
                    aria-pressed={filterActive} aria-label="filter-on-off">
                <img class="action-icon" alt="filter" src={filterActive ? filterIcon : filterOffIcon} />
            </button>
            <button type="button" class="image-button" onclick={openEditor} aria-label="filter-adjust">
                <img class="action-icon" alt="adjust" src={adjustIcon} />
            </button>
        </div>
        <div class="filter-summary">
            {#if filterCount === 0}<span class="text-compact">No filters</span>{:else}
                {#if !filterActive}<span class="text-compact">(filter off)</span>{/if}
                {#if applied.name_prefix}<span class="actions-label">Name:</span><span>{applied.name_prefix}</span>{/if}
                {#if applied.required_tags.length}<span class="actions-label">Include tags:</span><span>{applied.required_tags.join(', ')}</span>{/if}
                {#if applied.forbidden_tags.length}<span class="actions-label">Exclude tags:</span><span>{applied.forbidden_tags.join(', ')}</span>{/if}
            {/if}
        </div>
    {:else}
        <div class="filter-buttons">
            <button class="image-button" onclick={apply}><img class="action-icon" alt="confirm" src={confirmIcon} /></button>
            <button class="image-button" onclick={cancel}><img class="action-icon" alt="cancel" src={cancelIcon} /></button>
            <button class="image-button" onclick={clear}><img class="action-icon" alt="clear" src={resetIcon} /></button>
        </div>
        <div class="filter-box"><p class="dialog-label">Name prefix</p>
            <input class="text-input full-width" bind:value={draft.name_prefix} /></div>
        <div class="filter-box"><TagEditor title="Include tags" tags={draft.required_tags}
            disabled={false} editable={false} onChanged={tags => draft.required_tags = tags} /></div>
        <div class="filter-box"><TagEditor title="Exclude tags" tags={draft.forbidden_tags}
            disabled={false} editable={false} onChanged={tags => draft.forbidden_tags = tags} /></div>
    {/if}
</section>
