<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: UserObjectDetails.svelte
 ! purpose: Sidebar editor for one user-defined object
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
import { locale } from '$lib/locale.svelte';

import TagEditor from '$components/controls/TagEditor.svelte';
import UserObjectFileSet from '$components/user-objects/UserObjectFileSet.svelte';
import UserObjectCollectionEditor from '$components/user-objects/UserObjectCollectionEditor.svelte';
import RelativePathEditor from '$components/controls/RelativePathEditor.svelte';
import closeIcon from '$icons/actions/close8.png';
import saveIcon from '$icons/actions/save16.png';
import moveUpIcon from '$icons/actions/move-up16.png';
import moveDownIcon from '$icons/actions/move-down16.png';
import syncIcon from '$icons/actions/move-up-down16.png';
import { shortDate } from '$lib/common';
import type { UserObject } from '$lib/objects';

let {
    item=$bindable(),
    changed,
    saving,
    operating,
    operationError,
    onSave,
    onClose,
    onSync,
    onMove,
    onRelocate,
    relativePaths,
    onCollectionsChanged
}: {
    item: UserObject;
    changed: boolean;
    saving: boolean;
    operating: boolean;
    operationError: string | null;
    onSave: () => Promise<boolean>;
    onClose: () => Promise<boolean>;
    onSync: () => Promise<void>;
    onMove: (destination: 'working' | 'archive') => Promise<void>;
    onRelocate: (destination: string) => Promise<void>;
    relativePaths: string[];
    onCollectionsChanged: () => Promise<void>;
} = $props();

function objectPath(root: string | undefined, relative: string): string {
    if (!root) return relative;
    const separator = root.includes('\\') ? '\\' : '/';
    return `${root.replace(/[\\/]$/, '')}${separator}${relative}`;
}
let workingPath = $derived(objectPath(item.type.working_dir, item.relative_path));
let archivePath = $derived(objectPath(item.type.archive_dir, item.relative_path));
const directoryOf = (path: string) => path.replace(/[\\/][^\\/]+$/, '').replace(path, '');
let destinationPath = $state(directoryOf(item.relative_path));
let destinationObjectId = $state(item.id);

$effect(() => {
    if (item.id !== destinationObjectId) {
        destinationObjectId = item.id;
        destinationPath = directoryOf(item.relative_path);
    }
});
</script>

<div class="space-below spaced-horizontally">
    <div></div>
    <button class="round" aria-label={locale.t('ui.user_object_details.close_object_details')} onclick={() => onClose()}>
        <img class="action-icon" alt="" src={closeIcon} /></button>
</div>
<div class="space-below spaced-horizontally">
    <p class="labeled"><span>{locale.t('ui.user_object_details.type')}</span>{item.type.name}</p>
    <p class="labeled"><span>{locale.t('ui.user_object_details.last_accessed')}</span>{shortDate(item.touched)}</p>
</div>
{#if operationError}<p class="error-message">{operationError}</p>{/if}
{#each item.errors as error}<p class="error-details">{error}</p>{/each}

<div class="space-below dialog-section">
    <label class="dialog-label">{locale.t('ui.user_object_details.name')}
        <input class="text-input full-width" disabled={item.read_only} bind:value={item.display_name} />
    </label>
    <p class="annotation-right">{item.id}</p>
    <label class="dialog-label">{locale.t('ui.user_object_details.purpose')}
        <textarea class="text-input full-width" disabled={item.read_only} bind:value={item.purpose}></textarea>
    </label>
    <TagEditor tags={[...item.tags]} title={locale.t('ui.user_object_details.tags')} editable={true} disabled={item.read_only}
        onChanged={(tags: string[]) => item.tags = [...tags]} />
    <div class="spaced-horizontally"><div></div>
        <button class="button-with-text" disabled={!changed || saving || item.read_only} onclick={onSave}>
            <img class="action-icon" alt={locale.t('ui.user_object_details.save')} src={saveIcon} /><span class="button-label">{locale.t('ui.user_object_details.save_2')}</span></button>
    </div>
</div>

<div class="space-below dialog-section">
    <RelativePathEditor bind:value={destinationPath} options={relativePaths}
        disabled={changed || operating || item.read_only}
        moveDisabled={destinationPath === directoryOf(item.relative_path)}
        onMove={() => onRelocate(destinationPath)} />

    <UserObjectFileSet set={item.working_set} path={workingPath} name="working set" />
    <UserObjectFileSet set={item.archive_set} path={archivePath} name="archive" />
    <div class="spaced-horizontally">
        <button class="button-with-text" disabled={operating || item.read_only ||
            !['archive', 'synced'].includes(item.deployment)} onclick={() => onMove('working')}>
            <img class="action-icon" alt={locale.t('ui.user_object_details.move_up')} src={moveUpIcon} />
            <span class="button-label">{locale.t('ui.user_object_details.to_working_set')}</span></button>
        <button class="button-with-text" disabled={operating || item.read_only || item.deployment === 'synced'}
            onclick={onSync}><img class="action-icon" alt={locale.t('ui.user_object_details.synchronize')} src={syncIcon} />
            <span class="button-label">{locale.t('ui.user_object_details.sync')}</span></button>
        <button class="button-with-text" disabled={operating || item.read_only ||
            !['working', 'synced'].includes(item.deployment)} onclick={() => onMove('archive')}>
            <img class="action-icon" alt={locale.t('ui.user_object_details.move_down')} src={moveDownIcon} />
            <span class="button-label">{locale.t('ui.user_object_details.to_archive')}</span></button>
    </div>
</div>
<div class="space-below dialog-section">
    <UserObjectCollectionEditor {item} onChanged={onCollectionsChanged} />
</div>
