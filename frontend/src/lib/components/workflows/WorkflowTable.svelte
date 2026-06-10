<script lang=ts>
    let { workflows, error, loading } = $props();
</script>

<main class="table-container">
    <h1>Workflows</h1>
    <p>{ workflows.length } models in library.</p>

    {#if error}
    <div class="message-container error-message">
        <p>{error}</p>
    </div>

    {:else}
    <table class="main-table">
        <thead>
        <tr class="table-head table-section">
            <th>Type</th>
            <th class="clear" id="header"><input type=checkbox></th>
            <th>Name</th>
            <th>Active</th>
            <th>Archived</th>
        </tr>
        </thead>
        <tbody>
        {#each workflows as w, i (w.id)}
        <tr>
            <td class="clear"></td>
            <td class="clear" id="{w.id}"><input type=checkbox></td>
            <td>{w.name}</td>
            <td>{w.active ? 'yes' : 'no'}</td>
            <td>{w.archived ? 'yes': 'no'}</td>
        </tr>
        {/each}
        </tbody>
    </table>
    {/if}
</main>

<style>

</style>