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
import BaseModelEditor from '$components/controls/BaseModelEditor.svelte'
import ModelCollectionEditor from '$components/models/ModelCollectionEditor.svelte'
import moveDownIcon from '$icons/actions/move-down16.png';
import moveUpIcon from '$icons/actions/move-up16.png';
import moveUpDownIcon from '$icons/actions/move-up-down16.png';
import saveIcon from '$icons/actions/save16.png';
import closeIcon from '$icons/actions/close8.png';

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

<div class="space-below spaced-horizontally">
    <div></div>
    <button type="button"
            class="round"
            aria-label="Close model details"
            onclick={() => onClose()}>
        <img class="action-icon" alt="" src={closeIcon} />
    </button>
</div>

<div class="space-below spaced-horizontally">
    <div>
        <p class="labeled"><span>Type:</span>{model.type}</p>
    </div>
    
    <div>
        <p class="labeled"><span>Last accessed:</span>{shortDate(model.touched)}</p>
    </div>
</div>

{#if operationError}
    <p class="error-message">{operationError}</p>
{/if}
{#each model.errors as error}
    <p class="error-details">{error}</p>
{/each}
{#if model.deployment === 'mismatch'}
    <p class="warning-details">Model is mismatched; synchronize it before continuing.</p>
{/if}

<div class="space-below dialog-section">
    <div class="space-below">
        <label class="dialog-label">
            File name
            <input class="text-input full-width"
                   onkeydown={handleEnter}
                   disabled={model.read_only || model.deployment === 'mismatch'}
                   bind:value={model.file_name} />
        </label>
        <p class="annotation-right">{model.id}</p>

        <label class="dialog-label">
            Internal name
            <input class="text-input full-width"
                   onkeydown={handleEnter}
                   disabled={model.read_only || model.deployment === 'mismatch'}
                   bind:value={model.internal_name} />
        </label>
     </div>

    <div class="space-below">
        <label class="dialog-label" for="model-base-model">Base model</label>
        <div class="base-model-row">
            <span class="base-model-abbreviation">{model.base_model_abbreviation}</span>
            <BaseModelEditor value={model.base_model} inputId="model-base-model"
                disabled={model.read_only || model.deployment === 'mismatch'}
                onChanged={(value) => model.base_model = value} />
        </div>
    </div>

    <div class="space-below">
        <TagEditor {tags}
            onChanged={(updated: string[]) => { tags = [...updated]; model.tags = [...updated]; }}
            disabled={model.read_only || model.deployment === 'mismatch'}
            title={'Tags'}
            editable={true} />
    </div>

    <div class="spaced-horizontally">
        <div></div>
        <button class="button-with-text"
                disabled={!changed || saving || model.read_only || model.deployment === 'mismatch'}
                onclick={() => onSave()} >
            <img class="action-icon" alt="save" src={saveIcon} />
            <span  class="button-label">Save</span>
        </button>
    </div>
</div>

<div class="space-below dialog-section">
    <FileSet set={working_set} path={model.working_path} name="working set" />

    <FileSet set={archive_set} path={model.archive_path} name="archive" />

    <div class="spaced-horizontally">
        <button class="button-with-text"
                disabled={operating || model.read_only ||
                          !['archive', 'synced'].includes(model.deployment)}
                onclick={() => onMove('working')}>
            <img class="action-icon" alt="move up" src={moveUpIcon} />
            <span class="button-label">To working set</span>
        </button>
        <button class="button-with-text"
                disabled={operating || model.read_only || model.deployment === 'synced'}
                onclick={() => onSync()}>
            <img class="action-icon" alt="move up down" src={moveUpDownIcon} />
            <span class="button-label">Sync</span>
        </button>
        <button class="button-with-text"
                disabled={operating || model.read_only ||
                          !['working', 'synced'].includes(model.deployment)}
                onclick={() => onMove('archive')}>
            <img class="action-icon" alt="move down" src={moveDownIcon} />
            <span class="button-label">To archive</span>
        </button>
    </div>
</div>

<div class="space-below dialog-section">
    <ModelCollectionEditor {model} onChanged={onCollectionsChanged} />
</div>

<style>
</style>
