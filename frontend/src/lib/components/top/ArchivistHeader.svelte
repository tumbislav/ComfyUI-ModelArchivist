<!---------------------------------------------------
 ! system: ModelArchivist
 ! file: ArchivistHeader.svelte
 ! purpose: Top navigation
 ! -------------------------------------------------->

<script lang=ts>
    let { selectContents } = $props();
    import logo_pic from '$lib/assets/icons/archivist.png';
    import model_ico from '$lib/assets/icons/model-32.png';
    import workflow_ico from '$lib/assets/icons/workflow-32.png';
    import collection_ico from '$lib/assets/icons/collection-32.png';

    let theme = $state<'light' | 'dark'>('light');

    $effect(() => {
        document.documentElement.dataset.theme = theme;
        localStorage.setItem('theme', theme);
    });
</script>

<div class="nav-container">
    <div class="header-branding">
        <img src={logo_pic} class="logo-image" alt="logo">
        <span class="app-title">Model Archivist</span>
    </div>

    <nav class="main-nav">
        <button class="combined-button nav-button" onclick={() => selectContents("models")}>
        <img src={model_ico} class="nav-icon" alt="Models">
        <span>Models</span>
        </button>

        <button class="combined-button nav-button" onclick={() => selectContents("workflows")} >
        <img src={workflow_ico} class="nav-icon" alt="Workflows">
        <span>Workflows</span>
        </button>

        <button class="combined-button nav-button" onclick={() => selectContents("collections")}>
        <img src={collection_ico} class="nav-icon" alt="Collections">
        <span>Collections</span>
        </button>

        <button class="combined-button nav-button">
            <img src={collection_ico} class="nav-icon" alt="Collectons">
            <span>Repository</span>
        </button>

    </nav>

    <div class="nav-options">
    <button class="option-button theme-toggle"
            onclick={() => theme = theme === 'light' ? 'dark' : 'light'}
            aria-label="toggle theme"></button>
    </div>
</div>


<style>
/* Header and navigation --------------------------*/

.nav-container {
    width: 100%;
    height: 100%;
    margin: 0 auto;
    padding: 0;
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
}

.header-branding {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    gap: var(--gap-small);
    padding: 0 var(--gap-large);
}

.app-title {
    font-size: var(--title-font-size);
    color: var(--text-title);
    font-weight: 700;
}

.logo-image {
    width: 40px;
    height: var(--large-button-height);
}

.main-nav {
    display: flex;
    gap: var(--gap-large);
    flex-shrink: 0;
}

.nav-options {
    display: flex;
    gap: var(--gap-large);
    flex-shrink: 0;
    flex-direction: row;
    padding: 0 var(--gap-large);
}

.nav-button {
    height: var(--large-button-height);
    width: 150px;
    font-size: var(--large-font-size);
    border-radius: var(--radius-mid);
}

.option-button {
    height: var(--large-button-height);
    width: var(--large-button-height);
    font-size: var(--icon-font-size);
    border-radius: var(--radius-mid);
}


</style>