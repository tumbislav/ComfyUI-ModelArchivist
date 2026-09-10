<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: WorkflowSettings.svelte
 ! purpose: Workflow repository settings tab
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
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
                <img class="action-icon" alt="undo" src={resetIcon} />
                <span class="button-label">Undo</span>
            </button>
            <button class="button-with-text" disabled={!dirty || saving} onclick={onSave}>
                <img class="action-icon" alt="save" src={saveIcon} />
                <span class="button-label">{saving ? 'Saving…' : 'Save'}</span>
            </button>
        </div>
    </div>

    <div class="settings-item-list">
        {#if settings.workflow_locations[0]}
            {@const location = settings.workflow_locations[0]}
            <div class="settings-form aligned-settings-form dialog-section">
                <label class="dialog-label">
                    Working folder
                    <PathInput bind:value={location.working_dir}
                               disabled={settings.mode === 'comfyui'}
                               onError={onError} />
                </label>
                <label class="dialog-label">
                    Archive folder
                    <PathInput bind:value={location.archive_dir} onError={onError} />
                </label>
            </div>
        {/if}
    </div>
{/if}
