<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ModelActions.svelte
 ! purpose: Model selection actions and expandable filtering panel
 ! -------------------------------------------------->

<script lang="ts">
    import { onMount } from 'svelte';
    import filterIcon from '$icons/filter16.png';
    import filterOffIcon from '$icons/filter-off16.png';
    import adjustIcon from '$icons/adjust16.png';
    import confirmIcon from '$icons/confirm16.png';
    import cancelIcon from '$icons/cancel16.png';
    import resetIcon from '$icons/reset16.png';
    import openIcon from '$icons/open16.png';

    import MultiSelect from '$components/controls/MultiSelect.svelte';
    import TagEditor from '$components/controls/TagEditor.svelte';
    import {
        type ConfigOption,
        getFileFormats,
        getModelTypes
    } from '$lib/configuration';
    import { type ModelSearchCriteria } from '$lib/models';

    let {
        selectedCount,
        onFilter,
        onOpenMulti
    }: {
        selectedCount: number;
        onFilter: (filter: ModelSearchCriteria) => Promise<boolean>;
        onOpenMulti: () => Promise<void>;
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
    let filterActive = $state<boolean>(false);

    let filterCount = $derived(
        applied.types.length + applied.file_formats.length +
        applied.required_tags.length + applied.forbidden_tags.length +
        (applied.name_prefix ? 1 : 0)
    );

    function hasFilters(filter: ModelSearchCriteria): boolean {
        return filter.types.length > 0 || filter.file_formats.length > 0 ||
            filter.required_tags.length > 0 || filter.forbidden_tags.length > 0 ||
            filter.name_prefix.length > 0;
    }

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

    async function toggleFilter(): Promise<void> {
        if (filterCount === 0) {
            openEditor();
            return;
        }

        const nextActive = !filterActive;
        const criteria = nextActive ? copyFilter(applied) : emptyFilter();
        if (await onFilter(criteria)) {
            filterActive = nextActive;
        }
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
        const nextActive = hasFilters(next);
        if (await onFilter(nextActive ? next : emptyFilter())) {
            applied = next;
            filterActive = nextActive;
            expanded = false;
        }
    }
</script>

<section class="filter-bar" data-model-actions>
    {#if !expanded}
            <div class="model-selection-actions">
                <button type="button" class="image-button"
                        disabled={selectedCount < 2}
                        onclick={onOpenMulti}
                        aria-label="edit selected models">
                    <img class="action-icon" alt="edit selected models" src={openIcon} />
                </button>
            </div>
            <div class="filter-buttons">
                <button type="button" class="image-button" onclick={toggleFilter}
                        aria-pressed={filterActive} aria-label="filter-on-off">
                    {#if filterActive}
                        <img class="action-icon" alt="filter" src={filterIcon} />
                    {:else}
                        <img class="action-icon" alt="filter off" src={filterOffIcon} />
                    {/if}
                </button>
                <button type="button" class="image-button" onclick={openEditor}
                        aria-expanded="false" aria-label="filter-adjust">
                    <img class="action-icon" alt="adjust" src={adjustIcon} />
                </button>
            </div>
            <div class="filter-summary">
                {#if filterCount === 0}
                    <span class="text-compact">No filters</span>
                {:else}
                    {#if !filterActive}
                        <span class="text-compact">(filter off)</span>
                    {/if}
                    {#if applied.name_prefix}
                        <span class="actions-label">Name:</span>
                        <span class="text-compact">{applied.name_prefix}</span>
                    {/if}
                    {#if applied.file_formats.length > 0}
                        <span class="actions-label">Formats:</span>
                        <span class="text-compact">{applied.file_formats.join(', ')}</span>
                    {/if}
                    {#if applied.types.length > 0}
                        <span class="actions-label">Types:</span>
                        <span class="text-compact">
                            {applied.types.map((type) =>
                             modelTypeOptions.find(o => o.value === type)?.label ?? type).join(', ')}
                        </span>
                    {/if}
                    {#if applied.required_tags.length > 0}
                        <span class="actions-label">Include tags:</span>
                        <span class="text-compact">{applied.required_tags.join(', ')}</span>
                    {/if}
                    {#if applied.forbidden_tags.length > 0}
                        <span class="actions-label">Exclude tags:</span>
                        <span class="text-compact">{applied.forbidden_tags.join(', ')}</span>
                    {/if}
                {/if}
            </div>
    {:else}
        <div class="filter-editor" aria-label="Model filters">
            <div class="model-selection-actions">
                <button type="button" class="image-button"
                        disabled={selectedCount < 2}
                        onclick={onOpenMulti}
                        aria-label="edit selected models">
                    <img class="action-icon" alt="edit selected models" src={openIcon} />
                </button>
            </div>
            <div class="filter-buttons">
                <button type="button" class="image-button" onclick={apply}>
                    <img class="action-icon" alt="confirm" src={confirmIcon} />
                </button>
                <button type="button" class="image-button" onclick={cancel}>
                    <img class="action-icon" alt="cancel" src={cancelIcon} />
                </button>
                <button type="button" class="image-button" onclick={clear}>
                    <img class="action-icon" alt="reset" src={resetIcon} />
                </button>
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
                <TagEditor title="Include tags" tags={draft.required_tags}
                           disabled={false} editable={false}
                           onChanged={tags => draft.required_tags = tags} />
            </div>

            <div class="filter-box">
                <TagEditor title="Exclude tags" tags={draft.forbidden_tags}
                           disabled={false} editable={false}
                           onChanged={tags => draft.forbidden_tags = tags} />
            </div>
        </div>
    {/if}
</section>

<style>

</style>
