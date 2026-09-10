<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: SettingsLayout.svelte
 ! purpose: Settings navigation and fixed tab content area
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import type { Snippet } from 'svelte';

    import generalIcon from '$icons/nav/settings16.png';
    import modelIcon from '$icons/nav/model16.png';
    import workflowIcon from '$icons/nav/workflow16.png';
    import userTypeIcon from '$icons/nav/user-defined16.png';

    type SettingsTab = 'general' | 'models' | 'workflows' | 'user-types';

    let {
        activeTab,
        dirty,
        loading,
        disabled,
        error,
        onTab,
        children
    }: {
        activeTab: SettingsTab;
        dirty: Record<SettingsTab, boolean>;
        loading: boolean;
        disabled: boolean;
        error: string | null;
        onTab: (tab: SettingsTab) => void;
        children: Snippet<[SettingsTab]>;
    } = $props();

    const tabs: { id: SettingsTab; label: string; icon: string }[] = [
        { id: 'general', label: 'General', icon: generalIcon },
        { id: 'models', label: 'Models', icon: modelIcon },
        { id: 'workflows', label: 'Workflows', icon: workflowIcon },
        { id: 'user-types', label: 'User types', icon: userTypeIcon }
    ];
</script>

<div class="settings-layout">
    <nav class="settings-tabs" aria-label="Settings sections">
        {#each tabs as tab}
            <button type="button" class:active={activeTab === tab.id} onclick={() => onTab(tab.id)}>
                <img class="action-icon-small" src={tab.icon} alt="" />
                <span class="button-label">
                    {tab.label}

                    {#if dirty[tab.id]}
                        <span aria-label="Unsaved">•</span>
                    {/if}
                </span>
            </button>
        {/each}
    </nav>

    <section class="settings-content"
             class:structured-settings-content={activeTab !== 'general'}>
        <fieldset class="settings-edit-controls" {disabled}>
            {#if loading}
                <p>Loading settings…</p>
            {:else}
                {@render children(activeTab)}
            {/if}

            {#if error}
                <p class="error-message">{error}</p>
            {/if}
        </fieldset>
    </section>
</div>
