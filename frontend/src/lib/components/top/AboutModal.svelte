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

    let { image, onClose }: { image: string; onClose: () => void } = $props();
    let dialog = $state<HTMLDialogElement>();
    let about = $state<{ version: string; mode: 'standalone' | 'comfyui' } | null>(null);
    let error = $state<string | null>(null);
    const images = import.meta.glob<string>('/src/lib/assets/images/logo/Library-*.png',
        { eager: true, query: '?url', import: 'default' });
    const captions = import.meta.glob<string>('/src/lib/assets/images/logo/Library-*.html',
        { eager: true, query: '?raw', import: 'default' });
    const slides = Object.entries(images)
        .sort(([left], [right]) => left.localeCompare(right, 'en'))
        .map(([path, url]) => ({
            url,
            name: path.split('/').at(-1)!.replace(/^Library-/, '').replace(/\.png$/, '').replaceAll('-', ' '),
            caption: captions[path.replace(/\.png$/, '.html')] ?? ''
        }));
    let selected = $state(0);
    let slide = $derived(slides[selected]);

    function advance(direction: number): void {
        selected = (selected + direction + slides.length) % slides.length;
    }

    onMount(() => {
        selected = Math.max(0, slides.findIndex(slide => slide.url === image));
        dialog?.showModal();
        void loadAbout();
    });

    async function loadAbout(): Promise<void> {
        const response = await apiFetch(getUrl('/about'));
        const result = await parseResponse<NonNullable<typeof about>>(response, value => value, 'about');

        if (result.ok) {
            about = result.data;
        } else {
            error = result.message ?? 'Cannot load version information';
        }
    }
</script>

<dialog class="about-dialog" bind:this={dialog} aria-label="About Model Archivist"
        oncancel={event => {
            event.preventDefault();
            onClose();
        }}>
    <header class="spaced-horizontally">
        <h2>About Model Archivist</h2>
        <button class="round" type="button" aria-label="Close About" onclick={onClose}>
            <img class="action-icon" alt="" src={closeIcon} />
        </button>
    </header>

    <section class="about-carousel" aria-label="Library illustrations" aria-roledescription="carousel">
        <div class="about-slide">
            <img class="about-image" src={slide.url} alt={slide.name} width="1600" height="640" />

            <button class="about-carousel-arrow about-carousel-left" type="button"
                    aria-label="Previous image" onclick={() => advance(-1)}>
                <img src={leftIcon} alt="" width="32" height="32" />
            </button>
            <button class="about-carousel-arrow about-carousel-right" type="button"
                    aria-label="Next image" onclick={() => advance(1)}>
                <img src={rightIcon} alt="" width="32" height="32" />
            </button>
        </div>

        <div class="about-caption" aria-live="polite" aria-atomic="true">
            {#key selected}
                {@html slide.caption}
            {/key}
        </div>
    </section>

    <div class="about-information">
        <h2>Model Archivist</h2>
        <div>Version: {about?.version ?? '…'}</div>
        {#if about}
            <div>{about.mode === 'comfyui' ? 'ComfyUI embedded version' : 'Standalone version'}</div>
        {/if}
        <div>
            GitHub: <a href="https://github.com/tumbislav/ComfyUI-ModelArchivist"
                       target="_blank" rel="noopener noreferrer">https://github.com/tumbislav/ComfyUI-ModelArchivist</a>
        </div>
        <div>Author: Marko Čibej</div>
        <div>Coding: Marko Čibej, ChatGPT</div>

        {#if error}
            <p class="error-details" role="alert">{error}</p>
        {/if}
    </div>

    <div class="about-help">
        <button class="button-with-text" type="button"
                onclick={() => window.open(
                    'https://github.com/tumbislav/ComfyUI-ModelArchivist/blob/master/docs/HELP.md',
                    '_blank', 'noopener,noreferrer')}>Help</button>
    </div>
</dialog>
