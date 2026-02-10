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

<button on:click={refresh} disabled={loading}>
    {loading ? "Loading..." : "Refresh"}
</button>

<button on:click={rescan} disabled={loading}>
    {loading ? "Loading..." : "Re-scan"}
</button>