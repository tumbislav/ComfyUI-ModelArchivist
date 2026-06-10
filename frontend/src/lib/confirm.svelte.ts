/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/confirm.ts
 * purpose: Confirmation box handling
 * ---------------------------------------------------------------------------*/

type ConfirmOptions = {
    title?: string;
    message: string;
};

type ConfirmState = {
    open: boolean;
    title: string;
    message: string;
    response?: (value: boolean) => void;
};

export const confirmState = $state<ConfirmState>({
    open: false,
    title: '',
    message: ''
});

export function confirmBox(options: ConfirmOptions): Promise<boolean> {
    confirmState.open = true;
    confirmState.title = options.title ?? 'Confirm';
    confirmState.message = options.message;

    return new Promise<boolean>((response) => {confirmState.response = response;});
}
