<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: HelpButton.svelte
 ! purpose: Clickable and hoverable contextual help tooltip
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

let { text }: { text: string } = $props();
let pinned = $state(false);
let hovered = $state(false);
let focused = $state(false);
let visible = $derived(pinned || hovered || focused);
</script>

<span class="help-control">
    <button type="button" class="round help-button"
            aria-label={locale.t('ui.help_button.help')} aria-expanded={text.length > 0 && visible}
            onclick={() => pinned = !pinned}
            onmouseenter={() => hovered = true}
            onmouseleave={() => hovered = false}
            onfocus={() => focused = true}
            onblur={() => focused = false}>?</button>
    {#if visible && text.length > 0}
        <span class="help-tooltip" role="tooltip">{text}</span>
    {/if}
</span>
