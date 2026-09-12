<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: WorkflowSettings.svelte
 ! purpose: Workflow repository settings tab
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

    import resetIcon from '$icons/actions/reset16.png';
    import saveIcon from '$icons/actions/save16.png';

    import PathInput from '$components/controls/PathInput.svelte';
    import type { RepositorySettings } from '$lib/settings';

    let {
        settings = $bindable(),
        dirty,
        saving,
        onUndo,
        onSave,
        onError
    }: {
        settings: RepositorySettings | null;
        dirty: boolean;
        saving: boolean;
        onUndo: () => void;
        onSave: () => void;
        onError: (message: string) => void;
    } = $props();
</script>

{#if settings}
    <div class="spaced-horizontally settings-tab-actions">
        <div></div>
        <div class="settings-actions">
            <button class="button-with-text" disabled={!dirty || saving} onclick={onUndo}>
                <img class="action-icon" alt={locale.t('ui.workflow_settings.undo')} src={resetIcon} />
                <span class="button-label">{locale.t('ui.workflow_settings.undo_2')}</span>
            </button>
            <button class="button-with-text" disabled={!dirty || saving} onclick={onSave}>
                <img class="action-icon" alt={locale.t('ui.workflow_settings.save')} src={saveIcon} />
                <span class="button-label">{locale.t(saving ? 'dynamic.saving' : 'dynamic.save')}</span>
            </button>
        </div>
    </div>

    <div class="settings-item-list">
        {#if settings.workflow_locations[0]}
            {@const location = settings.workflow_locations[0]}
            <div class="settings-form aligned-settings-form dialog-section">
                <label class="dialog-label">
                    {locale.t('ui.workflow_settings.working_folder')}
                    <PathInput bind:value={location.working_dir}
                               disabled={settings.mode === 'comfyui'}
                               onError={onError} />
                </label>
                <label class="dialog-label">
                    {locale.t('ui.workflow_settings.archive_folder')}
                    <PathInput bind:value={location.archive_dir} onError={onError} />
                </label>
            </div>
        {/if}
    </div>
{/if}
