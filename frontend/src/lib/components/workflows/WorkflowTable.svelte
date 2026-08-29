<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: WorkflowTable.svelte
 ! purpose: Workflow table and selection
 ! -------------------------------------------------->

<script lang="ts">
import { type WorkflowSummary } from '$lib/objects';
let { workflows, error, selected_id=$bindable(), selected_ids=$bindable() }: {
    workflows: WorkflowSummary[]; error: string | null; selected_id: string | null;
    selected_ids: Set<string>;
} = $props();
let allVisibleSelected = $derived(workflows.length > 0 &&
    workflows.every(workflow => selected_ids.has(workflow.id)));
function toggleSelected(id: string) {
    const next = new Set(selected_ids); next.has(id) ? next.delete(id) : next.add(id);
    selected_ids = next;
}
function toggleAllVisible() {
    const next = new Set(selected_ids);
    workflows.forEach(workflow => allVisibleSelected ? next.delete(workflow.id) : next.add(workflow.id));
    selected_ids = next;
}
</script>

{#if error}<div class="message-container error-message"><p>Error loading workflows: {error}</p></div>
{:else}
<table class="main-table workflow-table" data-workflow-table>
    <thead><tr class="table-head table-section">
        <th class="clear"><input type="checkbox" checked={allVisibleSelected}
            onclick={event => event.stopPropagation()} onchange={toggleAllVisible} /></th>
        <th>Name</th><th>Purpose</th><th>Working</th><th>Archive</th>
    </tr></thead>
    <tbody>{#each workflows as workflow (workflow.id)}
        <tr class="table-clickable" aria-selected={selected_id === workflow.id}
            onclick={() => selected_id = workflow.id}>
            <td class="clear"><input type="checkbox" checked={selected_ids.has(workflow.id)}
                onclick={event => event.stopPropagation()} onchange={() => toggleSelected(workflow.id)} /></td>
            <td>{workflow.internal_name}</td>
            <td class="workflow-purpose" title={workflow.purpose}>{workflow.purpose}</td>
            <td>{['working', 'synced'].includes(workflow.deployment) ? 'yes' : ''}</td>
            <td>{['archive', 'synced'].includes(workflow.deployment) ? 'yes' : ''}</td>
        </tr>
    {/each}</tbody>
</table>
{/if}
