<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: UserTypeSettings.svelte
 ! purpose: User-defined object type settings tab
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
    import IconPicker from '$components/controls/IconPicker.svelte';
    import PathInput from '$components/controls/PathInput.svelte';
    import type { UserDefinedType } from '$lib/objects';

    let {
        userTypes = $bindable(),
        dirty,
        saving,
        expandedTypes,
        isDirty,
        onAddType,
        onRemoveType,
        onUndo,
        onSave,
        onSaveType,
        onError
    }: {
        userTypes: UserDefinedType[];
        dirty: boolean;
        saving: boolean;
        expandedTypes: SvelteMap<object, boolean>;
        isDirty: (type: UserDefinedType) => boolean;
        onAddType: () => void;
        onRemoveType: (type: UserDefinedType, index: number) => void;
        onUndo: () => void;
        onSave: () => void;
        onSaveType: (type: UserDefinedType, scan: boolean) => void;
        onError: (message: string) => void;
    } = $props();

    const iconNames = ['any', 'dataset', 'file', 'folder-images', 'folder-sound', 'folder-speech',
        'folder-video', 'folder-wildcards', 'folder', 'image', 'sound', 'speech', 'stencil',
        'training-set', 'video', 'wildcard'];
</script>

<div class="spaced-horizontally settings-tab-actions">
    <button class="button-with-text" onclick={onAddType}>
        <img class="action-icon" alt={locale.t('ui.user_type_settings.add')} src={addIcon} />
        <span class="button-label">{locale.t('ui.user_type_settings.add_type')}</span>
    </button>
    <button class="button-with-text" disabled={!dirty || saving} onclick={onUndo}>
        <img class="action-icon" alt={locale.t('ui.user_type_settings.undo')} src={resetIcon} />
        <span class="button-label">{locale.t('ui.user_type_settings.undo_2')}</span>
    </button>
    <button class="button-with-text" disabled={!dirty || saving} onclick={onSave}>
        <img class="action-icon" alt={locale.t('ui.user_type_settings.save')} src={saveIcon} />
        <span class="button-label">{locale.t(saving ? 'dynamic.saving' : 'dynamic.save')}</span>
    </button>
</div>

<div class="settings-item-list">
    {#each userTypes as type, typeIndex (type)}
        <details class:unsaved={!type.id}
                 bind:open={() => expandedTypes.get(type) ?? !type.id,
                            open => expandedTypes.set(type, open)}>
            <summary>{type.name || locale.t('dynamic.new_user_type')}</summary>
            <div class="user-type-help">
                <HelpButton text="" />
            </div>

            <div class="settings-form aligned-settings-form">
                <label class="dialog-label">
                    {locale.t('ui.user_type_settings.name')}
                    <input class="text-input" bind:value={type.name} />
                </label>
                <label class="dialog-label">
                    {locale.t('ui.user_type_settings.short_name')}
                    <input class="text-input" maxlength="8" bind:value={type.short_name} />
                </label>
                <label class="dialog-label">
                    {locale.t('ui.user_type_settings.icon')}
                    <IconPicker bind:value={type.icon} options={iconNames} />
                </label>
                <label class="dialog-label">
                    {locale.t('ui.user_type_settings.purpose')}
                    <textarea class="text-input" bind:value={type.purpose}></textarea>
                </label>
                <label class="dialog-label">
                    {locale.t('ui.user_type_settings.content')}
                    <select class="text-input" bind:value={type.object_class} disabled={type.object_count > 0}>
                        <option value="file">{locale.t('ui.user_type_settings.single_file')}</option>
                        <option value="folder">{locale.t('ui.user_type_settings.directory_tree')}</option>
                    </select>
                </label>

                {#if type.object_class === 'file'}
                    <label class="dialog-label">
                        {locale.t('ui.user_type_settings.extensions')}
                        <input class="text-input" value={type.extensions.join(', ')}
                               oninput={event => type.extensions = event.currentTarget.value
                                   .split(',').map(value => value.trim()).filter(Boolean)} />
                    </label>
                {/if}

                <label class="dialog-label">
                    {locale.t('ui.user_type_settings.working_folder')}
                    <PathInput bind:value={type.working_dir} onError={onError} />
                </label>
                <label class="dialog-label">
                    {locale.t('ui.user_type_settings.archive_folder')}
                    <PathInput bind:value={type.archive_dir} onError={onError} />
                </label>
                <label class="dialog-label">
                    {locale.t('ui.user_type_settings.size_limit_bytes')}
                    <input class="text-input" type="number" min="1"
                           disabled={type.small} bind:value={type.size_limit} />
                </label>
                <label class="dialog-label checkbox-label">
                    {locale.t('ui.user_type_settings.small_object_type')}
                    <input type="checkbox" checked={type.small}
                           onchange={event => {
                               type.small = event.currentTarget.checked;

                               if (type.small) type.size_limit = 1024 * 1024;
                           }} />
                </label>
            </div>

            <div class="spaced-horizontally settings-item-actions">
                <button class="button-with-text danger" onclick={() => onRemoveType(type, typeIndex)}>
                    <img class="action-icon" alt={locale.t('ui.user_type_settings.remove')} src={removeIcon} />
                    <span class="button-label">{locale.t('ui.user_type_settings.delete_type')}</span>
                </button>
                <button class="button-with-text" disabled={!isDirty(type)}
                        onclick={() => onSaveType(type, false)}>
                    <img class="action-icon" alt="" src={saveIcon} />
                    <span class="button-label">{locale.t('ui.user_type_settings.save_2')}</span>
                </button>
                <button class="button-with-text" onclick={() => onSaveType(type, true)}>
                    <img class="action-icon" alt="" src={refreshIcon} />
                    <span class="button-label">{locale.t(isDirty(type) ? 'dynamic.save_and_scan' : 'dynamic.refresh')}</span>
                </button>
            </div>
        </details>
    {/each}
</div>
