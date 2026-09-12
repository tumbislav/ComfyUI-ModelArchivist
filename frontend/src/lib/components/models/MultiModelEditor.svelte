<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: MultiModelEditor.svelte
 ! purpose: Sidebar editor for multiple selected models
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

import { onMount } from 'svelte';
import TagEditor from '$components/controls/TagEditor.svelte';
import BaseModelEditor from '$components/controls/BaseModelEditor.svelte';
import MultiModelCollectionEditor from '$components/models/MultiModelCollectionEditor.svelte';
import RelativePathEditor from '$components/controls/RelativePathEditor.svelte';
import saveIcon from '$icons/actions/save16.png';
import moveUpIcon from '$icons/actions/move-up16.png';
import moveDownIcon from '$icons/actions/move-down16.png';
import syncIcon from '$icons/actions/move-up-down16.png';
import closeIcon from '$icons/actions/close8.png';
import { type Model } from '$lib/objects';
import {
    getModel,
    getModelRelativePaths,
    relocateModels,
    moveModels,
    syncModels,
    updateModelBaseModels,
    updateModelTags,
    type ModelDestination
} from '$lib/models';
import { statusMonitor } from '$lib/status.svelte';
import { confirmBox } from '$lib/confirm.svelte';
import { unsavedChangesBox } from '$lib/unsaved-changes.svelte';

let {
    modelIds,
    onClose,
    onChanged
}: {
    modelIds: string[];
    onClose: () => void;
    onChanged: () => Promise<void>;
} = $props();

let models = $state<Model[]>([]); let addTags = $state<string[]>([]); let removeTags = $state<string[]>([]); let baseModel = $state(''); let savedBaseModel = $state(''); let baseModelInitialized = $state(false); let busy = $state(false); let error = $state<string | null>(null); let relativePaths = $state<string[]>([]);
let destinationPath = $state('');
let removableTags = $derived([...new Set(models.flatMap(model => model.tags))].sort());
let hasObjectErrors = $derived(models.some(model => model.read_only));
let baseModelDirty = $derived(baseModel !== savedBaseModel);

async function loadModels() {
    const responses = await Promise.all(modelIds.map(getModel));
    const failed = responses.find(response => !response.ok);
    if (failed && !failed.ok) {
        error = failed.message ?? locale.t('ui.multi_model_editor.cannot_load_selected_models');
        return;
    }
    models = responses.flatMap(response => response.ok ? [response.data] : []);
    if (models.length > 0 && models.every(model => model.raw_type === models[0].raw_type)) {
        const paths = await getModelRelativePaths(models[0].raw_type);
        if (paths.ok) relativePaths = paths.data;
    }
    if (!baseModelInitialized && models.length > 0) {
        const first = models[0].base_model;
        baseModel = models.every(model => model.base_model === first) ? first : '';
        savedBaseModel = baseModel;
        baseModelInitialized = true;
    }
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
        error = response.message ?? locale.t('ui.multi_model_editor.cannot_update_model_tags');
        return;
    }
    addTags = [];
    removeTags = [];
    await refresh();
}

export async function requestClose(): Promise<void> {
    if (busy) return;

    if (baseModelDirty || addTags.length > 0 || removeTags.length > 0) {
        const result = await unsavedChangesBox({
            message: locale.t('messages.save_multi_model_changes_before_continuing')
        });
        if (result === 'cancel') return;
        if (result === 'save') {
            if (baseModelDirty) {
                await saveBaseModel();
            }
            if (addTags.length > 0 || removeTags.length > 0) {
                await saveTags();
            }
            if (baseModelDirty || addTags.length > 0 || removeTags.length > 0) return;
        }
    }
    onClose();
}

async function saveBaseModel() {
    busy = true;
    const response = await updateModelBaseModels(modelIds, baseModel);
    busy = false;
    if (!response.ok) {
        error = response.message ?? locale.t('ui.multi_model_editor.cannot_update_base_model');
        return;
    }
    baseModel = response.data[0]?.base_model ?? '';
    savedBaseModel = baseModel;
    await refresh();
}

async function runOperation(destination: ModelDestination | null) {
    busy = true;
    error = null;
    const started = destination === null
        ? await syncModels(modelIds)
        : await moveModels(modelIds, destination);
    if (!started.ok) {
        error = started.message ?? locale.t('ui.multi_model_editor.cannot_start_model_operation');
        busy = false;
        return;
    }
    const completed = await statusMonitor.waitForOperation(started.data);
    busy = false;
    if (!completed.ok || completed.data.state === 'failed') {
        error = completed.ok
            ? completed.data.error?.message ?? locale.t('ui.multi_model_editor.model_operation_failed')
            : completed.message ?? locale.t('ui.multi_model_editor.cannot_retrieve_model_operation');
        return;
    }
    await refresh();
}

async function relocate() {
    if (new Set(models.map(model => model.raw_type)).size !== 1) {
        error = locale.t('ui.multi_model_editor.models_of_different_types_cannot_be_moved_together');
        return;
    }
    busy = true;
    error = null;
    const preview = await relocateModels(modelIds, destinationPath, true);
    busy = false;
    if (!preview.ok || !preview.data.allowed) {
        error = preview.ok
            ? preview.data.errors?.map((issue: {message: string}) => issue.message).join('; ')
            : preview.message ?? locale.t('ui.multi_model_editor.cannot_move_models');
        return;
    }
    if (!await confirmBox({
        message: locale.t('messages.move_selected_models', {
            destination: destinationPath || locale.t('dynamic.repository_root').toLocaleLowerCase(locale.language)
        })})) return;
    if (new Set(models.map(model => model.relative_path)).size > 1 && !await confirmBox({
        message: locale.t('ui.multi_model_editor.the_models_are_currently_in_different_subdirectories_are_you_sure_you_want_to_move_them_to_the_same_subdirectory')
    })) return;
    busy = true;
    const result = await relocateModels(modelIds, destinationPath, false);
    busy = false;
    if (!result.ok || !result.data.allowed) {
        error = result.ok ? result.data.errors?.map((issue: {message: string}) => issue.message).join('; ')
            : result.message ?? locale.t('ui.multi_model_editor.cannot_move_models');
        return;
    }
    await refresh();
}
</script>

<div class="space-below spaced-horizontally">
    <p class="annotation">{modelIds.length} models selected</p>
    <button type="button"
            class="round"
            aria-label={locale.t('ui.multi_model_editor.close_model_editor')}
            disabled={busy}
            onclick={() => void requestClose()}>
        <img class="action-icon" alt="" src={closeIcon} />
    </button>
</div>

<h2>{locale.t('ui.multi_model_editor.selected_models')}</h2>
<div class="multi-model-list space-below">
    {#each models as model (model.id)}
        <p>{model.internal_name}</p>
    {/each}
</div>

{#if error}
    <p class="error-message">{error}</p>
{/if}

{#if hasObjectErrors}
    <p class="error-details">
        {locale.t('ui.multi_model_editor.some_selected_models_have_errors_editing_is_disabled')}
    </p>
{:else}
    <div class="dialog-section space-below">
        <div class="dialog-section-blank">
            <h2>{locale.t('ui.multi_model_editor.set_base_model')}</h2>
            <BaseModelEditor
                value={baseModel}
                disabled={busy}
                placeholder={locale.t('ui.multi_model_editor.type_a_base_model_name')}
                onChanged={(value) => baseModel = value} />
            <div class="spaced-horizontally">
                <div></div>
                <button class="button-with-text"
                        disabled={busy || models.length === 0}
                        onclick={saveBaseModel}>
                    <img class="action-icon" alt={locale.t('ui.multi_model_editor.save')} src={saveIcon} />
                    <span class="button-label">{locale.t('ui.multi_model_editor.apply_base_model')}</span>
                </button>
            </div>
        </div>

        <div class="space-below">
            <TagEditor
                title={locale.t('ui.multi_model_editor.add_tags')}
                tags={addTags}
                disabled={busy}
                editable={true}
                onChanged={tags => addTags = tags} />
        </div>
        <div class="space-below">
            <TagEditor
                title={locale.t('ui.multi_model_editor.remove_tags')}
                tags={removeTags}
                disabled={busy}
                editable={false}
                availableTags={removableTags}
                onChanged={tags => removeTags = tags} />
        </div>
        <div class="spaced-horizontally">
            <div></div>
            <button class="button-with-text"
                    disabled={busy || (addTags.length === 0 && removeTags.length === 0)}
                    onclick={saveTags}>
                <img class="action-icon" alt={locale.t('ui.multi_model_editor.save')} src={saveIcon} />
                <span class="button-label">{locale.t('ui.multi_model_editor.apply_tags')}</span>
            </button>
        </div>
    </div>

    <div class="dialog-section">
        <div class="space-below">
            <RelativePathEditor
                bind:value={destinationPath}
                options={relativePaths}
                disabled={busy || models.length === 0 ||
                    new Set(models.map(model => model.raw_type)).size !== 1}
                onMove={relocate} />
        </div>

        <div class="space-below multi-model-deployment-actions">
            <button class="button-with-text" disabled={busy} onclick={() => runOperation('working')}>
                <img class="action-icon" alt={locale.t('ui.multi_model_editor.to_working_set')} src={moveUpIcon} />
                <span class="button-label">{locale.t('ui.multi_model_editor.to_working_set_2')}</span>
            </button>
            <button class="button-with-text" disabled={busy} onclick={() => runOperation(null)}>
                <img class="action-icon" alt={locale.t('ui.multi_model_editor.sync')} src={syncIcon} />
                <span class="button-label">{locale.t('ui.multi_model_editor.sync_2')}</span>
            </button>
            <button class="button-with-text" disabled={busy} onclick={() => runOperation('archive')}>
                <img class="action-icon" alt={locale.t('ui.multi_model_editor.to_archive')} src={moveDownIcon} />
                <span class="button-label">{locale.t('ui.multi_model_editor.to_archive_2')}</span>
            </button>
        </div>
    </div>

    {#if models.length > 0}
        <MultiModelCollectionEditor {models} onChanged={refresh} />
    {/if}
{/if}
