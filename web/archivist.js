/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: archivist.js
 * purpose: ComfyUI launch button for Model Archivist
 * ---------------------------------------------------------------------------*/

import { app } from '../../scripts/app.js';
import { api } from '../../scripts/api.js';

const BUTTON_TOOLTIP = 'Launch Model Archivist';
const ICON_URL = new URL('./assets/archivist-icon.svg', import.meta.url).href;
const ICON_CLASS = 'model-archivist-launch-icon';
const MAX_ICON_ATTACH_ATTEMPTS = 120;

async function openArchivist() {
    const url = new URL('/model-archivist/', window.location.origin);
    // This selects the host profile; it is not an authentication credential.
    url.hash = new URLSearchParams({ 'comfy-user': api.user || 'default' }).toString();
    window.open(url, '_blank', 'noopener');
}

function attachArchivistIcon(attempt = 0) {
    const icons = document.querySelectorAll(
        `button[aria-label="${BUTTON_TOOLTIP}"] .${ICON_CLASS}`);
    if (icons.length === 0) {
        if (attempt < MAX_ICON_ATTACH_ATTEMPTS) {
            requestAnimationFrame(() => attachArchivistIcon(attempt + 1));
        }
        return;
    }

    for (const icon of icons) {
        const image = document.createElement('img');
        image.src = ICON_URL;
        image.alt = '';
        image.width = 20;
        image.height = 20;
        image.style.display = 'block';
        image.style.objectFit = 'contain';
        icon.replaceChildren(image);
    }
}

app.registerExtension({
    name: 'ModelArchivist.Launcher',
    setup() {
        const style = document.createElement('style');
        style.id = 'model-archivist-launcher-styles';
        style.textContent = `button[aria-label="${BUTTON_TOOLTIP}"] {
            border-radius: 4px !important;
        }
        .${ICON_CLASS} {
            display: inline-block;
            width: 20px;
            height: 20px;
            background: url("${ICON_URL}") center / contain no-repeat;
        }
        .${ICON_CLASS}::before {
            content: none !important;
        }`;
        document.head.appendChild(style);
        requestAnimationFrame(() => attachArchivistIcon());
    },
    actionBarButtons: [{
        icon: ICON_CLASS,
        tooltip: BUTTON_TOOLTIP,
        onClick: openArchivist
    }]
});
