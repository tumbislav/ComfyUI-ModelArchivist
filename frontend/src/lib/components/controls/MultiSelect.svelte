<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: MultiSelect.svelte
 ! purpose: Select multiple values from a fixed list
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

    import closeIcon from '$icons/actions/close8.png';
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

{#if title}
    <h2 class="slim-margin">{title}</h2>
{/if}

<div class="multi-select">
    <div class="multi-select-list">
        {#each selectedOptions as option (option.value)}
            <div class="pill-container">
                <span class="pill-content">{option.label}</span>
                <button type="button" class="round"
                        aria-label={locale.t('messages.remove_option', {option: option.label})}
                        onclick={() => remove(option.value)} disabled={disabled}>
                    <img class="action-icon" alt="" src={closeIcon} />
                </button>
            </div>
        {/each}
        <div class="pill-container">
            <input class="pill-input" type="text" bind:value={query}
                   onkeydown={handleKeydown} placeholder={locale.t('ui.multi_select.find_option')} disabled={disabled} />
        </div>
    </div>

    {#if query.trim() && suggestions.length > 0}
        <div class="multi-select-dropdown">
            {#each suggestions as option (option.value)}
                <button type="button" class="pill-container"
                        onclick={() => add(option.value)}>{option.label}</button>
            {/each}
        </div>
    {/if}
</div>

<style>
</style>
