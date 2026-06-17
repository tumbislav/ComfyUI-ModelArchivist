<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ModelFilter.svelte
 ! purpose: Left sidebar for model filtering
 ! -------------------------------------------------->

<script lang=ts>
import TagEditor from '$components/controls/TagEditor.svelte'

import { type ModelSearchCriteria } from '$lib/models'

let {
    onFilter,
    onReset
}: {
    onFilter: (filter: ModelSearchCriteria) => Promise<void>;
    onReset: () => Promise<void>;
} = $props();

let changed = $state<boolean>( false );

function tagsChanged(updated: string[]): void {
    changed = true;
}
</script>

<aside class="left-sidebar">
    
    <div class="dialog-section">
        <TagEditor tags={[]} disabled={false} onChanged={tagsChanged} title={'Include tags'}/>
        
        <TagEditor tags={[]} disabled={false} onChanged={tagsChanged} title={'Exclude tags'}/>
    </div>
    
    <div class="dialog-section spaced-horizontally">
        <button class="simple-button">
            <i class="fa-solid fa-filter"></i>
            <span class="button-text">Show all</span>
        </button>
        
        <button class="simple-button"
            disabled={!changed}>
            <i class="fa-solid fa-filter"></i>
            <span class="button-text">Filter</span>
        </button>
    </div>
</aside>


<style>

</style>