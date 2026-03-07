<script lang=ts>
    let { models, error, loading } = $props();
</script>

<main class="table-container">
    <h1>Models and stuff</h1>
    <p>Found { models.length } models.</p>
    {#if error}
    <div class="message-container error-message">
        <p>{error}</p>
    </div>

    <!--
        <section>
        <article>

        <details>
        <summary>
    -->

    {:else}
    <table class="main-table">
        <!--
        <colgroup>
        <tfoot>
        -->
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
        {#each models as m, i (m.hash)}
        {#if i === 0 || m.type !== models[i - 1].type}
        <tr class="table-section">
            <td colspan=5>{m.type}</td>
        </tr>
        {/if}
        <tr>
            <td class="clear"></td>
            <td class="clear" id="{m.hash}"><input type=checkbox></td>
            <td>{m.name}</td>
            <td>{m.status ? 'yes' : 'no'}</td>
            <td>{m.archived ? 'yes': 'no'}</td>
        </tr>
        {/each}
        </tbody>
    </table>
    {/if}
</main>

<style>

</style>