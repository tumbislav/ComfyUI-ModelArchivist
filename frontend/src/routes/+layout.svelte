<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: +layout.svelte
 ! purpose: Svelte entry point
 ! -------------------------------------------------->

<script lang=ts>
    let { children } = $props();
    import '$styles/app.css';

/* Tags are a global context
 * ---------------------------------------------------------------------------*/

    import { setTagsContext, getTags } from '$lib/tags';

    let all_tags = $state<string[]>([]);
    let loading = $state(false);
    let error = $state<string | null>(null);
    
    async function refreshTags() {
        loading = true;
        const envelope = await getTags([]);
        if (envelope.ok) {
            all_tags = envelope.data;
            error = null;
        }
        else {
            error = envelope.message ?? null;
        }
        loading = false;
    }
    
    setTagsContext({
        get all_tags() {
            return all_tags;
        },
        get loading() {
            return loading;
        },
        get error() {
            return error;
        },
        get refresh() {
            return refreshTags;
        }
    });
    
    $effect(() => {
        refreshTags();
    });
</script>

<svelte:head>
    <link href="archivist-ico-32.png" rel="icon"/>
</svelte:head>

{@render children()}
