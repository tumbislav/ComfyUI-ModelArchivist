<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: RemapTags.svelte
 ! purpose: Review tag usage and remap tags across the repository
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

    import { onMount } from 'svelte';
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
    import { unsavedChangesBox } from '$lib/unsaved-changes.svelte';

    let { onClose, onRemapped }: {
        onClose: () => void;
        onRemapped: () => void;
    } = $props();

    const tagsContext = getTagsContext();
    let rows = $state<TagUsage[]>([]); const entries = new SvelteMap<string, string>(); let loading = $state(true); let busy = $state(false); let error = $state<string | null>(null);
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
                throw new Error(result.message ?? locale.t('ui.remap_tags.cannot_load_tags'));
            }

            rows = result.data;
        } catch (cause) {
            error = cause instanceof Error ? cause.message : locale.t('ui.remap_tags.cannot_load_tags');
        } finally {
            loading = false;
        }
    }

    async function requestClose(): Promise<void> {
        if (busy) return;

        if (dirty) {
            const result = await unsavedChangesBox({
                message: locale.t('ui.remap_tags.save_the_tag_mappings_before_continuing')
            });

            if (result === 'discard') {
                onClose();
            } else if (result === 'save') {
                await apply(true);
            }
        } else {
            onClose();
        }
    }

    async function apply(closeAfter: boolean): Promise<boolean> {
        busy = true;
        error = null;
        outcome = '';

        try {
            const mappings = Object.fromEntries([...entries].filter(([, value]) => value !== ''));
            const submitted = await remapTags(mappings);

            if (!submitted.ok) {
                throw new Error(submitted.message ?? locale.t('ui.remap_tags.cannot_remap_tags'));
            }

            const completed = await statusMonitor.waitForOperation(submitted.data);

            if (!completed.ok) {
                throw new Error(completed.message ?? locale.t('ui.remap_tags.cannot_retrieve_remap_result'));
            }
            if (completed.data.state === 'failed' || !completed.data.result) {
                throw new Error(completed.data.error?.message ?? locale.t('ui.remap_tags.remapping_failed'));
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
            return !error;
        } catch (cause) {
            error = cause instanceof Error ? cause.message : locale.t('ui.remap_tags.cannot_remap_tags');
            return false;
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
        <h2 id="remap-tags-title">{locale.t('ui.remap_tags.remap_tags')}</h2>
        <button class="round" aria-label={locale.t('ui.remap_tags.close_tag_remapping')} disabled={busy} onclick={requestClose}>
            <img class="action-icon" alt="" src={closeIcon} />
        </button>
    </header>

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
                    <th>{locale.t('ui.remap_tags.tag')}</th>
                    <th><img class="indicator-icon action-icon" src={modelIcon} alt={locale.t('ui.remap_tags.models')}/></th>
                    <th><img class="indicator-icon action-icon" src={workflowIcon} alt={locale.t('ui.remap_tags.workflows')}/></th>
                    <th><img class="indicator-icon action-icon" src={udtIcon} alt={locale.t('ui.remap_tags.user_types')}/></th>
                    <th><img class="indicator-icon action-icon" src={collectionIcon} alt={locale.t('ui.remap_tags.collections')}/></th>
                    <th>{locale.t('ui.remap_tags.remap_to')}</th>
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
                            <input class="text-input full-width"
                                   aria-label={locale.t('messages.remap_tag_to', {tag: row.tag})}
                                   aria-invalid={invalid} disabled={busy || loading}
                                   value={target} oninput={event => entries.set(row.tag, event.currentTarget.value)} />
                            {#if invalid}
                                <span class="error-message">{locale.t('ui.remap_tags.invalid_tag_this_row_will_be_skipped')}</span>
                            {/if}
                        </td>
                    </tr>
                {:else}
                    <tr>
                        <td colspan="6">{locale.t(loading ? 'dynamic.loading_tags' : 'dynamic.no_tags_period')}</td>
                    </tr>
                {/each}
            </tbody>
        </table>
    </div>

    <div class="spaced-horizontally space-below">
        <button class="button-with-text"
                disabled={busy || loading || !dirty}
                onclick={() => apply(false)}>
            {locale.t('ui.remap_tags.remap')}
        </button>
        <button class="button-with-text"
                disabled={busy || loading || !dirty}
                onclick={() => apply(true)}>
            {locale.t('ui.remap_tags.remap_and_close')}
        </button>
        <button class="button-with-text"
                disabled={busy || !dirty}
                onclick={() => {
                    entries.clear();
                    outcome = '';
                }}>
            {locale.t('ui.remap_tags.reset')}
        </button>
    </div>
</dialog>
