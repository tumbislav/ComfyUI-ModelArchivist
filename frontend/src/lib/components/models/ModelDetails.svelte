<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ModelDetails.svelte
 ! purpose: Sidebar dialogue with model details
 ! -------------------------------------------------->

<script lang="ts">
/* Nested components
 * ---------------------------------------------------------------------------*/
import FileSet from '$components/controls/FileSet.svelte'
import TagEditor from '$components/controls/TagEditor.svelte'
import ModelCollectionEditor from '$components/models/ModelCollectionEditor.svelte'
import moveDownIcon from '$icons/move-down16.png';
import moveUpIcon from '$icons/move-up16.png';
import moveUpDownIcon from '$icons/move-up-down16.png';
import saveIcon from '$icons/save16.png';

import {
    type Model,
    type ComponentSet
} from "$lib/objects";
import { shortDate } from "$lib/common";


let {
    model=$bindable(),
    changed,
    saving,
    operating,
    operationError,
    onSave,
    onClose,
    onSync,
    onMove,
    onCollectionsChanged,
}: {
    model: Model;
    changed: boolean;
    saving: boolean,
    operating: boolean;
    operationError: string | null;
    onSave: () => Promise<void>;
    onClose: () => Promise<boolean>;
    onSync: () => Promise<void>;
    onMove: (destination: 'working' | 'archive') => Promise<void>;
    onCollectionsChanged: () => Promise<void>;
} = $props();

let tags = $derived<string[]>([...model.tags]);
let archive_set = $derived<ComponentSet | undefined>(model.archive_set);
let working_set = $derived<ComponentSet | undefined>(model.working_set);


async function handleEnter(event: KeyboardEvent) {
    if (event.key === 'Enter') {
        event.preventDefault();
        await onSave();
    }
}

</script>

<div class="dialog-section spaced-horizontally">
    <div></div>
    <button type="button"
            class="round"
            onclick={() => onClose()}>×</button>
</div>

<div class="dialog-section spaced-horizontally">
    <div>
        <p class="labeled"><span>Type:</span>{model.type}</p>
    </div>
    
    <div>
        <p class="labeled"><span>Last accessed:</span>{shortDate(model.touched)}</p>
    </div>
</div>

{#if model.deployment === 'mismatch'}
    <p class="warning-message">Model is mismatched, synchronize it.</p>
{/if}

{#if operationError}
    <p class="error-message">{operationError}</p>
{/if}

<div class="dialog-section">
    <p class="dialog-label">File name</p>
    <input class="text-input full-width"
           onkeydown={handleEnter}
           disabled={model.deployment === 'mismatch'}
           bind:value={model.file_name} />
    
    <p class="annotation-right">{model.id}</p>
    
    <p class="dialog-label">Internal name</p>
    <input class="text-input full-width"
           onkeydown={handleEnter}
           disabled={model.deployment === 'mismatch'}
           bind:value={model.internal_name} />
</div>

<div class="dialog-section">
    <TagEditor {tags}
        onChanged={(updated: string[]) => { tags = [...updated]; model.tags = [...updated]; }}
        disabled={model.deployment === 'mismatch'}
        title={'Tags'}
        editable={true} />
</div>

<div class="dialog-section spaced-horizontally">
    <div></div>
    <button class="button-with-text"
            disabled={!changed || saving || model.deployment === 'mismatch'}
            onclick={() => onSave()} >
        <img class="action-icon" alt="save" src={saveIcon} />
        <span>Save</span>
    </button>
</div>

<FileSet set={working_set} path={model.working_path} name="working set" />

<div class="dialog-section spaced-horizontally">
    <button class="button-with-text"
            disabled={operating || !['archive', 'synced'].includes(model.deployment)}
            onclick={() => onMove('working')}>
        <img class="action-icon" alt="move up" src={moveUpIcon} />
        <span>To working set</span>
    </button>
    <button class="button-with-text"
            disabled={operating || model.deployment === 'synced'}
            onclick={() => onSync()}>
        <img class="action-icon" alt="move up down" src={moveUpDownIcon} />
        <span>Sync</span>
    </button>
    <button class="button-with-text"
            disabled={operating || !['working', 'synced'].includes(model.deployment)}
            onclick={() => onMove('archive')}>
        <img class="action-icon" alt="move down" src={moveDownIcon} />
        <span>To archive</span>
    </button>
</div>

<FileSet set={archive_set} path={model.archive_path} name="archive" />


<ModelCollectionEditor {model} onChanged={onCollectionsChanged} />

<style>
</style>
