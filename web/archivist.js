/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: archivist.js
 * purpose: ComfyUI launch button for Model Archivist
 * ---------------------------------------------------------------------------*/

import { app } from '../../scripts/app.js';
import { api } from '../../scripts/api.js';

const BUTTON_TOOLTIP = 'Launch Model Archivist';

async function openArchivist() {
    const url = new URL('/model-archivist/', window.location.origin);
    // This selects the host profile; it is not an authentication credential.
    url.hash = new URLSearchParams({ 'comfy-user': api.user || 'default' }).toString();
    window.open(url, '_blank', 'noopener');
}

app.registerExtension({
    name: 'ModelArchivist.Launcher',
    setup() {
        const style = document.createElement('style');
        style.textContent = `button[aria-label="${BUTTON_TOOLTIP}"] {
            border-radius: 4px !important;
        }`;
        document.head.appendChild(style);
    },
    actionBarButtons: [{
        icon: 'pi pi-box',
        tooltip: BUTTON_TOOLTIP,
        onClick: openArchivist
    }]
});
