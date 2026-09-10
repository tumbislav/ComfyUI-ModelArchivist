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

<h3>General</h3>

<div class="settings-form aligned-settings-form">
    <label>
        <input type="checkbox" bind:checked={startupScan}
               onchange={event => {
                   try {
                       saveScanAtStartup(event.currentTarget.checked);
                   } catch {
                       onError('Cannot save the startup preference in browser storage');
                   }
               }} />
        Always run a full scan at startup
    </label>

    <label>
        <input type="checkbox" bind:checked={rememberTab}
               onchange={event => {
                   try {
                       saveRememberLastTab(event.currentTarget.checked);
                   } catch {
                       onError('Cannot save the tab preference in browser storage');
                   }
               }} />
        Remember last open tab
    </label>

    <label>
        <input type="checkbox" checked={$rememberFilters}
               onchange={event => {
                   try {
                       setRememberFilters(event.currentTarget.checked);
                   } catch {
                       onError('Cannot save the filter preference in browser storage');
                   }
               }} />
        Remember last used filters
    </label>
</div>

{#if settings}
    <div class="dialog-section">
        <MultiSelect title="Model extensions"
                     options={settings.available_model_extensions.map(value => ({ value, label: value }))}
                     selected={settings.model_extensions}
                     disabled={editingLocked}
                     onChanged={values => {
                         if (settings) settings.model_extensions = values;
                     }} />

        {#if extensionsDirty}
            <p class="warning-details">
                Changing the list of extensions can invalidate parts of the repository. Please rescan before continuing.
            </p>
        {/if}

        <div class="spaced-horizontally">
            <button class="button-with-text" disabled={!extensionsDirty} onclick={() => onSave(false)}>
                <img class="action-icon" alt="" src={saveIcon} />
                <span class="button-label">Save</span>
            </button>
            <button class="button-with-text" disabled={!extensionsDirty} onclick={() => onSave(true)}>
                <img class="action-icon" alt="" src={refreshIcon} />
                <span class="button-label">Save and scan</span>
            </button>
        </div>
    </div>
{/if}
