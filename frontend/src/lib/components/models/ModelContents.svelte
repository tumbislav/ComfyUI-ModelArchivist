<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ModelContents.svelte
 ! purpose: Container for the Model contents
 ! -------------------------------------------------->

<script lang="ts">

/* Nested components
 * ---------------------------------------------------------------------------*/
import ModelFilter from '$components/models/ModelFilter.svelte'
import ModelTable from '$components/models/ModelTable.svelte'
import ModelDetails from '$components/models/ModelDetails.svelte'

/* General imports
 * ---------------------------------------------------------------------------*/
import { onMount } from "svelte";
import { fly } from "svelte/transition";
import { sidebar_in_out } from "$lib/common";
import { confirmBox } from '$lib/confirm.svelte';

import {
    type Model,
    type ModelSummary,
    toModelSummary
} from "$lib/objects";

import {
    getModels,
    getModel,
    updateModel,
    type ModelSearchCriteria
} from "$lib/models";

import { type ApiResult } from "$lib/api";

/* Initialize the contents
 * ---------------------------------------------------------------------------*/

let models = $state<ModelSummary[]>([]);
let models_error = $state<string | null>(null);

onMount(async () => {
    const envelope: ApiResult<ModelSummary[]> = await getModels();
    if (envelope.ok) {
        models = envelope.data;
        models_error = null;
    }
    else {
        models = [];
        models_error = envelope.message ?? null;
    }
});

/* Working with model details panel
 * ---------------------------------------------------------------------------*/

let selected_id = $state<string | null>(null);
let active_id = $state<string | null>(null);
let active_model = $state<Model | null>(null);
let active_changed = $state(false);
let saving_active = $state(false);

/* Focus sidebar when open ---------------------------------------------------*/

// svelte-ignore non_reactive_update
let sidebar: HTMLElement;
$effect(() => {
    if (active_model && sidebar) {
        sidebar.focus(); 
}});

/* Open the sidebar when the user clicks a model -----------------------------*/

$effect(() => {
    if (selected_id === null || selected_id === active_id)
        return;
    openDetails(selected_id);
});

async function openDetails(model_id: string) {
    if (!model_id || !(await closeDetails()))
        return;
    const envelope = await getModel(model_id);
    if (envelope.ok) { active_model = envelope.data; }
    active_changed = false;
    active_id = model_id;
}

/* Track changes to the active model -----------------------------------------*/

$effect(() => {
    if (active_model && !saving_active) {
        if (active_model.file_name || 
            active_model.internal_name || 
            active_model.tags)
            active_changed = true;
    }
});

/* Close the sidebar if there are no changes, or if user agrees -------------*/

async function closeDetails(): Promise<boolean> {
    if (active_changed) { 
        const confirm = await confirmBox({
            title: 'Unsaved changes',
            message: 'You have unsaved changes. Discard them?'
        });
        if (!confirm) return false; /* not closed */
    }
    
    selected_id = null;
    active_model = null;
    active_changed = false;
    saving_active = false;
    return true;
}

/* Close if the user hits Esc ------------------------------------------------*/
async function handleEscape(event: KeyboardEvent) {
    if (event.key === 'Escape') {
        event.preventDefault();
        await closeDetails();
    }
}

/* Close on click anywhere but on the table or the sidebar -------------------*/
async function clickOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;
    
    if (target.closest('[data-model-table]') ||
        target.closest('[data-model-details]')) {
        return;
    }
    await closeDetails();
}

/* Save a changed model ------------------------------------------------------*/
async function saveModel() {
    if (active_model == null) return;
    saving_active = true;
    
    const envelope = await updateModel(active_model);
    if (!envelope.ok) {
        throw new Error('Cannot update model');
    }
    active_model = envelope.data;
    models = models.map((m) => m.id === envelope.data.id ? toModelSummary(envelope.data) : m);
    
    active_changed = false;
    saving_active = false;
}


/* Model filter
 * ---------------------------------------------------------------------------*/
 
 async function filterModels(filter: ModelSearchCriteria): Promise<void> {
 }

async function resetFilter(): Promise<void> {}


</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions  -->
<div class="three-panel" onclick={clickOutside}>
    <ModelFilter onFilter={filterModels} onReset={resetFilter}/>
    
    <div class="content-with-actions">
        <main class="table-container" data-model-table>
            <ModelTable {models} error={models_error} bind:selected_id />
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
        <ModelDetails bind:model={active_model}
                      bind:changed={active_changed}
                      saving={saving_active}
                      onSave={saveModel}
                      onClose={closeDetails} />
    </aside>
{/if}
</div>


<style>

</style>