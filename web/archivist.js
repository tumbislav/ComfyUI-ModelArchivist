/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: archivist.js
 * purpose: ComfyUI launch button for Model Archivist
 * ---------------------------------------------------------------------------*/

import { app } from '../../scripts/app.js';

const BUTTON_TOOLTIP = 'Launch Model Archivist';

async function openArchivist() {
    window.open(new URL('/model-archivist/', window.location.origin), '_blank', 'noopener');
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
