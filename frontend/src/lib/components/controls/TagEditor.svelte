<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: TagEditor.svelte
 ! purpose: A control for editing a list of tags
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

    import closeIcon from '$icons/actions/close8.png';
    import { getTagsContext, loadTagRules, normalizeTag } from '$lib/tags';
    import { onMount } from 'svelte';
    
    const global_tags = getTagsContext();
    const inputId = $props.id();
    let rulesReady = $state(false);
    let validationError = $state<string | null>(null);

    onMount(async () => {
        try {
            await loadTagRules();
            rulesReady = true;
        } catch (error) {
            validationError = error instanceof Error ? error.message : locale.t('ui.tag_editor.cannot_load_tag_rules');
        }
    });

    let {
        tags,
        onChanged,
        disabled,
        title,
        editable,
        availableTags
    }: {
        tags: string[];
        onChanged: (t: string[]) => void;
        disabled: boolean;
        title?: string;
        editable: boolean;
        availableTags?: string[];
    } = $props();
    
    let draft_tags = $state<string[]>([]);
    let query = $state('');
    
    $effect(() => {
        tags;
        draft_tags = [...tags];
        query = '';
    });
    
    let normalizedDraft = $derived(
        new Set(draft_tags)
    );
    
    let suggestions = $derived.by(() => {
        const q = query.trim().toLowerCase();
        
        if (!q) return [];
        
        return (availableTags ?? global_tags.all_tags)
            .filter(tag => tag.toLowerCase().startsWith(q))
            .filter(tag => !normalizedDraft.has(tag))
            .filter(tag => !editable || (rulesReady && normalizeTag(tag) !== null));
    });
    
    let canAddNew = $derived.by(() => {
        const q = rulesReady ? normalizeTag(query) : null;
        if (!q || disabled || !editable) return false;
        
        return !normalizedDraft.has(q);
    });
    
    
    function addTag(tag: string) {
        const cleaned = editable ? normalizeTag(tag) : tag;
        if (!cleaned || disabled) return;
        
        if (!normalizedDraft.has(cleaned)) {
            draft_tags = [...draft_tags, cleaned];
        }
        
        query = '';
        onChanged(draft_tags);
    }

    function removeTag(tag: string) {
        if (disabled) return;
        draft_tags = draft_tags.filter(t => t !== tag);
        onChanged(draft_tags);
    }

    function handleKeydown(event: KeyboardEvent) {
        if (event.key === 'Enter') {
            event.preventDefault();

            if (canAddNew && editable) {
                addTag(query);
            } else if (suggestions.length > 0) {
                addTag(suggestions[0]);
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
    <h2 class="slim-margin">{title}</h2>
{/if}

<div class="multi-select">
    <div class="multi-select-list">
        {#each draft_tags as tag}
            <div class="pill-container">
                <span class="pill-content">{tag}</span>
                <button type="button"
                        class="round"
                        onclick={() => removeTag(tag)}
                        aria-label={locale.t('messages.remove_tag', {tag})}
                        disabled={disabled}>
                    <img class="action-icon" alt="" src={closeIcon} />
                </button>
            </div>
        {/each}
        
        <div class="pill-container" bind:this={inputWrapper}>
            <input class="pill-input" id={inputId}
                   type="text"
                   bind:value={query}
                   onfocus={positionDropdown}
                   oninput={positionDropdown}
                   onkeydown={handleKeydown}
                   placeholder={disabled ? ". . ." : locale.t(editable ? 'dynamic.add_tag' : 'dynamic.find_tag')}
                   disabled={disabled} />
        </div>
    </div>

    {#if query.trim()}
        <div class="multi-select-dropdown"
             style:--dropdown-top={dropdownTop}
             style:--dropdown-left={dropdownLeft}
             style:--dropdown-width={dropdownWidth}>
            {#each suggestions as tag}
                <button type="button" class="pill-container" {disabled} onclick={() => addTag(tag)}>
                    <span class="pill-content">{tag}</span>
                </button>
            {/each}

            {#if canAddNew}
                <button type="button" class="pill-container" {disabled} onclick={() => addTag(query)}>
                    <span class="pill-content">+ '{query.trim()}'</span>
                </button>
            {/if}
        </div>
    {/if}
</div>

{#if validationError}
    <p class="error-message">{validationError}</p>
{:else if editable && rulesReady && query && normalizeTag(query) === null}
    <p class="error-message">
        {locale.t('ui.tag_editor.start_with_a_letter_underscore_or_digit_0_9_use_name_characters_or_spaces_ascii_colon_and_dash_are_allowed_only_inside_the_tag')}
    </p>
{/if}

<style>
</style>
