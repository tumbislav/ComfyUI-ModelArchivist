<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: WorkflowDetails.svelte
 ! purpose: Sidebar editor for one workflow
 ! -------------------------------------------------->

<script lang="ts">
import FileSet from '$components/controls/FileSet.svelte';
import TagEditor from '$components/controls/TagEditor.svelte';
import WorkflowCollectionEditor from '$components/workflows/WorkflowCollectionEditor.svelte';
import RelativePathEditor from '$components/controls/RelativePathEditor.svelte';
import moveDownIcon from '$icons/actions/move-down16.png';
import moveUpIcon from '$icons/actions/move-up16.png';
import syncIcon from '$icons/actions/move-up-down16.png';
import saveIcon from '$icons/actions/save16.png';
import closeIcon from '$icons/actions/close8.png';
import { shortDate } from '$lib/common';
import { type ComponentSet, type Workflow } from '$lib/objects';
let { workflow=$bindable(), changed, saving, operating, operationError, onSave, onClose,
    onSync, onMove, onRelocate, relativePaths, onCollectionsChanged }: {
    workflow: Workflow; changed: boolean; saving: boolean; operating: boolean;
    operationError: string | null; onSave: () => Promise<void>; onClose: () => Promise<boolean>;
    onSync: () => Promise<void>; onMove: (destination: 'working'|'archive') => Promise<void>;
    onRelocate: (destination: string) => Promise<void>; relativePaths: string[];
    onCollectionsChanged: () => Promise<void>;
} = $props();
let tags = $derived([...workflow.tags]);
let workingSet = $derived<ComponentSet | undefined>(workflow.working_set);
let archiveSet = $derived<ComponentSet | undefined>(workflow.archive_set);
let destinationPath = $state(workflow.relative_path);
let destinationWorkflowId = $state(workflow.id);

$effect(() => {
    if (workflow.id !== destinationWorkflowId) {
        destinationWorkflowId = workflow.id;
        destinationPath = workflow.relative_path;
    }
});
</script>

<div class="space-below spaced-horizontally">
    <div></div>
    <button class="round" aria-label="Close workflow details" onclick={() => onClose()}>
        <img class="action-icon" alt="" src={closeIcon} />
    </button>
</div>
<div class="space-below">
    <p class="labeled"><span>Last accessed:</span>{shortDate(workflow.touched)}</p></div>
{#if operationError}
    <p class="error-message">{operationError}</p>
{/if}
{#each workflow.errors as error}
    <p class="error-details">{error}</p>
{/each}
<div class="space-below">
    <h2>File name</h2>
    <input class="text-input full-width" disabled={workflow.read_only} bind:value={workflow.file_name} />
    <p class="annotation-right">{workflow.id}</p>
    <h2>Name</h2>
    <input class="text-input full-width" disabled={workflow.read_only} bind:value={workflow.internal_name} />
    <h2>Purpose</h2>
    <textarea class="text-input full-width" disabled={workflow.read_only} bind:value={workflow.purpose}></textarea>
</div>
<div class="space-below">
    <TagEditor title="Tags"
               tags={tags}
               editable={true}
               disabled={workflow.read_only}
               onChanged={updated => { tags = [...updated]; workflow.tags = [...updated]; }} />
</div>
<div class="space-below spaced-horizontally">
    <div></div>
    <button class="button-with-text" disabled={!changed || saving || workflow.read_only} onclick={onSave}>
        <img class="action-icon" alt="save" src={saveIcon} />
        <span class="button-label">Save</span>
    </button>
</div>
<FileSet set={workingSet} path={workflow.working_path} name="working set" />
<div class="space-below">
    <RelativePathEditor bind:value={destinationPath} options={relativePaths}
        disabled={changed || operating || workflow.read_only}
        moveDisabled={destinationPath === workflow.relative_path}
        onMove={() => onRelocate(destinationPath)} />
</div>
<div class="space-below spaced-horizontally">
    <button class="button-with-text"
            disabled={operating || workflow.read_only || !['archive','synced'].includes(workflow.deployment)}
            onclick={() => onMove('working')}>
        <img class="action-icon" alt="to working" src={moveUpIcon} />
        <span class="button-label">To working set</span>
    </button>
    <button class="button-with-text"
            disabled={operating || workflow.read_only || workflow.deployment === 'synced'}
            onclick={onSync}>
        <img class="action-icon" alt="sync" src={syncIcon} />
        <span class="button-label">Sync</span>
    </button>
    <button class="button-with-text"
            disabled={operating || workflow.read_only || !['working','synced'].includes(workflow.deployment)}
            onclick={() => onMove('archive')}>
        <img class="action-icon" alt="to archive" src={moveDownIcon} />
        <span class="button-label">To archive</span>
    </button>
</div>
<FileSet set={archiveSet} path={workflow.archive_path} name="archive" />
<WorkflowCollectionEditor {workflow} onChanged={onCollectionsChanged} />
