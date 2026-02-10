<heading class="page-header">


    <div class="header-container">
        <div class="header-branding">
          <a href="/loras" class="logo-link">
            <img src="/static/favicon.png" alt="LoRA Manager" class="app-logo">
            <span class="app-title">Model Archivist</span>
          </a>
        </div>
    </div>
</heading>

<style>
    .page-header {
        background: #ffffff;
        border-bottom: 1px solid #e0e0e0;
        position: fixed;
        top: 0;
        z-index: 100;
        height: 48px;
        width: 100%;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    .header-container {
        max-width: 1400px;
        margin: 0 auto;
        padding: 0 15px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        height: 100%;
    }

    .header-branding {
        display: flex;
        align-items: center;
        flex-shrink: 0;
    }

    .logo-link {
        display: flex;
        align-items: center;
        text-decoration: none;
        color: #333333;
        gap: 2px;
    }

    .app-title {
        font-size: 1rem;
        font-weight: 600;
        margin: 0;
    }
</style>