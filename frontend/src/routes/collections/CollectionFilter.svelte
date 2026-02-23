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
    <!--
        <meter>
        <output>
    -->
    <button class="action-button" onclick={ submit } disabled={loading}>
        {loading ? "Loading..." : "Re-scan"}
    </button>
</aside>


<style>

</style>