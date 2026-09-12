/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: modal-control.ts
 * purpose: Native opening and cleanup for modal controls
 * ---------------------------------------------------------------------------*/

export function modalControl(node: HTMLDialogElement): {destroy: () => void} {
    queueMicrotask(() => {
        if (node.isConnected && !node.open) {
            node.showModal();
        }
    });

    return {
        destroy(): void {
            if (node.open) {
                node.close();
            }
        }
    };
}
