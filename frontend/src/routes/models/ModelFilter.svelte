<script lang=ts>
    let { tags, error, loading } = $props();

    import { createEventDispatcher } from 'svelte';

    const dispatch = createEventDispatcher<{ submit: FilterAttributes }>();

    let filters: FilterAttributes = {
        status: 'all',
    };

    function submit() {
        dispatch('submit', filters);
    };
</script>

<aside class="left-sidebar">
    {#if error}
    <div class="message-container error-message">
        <p>{error}</p>
    </div>
    {:else}
    <p>Found {tags.length} tags.</p>

    <label for="model-filter-include-tags"><span class="actions-label">Include tags</span></label>
    <div class="tag-list" id="model-filter-include-tags">
        <div class="tag-container"><span class="tag-content">+</span></div>
        {#each tags as t, i}
        <div class="tag-container"><span class="tag-content">
                    {t}<i class="fas fa-close tag-close"></i></span>
        </div>
        {/each}
    </div>

    <label class="actions-label" for="model-filter-exclude-tags">Exclude tags</label>
    <div class="tag-list" id="model-filter-exclude-tags">
        <div class="tag-container"><span class="tag-content">+</span></div>
        {#each tags as t, i}
        <div class="tag-container"><span class="tag-content">
                    {t}<i class="fas fa-close tag-close"></i></span>
        </div>
        {/each}
    </div>
    {/if}
    <!--
        <dialog>
        <fieldset>
        <label>
        <input>
        <legend>
        <optgroup>
        <option>
        <select>
        <textarea>
        <meter>
        <output>
    -->
    <button class="action-button" onclick={ submit } disabled={loading}>
        {loading ? "Loading..." : "Re-scan"}
    </button>
</aside>


<style>

</style>