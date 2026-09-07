<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: UserObjectFileSet.svelte
 ! purpose: Display one working or archive file set for a user-defined object
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
import type { UserObjectSet } from '$lib/objects';
let { set, path, name }: {set: UserObjectSet | undefined; path: string; name: string} = $props();
let entries = $derived(set?.entries ?? []);
let root = $derived(entries.find(entry => entry.relative_path === '') ?? entries[0]);
</script>

<div class="dialog-segment space-below">
    <h2 class="tight-vertical">Files in {name}</h2>
    <p class="path-preview fine-print rule-under no-top-margin" title={path}>{path}</p>
    {#if root}
        <p class="labeled"><span>{root.entry_type === 'directory' ? 'Folder:' : 'File:'}</span>
            {root.relative_path || '.'}</p>
        {#if root.entry_type === 'directory'}
            <p class="annotation">{Math.max(0, entries.length - 1)} contained entries; {set?.size ?? 0} bytes</p>
        {:else}
            <p class="annotation">{set?.size ?? 0} bytes</p>
        {/if}
    {:else}
        <p class="annotation">No files in {name}.</p>
    {/if}
</div>
