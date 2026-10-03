<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: PathInput.svelte
 ! purpose: Editable server path validated against the disk-owned filesystem policy
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';
    import type { DirectoryRole } from '$lib/settings';
    import DirectoryPicker from './DirectoryPicker.svelte';

    let { value = $bindable(), disabled = false, role }: {
        value: string | null | undefined;
        role: DirectoryRole;
        disabled?: boolean;
        onError?: (message: string) => void;
    } = $props();
    let open = $state(false);
</script>

<div class="path-input">
    <input class="text-input" bind:value {disabled} />
    <button type="button" {disabled} aria-label={locale.t(`picker.${role}`)}
            title={locale.t(`picker.${role}`)} onclick={() => open = true}>…</button>
</div>
{#if open && !disabled}
    <DirectoryPicker {role} initialPath={value ?? ''}
                     onSelect={path => { value = path; open = false; }}
                     onClose={() => open = false} />
{/if}
