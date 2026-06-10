<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ModelContents.svelte
 ! purpose: Container for the Model contents
 ! -------------------------------------------------->

<script lang=ts>

/* Nested components
 * ---------------------------------------------------------------------------*/
import ModelFilter from '$components/models/ModelFilter.svelte'
import ModelActions from '$components/models/ModelActions.svelte'
import ModelTable from '$components/models/ModelTable.svelte'
import ModelDetails from '$components/models/ModelDetails.svelte'

/* General imports
 * ---------------------------------------------------------------------------*/
import { onMount } from "svelte";
import { fly } from "svelte/transition";
import { sidebar_in_out } from "$lib/common";
import { confirmBox } from '$lib/confirm.svelte';

import {
    PrimaryObjectType,
    type Model,
    type ModelSummary,
    type Tag,
    toModelSummary
} from "$lib/objects";

import {
    getModels,
    getModel,
    updateModel
} from "$lib/models";

import { getTags } from "$lib/tags";

import { type ApiResult } from "$lib/api";

/* Initialize the contents
 * ---------------------------------------------------------------------------*/

let models = $state<ModelSummary[]>([]);
let models_error = $state<string | null>(null);
let tags = $state<ApiResult<string[]>>({ ok: false });

onMount(async () => {
    const model_envelope = await getModels();
    if (model_envelope.ok) {
        models = model_envelope.data;
        models_error = null;
    }
    else {
        models = [];
        models.error = model_envelope.message;
    }
    tags = await getTags([PrimaryObjectType.MODEL]);
});

/* Details panel management
 * ---------------------------------------------------------------------------*/

let selected_model_id = $state<string | null>(null);
let active_model = $state<Model | null>(null);
let changed = $state(false);
let saving = $state(false);

// Focus sidebar when open
// svelte-ignore non_reactive_update
let sidebar: HTMLElement;
$effect(() => { if (active_model && sidebar) { sidebar.focus(); } });

// Open the sidebar when the user clicks a model
async function selectModel(id: string): Promise<void> {
    if (id === selected_model_id) return;
    if (!canCloseDetails) return;

    selected_model_id = id;
    const envelope = await getModel(id);
    if (envelope.ok) { active_model = envelope.data; }
    changed = false;
}

// Close the sidebar
async function closeDetails() {
    const can_close = await canCloseDetails();

    if (changed) return;
    selected_model_id = null;
    active_model = null;
    saving = false;
}

// Close if the user hits Esc
async function handleEscape(event: KeyboardEvent) {
    if (event.key === 'Escape') {
        event.preventDefault();
        await closeDetails();
    }
}

// Check for unsaved changes
async function canCloseDetails(): Promise<boolean> {
    if (!changed) { return true; }

    const confirm = await confirmBox({title: 'Unsaved changes',
                                      message: 'You have unsaved changes. Discard them?'});
    console.log(`confirm ${confirm}`);
    changed = !confirm;
    return changed;
}

// Close on click anywhere but on the table or the sidebar
async function clickOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;

    if (target.closest('[data-model-table]') ||
        target.closest('[data-model-details]')) {
        return;
    }
    await closeDetails();
}

// Save a changed model
async function saveModel(model: Model) {
    saving = true;

    const envelope = await updateModel(active_model);
    if (!envelope.ok) {
        throw new Error('Cannot update model');
    }
    models = models.map((m) => m.id === envelope.data.id ? toModelSummary(envelope.data) : m);
    changed = false;
    await closeDetails();
}

</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions  -->
<div class="three-panel" onclick={clickOutside}>
    <ModelFilter />
    <div class="content-with-actions">
        <ModelActions />
        <main class="table-container" data-model-table>
            <ModelTable {models} error={models_error} {selected_model_id} onSelect={selectModel} />
        </main>
    </div>
{#if active_model}
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <aside class="right-sidebar"
           data-model-details
           tabindex="-1"
           onkeydown={handleEscape}
           bind:this={sidebar}
           transition:fly={sidebar_in_out}>
        <ModelDetails model={active_model}
                      {changed}
                      {saving}
                      updateChanged={(v) => changed=v}
                      onSave={saveModel} />
    </aside>
{/if}
</div>


<style>

</style>