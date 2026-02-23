<script lang=ts>
    let { selectContents } = $props();

</script>

<div class="header-container">
    <div class="header-branding">
        <img src="archivist.png" class="logo-image" alt="logo">
        <span class="app-title">Model Archivist</span>
    </div>

    <nav class="main-nav">
        <button class="archivist-button nav-button" onclick={() => selectContents("models")}>
            <img src="model-32.png" class="nav-icon" alt="Models">
            <span>Models</span>
        </button>

        <button class="archivist-button nav-button" onclick={() => selectContents("workflows")} >
            <img src="workflow-32.png" class="nav-icon" alt="Workflows">
            <span>Workflows</span>
        </button>

        <button class="archivist-button nav-button" onclick={() => selectContents("collections")}>
            <img src="collection-32.png" class="nav-icon" alt="Collections">
            <span>Collections</span>
        </button>

        <button class="archivist-button nav-button">
            <img src="collection-32.png" class="nav-icon" alt="Collectons">
            <span>Repository</span>
        </button>

    </nav>

    <nav class="main-nav">
        <button class="archivist-button nav-button">
            <img src="collection-32.png" class="nav-icon" alt="Models">
            <span>Models</span>
        </button>
    </nav>

    <!--
        <menu> for dropdowns?

        <progress> for full rescan

        <search>

    <div class="main-nav">
        <div class="header-controls">
            <div class="theme-toggle theme-light" title="Switch to dark theme">
                <i class="fas fa-moon dark-icon"></i>
                <i class="fas fa-sun light-icon"></i>
                <i class="fas fa-adjust auto-icon"></i>
            </div>
            <div class="settings-toggle" title="Settings">
                <i class="fas fa-cog"></i>
            </div>
        </div>
    </div> -->
</div>


<style>
    .header-container {
        width: 100%;
        margin: 0 auto;
        padding: 0 var(--gap-large) 0 var(--gap-large);
        display: flex;
        align-items: center;
        justify-content: space-around;
        height: 100%;
    }

    .header-branding {
        display: flex;
        align-items: center;
        flex-shrink: 0;
    }

    .app-title {
        font-size: 1rem;
        font-weight: 600;
        margin: 0;
    }
    .logo-image {
        width: 40px;
        height: 32px;
    }

    .main-nav {
        display: flex;
        gap: var(--gap-large);
        flex-shrink: 0;
    }

</style>