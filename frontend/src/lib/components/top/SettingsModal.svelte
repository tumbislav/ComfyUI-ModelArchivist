<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: SettingsModal.svelte
 ! purpose: Tabbed application and repository settings editor
 ! -------------------------------------------------->

<script lang="ts">
import generalIcon from '$icons/nav/settings16.png';
import modelIcon from '$icons/nav/model16.png';
import workflowIcon from '$icons/nav/workflow16.png';
import userTypeIcon16 from '$icons/nav/user-defined16.png';
import collectionIcon from '$icons/nav/collection16.png';
import { getRepositorySettings, saveModelSettings, saveWorkflowSettings,
    type ModelTypeSetting, type RepositoryLocation,
    type RepositorySettings } from '$lib/settings';
import { createUserType, deleteUserType, getUserType, updateUserType, userTypeState } from '$lib/user-types.svelte';
import { type UserDefinedType } from '$lib/objects';
import { onMount } from 'svelte';

export type SettingsTab = 'general' | 'models' | 'workflows' | 'user-types' | 'collections';
let { onClose, initialTab = 'general' }: { onClose: () => void; initialTab?: SettingsTab } = $props();

const tabs: {id: SettingsTab; label: string; icon: string}[] = [
    {id: 'general', label: 'General', icon: generalIcon},
    {id: 'models', label: 'Models', icon: modelIcon},
    {id: 'workflows', label: 'Workflows', icon: workflowIcon},
    {id: 'user-types', label: 'User-defined types', icon: userTypeIcon16},
    {id: 'collections', label: 'Collections', icon: collectionIcon}
];
const iconNames = ['any', 'dataset', 'file', 'folder-images', 'folder-sound', 'folder-speech',
    'folder-video', 'folder-wildcards', 'folder', 'image', 'sound', 'speech', 'stencil',
    'training-set', 'video', 'wildcard'];
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));
const same = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right);

let activeTab = $state<SettingsTab>('general');
let settings = $state<RepositorySettings | null>(null);
let savedModels = $state<ModelTypeSetting[]>([]);
let savedWorkflows = $state<RepositoryLocation[]>([]);
let userTypes = $state<UserDefinedType[]>([]);
let savedUserTypes = $state<UserDefinedType[]>([]);
let deletedUserTypeIds = $state<string[]>([]);
let loading = $state(true);
let saving = $state(false);
let error = $state<string | null>(null);
let guardTarget = $state<SettingsTab | 'close' | null>(null);
let modelsDirty = $derived(settings !== null && !same(settings.model_types, savedModels));
let workflowsDirty = $derived(settings !== null && !same(settings.workflow_locations, savedWorkflows));
let userTypesDirty = $derived(deletedUserTypeIds.length > 0 || !same(userTypes, savedUserTypes));
let activeDirty = $derived(activeTab === 'models' ? modelsDirty : activeTab === 'workflows'
    ? workflowsDirty : activeTab === 'user-types' ? userTypesDirty : false);

onMount(async () => {
    activeTab = initialTab;
    const repositoryResult = await getRepositorySettings();
    if (!repositoryResult.ok) {
        error = repositoryResult.message ?? 'Cannot load repository settings'; loading = false; return;
    }
    settings = clone(repositoryResult.data);
    savedModels = clone(repositoryResult.data.model_types);
    savedWorkflows = clone(repositoryResult.data.workflow_locations);
    await userTypeState.load();
    const details = await Promise.all(userTypeState.types.map(type => getUserType(type.id)));
    userTypes = details.map((result, index) => result.ok ? result.data : userTypeState.types[index]);
    savedUserTypes = clone(userTypes);
    loading = false;
});

function requestTab(tab: SettingsTab): void {
    if (tab === activeTab) return;
    if (activeDirty) guardTarget = tab; else activeTab = tab;
}
function requestClose(): void {
    if (activeDirty) { guardTarget = 'close'; return; }
    const dirtyTab: SettingsTab | null = modelsDirty ? 'models' : workflowsDirty ? 'workflows'
        : userTypesDirty ? 'user-types' : null;
    if (dirtyTab !== null) { activeTab = dirtyTab; guardTarget = 'close'; }
    else onClose();
}
function continueGuard(): void {
    const target = guardTarget; guardTarget = null;
    if (target === 'close') onClose(); else if (target !== null) activeTab = target;
}
function undo(): void {
    if (!settings) return;
    if (activeTab === 'models') settings.model_types = clone(savedModels);
    if (activeTab === 'workflows') settings.workflow_locations = clone(savedWorkflows);
    if (activeTab === 'user-types') { userTypes = clone(savedUserTypes); deletedUserTypeIds = []; }
    error = null;
}
async function save(): Promise<boolean> {
    if (!settings || !activeDirty) return true;
    saving = true; error = null;
    if (activeTab === 'models') {
        const result = await saveModelSettings(settings.model_types); saving = false;
        if (!result.ok) { error = result.message ?? 'Cannot save model settings'; return false; }
        settings = clone(result.data); savedModels = clone(result.data.model_types);
        savedWorkflows = clone(result.data.workflow_locations); return true;
    }
    if (activeTab === 'workflows') {
        const result = await saveWorkflowSettings(settings.workflow_locations); saving = false;
        if (!result.ok) { error = result.message ?? 'Cannot save workflow settings'; return false; }
        settings = clone(result.data); savedModels = clone(result.data.model_types);
        savedWorkflows = clone(result.data.workflow_locations); return true;
    }
    for (const id of deletedUserTypeIds) {
        const result = await deleteUserType(id);
        if (!result.ok) { saving = false; error = result.message ?? 'Cannot delete user-defined type'; return false; }
    }
    for (const type of userTypes) {
        const old = savedUserTypes.find(item => item.id === type.id);
        if (old && same(old, type)) continue;
        const result = old ? await updateUserType(type) : await createUserType(type);
        if (!result.ok) { saving = false; error = result.message ?? `Cannot save ${type.name}`; return false; }
    }
    await userTypeState.load();
    const details = await Promise.all(userTypeState.types.map(type => getUserType(type.id)));
    userTypes = details.map((result, index) => result.ok ? result.data : userTypeState.types[index]);
    savedUserTypes = clone(userTypes); deletedUserTypeIds = []; saving = false; return true;
}
async function saveAndContinue(): Promise<void> { if (await save()) continueGuard(); }
function discardAndContinue(): void { undo(); continueGuard(); }
function addModelType(): void {
    settings?.model_types.push({name: '', display_name: '', extensions: [],
        locations: [{working_dir: '', archive_dir: ''}]});
}
function addUserType(): void {
    userTypes.push({id: '', name: '', short_name: '', object_class: 'folder', extensions: [],
        icon: 'folder', purpose: '', size_limit: 10 * 1024 * 1024, small: false,
        object_count: 0, working_dir: '', archive_dir: ''});
}
function removeUserType(type: UserDefinedType, index: number): void {
    if (type.id && !confirm(`Delete the user-defined type “${type.name}”? Files will not be deleted.`)) return;
    if (type.id && !confirm(`This will remove ${type.object_count} object(s) from the repository and all collections. Are you really sure?`)) return;
    if (type.id) deletedUserTypeIds.push(type.id);
    userTypes.splice(index, 1);
}
</script>

<div class="modal-backdrop" role="presentation">
    <div class="modal-dialog settings-dialog" role="dialog" aria-modal="true" aria-label="Settings">
        <header class="spaced-horizontally"><h2>Settings</h2>
            <button type="button" class="round" aria-label="Close settings" onclick={requestClose}>×</button></header>
        <div class="settings-layout">
            <nav class="settings-tabs" aria-label="Settings sections">
                {#each tabs as tab}
                    <button type="button" class:active={activeTab === tab.id} onclick={() => requestTab(tab.id)}>
                        <img class="action-icon-small" src={tab.icon} alt="" />{tab.label}
                        {#if (tab.id === 'models' && modelsDirty) || (tab.id === 'workflows' && workflowsDirty) ||
                              (tab.id === 'user-types' && userTypesDirty)}<span aria-label="Unsaved">•</span>{/if}
                    </button>
                {/each}
            </nav>
            <section class="settings-content">
                {#if loading}<p>Loading settings…</p>
                {:else if activeTab === 'general'}<h3>General</h3><p>No general settings are currently available.</p>
                {:else if activeTab === 'models' && settings}
                    <div class="settings-heading"><h3>Models</h3>{#if settings.mode === 'standalone'}
                        <button class="button-with-text" onclick={addModelType}>Add type</button>{/if}</div>
                    <p class="class-annotation">{settings.mode === 'comfyui'
                        ? 'Working folders and extensions are supplied by ComfyUI.'
                        : 'Each model type has one working/archive location pair.'}</p>
                    {#each settings.model_types as type, typeIndex}
                        <details open><summary>{type.display_name || type.name || 'New model type'}</summary>
                            <div class="settings-form">
                                <label>Type key<input class="text-input" bind:value={type.name} disabled={settings.mode === 'comfyui'} /></label>
                                <label>Display name<input class="text-input" bind:value={type.display_name} /></label>
                                <label>Extensions<input class="text-input" value={type.extensions.join(', ')} disabled={settings.mode === 'comfyui'}
                                    oninput={event => type.extensions = event.currentTarget.value.split(',').map(x => x.trim()).filter(Boolean)} /></label>
                                {#each type.locations as location}
                                    <label>Working folder<input class="text-input" bind:value={location.working_dir} disabled={settings.mode === 'comfyui'} /></label>
                                    <label>Archive folder<input class="text-input" bind:value={location.archive_dir} /></label>
                                {/each}
                                {#if settings.mode === 'standalone'}<button class="button-with-text danger"
                                    onclick={() => settings?.model_types.splice(typeIndex, 1)}>Remove type</button>{/if}
                            </div>
                        </details>
                    {/each}
                {:else if activeTab === 'workflows' && settings}
                    <div class="settings-heading"><h3>Workflows</h3>
                        {#if settings.mode === 'standalone' && settings.workflow_locations.length === 0}
                            <button class="button-with-text" onclick={() => settings?.workflow_locations.push({working_dir: '', archive_dir: ''})}>Add location</button>
                        {/if}
                    </div>
                    {#each settings.workflow_locations as location}
                        <div class="settings-form raised-section">
                            <label>Working folder<input class="text-input" bind:value={location.working_dir} disabled={settings.mode === 'comfyui'} /></label>
                            <label>Archive folder<input class="text-input" bind:value={location.archive_dir} /></label>
                        </div>
                    {:else}<p>No workflow location is configured.</p>{/each}
                {:else if activeTab === 'user-types'}
                    <div class="settings-heading"><h3>User-defined types</h3>
                        <button class="button-with-text" onclick={addUserType}>Add type</button></div>
                    {#each userTypes as type, typeIndex}
                        <details><summary>{type.name || 'New user-defined type'}</summary>
                            <div class="settings-form">
                                <label>Name<input class="text-input" bind:value={type.name} /></label>
                                <label>Short name<input class="text-input" maxlength="8" bind:value={type.short_name} /></label>
                                <label>Icon<select class="text-input" bind:value={type.icon}>{#each iconNames as icon}<option value={icon}>{icon}</option>{/each}</select></label>
                                <label>Purpose<textarea class="text-input" bind:value={type.purpose}></textarea></label>
                                <label>Content<select class="text-input" bind:value={type.object_class} disabled={type.object_count > 0}>
                                    <option value="file">Single file</option><option value="folder">Directory tree</option></select></label>
                                {#if type.object_class === 'file'}<label>Extensions<input class="text-input" value={type.extensions.join(', ')}
                                    oninput={event => type.extensions = event.currentTarget.value.split(',').map(x => x.trim()).filter(Boolean)} /></label>{/if}
                                <label>Working folder<input class="text-input" bind:value={type.working_dir} /></label>
                                <label>Archive folder<input class="text-input" bind:value={type.archive_dir} /></label>
                                <label>Size limit (bytes)<input class="text-input" type="number" min="1" bind:value={type.size_limit} /></label>
                                <label class="checkbox-label"><input type="checkbox" bind:checked={type.small} /> Small-object type</label>
                                <button class="button-with-text danger" onclick={() => removeUserType(type, typeIndex)}>Delete type</button>
                            </div>
                        </details>
                    {/each}
                {:else if activeTab === 'collections'}<h3>Collections</h3><p>Collection settings will be added later.</p>{/if}
                {#if error}<p class="error-message">{error}</p>{/if}
                {#if activeTab === 'models' || activeTab === 'workflows' || activeTab === 'user-types'}
                    <footer class="settings-actions"><button class="button-with-text" disabled={!activeDirty || saving} onclick={undo}>Undo</button>
                        <button class="button-with-text" disabled={!activeDirty || saving} onclick={save}>{saving ? 'Saving…' : 'Save'}</button></footer>
                {/if}
            </section>
        </div>
    </div>
    {#if guardTarget !== null}
        <div class="modal-backdrop nested-settings-guard" role="presentation">
            <div class="modal-dialog settings-guard" role="alertdialog" aria-modal="true" aria-label="Unsaved settings">
                <h3>Unsaved changes</h3><p>Save changes to this tab before continuing?</p>
                <div class="settings-actions"><button class="button-with-text" onclick={() => guardTarget = null}>Cancel</button>
                    <button class="button-with-text" onclick={discardAndContinue}>Discard</button>
                    <button class="button-with-text" disabled={saving} onclick={saveAndContinue}>Save</button></div>
            </div>
        </div>
    {/if}
</div>
