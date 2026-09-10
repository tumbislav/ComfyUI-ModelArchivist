<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: ColumnFilter.svelte
 ! purpose: Accessible column filter dropdown with apply and cancel drafts
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import { onMount, tick, type Snippet } from 'svelte';
    import { applyColumn, columnValue, filterColumns, filterStates, openFilter,
        type FilterTab, type ColumnRule } from '$lib/column-filters';

    let { tab, columnKey, rows, children }: {
        tab: FilterTab; columnKey: string; rows: object[]; children: Snippet;
    } = $props();
    const id = $props.id();
    let button: HTMLButtonElement;
    let popup = $state<HTMLDivElement>();
    let prefix = $state('');
    let selected = $state<string[]>([]);
    let boolean = $state('all');
    let x = $state(0);
    let y = $state(0);
    let height = $state(300);
    let definition = $derived(filterColumns[tab].find(column => column.key === columnKey)!);
    let options = $derived([...new Set(rows.flatMap(row => {
        const value = columnValue(row, columnKey);
        return Array.isArray(value) ? value : [String(value)];
    }))]
        .sort((a, b) => a.localeCompare(b)));
    let isOpen = $derived($openFilter === id);
    let allSelected = $derived(options.every(value => selected.includes(value)));

    function cancel(): void {
        openFilter.set(null);
        button?.focus();
    }

    async function toggle(): Promise<void> {
        if (isOpen) { cancel(); return; }
        const rule = $filterStates[tab].columns[columnKey];
        prefix = typeof rule === 'string' ? rule : '';
        selected = Array.isArray(rule) ? [...rule] : [...options];
        boolean = typeof rule === 'boolean' ? String(rule) : 'all';
        const bounds = button.getBoundingClientRect();
        x = Math.max(8, Math.min(bounds.left, window.innerWidth - 300));
        const below = window.innerHeight - bounds.bottom - 12;
        const above = bounds.top - 12;
        height = Math.min(400, Math.max(below, above));
        if (below >= Math.min(200, above)) {
            height = Math.min(400, below);
            y = bounds.bottom + 4;
        } else {
            height = Math.min(400, above);
            y = Math.max(8, bounds.top - height - 4);
        }
        openFilter.set(id);
        await tick();
        popup?.querySelector<HTMLElement>('input, button')?.focus();
    }

    function apply(): void {
        let rule: ColumnRule | null = prefix;
        if (definition.kind === 'multi') rule = allSelected ? null : selected;
        if (definition.kind === 'boolean') rule = boolean === 'all' ? null : boolean === 'true';
        applyColumn(tab, columnKey, rule);
        cancel();
    }

    onMount(() => {
        function key(event: KeyboardEvent): void {
            if (isOpen && event.key === 'Escape') {
                event.preventDefault();
                event.stopImmediatePropagation();
                cancel();
            }
        }
        function outside(event: PointerEvent): void {
            const target = event.target as Node;
            if (isOpen && !popup?.contains(target) && !button?.contains(target)) openFilter.set(null);
        }
        window.addEventListener('keydown', key, true);
        window.addEventListener('pointerdown', outside);
        return () => {
            window.removeEventListener('keydown', key, true);
            window.removeEventListener('pointerdown', outside);
            if (isOpen) openFilter.set(null);
        };
    });
</script>

<button class="column-filter-trigger" class:column-filter-applied={columnKey in $filterStates[tab].columns}
        type="button" bind:this={button} aria-label={`Filter ${definition.label}`}
        aria-expanded={isOpen} aria-haspopup="dialog" onclick={toggle}>
    {@render children()}
</button>

{#if isOpen}
    <div class="column-filter-dropdown" role="dialog" aria-label={`Filter ${definition.label}`}
         tabindex="-1" bind:this={popup} style:left={`${x}px`} style:top={`${y}px`}
         style:max-height={`${height}px`}>
        <strong>{definition.label}</strong>
        {#if definition.kind === 'prefix'}
            <label class="column-filter-prefix">Text prefix
                <input class="text-input" bind:value={prefix} onkeydown={event => {
                    if (event.key === 'Enter') apply();
                }} />
            </label>
        {:else if definition.kind === 'multi'}
            <label>
                <input type="checkbox" checked={allSelected}
                       indeterminate={selected.length > 0 && !allSelected}
                       onchange={() => selected = allSelected ? [] : [...options]} />
                Select all
            </label>
            <div class="column-filter-values">
                {#each options as value}
                    <label>
                        <input type="checkbox" checked={selected.includes(value)}
                               onchange={() => selected = selected.includes(value)
                                   ? selected.filter(item => item !== value) : [...selected, value]} />
                        {value || '(blank)'}
                    </label>
                {/each}
            </div>
        {:else}
            {#each [['all', 'Show all'], ['true', definition.positive], ['false', definition.negative]] as [value, label]}
                <label><input type="radio" name={id} {value} bind:group={boolean} />{label}</label>
            {/each}
        {/if}
        <div class="spaced-horizontally">
            <button class="narrow-button" onclick={apply}>Apply</button>
            <button class="narrow-button" onclick={() => { applyColumn(tab, columnKey, null); cancel(); }}>Clear</button>
            <button class="narrow-button" onclick={cancel}>Cancel</button>
        </div>
    </div>
{/if}
