/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: archivist.js
 * purpose: ComfyUI launch button for Model Archivist
 * ---------------------------------------------------------------------------*/

import { app } from '../../scripts/app.js';

app.registerExtension({
    name: 'ModelArchivist.Launcher',
    async setup() {
        const button = document.createElement('button');
        button.textContent = 'Model Archivist';
        button.title = 'Launch Model Archivist';
        button.addEventListener('click', async () => {
            const response = await fetch('/model-archivist/launch-url');
            const { url } = await response.json();
            window.open(url, '_blank', 'noopener');
        });
        const menu = document.querySelector('.comfy-menu');
        if (menu) menu.append(button);
    }
});
