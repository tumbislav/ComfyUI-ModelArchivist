<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: FileSet.svelte
 ! purpose: Details of working or archive files used by a model or a workflow
 ! -------------------------------------------------->

<script lang="ts">
import { type ComponentSet } from "$lib/objects"
import { joinPath } from "$lib/common";
let { set, relative_path, name } = $props();

let primary_dir = $derived(joinPath(set.primary_dir, relative_path));
let unpacked = $derived(set.components.reduce<Record<string, string[]>>(
    (a, c) => { (a[c.component_type] ??= []).push(c.file_name); return a; }, {}
));

</script>

<div class="dialog-section raised-section">
    <p class="section-label">Files in {name}</p>
    <p class="path-preview" title={set.primary_dir}>{set.primary_dir}</p>
    {#if unpacked.model}
        <p class="labeled"><span>Model:</span>{unpacked.model[0]}</p>
    {/if}
    {#if unpacked.workflow}
        <p class="labeled"><span>Workflow:</span>{unpacked.workflow[0]}</p>
    {/if}
    {#if unpacked.metadata}
        <p class="labeled"><span>Metadata:</span>{unpacked.metadata[0]}</p>
    {/if}
    {#if unpacked.extra && unpacked.extra.length}
        <p class="labeled"><span>Others:</span>{unpacked.extra.join(', ')}</p>
    {/if}
    {#if unpacked.example && unpacked.example.length}
        <p class="path-preview" title={set.examples_dir}>{set.examples_dir}</p>
        <p class="labeled"><span>Samples:</span>{unpacked.example.join(', ')}</p>
    {/if}
</div>

<style>
</style>