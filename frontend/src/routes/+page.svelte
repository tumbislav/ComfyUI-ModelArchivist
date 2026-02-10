<script lang="ts">
    import Heading from './panels/Heading.svelte'
    import Sidebar from './panels/Sidebar.svelte'
    import MainPanel from './panels/MainPanel.svelte'
</script>

<Heading />

<div class="contents-overall">
    <Sidebar />
    <MainPanel />
</div>

<style>
.contents-overall {
    height: calc(100vh - 48px);
    margin-top: 48px;
    width: 100%;
    position: relative;
    overflow-x: hidden;
    overflow-y: scroll;
}
</style>