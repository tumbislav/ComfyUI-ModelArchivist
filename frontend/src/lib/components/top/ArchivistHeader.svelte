<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ArchivistHeader.svelte
 ! purpose: Top navigation
 ! -------------------------------------------------->

<script lang=ts>
import modelIcon from '$icons/nav/model24.png';
import workflowIcon from '$icons/nav/workflow24.png';
import userDefinedIcon from '$icons/nav/user-defined24.png';
import collectionIcon from '$icons/nav/collection24.png';
import tagIcon from '$icons/nav/tag24.png';
import settingsIcon from '$icons/nav/settings24.png';
import lightDarkModeIcon from '$icons/nav/light-dark-mode24.png';
import AboutModal from '$components/top/AboutModal.svelte';
import downIcon from '$icons/actions/down16.png';
import refreshIcon from '$icons/actions/refresh24.png';
import RepositorySummary from '$components/top/RepositorySummary.svelte';
import SettingsModal, { type SettingsTab } from '$components/top/SettingsModal.svelte';
import RemapTags from '$components/top/RemapTags.svelte';

import { onMount } from 'svelte';
import { serverUnresponsive } from '$lib/api';
import { savedTheme, saveTheme } from '$lib/preferences';
import { statusMonitor } from '$lib/status.svelte';
import { userTypeIcon, userTypeState } from '$lib/user-types.svelte';

import { startScan, type ActiveTab } from '$lib/admin';
let {
    current_tab = $bindable(),
    navigationLocked = false,
    serverReady,
    remapBlocked = false,
    onTagsRemapped
}: {
    current_tab: ActiveTab;
    navigationLocked: boolean;
    serverReady: boolean;
    remapBlocked?: boolean;
    onTagsRemapped: () => void;
} = $props();

let theme = $state<'light' | 'dark'>('light');
const logoImages = Object.values(import.meta.glob<string>(
    '/src/lib/assets/images/logo/Library-*.png',
    { eager: true, query: '?url', import: 'default' }
));
let logoImage = $state(logoImages[0]);
let aboutOpen = $state(false);

function selectLogo(): void {
    const candidates = logoImages.filter(image => image !== logoImage);
    if (candidates.length > 0) {
        logoImage = candidates[Math.floor(Math.random() * candidates.length)];
    }
}

function closeAbout(): void {
    aboutOpen = false;
    selectLogo();
}

let themeLoaded = $state(false);
let typeMenuOpen = $state(false);
let settingsOpen = $state(false);
let remapOpen = $state(false);
let repositoryOpen = $state(false);
let scanSubmitting = $state(false);
let scanBusy = $derived(scanSubmitting ||
    statusMonitor.operation?.state === 'pending' ||
    statusMonitor.operation?.state === 'running');
let repositoryLabel = $derived.by(() => {
    if ($serverUnresponsive) return 'Server...';
    if (!serverReady) return 'Wait...';

    const operation = statusMonitor.operation;

    if (operation?.state === 'pending' || operation?.state === 'running') {
        if (operation.type === 'scan') return 'Scanning...';
        if (operation.type.endsWith('_sync')) return 'Syncing...';
        if (operation.type.endsWith('_move')) return 'Moving...';
    }

    return scanSubmitting ? 'Scanning...' : 'Repository';
});
let settingsInitialTab = $state<SettingsTab>('general');
let activeTypeIcon = $derived(userTypeState.active
    ? userTypeIcon(userTypeState.active.icon, 24) ?? userDefinedIcon
    : userDefinedIcon);
onMount(() => {
    logoImage = logoImages[Math.floor(Math.random() * logoImages.length)];
    theme = savedTheme();
    themeLoaded = true;

    const stopStatus = statusMonitor.start();
    const closeTypeMenu = (event: PointerEvent) => {
        if (!(event.target as HTMLElement).closest('.nav-user-type')) typeMenuOpen = false;
    };
    const closeTypeMenuOnEscape = (event: KeyboardEvent) => {
        if (event.key === 'Escape') typeMenuOpen = false;
    };
    document.addEventListener('pointerdown', closeTypeMenu);
    document.addEventListener('keydown', closeTypeMenuOnEscape);
    void userTypeState.load();
    return () => {
        stopStatus();
        document.removeEventListener('pointerdown', closeTypeMenu);
        document.removeEventListener('keydown', closeTypeMenuOnEscape);
    };
});

function openUserType(): void {
    if (userTypeState.active === null) openSettings('user-types');
    else current_tab = 'user';
}

async function scanRepository(): Promise<void> {
    if (scanBusy) return;
    scanSubmitting = true;
    try {
        const result = await startScan();
        if (result.ok) statusMonitor.track(result.data);
        else statusMonitor.error = result.message ?? 'Cannot start scan';
    } catch (error) {
        statusMonitor.error = error instanceof Error ? error.message : 'Cannot start scan';
    } finally {
        scanSubmitting = false;
    }
}

function openSettings(tab: SettingsTab): void {
    settingsInitialTab = tab;
    settingsOpen = true;
}

function selectUserType(type: typeof userTypeState.active): void {
    if (type === null) return;
    userTypeState.select(type);
    typeMenuOpen = false;
    current_tab = 'user';
}

$effect(() => {
    if (!themeLoaded) return;

    document.documentElement.dataset.theme = theme;
    saveTheme(theme);
});
</script>

<div class="header">
    <div class="app-title">
        <button class="title-image" type="button" aria-label="About Model Archivist"
                aria-haspopup="dialog" onclick={() => aboutOpen = true}>
            <img src={logoImage} alt="" />
        </button>
        <span class="app-title-text">Model Archivist</span>
    </div>
    
    <div class="nav-set" role="radiogroup" aria-label="Tab select">
        <button class="nav-button"
            role="radio"
            disabled={navigationLocked}
            aria-checked={current_tab === 'models'}
            onclick={() => current_tab = 'models'} >
            <img class="action-icon" alt="model" src={modelIcon} />
            <span class="large-button-label">Models</span>
        </button>
        
        <button class="nav-button"
            role="radio"
            disabled={navigationLocked}
            aria-checked={current_tab === 'workflows'}
            onclick={() => current_tab = 'workflows'}>
            <img class="action-icon" alt="workflows" src={workflowIcon} />
            <span class="large-button-label">Workflows</span>
        </button>

        <div class="nav-user-type" aria-checked={current_tab === 'user'}>
            <button class="nav-button user-type-main" role="radio"
                    disabled={navigationLocked}
                    aria-checked={current_tab === 'user'}
                    onclick={openUserType}>
                <img class="action-icon" alt="" src={activeTypeIcon} />
                <span class="large-button-label">{userTypeState.active?.short_name ?? 'User types'}</span>
            </button>
            <button class="user-type-trigger" type="button" disabled={navigationLocked}
                    aria-label="Select user-defined type" aria-haspopup="menu"
                    aria-expanded={typeMenuOpen}
                    onclick={() => typeMenuOpen = !typeMenuOpen}>
                <img class="action-icon-small" alt="" src={downIcon} />
            </button>
            {#if typeMenuOpen}
                <div class="user-type-menu" role="menu">
                    <button type="button" role="menuitem"
                            onclick={() => { typeMenuOpen = false; openSettings('user-types'); }}>
                        Configure types...
                    </button>
                    {#each userTypeState.types as type (type.id)}
                        <button type="button" role="menuitemradio"
                                aria-checked={userTypeState.active?.id === type.id}
                                onclick={() => selectUserType(type)}>
                            <img class="action-icon-small" alt=""
                                 src={userTypeIcon(type.icon, 16) ?? userDefinedIcon} />
                            <span>{type.name}</span>
                        </button>
                    {/each}
                </div>
            {/if}
        </div>
        
        <button class="nav-button"
            role="radio"
            disabled={navigationLocked}
            aria-checked={current_tab === 'collections'}
            onclick={() => current_tab = 'collections'} >
            <img class="action-icon" alt="collections" src={collectionIcon} />
            <span class="large-button-label">Collections</span>
        </button>
    </div>

    <div class="option-set">
        <div class="nav-split" role="group" aria-label="Repository">
            <button class="nav-button nav-split-main" type="button"
                    disabled={!serverReady && !$serverUnresponsive}
                    aria-haspopup="dialog" onclick={() => repositoryOpen = true}>
                <span class="large-button-label" aria-live="polite">{repositoryLabel}</span>
            </button>

            <button class="nav-split-trigger repository-scan" type="button"
                    aria-label="Run a full repository scan" title="Run a full scan"
                    disabled={!serverReady || $serverUnresponsive || scanBusy} onclick={scanRepository}>
                <img class="action-icon" alt="" src={refreshIcon} />
            </button>
        </div>

        <button class="nav-option"
                aria-label="tag-editor"
                title={remapBlocked ? 'Save or discard object changes before remapping tags' : 'Remap tags'}
                disabled={navigationLocked || remapBlocked || scanBusy || settingsOpen}
                onclick={() => remapOpen = true}>
            <img class="action-icon" alt="options" src={tagIcon} />
        </button>
        <button class="nav-option"
                aria-label="options"
                onclick={() => openSettings('general')}>
            <img class="action-icon" alt="options" src={settingsIcon} />
        </button>
        <button class="nav-option"
                onclick={() => theme = theme === 'light' ? 'dark' : 'light'}
                aria-label="toggle theme">
            <img class="action-icon"  alt="dark light mode" src={lightDarkModeIcon} />
        </button>
    </div>
</div>

{#if settingsOpen}
    <SettingsModal initialTab={settingsInitialTab} onClose={() => settingsOpen = false} />
{/if}

{#if remapOpen}
    <RemapTags onClose={() => remapOpen = false} onRemapped={onTagsRemapped} />
{/if}


<style>
</style>

{#if repositoryOpen}
    <RepositorySummary onClose={() => repositoryOpen = false} />
{/if}

{#if aboutOpen}
    <AboutModal image={logoImage} onClose={closeAbout} />
{/if}
