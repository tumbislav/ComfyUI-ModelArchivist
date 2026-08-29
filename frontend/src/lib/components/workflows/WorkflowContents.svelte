<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: WorkflowContents.svelte
 ! purpose: Container for workflow browsing and editing
 ! -------------------------------------------------->

<script lang="ts">
import { onMount } from 'svelte';
import { fly } from 'svelte/transition';
import WorkflowActions from '$components/workflows/WorkflowActions.svelte';
import WorkflowTable from '$components/workflows/WorkflowTable.svelte';
import WorkflowDetails from '$components/workflows/WorkflowDetails.svelte';
import MultiWorkflowEditor from '$components/workflows/MultiWorkflowEditor.svelte';
import { sidebar_in_out } from '$lib/common';
import { confirmBox } from '$lib/confirm.svelte';
import { type Workflow, type WorkflowSummary, toWorkflowSummary } from '$lib/objects';
import { getWorkflow, getWorkflows, moveWorkflow, searchWorkflows, syncWorkflow,
    updateWorkflow, type WorkflowDestination, type WorkflowSearchCriteria } from '$lib/workflows';

let { multiEditorOpen=$bindable(false) }: { multiEditorOpen: boolean } = $props();
let workflows = $state<WorkflowSummary[]>([]), error = $state<string | null>(null);
let selected_id = $state<string | null>(null), selected_ids = $state<Set<string>>(new Set());
let active_id = $state<string | null>(null), active = $state<Workflow | null>(null);
let snapshot = $state<WorkflowSnapshot | null>(null), saving = $state(false), operating = $state(false);
let operationError = $state<string | null>(null);
// svelte-ignore non_reactive_update
let sidebar: HTMLElement;
type WorkflowSnapshot = {file_name: string; internal_name: string; purpose: string; tags: string[]};
const makeSnapshot = (workflow: Workflow): WorkflowSnapshot => ({file_name: workflow.file_name,
    internal_name: workflow.internal_name, purpose: workflow.purpose, tags: [...workflow.tags]});
let changed = $derived(active !== null && snapshot !== null &&
    (active.file_name !== snapshot.file_name || active.internal_name !== snapshot.internal_name ||
     active.purpose !== snapshot.purpose || active.tags.join('\0') !== snapshot.tags.join('\0')));
const emptyFilter: WorkflowSearchCriteria = {required_tags: [], forbidden_tags: [], name_prefix: ''};
let currentFilter = $state({...emptyFilter});
const hasFilters = (filter: WorkflowSearchCriteria) => !!filter.name_prefix ||
    filter.required_tags.length > 0 || filter.forbidden_tags.length > 0;

onMount(refreshWorkflows);
$effect(() => { if (selected_id && selected_id !== active_id) void openDetails(selected_id); });
$effect(() => { if (active && sidebar) sidebar.focus(); });

async function refreshWorkflows(): Promise<boolean> {
    const result = hasFilters(currentFilter) ? await searchWorkflows(currentFilter) : await getWorkflows();
    if (!result.ok) { error = result.message ?? 'Cannot load workflows'; return false; }
    workflows = result.data; error = null; return true;
}
async function closeDetails(): Promise<boolean> {
    if (changed && !await confirmBox({title: 'Unsaved changes', message: 'Discard workflow changes?'})) {
        selected_id = active_id; return false;
    }
    selected_id = null; active_id = null; active = null; snapshot = null; operationError = null; return true;
}
async function openDetails(id: string) {
    if (!await closeDetails()) return;
    const result = await getWorkflow(id);
    if (!result.ok) { error = result.message ?? 'Cannot load workflow'; return; }
    active = result.data; active_id = id; selected_id = id; snapshot = makeSnapshot(result.data);
}
async function save() {
    if (!active) return; saving = true;
    const result = await updateWorkflow(active); saving = false;
    if (!result.ok) { operationError = result.message ?? 'Cannot save workflow'; return; }
    active = result.data; snapshot = makeSnapshot(result.data);
    workflows = workflows.map(item => item.id === result.data.id ? toWorkflowSummary(result.data) : item);
}
async function runOperation(destination: WorkflowDestination | null) {
    if (!active) return; operating = true; operationError = null;
    const id = active.id;
    const result = destination === null ? await syncWorkflow(id) : await moveWorkflow(id, destination);
    operating = false;
    if (!result.ok || result.data.allowed === false) {
        operationError = result.ok ? String(result.data.errors ?? 'Workflow operation failed') : result.message ?? 'Workflow operation failed'; return;
    }
    await refreshWorkflows(); await refreshActive();
}
async function refreshActive() {
    if (!active_id) return;
    const result = await getWorkflow(active_id);
    if (!result.ok) { operationError = result.message ?? 'Cannot refresh workflow'; return; }
    active = result.data; snapshot = makeSnapshot(result.data); await refreshWorkflows();
}
async function filterWorkflows(filter: WorkflowSearchCriteria): Promise<boolean> {
    if (!await closeDetails()) return false;
    const previous = currentFilter;
    currentFilter = {required_tags: [...filter.required_tags], forbidden_tags: [...filter.forbidden_tags], name_prefix: filter.name_prefix};
    if (await refreshWorkflows()) return true; currentFilter = previous; return false;
}
async function openMulti() { if (selected_ids.size >= 2 && await closeDetails()) multiEditorOpen = true; }
function closeMulti() { multiEditorOpen = false; }
async function refreshAfterMultiEdit() { await refreshWorkflows(); }
async function handleEscape(event: KeyboardEvent) { if (event.key === 'Escape') await closeDetails(); }
async function clickOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (target.closest('[data-workflow-table]') || target.closest('[data-workflow-details]') ||
        target.closest('[data-workflow-actions]')) return;
    await closeDetails();
}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="object-view" onclick={clickOutside}>
    <WorkflowActions selectedCount={selected_ids.size} onFilter={filterWorkflows} onOpenMulti={openMulti} />
    <div class="object-results"><main data-workflow-table><WorkflowTable {workflows} {error}
        bind:selected_id bind:selected_ids /></main></div>
    {#if active}
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <aside class="right-sidebar" data-workflow-details tabindex="-1" onkeydown={handleEscape}
            bind:this={sidebar} transition:fly={sidebar_in_out}>
            <WorkflowDetails bind:workflow={active} {changed} {saving} {operating} {operationError}
                onSave={save} onClose={closeDetails} onSync={() => runOperation(null)}
                onMove={runOperation} onCollectionsChanged={refreshActive} />
        </aside>
    {/if}
    {#if multiEditorOpen}<MultiWorkflowEditor workflowIds={[...selected_ids]} onClose={closeMulti}
        onChanged={refreshAfterMultiEdit} />{/if}
</div>
