<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: IconPicker.svelte
 ! purpose: Image-based chooser for user-defined type icons
 ! -------------------------------------------------->

<script lang="ts">
import { userTypeIcon } from '$lib/user-types.svelte';

let { value = $bindable(), options }: { value: string; options: string[] } = $props();
let picker: HTMLDetailsElement;

function select(icon: string): void {
    value = icon;
    picker.open = false;
}
</script>

<details class="icon-picker" bind:this={picker}>
    <summary aria-label="Select icon">
        <img class="action-icon" src={userTypeIcon(value, 16)} alt={value} />
    </summary>
    <div class="icon-picker-options">
        {#each options as icon}
            <button type="button" class:active={icon === value}
                    aria-label={icon} title={icon} onclick={() => select(icon)}>
                <img class="action-icon" src={userTypeIcon(icon, 16)} alt="" />
            </button>
        {/each}
    </div>
</details>
