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
    import { PrimaryObjectType } from '$lib/objects';

    let all_tags = $state<string[]>([]);
    let loading = $state(false);
    let error = $state<string | null>(null);
    
    async function refreshTags() {
        loading = true;
        const envelope = await getTags([PrimaryObjectType.MODEL,
                                        PrimaryObjectType.WORKFLOW,
                                        PrimaryObjectType.COLLECTION]);
        if (envelope.ok) {
            all_tags = envelope.data;
        }
        else {
            error = envelope.message ?? null;
        }
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
