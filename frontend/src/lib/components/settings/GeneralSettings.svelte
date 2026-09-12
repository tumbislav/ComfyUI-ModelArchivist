<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: GeneralSettings.svelte
 ! purpose: General application settings tab
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import refreshIcon from '$icons/actions/refresh16.png';
    import saveIcon from '$icons/actions/save16.png';

    import MultiSelect from '$components/controls/MultiSelect.svelte';
    import { rememberFilters, setRememberFilters } from '$lib/column-filters';
    import { locale } from '$lib/locale.svelte';
    import { saveRememberLastTab, saveScanAtStartup } from '$lib/preferences';
    import type { RepositorySettings } from '$lib/settings';

    let {
        settings = $bindable(),
        startupScan = $bindable(),
        rememberTab = $bindable(),
        extensionsDirty,
        editingLocked,
        onError,
        onSave
    }: {
        settings: RepositorySettings | null;
        startupScan: boolean;
        rememberTab: boolean;
        extensionsDirty: boolean;
        editingLocked: boolean;
        onError: (message: string) => void;
        onSave: (scan: boolean) => void;
    } = $props();
</script>

<div class="settings-form aligned-settings-form space-below">
    <label class="dialog-label">
        {locale.t('settings.language')}
        <select class="text-input" value={locale.language}
                onchange={event => locale.set(event.currentTarget.value)}>
            {#each locale.available as option}
                <option value={option.code}>{option.metadata.name}</option>
            {/each}
        </select>
    </label>
</div>

<div class="settings-form aligned-settings-form space-below">
    <label>
        <input type="checkbox" bind:checked={startupScan}
               onchange={event => {
                   try {
                       saveScanAtStartup(event.currentTarget.checked);
                   } catch {
                       onError(locale.t('dynamic.pref_startup_error'));
                   }
               }} />
        {locale.t('ui.general_settings.always_run_a_full_scan_at_startup')}
    </label>

    <label>
        <input type="checkbox" bind:checked={rememberTab}
               onchange={event => {
                   try {
                       saveRememberLastTab(event.currentTarget.checked);
                   } catch {
                       onError(locale.t('dynamic.pref_tab_error'));
                   }
               }} />
        {locale.t('ui.general_settings.remember_last_open_tab')}
    </label>

    <label>
        <input type="checkbox" checked={$rememberFilters}
               onchange={event => {
                   try {
                       setRememberFilters(event.currentTarget.checked);
                   } catch {
                       onError(locale.t('dynamic.pref_filter_error'));
                   }
               }} />
        {locale.t('ui.general_settings.remember_last_used_filters')}
    </label>
</div>

{#if settings}
        <div class="dialog-section-blank">
        <MultiSelect title={locale.t('ui.general_settings.model_extensions')}
                     options={settings.available_model_extensions.map(value => ({ value, label: value }))}
                     selected={settings.model_extensions}
                     disabled={editingLocked}
                     onChanged={values => {
                         if (settings) settings.model_extensions = values;
                     }} />
        </div>
        {#if extensionsDirty}
            <p class="warning-details">
                {locale.t('ui.general_settings.changing_the_list_of_extensions_can_invalidate_parts_of_the_repository_please_rescan_before_continuing')}
            </p>
        {/if}

        <div class="spaced-horizontally">
            <button class="button-with-text" disabled={!extensionsDirty} onclick={() => onSave(false)}>
                <img class="action-icon" alt="" src={saveIcon} />
                <span class="button-label">{locale.t('ui.general_settings.save')}</span>
            </button>
            <button class="button-with-text" disabled={!extensionsDirty} onclick={() => onSave(true)}>
                <img class="action-icon" alt="" src={refreshIcon} />
                <span class="button-label">{locale.t('ui.general_settings.save_and_scan')}</span>
            </button>
        </div>
{/if}
