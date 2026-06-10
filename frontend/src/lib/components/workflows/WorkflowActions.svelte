<script lang=ts>
    import cp_active_ico from '$lib/assets/icons/copy-to-active-16.png';
    import mv_active_ico from '$lib/assets/icons/move-to-active-16.png';
    import cp_archive_ico from '$lib/assets/icons/copy-to-archive-16.png';
    import mv_archive_ico from '$lib/assets/icons/move-to-archive-16.png';
    import to_collection_ico from '$lib/assets/icons/to-collection-16.png';
</script>

<div class="control-bar">
    <div class="actions-bar">
        <div class="actions-group">
            <span class="actions-label-dim">Active</span>
            <button class="archivist-button action-button">
                <img src={cp_active_ico} class="action-icon" alt="copy to active">
                <span class="actions-label">Copy</span>
            </button>
            <button class="archivist-button action-button">
                <img src={mv_active_ico} class="action-icon" alt="move to active">
                <span class="actions-label">Move</span>
            </button>
        </div>
        <div class="actions-group">
            <span class="actions-label-dim">Archive</span>
            <button class="archivist-button action-button">
                <img src={cp_archive_ico} class="action-icon" alt="copy to archive">
                <span class="actions-label">Copy</span>
            </button>
            <button class="archivist-button action-button">
                <img src={mv_archive_ico} class="action-icon" alt="move to archive">
                <span class="actions-label">Move</span>
            </button>
        </div>
        <div class="actions-group">
            <span class="actions-label-dim">Collection</span>
            <button class="archivist-button action-button">
                <img src={to_collection_ico} class="action-icon" alt="model to collection">
                <span class="actions-label">Add</span>
            </button>
        </div>
    </div>
</div>

<style>
</style>