<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: ModelSettings.svelte
 ! purpose: Model type and directory mapping settings tab
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

    import type { SvelteMap } from 'svelte/reactivity';

    import addIcon from '$icons/actions/add16.png';
    import refreshIcon from '$icons/actions/refresh16.png';
    import removeIcon from '$icons/actions/remove16.png';
    import resetIcon from '$icons/actions/reset16.png';
    import saveIcon from '$icons/actions/save16.png';

    import HelpButton from '$components/controls/HelpButton.svelte';
    import PathInput from '$components/controls/PathInput.svelte';
    import type { ModelTypeSetting, RepositorySettings } from '$lib/settings';

    let {
        settings = $bindable(),
        modelMappingRoots,
        mappingWorkingRoot = $bindable(),
        mappingArchiveRoot = $bindable(),
        mappingExtensions = $bindable(),
        dirty,
        saving,
        expandedTypes,
        isDirty,
        onAddType,
        onAddMappings,
        onUndo,
        onSave,
        onSaveType,
        onRemoveType,
        onError
    }: {
        settings: RepositorySettings | null;
        modelMappingRoots: string[];
        mappingWorkingRoot: string;
        mappingArchiveRoot: string;
        mappingExtensions: string;
        dirty: boolean;
        saving: boolean;
        expandedTypes: SvelteMap<object, boolean>;
        isDirty: (type: ModelTypeSetting) => boolean;
        onAddType: () => void;
        onAddMappings: () => void;
        onUndo: () => void;
        onSave: () => void;
        onSaveType: (type: ModelTypeSetting, scan: boolean) => void;
        onRemoveType: (index: number) => void;
        onError: (message: string) => void;
    } = $props();
</script>

{#if settings}
    <section class="dialog-section model-mapping-assistant">
        <div class="spaced-horizontally">
            <h2 class="tight-vertical">{locale.t('ui.model_settings.map_model_directories')}</h2>
            <HelpButton text={locale.t(settings.mode === 'comfyui'
                ? 'dynamic.comfyui_model_help' : 'dynamic.standalone_model_help')} />
        </div>

        <div class="settings-form model-settings-form">
            <label class="dialog-label">
                Working root
                {#if settings.mode === 'comfyui'}
                    <select class="text-input" bind:value={mappingWorkingRoot}>
                        {#each modelMappingRoots as root}
                            <option value={root}>{root}</option>
                        {/each}
                    </select>
                {:else}
                    <PathInput bind:value={mappingWorkingRoot} onError={onError} />
                {/if}
            </label>
            <label class="dialog-label">
                {locale.t('ui.model_settings.archive_root')}
                <PathInput bind:value={mappingArchiveRoot} onError={onError} />
            </label>

            {#if settings.mode === 'standalone'}
                <label class="dialog-label">
                    {locale.t('ui.model_settings.model_extensions')}
                    <input class="text-input" bind:value={mappingExtensions} />
                </label>
            {/if}
        </div>

        <div class="spaced-horizontally">
            <div></div>
            <button class="button-with-text"
                    disabled={!mappingWorkingRoot || !mappingArchiveRoot}
                    onclick={onAddMappings}>
                <img class="action-icon" alt={locale.t('ui.model_settings.add')} src={addIcon} />
                <span class="button-label">{locale.t('ui.model_settings.add_mappings')}</span>
            </button>
        </div>
    </section>

    <div class="spaced-horizontally model-settings-actions">
        {#if settings.mode === 'standalone'}
            <button class="button-with-text" onclick={onAddType}>
                <img class="action-icon" alt={locale.t('ui.model_settings.add')} src={addIcon} />
                <span class="button-label">{locale.t('ui.model_settings.add_type')}</span>
            </button>
        {:else}
            <div class="button-placeholder"></div>
        {/if}
        <button class="button-with-text" disabled={!dirty || saving} onclick={onUndo}>
            <img class="action-icon" alt={locale.t('ui.model_settings.undo')} src={resetIcon} />
            <span class="button-label">{locale.t('ui.model_settings.undo_2')}</span>
        </button>
        <button class="button-with-text" disabled={!dirty || saving} onclick={onSave}>
            <img class="action-icon" alt={locale.t('ui.model_settings.save')} src={saveIcon} />
            <span class="button-label">{locale.t(saving ? 'dynamic.saving' : 'dynamic.save')}</span>
        </button>
    </div>

    <div class="model-type-list">
        {#each settings.model_types as type, typeIndex (type)}
            <details class:unsaved={type._new === true}
                     bind:open={() => expandedTypes.get(type) ?? type._new === true,
                                open => expandedTypes.set(type, open)}>
                <summary>{type.display_name || type.name || locale.t('dynamic.new_model_type')}</summary>

                <div class="settings-form model-settings-form">
                    <label class="dialog-label">
                        {locale.t('ui.model_settings.type_key')}
                        <input class="text-input" bind:value={type.name}
                               disabled={settings.mode === 'comfyui'} />
                    </label>
                    <label class="dialog-label">
                        {locale.t('ui.model_settings.display_name')}
                        <input class="text-input" bind:value={type.display_name} />
                    </label>
                    <label class="dialog-label">
                        {locale.t('ui.model_settings.extensions')}
                        <input class="text-input" value={type.extensions.join(', ')}
                               disabled={settings.mode === 'comfyui'}
                               oninput={event => type.extensions = event.currentTarget.value
                                   .split(',').map(value => value.trim()).filter(Boolean)} />
                    </label>

                    {#each type.locations as location}
                        <label class="dialog-label">
                            {locale.t('ui.model_settings.working_folder')}
                            <PathInput bind:value={location.working_dir}
                                       disabled={settings.mode === 'comfyui'}
                                       onError={onError} />
                        </label>
                        <label class="dialog-label">
                            {locale.t('ui.model_settings.archive_folder')}
                            <PathInput bind:value={location.archive_dir} onError={onError} />
                        </label>
                    {/each}
                </div>

                <div class="spaced-horizontally model-type-actions settings-actions">
                    {#if settings.mode === 'standalone'}
                        <button class="button-with-text danger" onclick={() => onRemoveType(typeIndex)}>
                            <img class="action-icon" alt="" src={removeIcon} />
                            <span class="button-label">{locale.t('ui.model_settings.remove_type')}</span>
                        </button>
                    {/if}
                    <button class="button-with-text" disabled={!isDirty(type)}
                            onclick={() => onSaveType(type, false)}>
                        <img class="action-icon" alt="" src={saveIcon} />
                        <span class="button-label">{locale.t('ui.model_settings.save_2')}</span>
                    </button>
                    <button class="button-with-text" onclick={() => onSaveType(type, true)}>
                        <img class="action-icon" alt="" src={refreshIcon} />
                        <span class="button-label">{locale.t(isDirty(type) ? 'dynamic.save_and_scan' : 'dynamic.refresh')}</span>
                    </button>
                </div>
            </details>
        {/each}
    </div>
{/if}
