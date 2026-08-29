<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: MultiModelEditor.svelte
 ! purpose: Modal editor for multiple selected models
 ! -------------------------------------------------->

<script lang="ts">
import { onMount } from 'svelte';
import TagEditor from '$components/controls/TagEditor.svelte';
import MultiModelCollectionEditor from '$components/models/MultiModelCollectionEditor.svelte';
import saveIcon from '$icons/save16.png';
import moveUpIcon from '$icons/move-up16.png';
import moveDownIcon from '$icons/move-down16.png';
import syncIcon from '$icons/move-up-down16.png';
import { type Model } from '$lib/objects';
import {
    getModel,
    moveModels,
    syncModels,
    updateModelTags,
    type ModelDestination
} from '$lib/models';
import { statusMonitor } from '$lib/status.svelte';

let {
    modelIds,
    onClose,
    onChanged
}: {
    modelIds: string[];
    onClose: () => void;
    onChanged: () => Promise<void>;
} = $props();

let models = $state<Model[]>([]);
let addTags = $state<string[]>([]);
let removeTags = $state<string[]>([]);
let busy = $state(false);
let error = $state<string | null>(null);
let removableTags = $derived([...new Set(models.flatMap(model => model.tags))].sort());

async function loadModels() {
    const responses = await Promise.all(modelIds.map(getModel));
    const failed = responses.find(response => !response.ok);
    if (failed && !failed.ok) {
        error = failed.message ?? 'Cannot load selected models';
        return;
    }
    models = responses.flatMap(response => response.ok ? [response.data] : []);
    error = null;
}

onMount(loadModels);

async function refresh() {
    await loadModels();
    await onChanged();
}

async function saveTags() {
    if (addTags.length === 0 && removeTags.length === 0) return;
    busy = true;
    const response = await updateModelTags(modelIds, addTags, removeTags);
    busy = false;
    if (!response.ok) {
        error = response.message ?? 'Cannot update model tags';
        return;
    }
    addTags = [];
    removeTags = [];
    await refresh();
}

async function runOperation(destination: ModelDestination | null) {
    busy = true;
    error = null;
    const started = destination === null
        ? await syncModels(modelIds)
        : await moveModels(modelIds, destination);
    if (!started.ok) {
        error = started.message ?? 'Cannot start model operation';
        busy = false;
        return;
    }
    const completed = await statusMonitor.waitForOperation(started.data);
    busy = false;
    if (!completed.ok || completed.data.state === 'failed') {
        error = completed.ok
            ? completed.data.error?.message ?? 'Model operation failed'
            : completed.message ?? 'Cannot retrieve model operation';
        return;
    }
    await refresh();
}
</script>

<div class="content-modal-backdrop">
    <div class="multi-model-editor" role="dialog" data-model-details
             aria-modal="true" aria-label="Edit selected models">
        <div class="dialog-section spaced-horizontally">
            <p class="annotation">{modelIds.length} models selected</p>
            <button type="button" class="round" disabled={busy} onclick={onClose}>×</button>
        </div>

        <div class="multi-model-list dialog-section">
            {#each models as model (model.id)}
                <p class="text-compact">{model.internal_name}</p>
            {/each}
        </div>

        {#if error}<p class="error-message">{error}</p>{/if}

        <div class="dialog-section">
            <TagEditor title="Add tags" tags={addTags} disabled={busy} editable={true}
                       onChanged={tags => addTags = tags} />
        </div>
        <div class="dialog-section">
            <TagEditor title="Remove tags" tags={removeTags} disabled={busy} editable={false}
                       availableTags={removableTags}
                       onChanged={tags => removeTags = tags} />
        </div>
        <div class="dialog-section spaced-horizontally">
            <div></div>
            <button class="button-with-text"
                    disabled={busy || (addTags.length === 0 && removeTags.length === 0)}
                    onclick={saveTags}>
                <img class="action-icon" alt="save" src={saveIcon} /><span>Apply tags</span>
            </button>
        </div>

        <div class="dialog-section multi-model-deployment-actions">
            <button class="button-with-text" disabled={busy} onclick={() => runOperation('working')}>
                <img class="action-icon" alt="to working set" src={moveUpIcon} /><span>To working set</span>
            </button>
            <button class="button-with-text" disabled={busy} onclick={() => runOperation(null)}>
                <img class="action-icon" alt="sync" src={syncIcon} /><span>Sync</span>
            </button>
            <button class="button-with-text" disabled={busy} onclick={() => runOperation('archive')}>
                <img class="action-icon" alt="to archive" src={moveDownIcon} /><span>To archive</span>
            </button>
        </div>

        {#if models.length > 0}
            <MultiModelCollectionEditor {models} onChanged={refresh} />
        {/if}
    </div>
</div>

<style>
</style>
