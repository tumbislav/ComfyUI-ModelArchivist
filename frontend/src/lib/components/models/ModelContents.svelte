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
    searchModels,
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
let active_snapshot = $state<ModelSnapshot | null>(null);
let saving_active = $state(false);

type ModelSnapshot = {
    file_name: string;
    internal_name: string;
    tags: string[];
};

function modelSnapshot(model: Model): ModelSnapshot {
    return {
        file_name: model.file_name,
        internal_name: model.internal_name,
        tags: [...model.tags]
    };
}

function sameTags(first: string[], second: string[]): boolean {
    return first.length === second.length &&
        first.every((tag, index) => tag === second[index]);
}

let active_changed = $derived(
    active_model !== null &&
    active_snapshot !== null &&
    (active_model.file_name !== active_snapshot.file_name ||
     active_model.internal_name !== active_snapshot.internal_name ||
     !sameTags(active_model.tags, active_snapshot.tags))
);

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
    if (envelope.ok) {
        active_snapshot = modelSnapshot(envelope.data);
        active_model = envelope.data;
        active_id = model_id;
        selected_id = model_id;
    }
}

/* Close the sidebar if there are no changes, or if user agrees -------------*/

async function closeDetails(): Promise<boolean> {
    if (active_changed) { 
        const confirm = await confirmBox({
            title: 'Unsaved changes',
            message: 'You have unsaved changes. Discard them?'
        });
        if (!confirm) {
            selected_id = active_id;
            return false; /* not closed */
        }
    }
    
    selected_id = null;
    active_id = null;
    active_model = null;
    active_snapshot = null;
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
        target.closest('[data-model-details]') ||
        target.closest('[data-model-filter]')) {
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
    active_snapshot = modelSnapshot(envelope.data);
    models = models.map((m) => m.id === envelope.data.id ? toModelSummary(envelope.data) : m);
    saving_active = false;
}


/* Model filter
 * ---------------------------------------------------------------------------*/
 
async function filterModels(filter: ModelSearchCriteria): Promise<boolean> {
    if (!(await closeDetails())) return false;
    const hasFilters = filter.types.length > 0 || filter.file_formats.length > 0 ||
        filter.required_tags.length > 0 || filter.forbidden_tags.length > 0 ||
        filter.name_prefix.length > 0;
    const envelope = hasFilters ? await searchModels(filter) : await getModels();
    if (envelope.ok) {
        models = envelope.data;
        models_error = null;
        return true;
    }
    models_error = envelope.message ?? 'Cannot filter models';
    return false;
}


</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions  -->
<div class="object-view" onclick={clickOutside}>
    <ModelFilter onFilter={filterModels}/>

    <div class="object-results">
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
                      changed={active_changed}
                      saving={saving_active}
                      onSave={saveModel}
                      onClose={closeDetails} />
    </aside>
{/if}
    </div>
</div>


<style>

</style>
