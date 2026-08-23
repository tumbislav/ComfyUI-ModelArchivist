<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: MultiSelect.svelte
 ! purpose: Select multiple values from a fixed list
 ! -------------------------------------------------->

<script lang="ts">
    import { type ConfigOption } from '$lib/configuration';

    let {
        title,
        options,
        selected,
        onChanged,
        disabled = false
    }: {
        title?: string;
        options: ConfigOption[];
        selected: string[];
        onChanged: (selected: string[]) => void;
        disabled?: boolean;
    } = $props();

    let query = $state('');
    let selectedValues = $derived(new Set(selected));
    let selectedOptions = $derived(
        selected.map(value => options.find(option => option.value === value) ?? {
            value, label: value
        })
    );
    let suggestions = $derived.by(() => {
        const normalized = query.trim().toLowerCase();
        if (!normalized) return [];
        return options
            .filter(option => !selectedValues.has(option.value))
            .filter(option => option.label.toLowerCase().startsWith(normalized));
    });

    function add(value: string): void {
        if (!selectedValues.has(value)) onChanged([...selected, value]);
        query = '';
    }

    function remove(value: string): void {
        onChanged(selected.filter(item => item !== value));
    }

    function handleKeydown(event: KeyboardEvent): void {
        if (event.key === 'Enter' && suggestions.length > 0) {
            event.preventDefault();
            add(suggestions[0].value);
        } else if (event.key === 'Escape') {
            query = '';
        }
    }
</script>

{#if title}<p class="dialog-label">{title}</p>{/if}

<div class="multi-select">
    <div class="tag-list">
        {#each selectedOptions as option (option.value)}
            <div class="pill-container">
                <span class="pill-content">{option.label}</span>
                <button type="button" class="round"
                        onclick={() => remove(option.value)} disabled={disabled}>×</button>
            </div>
        {/each}
        <div class="pill-container">
            <input class="pill-input" type="text" bind:value={query}
                   onkeydown={handleKeydown} placeholder="Find option" disabled={disabled} />
        </div>
    </div>

    {#if query.trim() && suggestions.length > 0}
        <div class="tag-dropdown">
            {#each suggestions as option (option.value)}
                <button type="button" class="pill-container"
                        onclick={() => add(option.value)}>{option.label}</button>
            {/each}
        </div>
    {/if}
</div>

<style>
    .multi-select {
        position: relative;
    }

    .tag-list {
        background: var(--bg-accent);
        border: var(--solid-border);
        border-radius: var(--radius-mid);
        min-height: var(--button-height);
        max-height: 6rem;
        display: flex;
        flex-flow: row wrap;
        overflow-y: auto;
        padding: var(--gap-tiny);
        gap: var(--gap-tiny);
    }

    .tag-dropdown {
        position: absolute;
        z-index: var(--z-popup);
        top: calc(100% + var(--gap-tiny));
        left: 0;
        right: 0;
        padding: var(--gap-tiny);
        background: var(--bg-accent);
        border: var(--solid-border);
        border-radius: var(--radius-small);
    }
</style>
