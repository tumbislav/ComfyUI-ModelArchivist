<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ModelContents.svelte
 ! purpose: Container for the Model contents
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';


/* Nested components
 * ---------------------------------------------------------------------------*/
import FilterActions from '$components/controls/FilterActions.svelte'
import ModelTable from '$components/models/ModelTable.svelte'
import ModelDetails from '$components/models/ModelDetails.svelte'
import MultiModelEditor from '$components/models/MultiModelEditor.svelte'

/* General imports
 * ---------------------------------------------------------------------------*/
import { onMount, untrack } from "svelte";
import { fly } from "svelte/transition";
import { sidebar_in_out } from "$lib/common";
import { confirmBox } from '$lib/confirm.svelte';
import { unsavedChangesBox } from '$lib/unsaved-changes.svelte';

import {
    type Model,
    type ModelSummary
} from "$lib/objects";

import {
    getModels,
    getModel,
    updateModel,
    syncModel,
    moveModel,
    getModelRelativePaths,
    relocateModels,
    type ModelDestination,
} from "$lib/models";

import { type ApiResult } from "$lib/api";
import { statusMonitor } from '$lib/status.svelte';

let {
    multiEditorOpen=$bindable(false),
    remapBlocked=$bindable(false),
    tagRevision=0
}: {
    multiEditorOpen: boolean;
    remapBlocked?: boolean;
    tagRevision?: number;
} = $props();

$effect(() => {
    remapBlocked = active_changed || saving_active || operating_active || multiEditorOpen;
});

$effect(() => {
    if (tagRevision > 0) {
        untrack(() => {
            void refreshModels();
            if (active_id) void refreshActiveModel();
        });
    }
});

/* Initialize the contents
 * ---------------------------------------------------------------------------*/

let models = $state<ModelSummary[]>([]); let models_error = $state<string | null>(null);

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

let selected_id = $state<string | null>(null); let selected_ids = $state<Set<string>>(new Set()); let active_id = $state<string | null>(null); let active_model = $state<Model | null>(null); let active_snapshot = $state<ModelSnapshot | null>(null); let saving_active = $state(false); let operating_active = $state(false); let operation_error = $state<string | null>(null); let relativePaths = $state<string[]>([]);

type ModelSnapshot = {
    file_name: string;
    internal_name: string;
    base_model: string;
    tags: string[];
};

function modelSnapshot(model: Model): ModelSnapshot {
    return {
        file_name: model.file_name,
        internal_name: model.internal_name,
        base_model: model.base_model,
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
     active_model.base_model !== active_snapshot.base_model ||
     !sameTags(active_model.tags, active_snapshot.tags))
);

/* Focus sidebar when open ---------------------------------------------------*/

// svelte-ignore non_reactive_update
let sidebar: HTMLElement;
let multiSidebar = $state<HTMLElement>();
let multiEditor = $state<{requestClose: () => Promise<void>}>();
$effect(() => {
    if (active_model && sidebar) {
        sidebar.focus(); 
}});

$effect(() => {
    if (multiEditorOpen && multiSidebar) {
        multiSidebar.focus();
    }
});

/* Open the sidebar when the user clicks a model -----------------------------*/

$effect(() => {
    if (multiEditorOpen || selected_id === null || selected_id === active_id)
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
        const paths = await getModelRelativePaths(envelope.data.raw_type);
        if (paths.ok) relativePaths = paths.data;
        active_id = model_id;
        selected_id = model_id;
    }
}

/* Close the sidebar if there are no changes, or if user agrees -------------*/

async function closeDetails(): Promise<boolean> {
    if (active_changed) { 
        const result = await unsavedChangesBox({
            message: locale.t('ui.model_contents.save_model_changes_before_continuing')
        });

        if (result === 'cancel' || (result === 'save' && !await saveModel())) {
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

    if (multiEditorOpen) {
        if (!target.closest('[data-model-multi]')) {
            await multiEditor?.requestClose();
        }
        return;
    }
    
    if (target.closest('[data-model-table]') ||
        target.closest('[data-model-details]') ||
        target.closest('[data-filter-actions]')) {
        return;
    }
    await closeDetails();
}

/* Save a changed model ------------------------------------------------------*/
async function saveModel(): Promise<boolean> {
    if (active_model == null) return false;
    saving_active = true;

    try {
        const envelope = await updateModel(active_model);
        if (!envelope.ok) {
            operation_error = envelope.message ?? locale.t('ui.model_contents.cannot_update_model');
            return false;
        }
        active_model = envelope.data;
        active_snapshot = modelSnapshot(envelope.data);
        await refreshModels();
        return true;
    } finally {
        saving_active = false;
    }
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
            operation_error = started.message ?? locale.t('ui.model_contents.cannot_start_model_operation');
            return;
        }

        const completed = await statusMonitor.waitForOperation(started.data);
        if (!completed.ok) {
            operation_error = completed.message ?? locale.t('ui.model_contents.cannot_retrieve_model_operation');
            return;
        }
        if (completed.data.state === 'failed') {
            operation_error = completed.data.error?.message ?? locale.t('ui.model_contents.model_operation_failed');
            return;
        }

        await refreshModels();
        const refreshed = await getModel(model_id);
        if (refreshed.ok && active_id === model_id) {
            active_model = refreshed.data;
            active_snapshot = modelSnapshot(refreshed.data);
        } else if (!refreshed.ok && active_id === model_id) {
            operation_error = refreshed.message ?? locale.t('ui.model_contents.cannot_refresh_model_details');
        }
    } catch (error) {
        operation_error = error instanceof Error
            ? error.message
            : locale.t('ui.model_contents.model_operation_failed');
    } finally {
        operating_active = false;
    }
}

async function relocateModel(destination: string) {
    if (!active_model || operating_active) return;
    if (!await confirmBox({
        message: locale.t('messages.move_model', {
            destination: destination || locale.t('dynamic.repository_root').toLocaleLowerCase(locale.language)
        })
    })) return;

    operating_active = true;
    operation_error = null;
    const preview = await relocateModels([active_model.id], destination, true);
    const result = preview.ok && preview.data.allowed
        ? await relocateModels([active_model.id], destination, false)
        : preview;
    operating_active = false;

    if (!result.ok || !result.data.allowed) {
        operation_error = result.ok
            ? result.data.errors?.map((issue: {message: string}) => issue.message).join('; ')
            : result.message ?? locale.t('ui.model_contents.cannot_move_model');
        return;
    }
    await refreshActiveModel();
}

async function refreshActiveModel() {
    if (active_id === null) return;
    const refreshed = await getModel(active_id);
    if (!refreshed.ok) {
        operation_error = refreshed.message ?? locale.t('ui.model_contents.cannot_refresh_model_details');
        return;
    }
    active_model = refreshed.data;
    active_snapshot = modelSnapshot(refreshed.data);
    await refreshModels();
}


/* Model filter
 * ---------------------------------------------------------------------------*/

async function refreshModels(): Promise<boolean> {
    const envelope = await getModels();
    if (envelope.ok) {
        models = envelope.data;
        models_error = null;
        return true;
    }
    models_error = envelope.message ?? locale.t('ui.model_contents.cannot_load_models');
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
    <FilterActions tab="models"
                   selectedCount={selected_ids.size}
                   onOpenMulti={openMultiEditor}/>

    <div class="object-results">
        <main data-model-table>
            <ModelTable {models}
                        error={models_error}
                        disabled={multiEditorOpen}
                        bind:selected_id
                        bind:selected_ids />
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
                      onRelocate={relocateModel}
                      {relativePaths}
                      onCollectionsChanged={refreshActiveModel} />
    </aside>
{/if}
{#if multiEditorOpen}
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <aside class="right-sidebar"
           data-model-multi
           tabindex="-1"
           aria-label={locale.t('ui.multi_model_editor.edit_selected_models')}
           bind:this={multiSidebar}
           onkeydown={(event) => { if (event.key === 'Escape') void multiEditor?.requestClose(); }}
           transition:fly={sidebar_in_out}>
        <MultiModelEditor
            bind:this={multiEditor}
            modelIds={[...selected_ids]}
            onClose={closeMultiEditor}
            onChanged={refreshAfterMultiEdit} />
    </aside>
{/if}
</div>


<style>

</style>
