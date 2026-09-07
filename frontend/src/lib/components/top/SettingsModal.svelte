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
import addIcon from '$icons/actions/add16.png';
import cancelIcon from '$icons/actions/cancel16.png';
import removeIcon from '$icons/actions/remove16.png';
import resetIcon from '$icons/actions/reset16.png';
import saveIcon from '$icons/actions/save16.png';
import closeIcon from '$icons/actions/close8.png';
import PathInput from '$components/controls/PathInput.svelte';
import HelpButton from '$components/controls/HelpButton.svelte';
import IconPicker from '$components/controls/IconPicker.svelte';
import { getModelMappingRoots, getRepositorySettings, previewModelMappings,
    saveModelSettings, saveWorkflowSettings,
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
    {id: 'user-types', label: 'User types', icon: userTypeIcon16},
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
let modelMappingRoots = $state<string[]>([]);
let mappingWorkingRoot = $state('');
let mappingArchiveRoot = $state('');
let mappingExtensions = $state('.safetensors, .ckpt, .pt, .pth, .bin, .gguf');
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
    const workflowLocations = repositoryResult.data.workflow_locations.length > 0
        ? clone(repositoryResult.data.workflow_locations)
        : [{working_dir: '', archive_dir: ''}];
    settings.workflow_locations = clone(workflowLocations);
    savedModels = clone(repositoryResult.data.model_types);
    savedWorkflows = clone(workflowLocations);
    const rootsResult = await getModelMappingRoots();
    if (rootsResult.ok) {
        modelMappingRoots = rootsResult.data;
        mappingWorkingRoot = rootsResult.data[0] ?? '';
    }
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
    settings?.model_types.unshift({name: '', display_name: '', extensions: [],
        locations: [{working_dir: '', archive_dir: ''}], _new: true});
}
async function addModelMappings(): Promise<void> {
    if (!settings) return;
    error = null;
    const extensions = mappingExtensions.split(',').map(item => item.trim()).filter(Boolean);
    const result = await previewModelMappings(
        mappingWorkingRoot, mappingArchiveRoot, extensions);
    if (!result.ok) {
        error = result.message ?? 'Cannot discover model mappings';
        return;
    }
    const newTypes: ModelTypeSetting[] = [];
    for (const candidate of result.data) {
        const existing = settings.model_types.find(item => item.name === candidate.name);
        if (existing === undefined) {
            newTypes.push({...candidate, _new: true});
            continue;
        }
        const knownPaths = new Set(existing.locations.map(item => item.working_dir.toLowerCase()));
        existing.locations.push(...candidate.locations.filter(
            item => !knownPaths.has(item.working_dir.toLowerCase())));
    }
    settings.model_types.unshift(...newTypes);
}
function addUserType(): void {
    userTypes.unshift({id: '', name: '', short_name: '', object_class: 'folder', extensions: [],
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
        <header class="spaced-horizontally">
            <h2>Settings</h2>
            <button type="button" class="round" aria-label="Close settings" onclick={requestClose}>
                <img class="action-icon" alt="" src={closeIcon} />
            </button>
        </header>
        <div class="settings-layout">
            <nav class="settings-tabs" aria-label="Settings sections">
                {#each tabs as tab}
                    <button type="button" class:active={activeTab === tab.id} onclick={() => requestTab(tab.id)}>
                        <img class="action-icon-small" src={tab.icon} alt="" />
                        <span class="button-label">
                            {tab.label}
                            {#if (tab.id === 'models' && modelsDirty) ||
                                 (tab.id === 'workflows' && workflowsDirty) ||
                                 (tab.id === 'user-types' && userTypesDirty)}
                                <span aria-label="Unsaved">•</span>
                            {/if}
                        </span>
                    </button>
                {/each}
            </nav>
            <section class="settings-content"
                     class:structured-settings-content={activeTab === 'models' ||
                         activeTab === 'workflows' || activeTab === 'user-types'}>
                {#if loading}
                    <p>Loading settings…</p>
                {:else if activeTab === 'general'}
                    <h3>General</h3>
                    <p>No general settings are currently available.</p>
                {:else if activeTab === 'models' && settings}
                    <section class="dialog-section model-mapping-assistant">
                        <div class="spaced-horizontally">
                            <h4 class="tight-vertical">Map model directories</h4>
                            <HelpButton text={settings.mode === 'comfyui'
                                ? 'Working folders and extensions are supplied by ComfyUI.'
                                : 'Each model type has one working/archive location pair.'} />
                        </div>
                        <div class="settings-form model-settings-form">
                            <label class="dialog-label">
                                Working root
                                {#if settings.mode === 'comfyui'}
                                    <select class="text-input" bind:value={mappingWorkingRoot}>
                                        {#each modelMappingRoots as root}
                                            <option value={root}>{root}</option>
                                        {/each}
                                    </select>
                                {:else}
                                    <PathInput bind:value={mappingWorkingRoot}
                                               onError={message => error = message} />
                                {/if}
                            </label>
                            <label class="dialog-label">
                                Archive root
                                <PathInput bind:value={mappingArchiveRoot}
                                           onError={message => error = message} />
                            </label>
                            {#if settings.mode === 'standalone'}
                                <label class="dialog-label">
                                    Model extensions
                                    <input class="text-input" bind:value={mappingExtensions} />
                                </label>
                            {/if}
                        </div>
                        <div class="spaced-horizontally">
                            <div></div>
                            <div>
                                <button class="button-with-text"
                                        disabled={!mappingWorkingRoot || !mappingArchiveRoot}
                                        onclick={addModelMappings}>
                                    <img class="action-icon" alt="add" src={addIcon} />
                                    <span class="button-label">Add mappings</span>
                                </button>
                            </div>
                        </div>
                    </section>
                    <div class="spaced-horizontally model-settings-actions">
                        <div>
                            {#if settings.mode === 'standalone'}
                                <button class="button-with-text" onclick={addModelType}>
                                    <img class="action-icon" alt="add" src={addIcon} />
                                    <span class="button-label">Add type</span>
                                </button>
                            {/if}
                        </div>
                        <div class="settings-actions">
                            <button class="button-with-text" disabled={!activeDirty || saving}
                                    onclick={undo}>
                                <img class="action-icon" alt="undo" src={resetIcon} />
                                <span class="button-label">Undo</span>
                            </button>
                            <button class="button-with-text" disabled={!activeDirty || saving}
                                    onclick={save}>
                                <img class="action-icon" alt="save" src={saveIcon} />
                                <span class="button-label">{saving ? 'Saving…' : 'Save'}</span>
                            </button>
                        </div>
                    </div>
                    <div class="model-type-list">
                        {#each settings.model_types as type, typeIndex}
                            <details class:unsaved={type._new === true} open={type._new === true}>
                                <summary>{type.display_name || type.name || 'New model type'}</summary>
                                <div class="settings-form model-settings-form">
                                <label class="dialog-label">
                                    Type key
                                    <input class="text-input" bind:value={type.name}
                                           disabled={settings.mode === 'comfyui'} />
                                </label>
                                <label class="dialog-label">
                                    Display name
                                    <input class="text-input" bind:value={type.display_name} />
                                </label>
                                <label class="dialog-label">
                                    Extensions
                                    <input class="text-input" value={type.extensions.join(', ')}
                                           disabled={settings.mode === 'comfyui'}
                                           oninput={event => type.extensions = event.currentTarget.value
                                               .split(',').map(x => x.trim()).filter(Boolean)} />
                                </label>
                                {#each type.locations as location}
                                    <label class="dialog-label">
                                        Working folder
                                        <PathInput bind:value={location.working_dir}
                                                   disabled={settings.mode === 'comfyui'}
                                                   onError={message => error = message} />
                                    </label>
                                    <label class="dialog-label">
                                        Archive folder
                                        <PathInput bind:value={location.archive_dir}
                                                   onError={message => error = message} />
                                    </label>
                                {/each}
                                </div>
                                {#if settings.mode === 'standalone'}
                                    <div class="spaced-horizontally model-type-actions">
                                        <div></div>
                                        <button class="button-with-text danger"
                                                onclick={() => settings?.model_types.splice(typeIndex, 1)}>
                                            <img class="action-icon" alt="remove" src={removeIcon} />
                                            <span class="button-label">Remove type</span>
                                        </button>
                                    </div>
                                {/if}
                            </details>
                        {/each}
                    </div>
                {:else if activeTab === 'workflows' && settings}
                    <div class="spaced-horizontally settings-tab-actions">
                        <div></div>
                        <div class="settings-actions">
                            <button class="button-with-text" disabled={!activeDirty || saving}
                                    onclick={undo}>
                                <img class="action-icon" alt="undo" src={resetIcon} />
                                <span class="button-label">Undo</span>
                            </button>
                            <button class="button-with-text" disabled={!activeDirty || saving}
                                    onclick={save}>
                                <img class="action-icon" alt="save" src={saveIcon} />
                                <span class="button-label">{saving ? 'Saving…' : 'Save'}</span>
                            </button>
                        </div>
                    </div>
                    <div class="settings-item-list">
                        {#if settings.workflow_locations[0]}
                            {@const location = settings.workflow_locations[0]}
                            <div class="settings-form aligned-settings-form dialog-section">
                                <label class="dialog-label">
                                    Working folder
                                    <PathInput bind:value={location.working_dir}
                                               disabled={settings.mode === 'comfyui'}
                                               onError={message => error = message} />
                                </label>
                                <label class="dialog-label">
                                    Archive folder
                                    <PathInput bind:value={location.archive_dir}
                                               onError={message => error = message} />
                                </label>
                            </div>
                        {/if}
                    </div>
                {:else if activeTab === 'user-types'}
                    <div class="spaced-horizontally settings-tab-actions">
                        <div>
                            <button class="button-with-text" onclick={addUserType}>
                                <img class="action-icon" alt="add" src={addIcon} />
                                <span class="button-label">Add type</span>
                            </button>
                        </div>
                        <div class="settings-actions">
                            <button class="button-with-text" disabled={!activeDirty || saving}
                                    onclick={undo}>
                                <img class="action-icon" alt="undo" src={resetIcon} />
                                <span class="button-label">Undo</span>
                            </button>
                            <button class="button-with-text" disabled={!activeDirty || saving}
                                    onclick={save}>
                                <img class="action-icon" alt="save" src={saveIcon} />
                                <span class="button-label">{saving ? 'Saving…' : 'Save'}</span>
                            </button>
                        </div>
                    </div>
                    <div class="settings-item-list">
                    {#each userTypes as type, typeIndex}
                        <details class:unsaved={!type.id} open={!type.id}>
                            <summary>{type.name || 'New user-defined type'}</summary>
                            <div class="user-type-help">
                                <HelpButton text="" />
                            </div>
                            <div class="settings-form aligned-settings-form">
                                <label class="dialog-label">
                                    Name
                                    <input class="text-input" bind:value={type.name} />
                                </label>
                                <label class="dialog-label">
                                    Short name
                                    <input class="text-input" maxlength="8" bind:value={type.short_name} />
                                </label>
                                <label class="dialog-label">
                                    Icon
                                    <IconPicker bind:value={type.icon} options={iconNames} />
                                </label>
                                <label class="dialog-label">
                                    Purpose
                                    <textarea class="text-input" bind:value={type.purpose}></textarea>
                                </label>
                                <label class="dialog-label">
                                    Content
                                    <select class="text-input" bind:value={type.object_class}
                                            disabled={type.object_count > 0}>
                                        <option value="file">Single file</option>
                                        <option value="folder">Directory tree</option>
                                    </select>
                                </label>
                                {#if type.object_class === 'file'}
                                    <label class="dialog-label">
                                        Extensions
                                        <input class="text-input" value={type.extensions.join(', ')}
                                               oninput={event => type.extensions = event.currentTarget.value
                                                   .split(',').map(x => x.trim()).filter(Boolean)} />
                                    </label>
                                {/if}
                                <label class="dialog-label">
                                    Working folder
                                    <PathInput bind:value={type.working_dir}
                                               onError={message => error = message} />
                                </label>
                                <label class="dialog-label">
                                    Archive folder
                                    <PathInput bind:value={type.archive_dir}
                                               onError={message => error = message} />
                                </label>
                                <label class="dialog-label">
                                    Size limit (bytes)
                                    <input class="text-input" type="number" min="1"
                                           disabled={type.small}
                                           bind:value={type.size_limit} />
                                </label>
                                <label class="dialog-label checkbox-label">
                                    Small-object type
                                    <input type="checkbox" checked={type.small}
                                           onchange={(event) => {
                                               type.small = event.currentTarget.checked;
                                               if (type.small) type.size_limit = 1024 * 1024;
                                           }} />
                                </label>
                            </div>
                            <div class="spaced-horizontally settings-item-actions">
                                <div></div>
                                <button class="button-with-text danger"
                                        onclick={() => removeUserType(type, typeIndex)}>
                                    <img class="action-icon" alt="remove" src={removeIcon} />
                                    <span class="button-label">Delete type</span>
                                </button>
                            </div>
                        </details>
                    {/each}
                    </div>
                {:else if activeTab === 'collections'}
                    <h3>Collections</h3>
                    <p>Collection settings will be added later.</p>
                {/if}
                {#if error}
                    <p class="error-message">{error}</p>
                {/if}
            </section>
        </div>
    </div>
    {#if guardTarget !== null}
        <div class="modal-backdrop nested-settings-guard" role="presentation">
            <div class="modal-dialog settings-guard" role="alertdialog" aria-modal="true" aria-label="Unsaved settings">
                <h3>Unsaved changes</h3>
                <p>Save changes to this tab before continuing?</p>
                <div class="settings-actions">
                    <button class="button-with-text" onclick={() => guardTarget = null}>
                        <img class="action-icon" alt="cancel" src={cancelIcon} />
                        <span class="button-label">Cancel</span>
                    </button>
                    <button class="button-with-text" onclick={discardAndContinue}>
                        <img class="action-icon" alt="discard" src={resetIcon} />
                        <span class="button-label">Discard</span>
                    </button>
                    <button class="button-with-text" disabled={saving} onclick={saveAndContinue}>
                        <img class="action-icon" alt="save" src={saveIcon} />
                        <span class="button-label">Save</span>
                    </button>
                </div>
            </div>
        </div>
    {/if}
</div>
