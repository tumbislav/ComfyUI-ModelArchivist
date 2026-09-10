<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: RemapTags.svelte
 ! purpose: Review tag usage and remap tags across the repository
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import { onMount, tick } from 'svelte';
    import { SvelteMap } from 'svelte/reactivity';
    import closeIcon from '$icons/actions/close8.png';
    import modelIcon from '$icons/indicators/model16.png';
    import workflowIcon from '$icons/indicators/workflow16.png';
    import udtIcon from '$icons/indicators/udt16.png';
    import collectionIcon from '$icons/indicators/collection16.png';


    import { getTagsContext, getTagUsage, loadTagRules, normalizeTag, remapTags,
        type TagUsage, type TagRemapResult } from '$lib/tags';
    import { statusMonitor } from '$lib/status.svelte';
    import { modalDialog } from '$lib/modal-dialog';

    let { onClose, onRemapped }: {
        onClose: () => void;
        onRemapped: () => void;
    } = $props();

    const tagsContext = getTagsContext();
    let rows = $state<TagUsage[]>([]);
    const entries = new SvelteMap<string, string>();
    let loading = $state(true);
    let busy = $state(false);
    let confirmClose = $state(false);
    let closeGuard = $state<HTMLDivElement>();
    let error = $state<string | null>(null);
    let outcome = $state('');
    let dirty = $derived([...entries.values()].some(value => value !== ''));

    onMount(() => {
        void load();
    });

    async function load(): Promise<void> {
        loading = true;
        error = null;

        try {
            await loadTagRules();
            const result = await getTagUsage();

            if (!result.ok) {
                throw new Error(result.message ?? 'Cannot load tags');
            }

            rows = result.data;
        } catch (cause) {
            error = cause instanceof Error ? cause.message : 'Cannot load tags';
        } finally {
            loading = false;
        }
    }

    async function requestClose(): Promise<void> {
        if (busy) return;

        if (dirty) {
            confirmClose = true;
            await tick();
            closeGuard?.focus();
        } else {
            onClose();
        }
    }

    async function apply(closeAfter: boolean): Promise<void> {
        busy = true;
        error = null;
        outcome = '';

        try {
            const mappings = Object.fromEntries([...entries].filter(([, value]) => value !== ''));
            const submitted = await remapTags(mappings);

            if (!submitted.ok) {
                throw new Error(submitted.message ?? 'Cannot remap tags');
            }

            const completed = await statusMonitor.waitForOperation(submitted.data);

            if (!completed.ok) {
                throw new Error(completed.message ?? 'Cannot retrieve remap result');
            }
            if (completed.data.state === 'failed' || !completed.data.result) {
                throw new Error(completed.data.error?.message ?? 'Remapping failed');
            }

            const result = completed.data.result as unknown as TagRemapResult;
            for (const source of result.applied) {
                entries.delete(source);
            }
            for (const skipped of result.skipped) {
                if (skipped.code === 'unchanged' || skipped.code === 'blank_target') {
                    entries.delete(skipped.source);
                }
            }

            await load();
            onRemapped();
            await tagsContext.refresh();

            const problems = [...result.errors.map(issue => issue.message),
                ...result.skipped.filter(issue => !['unchanged', 'blank_target'].includes(issue.code))
                    .map(issue => issue.message)];

            error = [error, ...problems].filter(Boolean).join('\n') || null;
            outcome = `${result.applied.length} tag mappings applied.`;

            if (closeAfter && !error && ![...entries.values()].some(value => value !== '')) {
                onClose();
            }
        } catch (cause) {
            error = cause instanceof Error ? cause.message : 'Cannot remap tags';
        } finally {
            busy = false;
        }
    }
</script>

<dialog class="nav-dialog"
        use:modalDialog
        aria-labelledby="remap-tags-title"
        oncancel={event => { event.preventDefault(); requestClose(); }}>
    <header class="dialog-header spaced-horizontally">
        <h2 id="remap-tags-title">Remap tags</h2>
        <button class="round" aria-label="Close tag remapping" disabled={busy} onclick={requestClose}>
            <img class="action-icon" alt="" src={closeIcon} />
        </button>
    </header>

    {#if confirmClose}
        <div class="dialog-section" role="alertdialog" aria-label="Unsaved tag mappings"
             tabindex="-1" bind:this={closeGuard}>
            <p>Discard the unsaved tag mappings and close?</p>
            <div class="spaced-horizontally">
                <button class="button-with-text" onclick={() => confirmClose = false}>Keep editing</button>
                <button class="button-with-text" onclick={onClose}>Discard and close</button>
            </div>
        </div>
    {/if}

    {#if error}
        <p class="error-message remap-message" role="alert">{error}</p>
    {/if}
    {#if outcome}
        <p role="status">{outcome}</p>
    {/if}

    <div class="remap-tags-scroll space-below">
        <table class="main-table remap-tags-table">
            <thead>
                <tr class="table-head table-section">
                    <th>Tag</th>
                    <th><img class="indicator-icon action-icon" src={modelIcon} alt="Models"/></th>
                    <th><img class="indicator-icon action-icon" src={workflowIcon} alt="Workflows"/></th>
                    <th><img class="indicator-icon action-icon" src={udtIcon} alt="User types"/></th>
                    <th><img class="indicator-icon action-icon" src={collectionIcon} alt="Collections"/></th>
                    <th>Remap to</th>
                </tr>
            </thead>
            <tbody>
                {#each rows as row (row.tag)}
                    {@const target = entries.get(row.tag) ?? ''}
                    {@const invalid = target !== '' && normalizeTag(target) === null}
                    <tr>
                        <td>{row.tag}</td>
                        <td>{row.models || ''}</td>
                        <td>{row.workflows || ''}</td>
                        <td>{row.user_objects || ''}</td>
                        <td>{row.collections || ''}</td>
                        <td>
                            <input class="text-input full-width" aria-label={`Remap ${row.tag} to`}
                                   aria-invalid={invalid} disabled={busy || loading || confirmClose}
                                   value={target} oninput={event => entries.set(row.tag, event.currentTarget.value)} />
                            {#if invalid}
                                <span class="error-message">Invalid tag; this row will be skipped.</span>
                            {/if}
                        </td>
                    </tr>
                {:else}
                    <tr>
                        <td colspan="6">{loading ? 'Loading tags…' : 'No tags.'}</td>
                    </tr>
                {/each}
            </tbody>
        </table>
    </div>

    <div class="spaced-horizontally space-below">
        <button class="button-with-text"
                disabled={busy || loading || !dirty || confirmClose}
                onclick={() => apply(false)}>
            Remap
        </button>
        <button class="button-with-text"
                disabled={busy || loading || !dirty || confirmClose}
                onclick={() => apply(true)}>
            Remap and close
        </button>
        <button class="button-with-text"
                disabled={busy || !dirty || confirmClose}
                onclick={() => {
                    entries.clear();
                    outcome = '';
                }}>
            Reset
        </button>
    </div>
</dialog>
