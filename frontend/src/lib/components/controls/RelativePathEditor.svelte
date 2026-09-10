<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: RelativePathEditor.svelte
 ! purpose: Editable relative-directory chooser with an explicit move action
 ! -------------------------------------------------->

<script lang="ts">
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
    Subdirectory
    <div class="spaced-horizontally">
        <input class="text-input full-width" list={listId} bind:value disabled={disabled}
               placeholder="Repository root" />

        <datalist id={listId}>
            {#each options as option}
                <option value={option}>{option || 'Repository root'}</option>
            {/each}
        </datalist>

        <button class="button-with-text" disabled={disabled || moveDisabled} onclick={onMove}>
            <img class="action-icon" alt="" src={moveIcon} />
            <span class="button-label">Move</span>
        </button>
    </div>
</label>
