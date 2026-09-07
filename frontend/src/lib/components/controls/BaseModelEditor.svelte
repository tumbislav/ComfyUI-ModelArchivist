<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: BaseModelEditor.svelte
 ! purpose: Free-text base-model editor with repository-backed suggestions
 ! -------------------------------------------------->

<script lang="ts">
import { onMount } from 'svelte';
import { getBaseModels } from '$lib/models';

let {
    value,
    disabled = false,
    placeholder = 'Base model',
    inputId,
    onChanged
}: {
    value: string;
    disabled?: boolean;
    placeholder?: string;
    inputId?: string;
    onChanged: (value: string) => void;
} = $props();

let available = $state<string[]>([]);
let focused = $state(false);
let suggestions = $derived.by(() => {
    const query = value.trim().toLocaleLowerCase();
    if (!focused || !query) return [];
    return available.filter(item => item.toLocaleLowerCase().includes(query));
});

onMount(async () => {
    const response = await getBaseModels();
    if (response.ok) available = response.data;
});

function change(next: string) {
    value = next;
    onChanged(next);
}

function select(value: string) {
    change(value);
    focused = false;
}
</script>

<div class="base-model-editor">
    <input class="text-input full-width"
           id={inputId}
           type="text"
           {value}
           {disabled}
           {placeholder}
           autocomplete="off"
           onfocus={() => focused = true}
           onblur={() => focused = false}
           oninput={(event) => change(event.currentTarget.value)}
           onkeydown={(event) => {
               if (event.key === 'Escape') focused = false;
               if (event.key === 'Enter' && suggestions.length > 0) {
                   event.preventDefault();
                   select(suggestions[0]);
               }
           }}>
    {#if suggestions.length > 0}
        <div class="base-model-suggestions">
            {#each suggestions as suggestion}
                <button type="button"
                        onmousedown={(event) => event.preventDefault()}
                        onclick={() => select(suggestion)}>
                    {suggestion}
                </button>
            {/each}
        </div>
    {/if}
</div>

<style>
</style>
