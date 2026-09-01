/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: archivist.js
 * purpose: ComfyUI launch button for Model Archivist
 * ---------------------------------------------------------------------------*/

import { app } from '../../scripts/app.js';

const BUTTON_TOOLTIP = 'Launch Model Archivist';

async function openArchivist() {
    try {
        const response = await fetch('/model-archivist/launch-url');
        if (!response.ok) {
            throw new Error(`launch URL request failed with status ${response.status}`);
        }
        const { url } = await response.json();
        window.open(url, '_blank', 'noopener');
    } catch (error) {
        console.error('Model Archivist: cannot open application', error);
    }
}

app.registerExtension({
    name: 'ModelArchivist.Launcher',
    actionBarButtons: [{
        icon: 'icon-[lucide--archive] size-4',
        tooltip: BUTTON_TOOLTIP,
        onClick: openArchivist
    }]
});
