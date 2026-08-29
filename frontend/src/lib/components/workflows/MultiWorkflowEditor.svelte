<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: MultiWorkflowEditor.svelte
 ! purpose: Modal editor for multiple selected workflows
 ! -------------------------------------------------->

<script lang="ts">
import { onMount } from 'svelte';
import TagEditor from '$components/controls/TagEditor.svelte';
import MultiWorkflowCollectionEditor from '$components/workflows/MultiWorkflowCollectionEditor.svelte';
import saveIcon from '$icons/save16.png';
import moveUpIcon from '$icons/move-up16.png';
import moveDownIcon from '$icons/move-down16.png';
import syncIcon from '$icons/move-up-down16.png';
import { type Workflow } from '$lib/objects';
import { getWorkflow, moveWorkflows, syncWorkflows, updateWorkflowTags,
    type WorkflowDestination } from '$lib/workflows';
let { workflowIds, onClose, onChanged }: { workflowIds: string[]; onClose: () => void;
    onChanged: () => Promise<void> } = $props();
let workflows = $state<Workflow[]>([]), addTags = $state<string[]>([]), removeTags = $state<string[]>([]);
let busy = $state(false), error = $state<string | null>(null);
let removableTags = $derived([...new Set(workflows.flatMap(workflow => workflow.tags))].sort());
async function load() {
    const results = await Promise.all(workflowIds.map(getWorkflow));
    const failed = results.find(result => !result.ok);
    if (failed && !failed.ok) { error = failed.message ?? 'Cannot load workflows'; return; }
    workflows = results.flatMap(result => result.ok ? [result.data] : []); error = null;
}
onMount(load);
async function refresh() { await load(); await onChanged(); }
async function saveTags() {
    busy = true; const result = await updateWorkflowTags(workflowIds, addTags, removeTags); busy = false;
    if (!result.ok) { error = result.message ?? 'Cannot update tags'; return; }
    addTags = []; removeTags = []; await refresh();
}
async function run(destination: WorkflowDestination | null) {
    busy = true; error = null;
    const result = destination === null ? await syncWorkflows(workflowIds) : await moveWorkflows(workflowIds, destination);
    busy = false;
    if (!result.ok || result.data.allowed === false) {
        error = result.ok ? String(result.data.errors ?? 'Workflow operation failed') : result.message ?? 'Workflow operation failed'; return;
    }
    await refresh();
}
</script>

<div class="content-modal-backdrop"><div class="multi-model-editor" role="dialog" data-workflow-details aria-modal="true" aria-label="Edit selected workflows">
    <div class="dialog-section spaced-horizontally"><p class="annotation">{workflowIds.length} workflows selected</p><button class="round" disabled={busy} onclick={onClose}>×</button></div>
    <div class="multi-model-list dialog-section">{#each workflows as workflow (workflow.id)}<p class="text-compact">{workflow.internal_name}</p>{/each}</div>
    {#if error}<p class="error-message">{error}</p>{/if}
    <div class="dialog-section"><TagEditor title="Add tags" tags={addTags} disabled={busy} editable={true} onChanged={tags => addTags = tags} /></div>
    <div class="dialog-section"><TagEditor title="Remove tags" tags={removeTags} disabled={busy} editable={false} availableTags={removableTags} onChanged={tags => removeTags = tags} /></div>
    <div class="dialog-section spaced-horizontally"><div></div><button class="button-with-text" disabled={busy || (!addTags.length && !removeTags.length)} onclick={saveTags}><img class="action-icon" alt="save" src={saveIcon} /><span>Apply tags</span></button></div>
    <div class="dialog-section multi-model-deployment-actions">
        <button class="button-with-text" disabled={busy} onclick={() => run('working')}><img class="action-icon" alt="working" src={moveUpIcon} /><span>To working set</span></button>
        <button class="button-with-text" disabled={busy} onclick={() => run(null)}><img class="action-icon" alt="sync" src={syncIcon} /><span>Sync</span></button>
        <button class="button-with-text" disabled={busy} onclick={() => run('archive')}><img class="action-icon" alt="archive" src={moveDownIcon} /><span>To archive</span></button>
    </div>
    {#if workflows.length}<MultiWorkflowCollectionEditor {workflows} onChanged={refresh} />{/if}
</div></div>
