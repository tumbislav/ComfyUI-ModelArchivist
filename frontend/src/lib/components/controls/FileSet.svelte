<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: FileSet.svelte
 ! purpose: Details of working or archive files used by a model or a workflow
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

import { type ComponentSet } from "$lib/objects"

let {
    set,
    path,
    name
}: {
    set: ComponentSet | undefined,
    path: string | null,
    name: string
} = $props();

let unpacked = $derived((set?.components ?? []).reduce<Record<string, string[]>>(
    (a, c) => { (a[c.component_type] ??= []).push(c.file_name); return a; }, {}
));

</script>

<div class="dialog-segment space-below">
    <h2 class="tight-vertical">Files in {name}</h2>
    {#if path}
        <p class="path-preview fine-print rule-under no-top-margin" title={path}>{path}</p>
    {/if}
    {#if unpacked.model}
        <p class="labeled"><span>{locale.t('ui.file_set.model')}</span>{unpacked.model[0]}</p>
    {/if}
    {#if unpacked.workflow}
        <p class="labeled"><span>{locale.t('ui.file_set.workflow')}</span>{unpacked.workflow[0]}</p>
    {/if}
    {#if unpacked.metadata}
        <p class="labeled"><span>{locale.t('ui.file_set.metadata')}</span>{unpacked.metadata[0]}</p>
    {/if}
    {#if unpacked.extra && unpacked.extra.length}
        <p class="labeled"><span>{locale.t('ui.file_set.others')}</span>{unpacked.extra.join(', ')}</p>
    {/if}
    {#if unpacked.example && unpacked.example.length}
        <p class="path-preview fine-print rule-under" title={set?.examples_dir}>{set?.examples_dir}</p>
        <p class="labeled"><span>{locale.t('ui.file_set.samples')}</span>{unpacked.example.join(', ')}</p>
    {/if}
</div>

<style>
</style>
