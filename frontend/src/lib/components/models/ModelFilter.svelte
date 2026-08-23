<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ModelFilter.svelte
 ! purpose: Expandable model filtering panel
 ! -------------------------------------------------->

<script lang="ts">
    import { onMount } from 'svelte';

    import MultiSelect from '$components/controls/MultiSelect.svelte';
    import TagEditor from '$components/controls/TagEditor.svelte';
    import {
        type ConfigOption,
        getFileFormats,
        getModelTypes
    } from '$lib/configuration';
    import { type ModelSearchCriteria } from '$lib/models';

    let {
        onFilter
    }: {
        onFilter: (filter: ModelSearchCriteria) => Promise<boolean>;
    } = $props();

    const emptyFilter = (): ModelSearchCriteria => ({
        types: [],
        file_formats: [],
        required_tags: [],
        forbidden_tags: [],
        name_prefix: ''
    });

    const copyFilter = (filter: ModelSearchCriteria): ModelSearchCriteria => ({
        types: [...filter.types],
        file_formats: [...filter.file_formats],
        required_tags: [...filter.required_tags],
        forbidden_tags: [...filter.forbidden_tags],
        name_prefix: filter.name_prefix
    });

    let expanded = $state(false);
    let applied = $state<ModelSearchCriteria>(emptyFilter());
    let draft = $state<ModelSearchCriteria>(emptyFilter());
    let fileFormatOptions = $state<ConfigOption[]>([]);
    let modelTypeOptions = $state<ConfigOption[]>([]);
    let optionsError = $state<string | null>(null);

    let filterCount = $derived(
        applied.types.length + applied.file_formats.length +
        applied.required_tags.length + applied.forbidden_tags.length +
        (applied.name_prefix ? 1 : 0)
    );

    onMount(async () => {
        const [formats, types] = await Promise.all([getFileFormats(), getModelTypes()]);
        if (formats.ok) {
            fileFormatOptions = formats.data.map(value => ({value, label: value}));
        } else {
            optionsError = formats.message ?? 'Cannot load model file formats';
        }
        if (types.ok) {
            modelTypeOptions = types.data;
        } else {
            optionsError = types.message ?? 'Cannot load model types';
        }
    });

    function openEditor(): void {
        draft = copyFilter(applied);
        expanded = true;
    }

    function cancel(): void {
        draft = copyFilter(applied);
        expanded = false;
    }

    function clear(): void {
        draft = emptyFilter();
    }

    async function apply(): Promise<void> {
        const next = copyFilter(draft);
        if (await onFilter(next)) {
            applied = next;
            expanded = false;
        }
    }
</script>

<section class="model-filter" data-model-filter>
    {#if !expanded}
        <button type="button" class="filter-summary" onclick={openEditor}
                aria-expanded="false">
            <i class="fa-solid fa-filter"></i>
            {#if filterCount === 0}
                <span>No filters applied</span>
            {:else}
                {#if applied.name_prefix}<span>Name: {applied.name_prefix}</span>{/if}
                {#each applied.file_formats as format}<span>{format}</span>{/each}
                {#each applied.types as type}<span>{modelTypeOptions.find(o => o.value === type)?.label ?? type}</span>{/each}
                {#each applied.required_tags as tag}<span>+{tag}</span>{/each}
                {#each applied.forbidden_tags as tag}<span>−{tag}</span>{/each}
            {/if}
        </button>
    {:else}
        <div class="filter-editor" aria-label="Model filters">
            <div class="filter-box filter-actions">
                <button type="button" class="simple-button" onclick={apply}>Apply</button>
                <button type="button" class="simple-button" onclick={cancel}>Cancel</button>
                <button type="button" class="simple-button" onclick={clear}>Clear</button>
                {#if optionsError}<p class="error-message">{optionsError}</p>{/if}
            </div>

            <div class="filter-box">
                <p class="dialog-label">Name prefix</p>
                <input class="text-input full-width" type="text"
                       bind:value={draft.name_prefix} />
            </div>

            <div class="filter-box">
                <MultiSelect title="File formats" options={fileFormatOptions}
                             selected={draft.file_formats}
                             onChanged={selected => draft.file_formats = selected} />
            </div>

            <div class="filter-box">
                <MultiSelect title="Model types" options={modelTypeOptions}
                             selected={draft.types}
                             onChanged={selected => draft.types = selected} />
            </div>

            <div class="filter-box">
                <TagEditor title="Required tags" tags={draft.required_tags}
                           disabled={false} editable={false}
                           onChanged={tags => draft.required_tags = tags} />
            </div>

            <div class="filter-box">
                <TagEditor title="Forbidden tags" tags={draft.forbidden_tags}
                           disabled={false} editable={false}
                           onChanged={tags => draft.forbidden_tags = tags} />
            </div>
        </div>
    {/if}
</section>

<style>
    .model-filter {
        flex: 0 0 auto;
        padding: var(--gap-small);
        border-bottom: var(--solid-border);
        background: var(--bg-color);
        box-shadow: var(--shadow-down);
    }

    .filter-summary {
        width: 100%;
        min-height: var(--button-height);
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: var(--gap-small);
        padding: var(--gap-small) var(--gap-mid);
        border-radius: var(--radius-small);
        text-align: left;
    }

    .filter-editor {
        display: flex;
        flex-flow: row wrap;
        align-items: stretch;
        gap: var(--gap-small);
    }

    .filter-box {
        flex: 1 1 12rem;
        min-width: 10rem;
        padding: var(--gap-small);
        border: var(--solid-border);
        border-radius: var(--radius-small);
        background: var(--bg-color);
    }

    .filter-actions {
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        gap: var(--gap-small);
    }
</style>
