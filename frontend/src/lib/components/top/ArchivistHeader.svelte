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
import settingsIcon from '$icons/nav/settings24.png';
import lightDarkModeIcon from '$icons/nav/light-dark-mode24.png';
import logo_pic from '$icons/nav/archivist.png';
import downIcon from '$icons/actions/down16.png';
import SettingsModal, { type SettingsTab } from '$components/top/SettingsModal.svelte';

import { onMount } from 'svelte';
import { statusMonitor } from '$lib/status.svelte';
import { userTypeIcon, userTypeState } from '$lib/user-types.svelte';

import { type ActiveTab } from '$lib/admin';
let {
    current_tab = $bindable(),
    navigationLocked = false
}: {
    current_tab: ActiveTab;
    navigationLocked: boolean;
} = $props();

let theme = $state<'light' | 'dark'>('light');
let typeMenuOpen = $state(false);
let settingsOpen = $state(false);
let settingsInitialTab = $state<SettingsTab>('general');
let activeTypeIcon = $derived(userTypeState.active
    ? userTypeIcon(userTypeState.active.icon, 24) ?? userDefinedIcon
    : userDefinedIcon);
let progress = $derived(statusMonitor.operation?.progress ?? null);
let bytesTotal = $derived(typeof progress?.bytes_total === 'number'
    ? progress.bytes_total : 0);
let bytesCompleted = $derived(typeof progress?.bytes_completed === 'number'
    ? progress.bytes_completed : 0);
let percent = $derived(bytesTotal > 0
    ? Math.min(100, Math.round(bytesCompleted * 100 / bytesTotal)) : 0);

onMount(() => {
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
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('theme', theme);
});
</script>

<div class="header">
    <div class="app-title">
        <div class="title-image"><img src={logo_pic} alt="archivist"></div>
        <span class="app-title-text">Model Archivist</span>
    </div>
    
    <div class="nav-set" role="radiogroup" aria-label="Tab select">
        <button class="nav-button"
            role="radio"
            disabled={navigationLocked}
            aria-checked={current_tab === 'models'}
            onclick={() => current_tab = 'models'} >
            <img class="action-icon" alt="model" src={modelIcon} /><span>Models</span>
        </button>
        
        <button class="nav-button"
            role="radio"
            disabled={navigationLocked}
            aria-checked={current_tab === 'workflows'}
            onclick={() => current_tab = 'workflows'}>
            <img class="action-icon" alt="workflows" src={workflowIcon} /><span>Workflows</span>
        </button>

        <div class="nav-user-type" aria-checked={current_tab === 'user'}>
            <button class="nav-button user-type-main" role="radio"
                    disabled={navigationLocked}
                    aria-checked={current_tab === 'user'}
                    onclick={openUserType}>
                <img class="action-icon" alt="" src={activeTypeIcon} />
                <span>{userTypeState.active?.short_name ?? 'User'}</span>
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
            <img class="action-icon" alt="collections" src={collectionIcon} /><span>Collections</span>
        </button>
    </div>

    <div class="option-set">
        <div class="status-box">
            <div class="status-summary">
                <table class="summary-table">
                    <tbody>
                        <tr>
                            <td title="Models">{statusMonitor.counts.models}</td>
                            <td title="Workflows">{statusMonitor.counts.workflows}</td>
                            <td title="User-defined objects">{statusMonitor.counts.user_objects}</td>
                            <td title="Collections">{statusMonitor.counts.collections}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <div class="progress-bar">
                {#if statusMonitor.operation?.type === 'scan'}
                    <span>Scanning</span><span class="status-blinker" aria-hidden="true"></span>
                {:else if statusMonitor.operation && bytesTotal > 0}
                    <progress max="100" value={percent} aria-label={`${percent}% complete`}></progress>
                    <span class="progress-label">{percent}%</span>
                {/if}
            </div>
        </div>
        <button class="nav-option" aria-label="options" onclick={() => openSettings('general')}>
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


<style>
</style>
