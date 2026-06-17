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

import {
    type Model,
    type ComponentSet
} from "$lib/objects";
import { shortDate } from "$lib/common";


let {
    model=$bindable(),
    changed=$bindable(),
    saving,
    onSave,
    onClose,
}: {
    model: Model;
    changed: boolean;
    saving: boolean,
    onSave: () => Promise<void>;
    onClose: () => Promise<boolean>;
} = $props();

let tags = $derived<string[]>([...model.tags]);
let archive_set = $derived<ComponentSet | undefined>(model.component_sets.find(c_set => c_set.where === 'a'));
let working_set = $derived<ComponentSet | undefined>(model.component_sets.find(c_set => c_set.where === 'w'));


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
    <button class="simple-button"
            disabled={!changed || saving || model.deployment === 'mismatch'}
            onclick={() => onSave()} >
        <span class="button-text">Save</span>
    </button>
</div>

{#if working_set}
    <FileSet set={working_set} name="working set" />
{/if}

<div class="dialog-section spaced-horizontally">
    <button class="simple-button"
            disabled={model.deployment !== 'archive'} >
        <i class="fa-solid fa-arrow-up"></i>
        <span class="button-text">To working set</span>
    </button>
    <button class="simple-button"
            disabled={model.deployment === 'synced'} >
        <i class="fa-solid fa-up-down"></i>
        <span class="button-text">Sync</span>
    </button>
    <button class="simple-button"
            disabled={model.deployment !== 'working'} >
        <i class="fa-solid fa-arrow-down"></i>
        <span class="button-text">To archive</span>
    </button>
</div>

{#if archive_set}
    <FileSet set={archive_set} name="archive" />
{/if}


<div class="dialog-section">
    <p class="dialog-label">Collections</p>
    <div>
        <table class="main-table">
            <tbody>
                {#each model.collections as g, i (g.id)}
                    <tr>
                        <td>{g.name}</td>
                    </tr>
                {/each}
            </tbody>
        </table>
    </div>
</div>

<style>
</style>