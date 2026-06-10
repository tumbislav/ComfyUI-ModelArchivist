<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ModelFilter.svelte
 ! purpose: Left sidebar for model filtering
 ! -------------------------------------------------->

<script lang=ts>
    import TagEditor from '$components/controls/TagEditor.svelte'

    import { createEventDispatcher } from 'svelte';

    const dispatch = createEventDispatcher<{ submit: FilterAttributes }>();

    let filters: FilterAttributes = {
        status: 'all',
    };

    function submit() {
        dispatch('submit', filters);
    };

    function tagsChanged(updated: string[]): void {
    }
</script>

<aside class="left-sidebar">

    <div class="dialog-section">
        <p class="section-label">Include tags</p>
        <TagEditor tags={[]} onChanged={tagsChanged}  />

        <p class="section-label">Exclude tags</p>
        <TagEditor tags={[]} onChanged={tagsChanged}  />
    </div>

    <div class="dialog-section spaced-horizontally">
        <div></div>
        <button class="simple-button action-button">
            <i class="fa-solid fa-filter"></i> <span class="actions-label">Filter</span>
        </button>
    </div>
</aside>


<style>

</style>