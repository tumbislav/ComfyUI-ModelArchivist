<script lang=ts>
    import { type ModelRecord } from "$lib/api";
    let {
            models,
            selectedId,
            onSelect,
            error,
            loading
        }: {
            models: ModelRecord[];
            selectedId: string | null;
            onSelect: (model: ModelRecord) => void;
            error: string | null;
            loading: string | null;
        }= $props();
</script>

<main class="table-container">
    <h1>Models</h1>
    <p>{ models.length } models in library.</p>
    {#if error}
        <div class="message-container error-message">
            <p>{error}</p>
        </div>
    {:else}
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
            {#each models as m, i (m.id)}
                {#if i === 0 || m.type !== models[i - 1].type}
                    <tr class="table-section">
                        <td colspan=5>{m.type}</td>
                    </tr>
                {/if}
                <tr class:selected = {object.id === selectedId}
                    onClick = {() => onSelect(m)} >
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