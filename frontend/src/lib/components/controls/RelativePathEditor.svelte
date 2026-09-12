<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: RelativePathEditor.svelte
 ! purpose: Editable relative-directory chooser with an explicit move action
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

    import moveIcon from '$icons/actions/move-right16.png';

    let {
        value = $bindable(),
        options,
        disabled = false,
        moveDisabled = false,
        onMove
    }: {
        value: string;
        options: string[];
        disabled?: boolean;
        moveDisabled?: boolean;
        onMove: () => Promise<void>;
    } = $props();

    const listId = `relative-paths-${crypto.randomUUID()}`;
</script>

<label class="dialog-label">
    {locale.t('ui.relative_path_editor.subdirectory')}
    <div class="input-with-action">
        <input class="text-input full-width" list={listId} bind:value disabled={disabled}
               placeholder={locale.t('ui.relative_path_editor.repository_root')} />

        <datalist id={listId}>
            {#each options as option}
                <option value={option}>{option || locale.t('dynamic.repository_root')}</option>
            {/each}
        </datalist>

        <button class="narrow-button" disabled={disabled || moveDisabled} onclick={onMove}>
            <span class="button-label">{locale.t('ui.relative_path_editor.move')}</span>
        </button>
    </div>
</label>
