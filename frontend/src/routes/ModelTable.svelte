<script lang="ts">
  import { onMount } from "svelte";
  import { getModels, getModelsRescan, type ModelRecord } from "$lib/api";

  let models: ModelRecord[] = [];
  let error: string | null = null;
  let loading = true;

  async function refresh() {
    loading = true;
    error = null;
    try {
      models = await getModels();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  async function rescan() {
    loading = true;
    error = null;
    try {
      models = await getModelsRescan();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  onMount(refresh);
</script>

<div class="control-group">
    <button on:click={refresh} disabled={loading}>
        {loading ? "Loading..." : "Refresh"}
    </button>
</div>

<button on:click={rescan} disabled={loading}>
    {loading ? "Loading..." : "Re-scan"}
</button>

<main>
  <h1>Models</h1>
  {#if error}
    <p style="color: red">{error}</p>
  {/if}

  <table>
    <thead>
      <tr>
        <th>Type</th>
        <th>Name</th>
        <th>Active</th>
        <th>Archived</th>
      </tr>
    </thead>
    <tbody>
      {#each models as m}
        <tr>
          <td>{m.type}</td>
          <td>{m.name}</td>
          <td>{m.status == 'ACTIVE' ? 'yes' : 'no'}</td>
          <td>{m.archived ? 'yes': 'no'}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</main>

<style>
  main { font-family: system-ui, sans-serif; padding: 1rem; }
  table { margin-top: 1rem; border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ccc; padding: 0.5rem; text-align: left; }

/* Action button styling */
.control-group {
    position: relative;
}

.control-group button {
    min-width: 100px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    border-radius: var(--border-radius-xs);
    padding: 4px 10px;
    border: 1px solid var(--border-color);
    background: var(--card-bg);
    color: var(--text-color);
    font-size: 0.85em;
    transition: all 0.2s ease;
    cursor: pointer;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.control-group button:hover {
    border-color: var(--lora-accent);
    background: var(--bg-color);
    transform: translateY(-1px);
    box-shadow: 0 3px 5px rgba(0, 0, 0, 0.08);
}

.control-group button:active {
    transform: translateY(0);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.control-group button:disabled {
    cursor: not-allowed;
    opacity: 0.6;
    pointer-events: none;
}

</style>