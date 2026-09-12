<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: SettingsModal.svelte
 ! purpose: Tabbed application and repository settings editor
 ! -------------------------------------------------->

<script lang="ts">
    import { locale } from '$lib/locale.svelte';

    let {
        onClose,
        initialTab = 'general'
    }: {
        onClose: () => void;
        initialTab?: SettingsTab;
    } = $props();

    import closeIcon from '$icons/actions/close8.png';

    import { startScan, type ScanScope } from '$lib/admin';
    import { statusMonitor } from '$lib/status.svelte';
    import { serverUnresponsive } from '$lib/api';
    import { modalDialog } from '$lib/modal-dialog';
    import { confirmBox } from '$lib/confirm.svelte';
    import { unsavedChangesBox } from '$lib/unsaved-changes.svelte';

    import GeneralSettings from '$components/settings/GeneralSettings.svelte';
    import ModelSettings from '$components/settings/ModelSettings.svelte';
    import SettingsLayout from '$components/settings/SettingsLayout.svelte';
    import UserTypeSettings from '$components/settings/UserTypeSettings.svelte';
    import WorkflowSettings from '$components/settings/WorkflowSettings.svelte';
    import {
        getModelMappingRoots,
        getRepositorySettings,
        previewModelMappings,
        saveModelSettings,
        saveModelType,
        saveWorkflowSettings,
        saveModelExtensions,
        type ModelTypeSetting,
        type RepositoryLocation,
        type RepositorySettings } from '$lib/settings';

    import {
        createUserType,
        deleteUserType,
        getUserType,
        updateUserType,
        userTypeState } from '$lib/user-types.svelte';

    import { type UserDefinedType } from '$lib/objects';
    import { onMount } from 'svelte';
    import { SvelteMap } from 'svelte/reactivity';
    import {
        rememberLastTab,
        saveRememberLastTab,
        scanAtStartup,
        saveScanAtStartup } from '$lib/preferences';

    export type SettingsTab = 'general' | 'models' | 'workflows' | 'user-types';
    const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));
    const same = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right); let activeTab = $state<SettingsTab>('general'); let settings = $state<RepositorySettings | null>(null); let savedModels = $state<ModelTypeSetting[]>([]); let savedExtensions = $state<string[]>([]); let savedWorkflows = $state<RepositoryLocation[]>([]); let userTypes = $state<UserDefinedType[]>([]); let savedUserTypes = $state<UserDefinedType[]>([]); let deletedUserTypeIds = $state<string[]>([]); let loading = $state(true); let startupScan = $state(true); let rememberTab = $state(false); let saving = $state(false); let error = $state<string | null>(null); let guardTarget = $state<SettingsTab | 'close' | null>(null); let modelMappingRoots = $state<string[]>([]); let mappingWorkingRoot = $state(''); let mappingArchiveRoot = $state(''); let mappingExtensions = $state('.safetensors, .ckpt, .pt, .pth, .bin, .gguf'); let operationActive = $derived(statusMonitor.operation?.state === 'pending' || statusMonitor.operation?.state === 'running'); let editingLocked = $derived(saving || operationActive || $serverUnresponsive); const modelOriginalNames = new SvelteMap<object, string>(); const expandedTypes = new SvelteMap<object, boolean>(); function preserveExpansion<T extends object>(previous: T[], next: T[], key: (type: T) => string): void {
        for (const type of next) {
            const old = previous.find(candidate => key(candidate) === key(type));

            if (old && expandedTypes.has(old)) {
                expandedTypes.set(type, expandedTypes.get(old)!);
            }
        }
    }

    function replaceSettings(next: RepositorySettings): void {
        const previous = settings?.model_types ?? [];
        settings = next;

        preserveExpansion(previous, settings.model_types, type => type.name);
        rememberModelNames();
    }

    function replaceUserTypes(next: UserDefinedType[]): void {
        const previous = userTypes;
        userTypes = next;

        preserveExpansion(previous, userTypes, type => type.id || type.name);
    }

    let modelsDirty = $derived(
        settings !== null &&
        (settings.model_types.some(modelDirty) ||
            savedModels.some(saved => !settings!.model_types.some(type => modelOriginalNames.get(type) === saved.name))));
    let workflowsDirty = $derived(
        settings !== null &&
        !same(settings.workflow_locations, savedWorkflows));
    let userTypesDirty = $derived(deletedUserTypeIds.length > 0 || userTypes.some(userDirty));
    let extensionsDirty = $derived(
        settings !== null &&
        !same([...settings.model_extensions].sort(), [...savedExtensions].sort()));
    let activeDirty = $derived(activeTab === 'models' ? modelsDirty : activeTab === 'workflows'
        ? workflowsDirty : activeTab === 'user-types' ? userTypesDirty : extensionsDirty);

    onMount(async () => {
        startupScan = scanAtStartup();
        rememberTab = rememberLastTab();
        activeTab = initialTab;
        const repositoryResult = await getRepositorySettings();

        if (!repositoryResult.ok) {
            error = repositoryResult.message ?? locale.t('ui.settings_modal.cannot_load_repository_settings');
            loading = false;
            return;
        }

        settings = clone(repositoryResult.data);
        savedExtensions = clone(settings.model_extensions);

        const workflowLocations = repositoryResult.data.workflow_locations.length > 0
            ? clone(repositoryResult.data.workflow_locations)
            : [{working_dir: '', archive_dir: ''}];
        settings.workflow_locations = clone(workflowLocations);
        savedWorkflows = clone(workflowLocations);

        savedModels = clone(repositoryResult.data.model_types);
        rememberModelNames();

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

    async function resolveGuard(target: SettingsTab | 'close'): Promise<void> {
        guardTarget = target;
        const result = await unsavedChangesBox({
            message: locale.t('ui.settings_modal.save_changes_to_this_tab_before_continuing'),
            saveDisabled: editingLocked
        });

        if (result === 'save' && !await save()) {
            guardTarget = null;
            return;
        }
        if (result === 'discard') {
            undo();
        }
        if (result !== 'cancel') {
            continueGuard();
        } else {
            guardTarget = null;
        }
    }

    function requestTab(tab: SettingsTab): void {
        if (saving || tab === activeTab) return;
        if (operationActive) {
            activeTab = tab;
            return;
        }
        if (activeDirty) void resolveGuard(tab); else activeTab = tab;
    }
    function requestClose(): void {
        if (saving) return;
        if (activeDirty) {
            void resolveGuard('close');
            return;
        }
        const dirtyTab: SettingsTab | null = modelsDirty ? 'models' : workflowsDirty ? 'workflows'
            : userTypesDirty ? 'user-types' : extensionsDirty ? 'general' : null;
        if (dirtyTab !== null) {
            activeTab = dirtyTab;
            void resolveGuard('close');
        }
        else onClose();
    }
    function continueGuard(): void {
        const target = guardTarget; guardTarget = null;
        if (target === 'close') onClose(); else if (target !== null) activeTab = target;
    }
    function undo(): void {
        if (!settings) return;
        if (activeTab === 'general') settings.model_extensions = clone(savedExtensions);
        if (activeTab === 'models') {
            const previous = settings.model_types;
            settings.model_types = clone(savedModels);
            preserveExpansion(previous, settings.model_types, type => type.name);
            rememberModelNames();
        }
        if (activeTab === 'workflows') settings.workflow_locations = clone(savedWorkflows);
        if (activeTab === 'user-types') {
            replaceUserTypes(clone(savedUserTypes));
            deletedUserTypeIds = [];
        }
        error = null;
    }
    function rememberModelNames(): void {
        for (const type of settings?.model_types ?? []) {
            if (!type._new) modelOriginalNames.set(type, type.name);
        }
    }

    function modelDirty(type: ModelTypeSetting): boolean {
        const name = modelOriginalNames.get(type);
        return name === undefined || !same(type, savedModels.find(item => item.name === name));
    }

    function userDirty(type: UserDefinedType): boolean {
        return !type.id || !same(type, savedUserTypes.find(item => item.id === type.id));
    }

    async function persistModels(target?: ModelTypeSetting): Promise<string[] | null> {
        if (!settings) return null;
        const changed = target ? [target] : settings.model_types.filter(modelDirty);
        const names = changed.map(type => type.name.trim());
        if (target && !modelDirty(target)) return names;
        if (!target && !modelsDirty) return names;

        const originalName = target ? modelOriginalNames.get(target) : undefined;
        const result = target ? await saveModelType(target, originalName)
            : await saveModelSettings(settings.model_types);
        if (!result.ok) {
            error = result.message ?? locale.t('ui.settings_modal.cannot_save_model_settings');
            return null;
        }

        if (target) {
            const saved = result.data.model_types.find(type => type.name === target.name.trim())!;
            Object.assign(target, clone(saved));
            delete target._new;
            modelOriginalNames.set(target, saved.name);
            savedModels = savedModels.filter(type => type.name !== originalName && type.name !== saved.name);
            savedModels.push(clone(saved));
        } else {
            const previous = settings.model_types;
            settings.model_types = clone(result.data.model_types);
            preserveExpansion(previous, settings.model_types, type => type.name);
            savedModels = clone(result.data.model_types);
            rememberModelNames();
        }
        settings.setup_complete = result.data.setup_complete;
        return names;
    }

    async function persistUsers(target?: UserDefinedType): Promise<string[] | null> {
        const changed = target ? [target] : userTypes.filter(userDirty);
        const ids: string[] = [];
        if (!target) {
            for (const id of [...deletedUserTypeIds]) {
                const result = await deleteUserType(id);
                if (!result.ok) {
                    error = result.message ?? locale.t('ui.settings_modal.cannot_delete_user_defined_type');
                    return null;
                }
                deletedUserTypeIds = deletedUserTypeIds.filter(item => item !== id);
                savedUserTypes = savedUserTypes.filter(item => item.id !== id);
            }
        }

        for (const type of changed) {
            if (userDirty(type)) {
                const result = type.id ? await updateUserType(type) : await createUserType(type);
                if (!result.ok) {
                    error = result.message ?? locale.t('messages.cannot_save_named', {name: type.name});
                    return null;
                }
                Object.assign(type, clone(result.data));
                savedUserTypes = savedUserTypes.filter(item => item.id !== type.id);
                savedUserTypes.push(clone(type));
            }
            ids.push(type.id);
        }
        await userTypeState.load();
        return ids;
    }

    async function runSave(tab: SettingsTab, scan = false,
                           model?: ModelTypeSetting, user?: UserDefinedType): Promise<boolean> {
        if (!settings || editingLocked) return false;
        saving = true;
        error = null;

        try {
            let ids: string[] | null = [];
            let scope: ScanScope = 'models';
            if (tab === 'general') {
                scope = 'all';
                if (extensionsDirty) {
                    const result = await saveModelExtensions(settings.model_extensions);
                    if (!result.ok) {
                        error = result.message ?? locale.t('ui.settings_modal.cannot_save_model_extensions');
                        return false;
                    }
                    settings.model_extensions = clone(result.data.model_extensions);
                    settings.available_model_extensions = clone(result.data.available_model_extensions);
                    savedExtensions = clone(result.data.model_extensions);
                }
            } else if (tab === 'models') {
                ids = await persistModels(model);
            } else if (tab === 'user-types') {
                scope = 'user_objects';
                ids = await persistUsers(user);
            } else if (tab === 'workflows') {
                scope = 'workflows';
                if (workflowsDirty) {
                    const result = await saveWorkflowSettings(settings.workflow_locations);
                    if (!result.ok) {
                        error = result.message ?? locale.t('ui.settings_modal.cannot_save_workflow_settings');
                        return false;
                    }
                    settings.workflow_locations = clone(result.data.workflow_locations);
                    savedWorkflows = clone(result.data.workflow_locations);
                    settings.setup_complete = result.data.setup_complete;
                }
            }
            if (ids === null) return false;

            if (scan && (scope === 'all' || scope === 'workflows' || ids.length > 0)) {
                const result = await startScan(false, scope,
                    scope === 'all' || scope === 'workflows' ? undefined : ids);
                if (!result.ok) {
                    error = result.message ?? locale.t('ui.settings_modal.settings_saved_but_the_scan_could_not_start');
                    return false;
                }
                statusMonitor.track(result.data);
            }
            return true;
        } catch (cause) {
            error = cause instanceof Error ? cause.message : locale.t('ui.settings_modal.cannot_save_settings');
            return false;
        } finally {
            saving = false;
        }
    }

    async function save(): Promise<boolean> {
        return runSave(activeTab);
    }
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
            error = result.message ?? locale.t('ui.settings_modal.cannot_discover_model_mappings');
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
    async function removeUserType(type: UserDefinedType, index: number): Promise<void> {
        if (type.id && !await confirmBox({
            message: locale.t('messages.delete_user_type', {name: type.name})
        })) return;
        if (type.id && !await confirmBox({
            message: locale.plural('messages.delete_user_type_objects', type.object_count)
        })) return;
        if (type.id) deletedUserTypeIds.push(type.id);
        userTypes.splice(index, 1);
    }
</script>

<dialog class="nav-dialog"
        use:modalDialog
        aria-label={locale.t('ui.settings_modal.settings')}
        oncancel={event => { event.preventDefault(); requestClose(); }}>
    <header class="dialog-header spaced-horizontally">
        <h2>{locale.t('ui.settings_modal.settings')}</h2>
        <button type="button"
                class="round"
                aria-label={locale.t('ui.settings_modal.close_settings')}
                onclick={requestClose}>
            <img class="action-icon" alt="" src={closeIcon} />
        </button>
    </header>

    <SettingsLayout
        {activeTab}
        dirty={{
            general: extensionsDirty,
            models: modelsDirty,
            workflows: workflowsDirty,
            'user-types': userTypesDirty
        }}
        {loading}
        disabled={editingLocked}
        {error}
        onTab={requestTab}>
        {#snippet children(tab)}
            {#if tab === 'general'}
                <GeneralSettings
                    bind:settings
                    bind:startupScan
                    bind:rememberTab
                    {extensionsDirty}
                    {editingLocked}
                    onError={message => error = message}
                    onSave={scan => runSave('general', scan)} />
            {:else if tab === 'models'}
                <ModelSettings
                    bind:settings
                    {modelMappingRoots}
                    bind:mappingWorkingRoot
                    bind:mappingArchiveRoot
                    bind:mappingExtensions
                    dirty={modelsDirty}
                    {saving}
                    {expandedTypes}
                    isDirty={modelDirty}
                    onAddType={addModelType}
                    onAddMappings={addModelMappings}
                    onUndo={undo}
                    onSave={save}
                    onSaveType={(type, scan) => runSave('models', scan, type)}
                    onRemoveType={index => settings?.model_types.splice(index, 1)}
                    onError={message => error = message} />
            {:else if tab === 'workflows'}
                <WorkflowSettings
                    bind:settings
                    dirty={workflowsDirty}
                    {saving}
                    onUndo={undo}
                    onSave={save}
                    onError={message => error = message} />
            {:else}
                <UserTypeSettings
                    bind:userTypes
                    dirty={userTypesDirty}
                    {saving}
                    {expandedTypes}
                    isDirty={userDirty}
                    onAddType={addUserType}
                    onRemoveType={(type, index) => void removeUserType(type, index)}
                    onUndo={undo}
                    onSave={save}
                    onSaveType={(type, scan) => runSave('user-types', scan, undefined, type)}
                    onError={message => error = message} />
            {/if}
        {/snippet}
    </SettingsLayout>
</dialog>
