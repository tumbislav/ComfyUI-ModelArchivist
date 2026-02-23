<script lang=ts>
    import CollectionFilter from './CollectionFilter.svelte'
    import CollectionActions from './CollectionActions.svelte'
    import CollectionTable from './CollectionTable.svelte'
    import CollectionDetails from './CollectionDetails.svelte'

    let { collections } = $state([]);
    let { error } = $state(false);
    let { loading } = $state(false);
</script>


<div class="three-panel">
    <CollectionFilter loading={ false } />
    <div class="content-with-actions">
        <CollectionActions />
        <CollectionTable collections={ collections } error={ error } loading={ loading } />
    </div>
    <CollectionDetails />
</div>


<style>

</style>