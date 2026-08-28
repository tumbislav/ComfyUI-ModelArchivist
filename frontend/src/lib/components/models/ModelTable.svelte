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
    selected_ids=$bindable(),
} : {
    models: ModelSummary[],
    error: string | null,
    selected_id: string | null,
    selected_ids: Set<string>,
} = $props();

let allVisibleSelected = $derived(
    models.length > 0 && models.every((model) => selected_ids.has(model.id))
);

function toggleSelected(modelId: string) {
    const next = new Set(selected_ids);
    next.has(modelId) ? next.delete(modelId) : next.add(modelId);
    selected_ids = next;
}

function toggleAllVisible() {
    const next = new Set(selected_ids);
    if (allVisibleSelected) {
        models.forEach((model) => next.delete(model.id));
    } else {
        models.forEach((model) => next.add(model.id));
    }
    selected_ids = next;
}
</script>

{#if error}
    <div class="message-container error-message">
        <p>Error loading models: {error}</p>
        <pre>{ JSON.stringify(models, null, 2) }</pre>
    </div>
{:else}

<!--    <p class="subtitle">Showing { models.length } models.</p> -->
    <table class="main-table">
        <thead>
        <tr class="table-head table-section">
            <th class="clear" id="header">
                <input type="checkbox" class="selector"
                       checked={allVisibleSelected}
                       onclick={(event) => event.stopPropagation()}
                       onchange={toggleAllVisible}>
            </th>
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
                <td class="clear" id="{m.id}">
                    <input type="checkbox"
                           checked={selected_ids.has(m.id)}
                           onclick={(event) => event.stopPropagation()}
                           onchange={() => toggleSelected(m.id)}>
                </td>
                <td>{m.internal_name}</td>
                <td>{m.deployment}</td>
            </tr>
        {/each}
        </tbody>
    </table>
{/if}

<style>

</style>
