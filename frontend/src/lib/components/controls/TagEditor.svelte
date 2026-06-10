<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: TagEditor.svelte
 ! purpose: A control for editing a list of tags
 ! -------------------------------------------------->

<script lang="ts">
    import { getTagsContext } from '$lib/tags';

    const global_tags = getTagsContext();

    let {
        tags,
        onChanged,
        disabled
    }: {
        tags: string[];
        onChanged: (t: string[]) => void;
        disabled: boolean;
    } = $props();

    let draft_tags = $state<string[]>([]);
    let query = $state('');

    $effect(() => {
        tags;
        draft_tags = [...tags];
        query = '';
    });

    let normalizedDraft = $derived(
        new Set(draft_tags.map(t => t.toLowerCase()))
    );

    let suggestions = $derived.by(() => {
        const q = query.trim().toLowerCase();

        if (!q) return [];

        return global_tags.all_tags
            .filter(tag => tag.toLowerCase().startsWith(q))
            .filter(tag => !normalizedDraft.has(tag.toLowerCase()));
    });

    let canAddNew = $derived.by(() => {
        const q = query.trim();
        if (!q) return false;

        return !normalizedDraft.has(q.toLowerCase());
    });


    function addTag(tag: string) {
        const cleaned = tag.trim();
        if (!cleaned) return;

        if (!normalizedDraft.has(cleaned.toLowerCase())) {
            draft_tags = [...draft_tags, cleaned];
        }

        query = '';
        onChanged(draft_tags);
    }

    function removeTag(tag: string) {
        draft_tags = draft_tags.filter(t => t !== tag);
        onChanged(draft_tags);
    }

    function handleKeydown(event: KeyboardEvent) {
        if (event.key === 'Enter') {
            event.preventDefault();

            if (suggestions.length > 0) {
                addTag(suggestions[0]);
            } else if (canAddNew) {
                addTag(query);
            }
        }

        if (event.key === 'Escape') {
            query = '';
        }
    }

    let inputWrapper: HTMLElement;
    let dropdownTop = $state('0px');
    let dropdownLeft = $state('0px');
    let dropdownWidth = $state('0px');

    function positionDropdown() {
        if (!inputWrapper) return;
        const rect = inputWrapper.getBoundingClientRect();

        dropdownTop = `${rect.bottom + 4}px`;
        dropdownLeft = `${rect.left}px`;
        dropdownWidth = `${rect.width}px`;
    }
</script>


<div class="tag-editor">
    <div class="tag-list">
        {#each draft_tags as tag}
            <div class="tag-container">
                <span class="tag-content">{tag}</span>
                <button type="button"
                        class="tag-remove"
                        onclick={() => removeTag(tag)}
                        disabled={disabled}>×</button>
            </div>
        {/each}

        <div class="tag-container" bind:this={inputWrapper}>
            <input class="tag-input"
                   type="text"
                   bind:value={query}
                   onfocus={positionDropdown}
                   oninput={positionDropdown}
                   onkeydown={handleKeydown}
                   placeholder={disabled ? ". . ." : "Add tag"}
                   disabled={disabled} />
        </div>
    </div>

{#if query.trim()}
    <div class="tag-dropdown"
         style:--dropdown-top={dropdownTop}
         style:--dropdown-left={dropdownLeft}
         style:--dropdown-width={dropdownWidth}>
    {#if suggestions.length > 0}
        {#each suggestions as tag}
            <button type="button" class="tag-container" onclick={() => addTag(tag)} >
                {tag}
            </button>
        {/each}
    {:else if canAddNew}
            <button type="button" class="tag-container"  onclick={() => addTag(query)} >
            + '{query.trim()}'
            </button>
    {/if}
    </div>
{/if}
</div>

<style>

:root {
    --tag-pill-height: 1.2rem;
    --tag-pill-radius: calc(0.5 * var(--tag-pill-height));
}

/* List of selected tags with editing functions */
.tag-list {
    background: var(--bg-accent);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-mid);
    max-height: 6rem;
    display: flex;
    flex-direction: row;
    flex-flow: wrap;
    overflow-x: hidden;
    overflow-y: auto;
    padding: var(--gap-tiny);
    gap: var(--gap-tiny);
}

/* Container for a single tag */
.tag-container {
    display: flex;
    align-items: center;
    border-radius: var(--tag-pill-radius);
    border: 1px solid var(--border-color);
    background: var(--bg-color);
    margin: 0;
    height: var(--tag-pill-height);
    font-size: var(--small-font-size);
    white-space: nowrap;
    overflow: hidden;
}

.tag-remove {
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--tag-pill-radius);
    border: 1px solid var(--border-color);
    background: var(--bg-intense);
    color: var(--text-color);
    height: var(--tag-pill-height);
    width: var(--tag-pill-height);
    margin-left: var(--gap-small);
    font-size: var(--medium-font-size);
}

button.tag-remove:hover {
    border: 1px solid var(--border-color);
    background: var(--bg-highlight);
    transform: none;
    box-shadow: none;
}

.tag-content {
    width: auto;
    margin-left: var(--gap-small);
}

.tag-input {
    border: 0;
    color: var(--text-color);
    background: var(--bg-color);
    margin: 0 var(--gap-small);
    box-sizing: border-box;
}

.tag-input:focus-visible {
    outline: 0;
}

.tag-dropdown {
    position: fixed;
    z-index: var(--z-popup);
    background: var(--bg-color);
    border: 1px solid var(--border-color);
    background: var(--bg-accent);

    top: var(--dropdown-top);
    left: var(--dropdown-left);
    width: var(--dropdown-width);
}
</style>