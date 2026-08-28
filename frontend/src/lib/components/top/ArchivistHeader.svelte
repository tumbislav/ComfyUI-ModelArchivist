<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ArchivistHeader.svelte
 ! purpose: Top navigation
 ! -------------------------------------------------->

<script lang=ts>
import modelIcon from '$icons/model24.png';
import workflowIcon from '$icons/workflow24.png';
import collectionIcon from '$icons/collection24.png';
import settingsIcon from '$icons/settings24.png';
import lightDarkModeIcon from '$icons/light-dark-mode24.png';

import { type ActiveTab } from '$lib/admin';
let {
    current_tab = $bindable(),
    navigationLocked = false
}: {
    current_tab: ActiveTab;
    navigationLocked: boolean;
} = $props();
import logo_pic from '$lib/assets/icons/archivist.png';

let theme = $state<'light' | 'dark'>('light');

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
        
        <button class="nav-button"
            role="radio"
            disabled={navigationLocked}
            aria-checked={current_tab === 'collections'}
            onclick={() => current_tab = 'collections'} >
            <img class="action-icon" alt="collections" src={collectionIcon} /><span>Collections</span>
        </button>
    </div>
    
    <div class="nav-set">
        <button class="nav-option" aria-label="options">
            <img class="action-icon" alt="options" src={settingsIcon} />
        </button>
        <button class="nav-option"
                onclick={() => theme = theme === 'light' ? 'dark' : 'light'}
                aria-label="toggle theme">
            <img class="action-icon"  alt="dark light mode" src={lightDarkModeIcon} />
        </button>
    </div>
</div>


<style>
</style>
