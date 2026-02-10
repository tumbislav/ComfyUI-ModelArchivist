<script lang=ts>

    import ModelTable from '../ModelTable.svelte'

</script>


<div class="main-panel">
<ModelTable/>
</div>

<style>
    .main-panel {
        height: 100%;
        margin-left: 200px;
        width: calc(100vw - 200px)%;
        position: relative;
        overflow-x: hidden;
        overflow-y: scroll;
    }
</style>