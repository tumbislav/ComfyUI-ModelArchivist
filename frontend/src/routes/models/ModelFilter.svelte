<script lang=ts>
    let { loading } = $props();

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
    <label for="model-filter-include-tags"><span class="actions-label">Include tags</span></label>
    <div class="tag-list" id="model-filter-include-tags">
        <div class="tag-container"><span class="tag-content">+</span></div>
        <div class="tag-container"><span class="tag-content">a tag<i class="fas fa-close tag-close"></i></span></div>
        <div class="tag-container"><span class="tag-content">another tag<i class="fas fa-close tag-close"></i></span></div>
        <div class="tag-container"><span class="tag-content">a third tag</span></div>
        <div class="tag-container"><span class="tag-content">yet another tag</span></div>
        <div class="tag-container"><span class="tag-content">more tags</span></div>
        <div class="tag-container"><span class="tag-content">a tag</span></div>
        <div class="tag-container"><span class="tag-content">another tag</span></div>
        <div class="tag-container"><span class="tag-content">a third tag</span></div>
        <div class="tag-container"><span class="tag-content">yet another tag</span></div>
        <div class="tag-container"><span class="tag-content">more tags</span></div>
        <div class="tag-container"><span class="tag-content">a tag</span></div>
        <div class="tag-container"><span class="tag-content">another tag</span></div>
        <div class="tag-container"><span class="tag-content">a third tag</span></div>
        <div class="tag-container"><span class="tag-content">yet another tag</span></div>
        <div class="tag-container"><span class="tag-content">more tags</span></div>
    </div>

    <label class="actions-label" for="model-filter-exclude-tags">Exclude tags</label>
    <div class="tag-list" id="model-filter-exclude-tags">
        <div class="tag-container"><span class="tag-content">+</span></div>
        <div class="tag-container"><span class="tag-content">a tag<i class="fas fa-close tag-close"></i></span></div>
        <div class="tag-container"><span class="tag-content">another tag<i class="fas fa-close tag-close"></i></span></div>
        <div class="tag-container"><span class="tag-content">a third tag</span></div>
        <div class="tag-container"><span class="tag-content">yet another tag</span></div>
        <div class="tag-container"><span class="tag-content">more tags</span></div>
        <div class="tag-container"><span class="tag-content">a tag</span></div>
        <div class="tag-container"><span class="tag-content">another tag</span></div>
        <div class="tag-container"><span class="tag-content">a third tag</span></div>
        <div class="tag-container"><span class="tag-content">yet another tag</span></div>
        <div class="tag-container"><span class="tag-content">more tags</span></div>
        <div class="tag-container"><span class="tag-content">a tag</span></div>
        <div class="tag-container"><span class="tag-content">another tag</span></div>
        <div class="tag-container"><span class="tag-content">a third tag</span></div>
        <div class="tag-container"><span class="tag-content">yet another tag</span></div>
        <div class="tag-container"><span class="tag-content">more tags</span></div>
    </div>

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