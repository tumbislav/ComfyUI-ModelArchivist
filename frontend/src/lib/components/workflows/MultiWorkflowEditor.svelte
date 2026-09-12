<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: MultiWorkflowEditor.svelte
 ! purpose: Sidebar editor for multiple selected workflows
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

import { onMount } from 'svelte';
import TagEditor from '$components/controls/TagEditor.svelte';
import MultiWorkflowCollectionEditor from '$components/workflows/MultiWorkflowCollectionEditor.svelte';
import RelativePathEditor from '$components/controls/RelativePathEditor.svelte';
import saveIcon from '$icons/actions/save16.png';
import moveUpIcon from '$icons/actions/move-up16.png';
import moveDownIcon from '$icons/actions/move-down16.png';
import syncIcon from '$icons/actions/move-up-down16.png';
import closeIcon from '$icons/actions/close8.png';
import { type Workflow } from '$lib/objects';
import { getWorkflow, moveWorkflows, syncWorkflows, updateWorkflowTags,
    getWorkflowRelativePaths, relocateWorkflows, type WorkflowDestination } from '$lib/workflows';
import { confirmBox } from '$lib/confirm.svelte';
import { unsavedChangesBox } from '$lib/unsaved-changes.svelte';
let { workflowIds, onClose, onChanged }: { workflowIds: string[]; onClose: () => void;
    onChanged: () => Promise<void> } = $props();
let workflows = $state<Workflow[]>([]), addTags = $state<string[]>([]), removeTags = $state<string[]>([]); let busy = $state(false), error = $state<string | null>(null); let relativePaths = $state<string[]>([]), destinationPath = $state('');
let removableTags = $derived([...new Set(workflows.flatMap(workflow => workflow.tags))].sort());
let hasObjectErrors = $derived(workflows.some(workflow => workflow.read_only));
async function load() {
    const results = await Promise.all(workflowIds.map(getWorkflow));
    const failed = results.find(result => !result.ok);
    if (failed && !failed.ok) { error = failed.message ?? locale.t('ui.multi_workflow_editor.cannot_load_workflows'); return; }
    workflows = results.flatMap(result => result.ok ? [result.data] : []); error = null;
    const paths = await getWorkflowRelativePaths();
    if (paths.ok) relativePaths = paths.data;
}
onMount(load);
async function refresh() { await load(); await onChanged(); }
async function saveTags() {
    busy = true; const result = await updateWorkflowTags(workflowIds, addTags, removeTags); busy = false;
    if (!result.ok) { error = result.message ?? locale.t('ui.multi_workflow_editor.cannot_update_tags'); return; }
    addTags = []; removeTags = []; await refresh();
}

export async function requestClose(): Promise<void> {
    if (busy) return;

    if (addTags.length > 0 || removeTags.length > 0) {
        const result = await unsavedChangesBox({
            message: locale.t('messages.save_tag_changes_before_continuing')
        });
        if (result === 'cancel') return;
        if (result === 'save') {
            await saveTags();
            if (addTags.length > 0 || removeTags.length > 0) return;
        }
    }
    onClose();
}
async function run(destination: WorkflowDestination | null) {
    busy = true; error = null;
    const result = destination === null ? await syncWorkflows(workflowIds) : await moveWorkflows(workflowIds, destination);
    busy = false;
    if (!result.ok || result.data.allowed === false) {
        error = result.ok ? String(result.data.errors ?? locale.t('ui.multi_workflow_editor.workflow_operation_failed')) : result.message ?? locale.t('ui.multi_workflow_editor.workflow_operation_failed'); return;
    }
    await refresh();
}
async function relocate() {
    busy = true; error = null;
    const preview = await relocateWorkflows(workflowIds, destinationPath, true);
    busy = false;
    if (!preview.ok || !preview.data.allowed) {
        error = preview.ok ? preview.data.errors?.map((issue: {message: string}) => issue.message).join('; ')
            : preview.message ?? locale.t('ui.multi_workflow_editor.cannot_move_workflows'); return;
    }
    if (!await confirmBox({
        message: locale.t('messages.move_selected_workflows', {
            destination: destinationPath || locale.t('dynamic.repository_root').toLocaleLowerCase(locale.language)
        })})) return;
    if (new Set(workflows.map(item => item.relative_path)).size > 1 && !await confirmBox({
        message: locale.t('ui.multi_workflow_editor.the_workflows_are_currently_in_different_subdirectories_are_you_sure_you_want_to_move_them_to_the_same_subdirectory')
    })) return;
    busy = true;
    const result = await relocateWorkflows(workflowIds, destinationPath, false);
    busy = false;
    if (!result.ok || !result.data.allowed) {
        error = result.ok ? result.data.errors?.map((issue: {message: string}) => issue.message).join('; ')
            : result.message ?? locale.t('ui.multi_workflow_editor.cannot_move_workflows'); return;
    }
    await refresh();
}
</script>

<div class="space-below spaced-horizontally">
    <p class="annotation">{workflowIds.length} workflows selected</p>
    <button class="round"
            aria-label={locale.t('ui.multi_workflow_editor.close_workflow_editor')}
            disabled={busy}
            onclick={() => void requestClose()}>
        <img class="action-icon" alt="" src={closeIcon} />
    </button>
</div>

<div class="multi-model-list space-below">
    {#each workflows as workflow (workflow.id)}
        <p>{workflow.internal_name}</p>
    {/each}
</div>

{#if error}
    <p class="error-message">{error}</p>
{/if}

{#if hasObjectErrors}
    <p class="error-details">
        {locale.t('ui.multi_workflow_editor.some_selected_workflows_have_errors_editing_is_disabled')}
    </p>
{:else}
    <div class="space-below">
        <TagEditor
            title={locale.t('ui.multi_workflow_editor.add_tags')}
            tags={addTags}
            disabled={busy}
            editable={true}
            onChanged={tags => addTags = tags} />
    </div>
    <div class="space-below">
        <TagEditor
            title={locale.t('ui.multi_workflow_editor.remove_tags')}
            tags={removeTags}
            disabled={busy}
            editable={false}
            availableTags={removableTags}
            onChanged={tags => removeTags = tags} />
    </div>
    <div class="space-below spaced-horizontally">
        <div></div>
        <button class="button-with-text"
                disabled={busy || (!addTags.length && !removeTags.length)}
                onclick={saveTags}>
            <img class="action-icon" alt={locale.t('ui.multi_workflow_editor.save')} src={saveIcon} />
            <span>{locale.t('ui.multi_workflow_editor.apply_tags')}</span>
        </button>
    </div>
    <div class="space-below multi-model-deployment-actions">
        <button class="button-with-text" disabled={busy} onclick={() => run('working')}>
            <img class="action-icon" alt={locale.t('ui.multi_workflow_editor.working')} src={moveUpIcon} />
            <span>{locale.t('ui.multi_workflow_editor.to_working_set')}</span>
        </button>
        <button class="button-with-text" disabled={busy} onclick={() => run(null)}>
            <img class="action-icon" alt={locale.t('ui.multi_workflow_editor.sync')} src={syncIcon} />
            <span>{locale.t('ui.multi_workflow_editor.sync_2')}</span>
        </button>
        <button class="button-with-text" disabled={busy} onclick={() => run('archive')}>
            <img class="action-icon" alt={locale.t('ui.multi_workflow_editor.archive')} src={moveDownIcon} />
            <span>{locale.t('ui.multi_workflow_editor.to_archive')}</span>
        </button>
    </div>
    <div class="space-below">
        <RelativePathEditor
            bind:value={destinationPath}
            options={relativePaths}
            disabled={busy || workflows.length === 0}
            onMove={relocate} />
    </div>
    {#if workflows.length}
        <MultiWorkflowCollectionEditor {workflows} onChanged={refresh} />
    {/if}
{/if}
