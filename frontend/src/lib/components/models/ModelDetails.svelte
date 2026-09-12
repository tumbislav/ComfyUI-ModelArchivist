<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ModelDetails.svelte
 ! purpose: Sidebar dialogue with model details
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

/* Nested components
 * ---------------------------------------------------------------------------*/
import FileSet from '$components/controls/FileSet.svelte'
import TagEditor from '$components/controls/TagEditor.svelte'
import BaseModelEditor from '$components/controls/BaseModelEditor.svelte'
import ModelCollectionEditor from '$components/models/ModelCollectionEditor.svelte'
import RelativePathEditor from '$components/controls/RelativePathEditor.svelte';
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
    onRelocate,
    relativePaths,
    onCollectionsChanged,
}: {
    model: Model;
    changed: boolean;
    saving: boolean,
    operating: boolean;
    operationError: string | null;
    onSave: () => Promise<boolean>;
    onClose: () => Promise<boolean>;
    onSync: () => Promise<void>;
    onMove: (destination: 'working' | 'archive') => Promise<void>;
    onRelocate: (destination: string) => Promise<void>;
    relativePaths: string[];
    onCollectionsChanged: () => Promise<void>;
} = $props();

let tags = $derived<string[]>([...model.tags]); let archive_set = $derived<ComponentSet | undefined>(model.archive_set); let working_set = $derived<ComponentSet | undefined>(model.working_set);
let destinationPath = $state(model.relative_path);
let destinationModelId = $state(model.id);

$effect(() => {
    if (model.id !== destinationModelId) {
        destinationModelId = model.id;
        destinationPath = model.relative_path;
    }
});


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
            aria-label={locale.t('ui.model_details.close_model_details')}
            onclick={() => onClose()}>
        <img class="action-icon" alt="" src={closeIcon} />
    </button>
</div>

<div class="space-below spaced-horizontally">
    <div>
        <p class="labeled"><span>{locale.t('ui.model_details.type')}</span>{model.type}</p>
    </div>
    
    <div>
        <p class="labeled"><span>{locale.t('ui.model_details.last_accessed')}</span>{shortDate(model.touched)}</p>
    </div>
</div>

{#if operationError}
    <p class="error-message">{operationError}</p>
{/if}
{#each model.errors as error}
    <p class="error-details">{error}</p>
{/each}
{#if model.deployment === 'mismatch'}
    <p class="warning-details">{locale.t('ui.model_details.model_is_mismatched_synchronize_it_before_continuing')}</p>
{/if}

<div class="space-below dialog-section">
    <div class="space-below">
        <label class="dialog-label">
            {locale.t('ui.model_details.file_name')}
            <input class="text-input full-width"
                   onkeydown={handleEnter}
                   disabled={model.read_only || model.deployment === 'mismatch'}
                   bind:value={model.file_name} />
        </label>
        <p class="annotation-right">{model.id}</p>

        <label class="dialog-label">
            {locale.t('ui.model_details.internal_name')}
            <input class="text-input full-width"
                   onkeydown={handleEnter}
                   disabled={model.read_only || model.deployment === 'mismatch'}
                   bind:value={model.internal_name} />
        </label>
     </div>

    <div class="space-below">
        <label class="dialog-label" for="model-base-model">{locale.t('ui.model_details.base_model')}</label>
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
            title={locale.t('filters.labels.tags')}
            editable={true} />
    </div>

    <div class="spaced-horizontally">
        <div></div>
        <button class="button-with-text"
                disabled={!changed || saving || model.read_only || model.deployment === 'mismatch'}
                onclick={() => onSave()} >
            <img class="action-icon" alt={locale.t('ui.model_details.save')} src={saveIcon} />
            <span  class="button-label">{locale.t('ui.model_details.save_2')}</span>
        </button>
    </div>
</div>

<div class="space-below dialog-section">
    <div class="dialog-section-blank">
    <RelativePathEditor bind:value={destinationPath} options={relativePaths}
        disabled={changed || operating || model.read_only}
        moveDisabled={destinationPath === model.relative_path}
        onMove={() => onRelocate(destinationPath)} />
    </div>
    <FileSet set={working_set} path={model.working_path} name="working set" />

    <FileSet set={archive_set} path={model.archive_path} name="archive" />

    <div class="spaced-horizontally">
        <button class="button-with-text"
                disabled={operating || model.read_only ||
                          !['archive', 'synced'].includes(model.deployment)}
                onclick={() => onMove('working')}>
            <img class="action-icon" alt={locale.t('ui.model_details.move_up')} src={moveUpIcon} />
            <span class="button-label">{locale.t('ui.model_details.to_working_set')}</span>
        </button>
        <button class="button-with-text"
                disabled={operating || model.read_only || model.deployment === 'synced'}
                onclick={() => onSync()}>
            <img class="action-icon" alt={locale.t('ui.model_details.move_up_down')} src={moveUpDownIcon} />
            <span class="button-label">{locale.t('ui.model_details.sync')}</span>
        </button>
        <button class="button-with-text"
                disabled={operating || model.read_only ||
                          !['working', 'synced'].includes(model.deployment)}
                onclick={() => onMove('archive')}>
            <img class="action-icon" alt={locale.t('ui.model_details.move_down')} src={moveDownIcon} />
            <span class="button-label">{locale.t('ui.model_details.to_archive')}</span>
        </button>
    </div>
</div>

<div class="space-below dialog-section">
    <ModelCollectionEditor {model} onChanged={onCollectionsChanged} />
</div>

<style>
</style>
