<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: AboutModal.svelte
 ! purpose: About dialog displaying the current library image
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
    import { onMount } from 'svelte';

    import closeIcon from '$icons/actions/close8.png';
    import leftIcon from '$icons/actions/left32.png';
    import rightIcon from '$icons/actions/right32.png';

    import { apiFetch, getUrl, parseResponse } from '$lib/api';
    import { locale } from '$lib/locale.svelte';
    import { modalDialog } from '$lib/modal-dialog';

    let { image, onClose }: { image: string; onClose: () => void } = $props();
    let about = $state<{ version: string; mode: 'standalone' | 'comfyui' } | null>(null); let error = $state<string | null>(null); const images = import.meta.glob<string>('/src/lib/assets/images/logo/Library-*.png',
        { eager: true, query: '?url', import: 'default' });
    const slides = Object.entries(images)
        .sort(([left], [right]) => left.localeCompare(right, 'en'))
        .map(([path, url]) => ({
            url,
            name: path.split('/').at(-1)!.replace(/^Library-/, '').replace(/\.png$/, '').replaceAll('-', ' '),
            captionKey: `about.captions.${path.split('/').at(-1)!.replace(/\.png$/, '')}`
        }));
    let selected = $state(0);
    let slide = $derived(slides[selected]);

    function advance(direction: number): void {
        selected = (selected + direction + slides.length) % slides.length;
    }

    onMount(() => {
        selected = Math.max(0, slides.findIndex(slide => slide.url === image));
        void loadAbout();
    });

    async function loadAbout(): Promise<void> {
        const response = await apiFetch(getUrl('/about'));
        const result = await parseResponse<NonNullable<typeof about>>(response, value => value, 'about');

        if (result.ok) {
            about = result.data;
        } else {
            error = result.message ?? locale.t('ui.about_modal.cannot_load_version_information');
        }
    }
</script>

<dialog class="nav-dialog" use:modalDialog aria-label={locale.t('ui.about_modal.about_model_archivist')}
        oncancel={event => {
            event.preventDefault();
            onClose();
        }}>
    <header class="dialog-header spaced-horizontally">
        <h1>{locale.t('ui.about_modal.about_model_archivist')}</h1>
        <button class="round" type="button" aria-label={locale.t('ui.about_modal.close_about')} onclick={onClose}>
            <img class="action-icon" alt="" src={closeIcon} />
        </button>
    </header>

    <div class="about-contents">
        <section class="about-carousel" aria-label={locale.t('ui.about_modal.library_illustrations')} aria-roledescription="carousel">
            <div class="about-slide">
                <img class="about-image" src={slide.url} alt={slide.name} width="1600" height="640" />

                <button class="about-carousel-arrow about-carousel-left" type="button"
                        aria-label={locale.t('ui.about_modal.previous_image')} onclick={() => advance(-1)}>
                    <img src={leftIcon} alt="" width="32" height="32" />
                </button>
                <button class="about-carousel-arrow about-carousel-right" type="button"
                        aria-label={locale.t('ui.about_modal.next_image')} onclick={() => advance(1)}>
                    <img src={rightIcon} alt="" width="32" height="32" />
                </button>
            </div>

            <div class="about-caption" aria-live="polite" aria-atomic="true">
                {#key selected}
                    {@html locale.t(slide.captionKey)}
                {/key}
            </div>
        </section>

        <div class="about-information">
            <h1>{locale.t('ui.about_modal.model_archivist')}</h1>
            <div>Version: {about?.version ?? '…'}</div>
            {#if about}
                <div>{locale.t(about.mode === 'comfyui' ? 'dynamic.comfyui_version' : 'dynamic.standalone_version')}</div>
            {/if}
            <div>
                {locale.t('ui.about_modal.github')} <a href="https://github.com/tumbislav/ComfyUI-ModelArchivist"
                           target="_blank" rel="noopener noreferrer">{locale.t('ui.about_modal.https_github_com_tumbislav_comfyui_modelarchivist')}</a>
            </div>
            <div>{locale.t('ui.about_modal.author_tumbislav_nilski')}</div>
            <div>{locale.t('ui.about_modal.coding_tumbislav_nilski_chatgpt')}</div>

            {#if error}
                <p class="error-details" role="alert">{error}</p>
            {/if}
        </div>

        <div class="about-help">
            <button class="button-with-text" type="button"
                    onclick={() => window.open(
                        'https://github.com/tumbislav/ComfyUI-ModelArchivist/blob/master/docs/HELP.md',
                        '_blank', 'noopener,noreferrer')}>{locale.t('ui.about_modal.help')}</button>
        </div>
    </div>
</dialog>
