<script lang="ts">
  import { onMount } from "svelte";
  import { getModels, type ModelRecord } from "$lib/api";

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

  onMount(refresh);
</script>

<button on:click={refresh} disabled={loading}>
    {loading ? "Loading..." : "Refresh"}
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
        <th>Status</th>
        <th>Archived</th>
      </tr>
    </thead>
    <tbody>
      {#each models as m}
        <tr>
          <td>{m.type}</td>
          <td>{m.name}</td>
          <td>{m.status}</td>
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
</style>