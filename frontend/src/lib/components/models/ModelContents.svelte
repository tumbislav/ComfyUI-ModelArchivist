<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ModelContents.svelte
 ! purpose: Container for the Model contents
 ! -------------------------------------------------->

<script lang="ts">

/* Nested components
 * ---------------------------------------------------------------------------*/
import ModelActions from '$components/models/ModelActions.svelte'
import ModelTable from '$components/models/ModelTable.svelte'
import ModelDetails from '$components/models/ModelDetails.svelte'
import MultiModelEditor from '$components/models/MultiModelEditor.svelte'

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
    syncModel,
    moveModel,
    type ModelDestination,
    type ModelSearchCriteria
} from "$lib/models";

import { type ApiResult } from "$lib/api";
import { statusMonitor } from '$lib/status.svelte';

let {
    multiEditorOpen=$bindable(false)
}: {
    multiEditorOpen: boolean;
} = $props();

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
let selected_ids = $state<Set<string>>(new Set());
let active_id = $state<string | null>(null);
let active_model = $state<Model | null>(null);
let active_snapshot = $state<ModelSnapshot | null>(null);
let saving_active = $state(false);
let operating_active = $state(false);
let operation_error = $state<string | null>(null);

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
        operation_error = null;
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
    operation_error = null;
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
        target.closest('[data-model-actions]')) {
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

/* Synchronize or move a model ----------------------------------------------*/

async function runModelOperation(destination: ModelDestination | null) {
    if (active_model == null || operating_active) return;
    const model_id = active_model.id;
    operating_active = true;
    operation_error = null;

    try {
        const started = destination === null
            ? await syncModel(model_id)
            : await moveModel(model_id, destination);
        if (!started.ok) {
            operation_error = started.message ?? 'Cannot start model operation';
            return;
        }

        const completed = await statusMonitor.waitForOperation(started.data);
        if (!completed.ok) {
            operation_error = completed.message ?? 'Cannot retrieve model operation';
            return;
        }
        if (completed.data.state === 'failed') {
            operation_error = completed.data.error?.message ?? 'Model operation failed';
            return;
        }

        await refreshModels();
        const refreshed = await getModel(model_id);
        if (refreshed.ok && active_id === model_id) {
            active_model = refreshed.data;
            active_snapshot = modelSnapshot(refreshed.data);
        } else if (!refreshed.ok && active_id === model_id) {
            operation_error = refreshed.message ?? 'Cannot refresh model details';
        }
    } catch (error) {
        operation_error = error instanceof Error
            ? error.message
            : 'Model operation failed';
    } finally {
        operating_active = false;
    }
}

async function refreshActiveModel() {
    if (active_id === null) return;
    const refreshed = await getModel(active_id);
    if (!refreshed.ok) {
        operation_error = refreshed.message ?? 'Cannot refresh model details';
        return;
    }
    active_model = refreshed.data;
    active_snapshot = modelSnapshot(refreshed.data);
    await refreshModels();
}


/* Model filter
 * ---------------------------------------------------------------------------*/

const empty_filter: ModelSearchCriteria = {
    types: [],
    file_formats: [],
    required_tags: [],
    forbidden_tags: [],
    name_prefix: ''
};
let current_filter = $state<ModelSearchCriteria>({...empty_filter});

function hasFilters(filter: ModelSearchCriteria): boolean {
    return filter.types.length > 0 || filter.file_formats.length > 0 ||
        filter.required_tags.length > 0 || filter.forbidden_tags.length > 0 ||
        filter.name_prefix.length > 0;
}

async function refreshModels(): Promise<boolean> {
    const envelope = hasFilters(current_filter)
        ? await searchModels(current_filter)
        : await getModels();
    if (envelope.ok) {
        models = envelope.data;
        models_error = null;
        return true;
    }
    models_error = envelope.message ?? 'Cannot load models';
    return false;
}

async function filterModels(filter: ModelSearchCriteria): Promise<boolean> {
    if (!(await closeDetails())) return false;
    const previous_filter = current_filter;
    current_filter = {
        types: [...filter.types],
        file_formats: [...filter.file_formats],
        required_tags: [...filter.required_tags],
        forbidden_tags: [...filter.forbidden_tags],
        name_prefix: filter.name_prefix
    };
    if (await refreshModels()) return true;
    current_filter = previous_filter;
    return false;
}

async function openMultiEditor() {
    if (selected_ids.size < 2 || !(await closeDetails())) return;
    multiEditorOpen = true;
}

function closeMultiEditor() {
    multiEditorOpen = false;
}

async function refreshAfterMultiEdit() {
    await refreshModels();
}


</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions  -->
<div class="object-view" onclick={clickOutside}>
    <ModelActions selectedCount={selected_ids.size}
                  onFilter={filterModels}
                  onOpenMulti={openMultiEditor}/>

    <div class="object-results">
        <main data-model-table>
            <ModelTable {models} error={models_error}
                        bind:selected_id bind:selected_ids />
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
                      operating={operating_active}
                      operationError={operation_error}
                      onSave={saveModel}
                      onClose={closeDetails}
                      onSync={() => runModelOperation(null)}
                      onMove={runModelOperation}
                      onCollectionsChanged={refreshActiveModel} />
    </aside>
{/if}
{#if multiEditorOpen}
    <MultiModelEditor modelIds={[...selected_ids]}
                      onClose={closeMultiEditor}
                      onChanged={refreshAfterMultiEdit} />
{/if}
</div>


<style>

</style>
