/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: modal-dialog.ts
 * purpose: Native opening and bounded dragging for navigation dialogs
 * ---------------------------------------------------------------------------*/


export function modalDialog(node: HTMLDialogElement): {destroy: () => void} {
    let header: HTMLElement | null = null;
    let destroyed = false;
    let dragging = false;
    let pointerId = 0;
    let offsetX = 0;
    let offsetY = 0;

    function minimumTop(): number {
        const value = getComputedStyle(document.documentElement)
            .getPropertyValue('--nav-bar-height');
        return Number.parseFloat(value) || 0;
    }

    function place(left: number, top: number): void {
        const maximumLeft = Math.max(0, window.innerWidth - node.offsetWidth);
        const minimum = minimumTop();
        const maximumTop = Math.max(minimum, window.innerHeight - node.offsetHeight);
        node.style.left = `${Math.min(Math.max(0, left), maximumLeft)}px`;
        node.style.top = `${Math.min(Math.max(minimum, top), maximumTop)}px`;
    }

    function begin(event: PointerEvent): void {
        const target = event.target as HTMLElement;
        if (event.button !== 0 || target.closest('button, a, input, select, textarea')) return;

        const bounds = node.getBoundingClientRect();
        node.style.position = 'fixed';
        node.style.margin = '0';
        node.style.transform = 'none';
        place(bounds.left, bounds.top);

        dragging = true;
        pointerId = event.pointerId;
        offsetX = event.clientX - bounds.left;
        offsetY = event.clientY - bounds.top;
        header?.setPointerCapture(pointerId);
        event.preventDefault();
    }

    function move(event: PointerEvent): void {
        if (!dragging || event.pointerId !== pointerId) return;
        place(event.clientX - offsetX, event.clientY - offsetY);
    }

    function end(event: PointerEvent): void {
        if (!dragging || event.pointerId !== pointerId) return;
        dragging = false;
        if (header?.hasPointerCapture(pointerId)) header.releasePointerCapture(pointerId);
    }

    function resize(): void {
        if (node.style.left && node.style.top) {
            place(Number.parseFloat(node.style.left), Number.parseFloat(node.style.top));
        }
    }

    function initialize(): void {
        if (destroyed || !node.isConnected) return;
        if (!node.open) node.showModal();
        header = node.querySelector<HTMLElement>('.dialog-header');
        header?.addEventListener('pointerdown', begin);
        header?.addEventListener('pointermove', move);
        header?.addEventListener('pointerup', end);
        header?.addEventListener('pointercancel', end);
        window.addEventListener('resize', resize);
    }

    queueMicrotask(initialize);

    return {
        destroy(): void {
            destroyed = true;
            header?.removeEventListener('pointerdown', begin);
            header?.removeEventListener('pointermove', move);
            header?.removeEventListener('pointerup', end);
            header?.removeEventListener('pointercancel', end);
            window.removeEventListener('resize', resize);
            if (node.open) node.close();
        }
    };
}
