/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/confirm.ts
 * purpose: Confirmation box handling
 * ---------------------------------------------------------------------------*/

type ConfirmOptions = {
    title?: string;
    message: string;
    anchor?: HTMLElement;
};

type ConfirmState = {
    open: boolean;
    title: string;
    message: string;
    position: string;
    response?: (value: boolean) => void;
};

export const confirmState = $state<ConfirmState>({
    open: false,
    title: '',
    message: '',
    position: ''
});

export function sideDialogPosition(anchor: HTMLElement): string {
    const details = anchor.closest('[data-model-details]') as HTMLElement | null;
    const anchorRect = anchor.getBoundingClientRect();
    const detailsRect = (details ?? anchor).getBoundingClientRect();
    return `--dialog-top: ${anchorRect.top}px; top: var(--dialog-top); ` +
        `right: calc(100vw - ${detailsRect.left}px + var(--gap-mid)); ` +
        'left: auto; transform: none;';
}

export function confirmBox(options: ConfirmOptions): Promise<boolean> {
    confirmState.open = true;
    confirmState.title = options.title ?? 'Confirm';
    confirmState.message = options.message;
    confirmState.position = options.anchor ? sideDialogPosition(options.anchor) : '';

    return new Promise<boolean>((response) => {confirmState.response = response;});
}
