/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: user-types.svelte.ts
 * purpose: User-defined type API and active front-end selection
 * ---------------------------------------------------------------------------*/

import { getUrl, parseResponse, type ApiResult } from '$lib/api';
import { type UserDefinedType } from '$lib/objects';

const ACTIVE_TYPE_KEY = 'active-user-type';

export async function getUserTypes(): Promise<ApiResult<UserDefinedType[]>> {
    const response = await fetch(getUrl('/user-types'));
    return await parseResponse<UserDefinedType[]>(response, value => value, 'getUserTypes');
}

async function userTypeRequest(path: string, method: string, body: unknown): Promise<ApiResult<UserDefinedType>> {
    const response = await fetch(getUrl(path), {
        method,
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body)
    });
    return await parseResponse<UserDefinedType>(response, value => value, path);
}

export async function getUserType(id: string): Promise<ApiResult<UserDefinedType>> {
    const response = await fetch(getUrl(`/user-types/${id}`));
    return await parseResponse<UserDefinedType>(response, value => value, 'getUserType');
}

export const createUserType = (type: Omit<UserDefinedType, 'id' | 'object_count'>) =>
    userTypeRequest('/user-types', 'POST', type);

export const updateUserType = (type: UserDefinedType) =>
    userTypeRequest(`/user-types/${type.id}`, 'PUT', type);

export async function deleteUserType(id: string): Promise<ApiResult<unknown>> {
    const previewResponse = await fetch(getUrl(`/user-types/${id}/deletion-preview`), {
        method: 'POST'
    });
    const preview = await parseResponse<{confirmation_id: string}>(
        previewResponse, value => value, 'previewUserTypeDeletion');
    if (!preview.ok) return preview;
    const response = await fetch(getUrl(
        `/user-types/${id}?confirmation_id=${encodeURIComponent(preview.data.confirmation_id)}`), {
        method: 'DELETE'
    });
    return await parseResponse<unknown>(response, value => value, 'deleteUserType');
}

class UserTypeState {
    types = $state<UserDefinedType[]>([]);
    active = $state<UserDefinedType | null>(null);
    error = $state<string | null>(null);
    loaded = $state(false);

    async load(): Promise<void> {
        const result = await getUserTypes();
        this.loaded = true;
        if (!result.ok) {
            this.error = result.message ?? 'Cannot retrieve user-defined types';
            return;
        }
        this.types = result.data;
        const storedId = localStorage.getItem(ACTIVE_TYPE_KEY);
        this.active = this.types.find(item => item.id === storedId) ?? null;
        if (storedId !== null && this.active === null) {
            localStorage.removeItem(ACTIVE_TYPE_KEY);
        }
        this.error = null;
    }

    select(type: UserDefinedType): void {
        this.active = type;
        localStorage.setItem(ACTIVE_TYPE_KEY, type.id);
    }
}

export const userTypeState = new UserTypeState();

const iconModules = import.meta.glob<string>(
    '/src/lib/assets/icons/user-types/*24.png',
    { eager: true, query: '?url', import: 'default' }
);

const smallIconModules = import.meta.glob<string>(
    '/src/lib/assets/icons/user-types/*16.png',
    { eager: true, query: '?url', import: 'default' }
);

function iconMap(modules: Record<string, string>, suffix: string): Record<string, string> {
    return Object.fromEntries(Object.entries(modules).map(([path, url]) => [
        (path.split('/').at(-1) ?? '').slice(0, -suffix.length), url
    ]));
}

const icons24 = iconMap(iconModules, '24.png');
const icons16 = iconMap(smallIconModules, '16.png');

export function userTypeIcon(icon: string, size: 16 | 24): string | undefined {
    return (size === 24 ? icons24 : icons16)[icon];
}
