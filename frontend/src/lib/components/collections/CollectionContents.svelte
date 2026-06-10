<script lang=ts>
    import CollectionFilter from '$components/collections/CollectionFilter.svelte'
    import CollectionActions from '$components/collections/CollectionActions.svelte'
    import CollectionTable from '$components/collections/CollectionTable.svelte'
    import CollectionDetails from '$components/collections/CollectionDetails.svelte'

    let { collections } = $state([]);
    let { error } = $state(false);
    let { loading } = $state(false);
</script>


<div class="three-panel">
    <CollectionFilter loading={ false }/>
    <div class="content-with-actions">
        <CollectionActions/>
        <CollectionTable collections={ collections } error={ error } loading={ loading }/>
    </div>
    <CollectionDetails/>
</div>


<style>

</style>