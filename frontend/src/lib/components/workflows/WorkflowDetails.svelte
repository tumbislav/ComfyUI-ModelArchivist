<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: WorkflowDetails.svelte
 ! purpose: Sidebar editor for one workflow
 ! -------------------------------------------------->

<script lang="ts">
import FileSet from '$components/controls/FileSet.svelte';
import TagEditor from '$components/controls/TagEditor.svelte';
import WorkflowCollectionEditor from '$components/workflows/WorkflowCollectionEditor.svelte';
import moveDownIcon from '$icons/actions/move-down16.png';
import moveUpIcon from '$icons/actions/move-up16.png';
import syncIcon from '$icons/actions/move-up-down16.png';
import saveIcon from '$icons/actions/save16.png';
import { shortDate } from '$lib/common';
import { type ComponentSet, type Workflow } from '$lib/objects';
let { workflow=$bindable(), changed, saving, operating, operationError, onSave, onClose,
    onSync, onMove, onCollectionsChanged }: {
    workflow: Workflow; changed: boolean; saving: boolean; operating: boolean;
    operationError: string | null; onSave: () => Promise<void>; onClose: () => Promise<boolean>;
    onSync: () => Promise<void>; onMove: (destination: 'working'|'archive') => Promise<void>;
    onCollectionsChanged: () => Promise<void>;
} = $props();
let tags = $derived([...workflow.tags]);
let workingSet = $derived<ComponentSet | undefined>(workflow.working_set);
let archiveSet = $derived<ComponentSet | undefined>(workflow.archive_set);
</script>

<div class="dialog-section spaced-horizontally"><div></div><button class="round" onclick={() => onClose()}>×</button></div>
<div class="dialog-section"><p class="labeled"><span>Last accessed:</span>{shortDate(workflow.touched)}</p></div>
{#if operationError}<p class="error-message">{operationError}</p>{/if}
<div class="dialog-section">
    <p class="dialog-label">File name</p><input class="text-input full-width" disabled={workflow.read_only} bind:value={workflow.file_name} />
    <p class="annotation-right">{workflow.id}</p>
    <p class="dialog-label">Name</p><input class="text-input full-width" disabled={workflow.read_only} bind:value={workflow.internal_name} />
    <p class="dialog-label">Purpose</p><textarea class="text-input full-width" disabled={workflow.read_only} bind:value={workflow.purpose}></textarea>
</div>
<div class="dialog-section"><TagEditor title="Tags" tags={tags} editable={true}
    disabled={workflow.read_only} onChanged={updated => { tags = [...updated]; workflow.tags = [...updated]; }} /></div>
<div class="dialog-section spaced-horizontally"><div></div><button class="button-with-text"
    disabled={!changed || saving || workflow.read_only} onclick={onSave}><img class="action-icon" alt="save" src={saveIcon} /><span>Save</span></button></div>
<FileSet set={workingSet} path={workflow.working_path} name="working set" />
<div class="dialog-section spaced-horizontally">
    <button class="button-with-text" disabled={operating || workflow.read_only || !['archive','synced'].includes(workflow.deployment)} onclick={() => onMove('working')}><img class="action-icon" alt="to working" src={moveUpIcon} /><span>To working set</span></button>
    <button class="button-with-text" disabled={operating || workflow.read_only || workflow.deployment === 'synced'} onclick={onSync}><img class="action-icon" alt="sync" src={syncIcon} /><span>Sync</span></button>
    <button class="button-with-text" disabled={operating || workflow.read_only || !['working','synced'].includes(workflow.deployment)} onclick={() => onMove('archive')}><img class="action-icon" alt="to archive" src={moveDownIcon} /><span>To archive</span></button>
</div>
<FileSet set={archiveSet} path={workflow.archive_path} name="archive" />
<WorkflowCollectionEditor {workflow} onChanged={onCollectionsChanged} />
