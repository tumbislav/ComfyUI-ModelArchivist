/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: unsaved-changes.svelte.ts
 * purpose: Three-way unsaved changes prompt handling
 * ---------------------------------------------------------------------------*/

import { locale } from '$lib/locale.svelte';
import { sideDialogPosition } from '$lib/confirm.svelte';

export type UnsavedChangesResult = 'cancel' | 'discard' | 'save';

type UnsavedChangesOptions = {
    title?: string;
    message: string;
    anchor?: HTMLElement;
    saveDisabled?: boolean;
};

type UnsavedChangesState = {
    open: boolean;
    title: string;
    message: string;
    position: string;
    saveDisabled: boolean;
    response?: (value: UnsavedChangesResult) => void;
};

export const unsavedChangesState = $state<UnsavedChangesState>({
    open: false,
    title: '',
    message: '',
    position: '',
    saveDisabled: false
});

export function unsavedChangesBox(options: UnsavedChangesOptions): Promise<UnsavedChangesResult> {
    unsavedChangesState.open = true;
    unsavedChangesState.title = options.title ?? locale.t('common.unsaved_changes');
    unsavedChangesState.message = options.message;
    unsavedChangesState.position = options.anchor ? sideDialogPosition(options.anchor) : '';
    unsavedChangesState.saveDisabled = options.saveDisabled ?? false;

    return new Promise<UnsavedChangesResult>((response) => {
        unsavedChangesState.response = response;
    });
}
