<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ArchivistHeader.svelte
 ! purpose: Top navigation
 ! -------------------------------------------------->

<script lang=ts>
import { type ActiveTab } from '$lib/admin';
let {
    current_tab = $bindable()
}: {
    current_tab: ActiveTab;
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
        <button class="tab-button"
            role="radio"
            aria-checked={current_tab === 'models'}
            onclick={() => current_tab = 'models'} >
            <i class="fa-solid fa-scroll nav-icon"></i> Models
        </button>
        
        <button class="tab-button" 
            role="radio"
            aria-checked={current_tab === 'workflows'}
            onclick={() => current_tab = 'workflows'}>
            <i class="fa-solid fa-arrows-turn-to-dots nav-icon"></i> Workflows
        </button>
        
        <button class="tab-button" 
            role="radio"
            aria-checked={current_tab === 'collections'}
            onclick={() => current_tab = 'collections'} >
            <i class="fa-solid fa-object-group nav-icon"></i> Collections
        </button>
    </div>
    
    <div class="nav-set">
        <button class="option-button" aria-label="options">
            <i class="fa-solid fa-gear nav-icon"></i>
        </button>
        <button class="option-button theme-toggle"
                onclick={() => theme = theme === 'light' ? 'dark' : 'light'}
                aria-label="toggle theme"></button>
    </div>
</div>


<style>
</style>