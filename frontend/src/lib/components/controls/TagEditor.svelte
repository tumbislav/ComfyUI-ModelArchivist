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
        disabled,
        title,
        editable
    }: {
        tags: string[];
        onChanged: (t: string[]) => void;
        disabled: boolean;
        title?: string;
        editable: boolean;
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
            } else if (canAddNew && editable) {
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

{#if title}
<p class="dialog-label">{title}</p>
{/if}

<div class="tag-editor">
    <div class="tag-list">
        {#each draft_tags as tag}
            <div class="pill-container">
                <span class="pill-content">{tag}</span>
                <button type="button"
                        class="round"
                        onclick={() => removeTag(tag)}
                        disabled={disabled}>×</button>
            </div>
        {/each}
        
        <div class="pill-container" bind:this={inputWrapper}>
            <input class="pill-input"
                   type="text"
                   bind:value={query}
                   onfocus={positionDropdown}
                   oninput={positionDropdown}
                   onkeydown={handleKeydown}
                   placeholder={disabled ? ". . ." : (editable ? "Add tag" : "Find tag")}
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
            <button type="button" class="pill-container" onclick={() => addTag(tag)} >
                {tag}
            </button>
        {/each}
    {:else if canAddNew}
            <button type="button" class="pill-container"  onclick={() => addTag(query)} >
            + '{query.trim()}'
            </button>
    {/if}
    </div>
{/if}
</div>

<style>

/* List of selected tags with editing functions */
.tag-list {
    background: var(--bg-accent);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-mid);
    min-height: 32px;
    max-height: 6rem;
    display: flex;
    flex-direction: row;
    flex-flow: wrap;
    overflow-x: hidden;
    overflow-y: auto;
    padding: var(--gap-tiny);
    gap: var(--gap-tiny);
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
