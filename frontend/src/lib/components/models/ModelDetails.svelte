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

import { type Model,
         type ComponentSet
} from "$lib/objects";
import { shortDate, joinPath } from "$lib/common";
import { syncModel } from "$lib/models";

let {
    model,
    changed,
    saving,
    updateChanged,
    onSave,
}: {
    model: Model;
    changed: boolean;
    saving: boolean,
    updateChanged: (changed: boolean) => void;
    onSave: (model: Model) => Promise<void>;
} = $props();

let tags = $derived<string[]>([...model.tags]);

function tagsChanged(updated: string[]): void {
    markChanged();
    tags = [...updated];
    model.tags = [...updated];
}

function markChanged() {
    if (!changed) { updateChanged(true); }
}

async function handleEnter(event: KeyboardEvent) {
    if (event.key === 'Enter') {
        event.preventDefault();
        await onSave(model);
    }
}

async function saveTags(tags: string[]): Promise<void> {}
</script>

<div class="dialog-section spaced-horizontally">
    <div></div>
    <button type="button" class="tag-remove" >×</button>
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
    <p class="warning-message">Model mismatched, synchronize before editing.</p>
{/if}

<div class="dialog-section">
    <p class="dialog-label">File name</p>
    <input class="text-input full-width"
           oninput={markChanged}
           onkeydown={handleEnter}
           disabled={model.deployment === 'mismatch'}
           bind:value={model.file_name} />

    <p class="annotation-right">{model.id}</p>

    <p class="dialog-label">Internal name</p>
    <input class="text-input full-width"
           oninput={markChanged}
           onkeydown={handleEnter}
           disabled={model.deployment === 'mismatch'}
           bind:value={model.internal_name} />
</div>

<div class="dialog-section">
    <TagEditor {tags} onChanged={tagsChanged} disabled={model.deployment === 'mismatch'} />
</div>

<div class="dialog-section spaced-horizontally">
    <div></div>
    <button class="simple-button action-button"
            disabled={!changed || saving || model.deployment === 'mismatch'}
            onclick={() => onSave(model)} >
        <span class="actions-label button-text">Save</span>
    </button>
</div>

<FileSet set={model.component_sets.find(c_set => c_set.where === 'w')}
         relative_path={model.relative_path}
         name="working set" />

<div class="dialog-section spaced-horizontally">
    <button class="simple-button action-button"
            disabled={model.deployment !== 'archive'} >
        <i class="fa-solid fa-arrow-up"></i>
        <span class="actions-label button-text">To working set</span>
    </button>
    <button class="simple-button action-button"
            disabled={model.deployment === 'synced'} >
        <i class="fa-solid fa-up-down"></i>
        <span class="actions-label button-text">Sync</span>
    </button>
    <button class="simple-button action-button"
            disabled={model.deployment !== 'working'} >
        <i class="fa-solid fa-arrow-down"></i>
        <span class="actions-label button-text">To archive</span>
    </button>
</div>

<FileSet set={model.component_sets.find(c_set => c_set.where === 'a')}
         relative_path={model.relative_path}
         name="archive" />


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
    .tag-remove {
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--tag-pill-radius);
    border: 1px solid var(--border-color);
    background: var(--bg-intense);
    color: var(--text-color);
    height: var(--tag-pill-height);
    width: var(--tag-pill-height);
    margin-left: var(--gap-small);
    font-size: var(--medium-font-size);
}

button.tag-remove:hover {
    border: 1px solid var(--border-color);
    background: var(--bg-highlight);
    transform: none;
    box-shadow: none;
}
</style>