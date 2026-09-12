<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: PathInput.svelte
 ! purpose: Editable server path with host directory picker
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

import rightIcon from '$icons/actions/right12.png';
import { pickDirectory } from '$lib/settings';

let { value = $bindable(), disabled = false, onError = () => {} }: {
    value: string | null | undefined; disabled?: boolean;
    onError?: (message: string) => void;
} = $props();

async function choose(): Promise<void> {
    const result = await pickDirectory(value ?? '');
    if (result.ok && result.data.path !== null) value = result.data.path;
    else if (!result.ok) onError(result.message ?? locale.t('ui.path_input.cannot_open_directory_picker'));
}
</script>

<div class="path-input">
    <input class="text-input" bind:value {disabled} />
    <button type="button" aria-label={locale.t('ui.path_input.select_folder')} {disabled} onclick={choose}>
        <img class="action-icon" alt="" src={rightIcon} />
    </button>
</div>
