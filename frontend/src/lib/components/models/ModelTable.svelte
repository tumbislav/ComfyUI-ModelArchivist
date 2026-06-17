<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ModelTable.svelte
 ! purpose: Central component for models with model table
 ! -------------------------------------------------->

<script lang=ts>
import { type ModelSummary } from "$lib/objects";

let {
    models,
    error,
    selected_id=$bindable(),
} : {
    models: ModelSummary[],
    error: string | null,
    selected_id: string | null,
} = $props();
</script>

<h1>Models</h1>

{#if error}
    <div class="message-container error-message">
        <p>Error loading models: {error}</p>
        <pre>{ JSON.stringify(models, null, 2) }</pre>
    </div>
{:else}

    <p class="subtitle">Showing { models.length } models.</p>
    <table class="main-table">
        <thead>
        <tr class="table-head table-section">
            <th class="clear" id="header"><input type=checkbox class="selector"></th>
            <th>Model</th>
            <th>Location</th>
        </tr>
        </thead>
        <tbody>
        {#each models as m, i (m.id)}
            {#if i === 0 || m.type !== models[i - 1].type}
                <tr class="table-section">
                    <td colspan=4>{m.type}</td>
                </tr>
            {/if}
            <tr class="table-clickable"
                aria-selected={selected_id === m.id}
                onclick={() => selected_id = m.id} >
                <td class="clear" id="{m.id}"><input type=checkbox class="selector"></td>
                <td>{m.internal_name}</td>
                <td>{m.deployment}</td>
            </tr>
        {/each}
        </tbody>
    </table>
{/if}

<style>

</style>