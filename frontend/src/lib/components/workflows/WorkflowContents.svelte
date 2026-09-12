<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: WorkflowContents.svelte
 ! purpose: Container for workflow browsing and editing
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

import { onMount, untrack } from 'svelte';
import { fly } from 'svelte/transition';
import FilterActions from '$components/controls/FilterActions.svelte';
import WorkflowTable from '$components/workflows/WorkflowTable.svelte';
import WorkflowDetails from '$components/workflows/WorkflowDetails.svelte';
import MultiWorkflowEditor from '$components/workflows/MultiWorkflowEditor.svelte';
import { sidebar_in_out } from '$lib/common';
import { confirmBox } from '$lib/confirm.svelte';
import { unsavedChangesBox } from '$lib/unsaved-changes.svelte';
import { type Workflow, type WorkflowSummary } from '$lib/objects';
import { getWorkflow, getWorkflows, moveWorkflow, syncWorkflow,
    updateWorkflow, getWorkflowRelativePaths, relocateWorkflows,
    type WorkflowDestination } from '$lib/workflows';

let { multiEditorOpen=$bindable(false), remapBlocked=$bindable(false), tagRevision=0 }: {
    multiEditorOpen: boolean;
    remapBlocked?: boolean;
    tagRevision?: number;
} = $props();

$effect(() => {
    remapBlocked = changed || saving || operating || multiEditorOpen;
});

$effect(() => {
    if (tagRevision > 0) {
        untrack(() => {
            void refreshWorkflows();
            if (active_id) void refreshActive();
        });
    }
});
let workflows = $state<WorkflowSummary[]>([]), error = $state<string | null>(null); let selected_id = $state<string | null>(null), selected_ids = $state<Set<string>>(new Set()); let active_id = $state<string | null>(null), active = $state<Workflow | null>(null); let snapshot = $state<WorkflowSnapshot | null>(null), saving = $state(false), operating = $state(false); let operationError = $state<string | null>(null); let relativePaths = $state<string[]>([]);
// svelte-ignore non_reactive_update
let sidebar: HTMLElement;
let multiSidebar = $state<HTMLElement>();
let multiEditor = $state<{requestClose: () => Promise<void>}>();
type WorkflowSnapshot = {file_name: string; internal_name: string; purpose: string; tags: string[]};
const makeSnapshot = (workflow: Workflow): WorkflowSnapshot => ({file_name: workflow.file_name,
    internal_name: workflow.internal_name, purpose: workflow.purpose, tags: [...workflow.tags]});
let changed = $derived(active !== null && snapshot !== null &&
    (active.file_name !== snapshot.file_name || active.internal_name !== snapshot.internal_name ||
     active.purpose !== snapshot.purpose || active.tags.join('\0') !== snapshot.tags.join('\0')));
onMount(async () => {
    await refreshWorkflows();
    const paths = await getWorkflowRelativePaths();
    if (paths.ok) relativePaths = paths.data;
});
$effect(() => { if (!multiEditorOpen && selected_id && selected_id !== active_id) void openDetails(selected_id); });
$effect(() => { if (active && sidebar) sidebar.focus(); });
$effect(() => { if (multiEditorOpen && multiSidebar) multiSidebar.focus(); });

async function refreshWorkflows(): Promise<boolean> {
    const result = await getWorkflows();
    if (!result.ok) { error = result.message ?? locale.t('ui.workflow_contents.cannot_load_workflows'); return false; }
    workflows = result.data; error = null; return true;
}
async function closeDetails(): Promise<boolean> {
    if (changed) {
        const result = await unsavedChangesBox({
            message: locale.t('ui.workflow_contents.save_workflow_changes_before_continuing')
        });

        if (result === 'cancel' || (result === 'save' && !await save())) {
            selected_id = active_id;
            return false;
        }
    }
    selected_id = null; active_id = null; active = null; snapshot = null; operationError = null; return true;
}
async function openDetails(id: string) {
    if (!await closeDetails()) return;
    const result = await getWorkflow(id);
    if (!result.ok) { error = result.message ?? locale.t('ui.workflow_contents.cannot_load_workflow'); return; }
    active = result.data; active_id = id; selected_id = id; snapshot = makeSnapshot(result.data);
}
async function save(): Promise<boolean> {
    if (!active) return false; saving = true;
    const result = await updateWorkflow(active); saving = false;
    if (!result.ok) { operationError = result.message ?? locale.t('ui.workflow_contents.cannot_save_workflow'); return false; }
    active = result.data; snapshot = makeSnapshot(result.data);
    await refreshWorkflows();
    return true;
}
async function runOperation(destination: WorkflowDestination | null) {
    if (!active) return; operating = true; operationError = null;
    const id = active.id;
    const result = destination === null ? await syncWorkflow(id) : await moveWorkflow(id, destination);
    operating = false;
    if (!result.ok || result.data.allowed === false) {
        operationError = result.ok ? String(result.data.errors ?? locale.t('ui.workflow_contents.workflow_operation_failed')) : result.message ?? locale.t('ui.workflow_contents.workflow_operation_failed'); return;
    }
    await refreshWorkflows(); await refreshActive();
}
async function relocate(destination: string) {
    if (!active || operating) return;
    if (!await confirmBox({
        message: locale.t('messages.move_workflow', {
            destination: destination || locale.t('dynamic.repository_root').toLocaleLowerCase(locale.language)
        })})) return;
    operating = true;
    operationError = null;
    const preview = await relocateWorkflows([active.id], destination, true);
    const result = preview.ok && preview.data.allowed
        ? await relocateWorkflows([active.id], destination, false) : preview;
    operating = false;
    if (!result.ok || !result.data.allowed) {
        operationError = result.ok
            ? result.data.errors?.map((issue: {message: string}) => issue.message).join('; ')
            : result.message ?? locale.t('ui.workflow_contents.cannot_move_workflow');
        return;
    }
    await refreshActive();
}
async function refreshActive() {
    if (!active_id) return;
    const result = await getWorkflow(active_id);
    if (!result.ok) { operationError = result.message ?? locale.t('ui.workflow_contents.cannot_refresh_workflow'); return; }
    active = result.data; snapshot = makeSnapshot(result.data); await refreshWorkflows();
}
async function openMulti() { if (selected_ids.size >= 2 && await closeDetails()) multiEditorOpen = true; }
function closeMulti() { multiEditorOpen = false; }
async function refreshAfterMultiEdit() { await refreshWorkflows(); }
async function handleEscape(event: KeyboardEvent) { if (event.key === 'Escape') await closeDetails(); }
async function clickOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;

    if (multiEditorOpen) {
        if (!target.closest('[data-workflow-multi]')) {
            await multiEditor?.requestClose();
        }
        return;
    }

    if (target.closest('[data-workflow-table]') || target.closest('[data-workflow-details]') ||
        target.closest('[data-filter-actions]')) return;
    await closeDetails();
}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="object-view" onclick={clickOutside}>
    <FilterActions tab="workflows"
                   selectedCount={selected_ids.size}
                   onOpenMulti={openMulti} />

    <div class="object-results">
        <main data-workflow-table>
            <WorkflowTable {workflows} {error}
                           disabled={multiEditorOpen}
                           bind:selected_id bind:selected_ids />
        </main>
    </div>
    {#if active}
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <aside class="right-sidebar"
               data-workflow-details
               tabindex="-1"
               onkeydown={handleEscape}
                bind:this={sidebar}
               transition:fly={sidebar_in_out}>
            <WorkflowDetails bind:workflow={active}
                             {changed}
                             {saving}
                             {operating}
                             {operationError}
                             onSave={save}
                             onClose={closeDetails}
                             onSync={() => runOperation(null)}
                             onMove={runOperation}
                             onRelocate={relocate}
                             {relativePaths}
                             onCollectionsChanged={refreshActive} />
        </aside>
    {/if}
    {#if multiEditorOpen}
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <aside class="right-sidebar"
               data-workflow-multi
               tabindex="-1"
               aria-label={locale.t('ui.multi_workflow_editor.edit_selected_workflows')}
               bind:this={multiSidebar}
               onkeydown={(event) => { if (event.key === 'Escape') void multiEditor?.requestClose(); }}
               transition:fly={sidebar_in_out}>
            <MultiWorkflowEditor
                bind:this={multiEditor}
                workflowIds={[...selected_ids]}
                onClose={closeMulti}
                onChanged={refreshAfterMultiEdit} />
        </aside>
    {/if}
</div>
