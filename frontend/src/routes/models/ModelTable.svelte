<script lang=ts>
    import { type ModelSummary } from "$lib/objects";
    import { type ApiResult } from "$lib/api";

    let { models } : { models: ApiResult<ModelSummary> } = $props();
</script>

<main class="table-container">
    <h1>Models</h1>
    {#if !models.ok}
        <div class="message-container error-message">
            <p>Error loading models: {models.message}</p>
            <pre>{ JSON.stringify(models, null, 2) }</pre>
        </div>
    {:else}
        <p>{ models.data.length } models in library.</p>
        <table class="main-table" id="model-table">
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
            {#each models.data as m, i (m.id)}
                {#if i === 0 || m.type !== models.data[i - 1].type}
                    <tr class="table-section">
                        <td colspan=5>{m.type}</td>
                    </tr>
                {/if}
                <tr >
                    <td class="clear"></td>
                    <td class="clear" id="{m.id}"><input type=checkbox></td>
                    <td>{m.name}</td>
                    <td>{m.active ? 'yes' : 'no'}</td>
                    <td>{m.archived ? 'yes' : 'no'}</td>
                </tr>
            {/each}
            </tbody>
        </table>
    {/if}
</main>

<style>

</style>