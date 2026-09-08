/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: user-objects.ts
 * purpose: User-defined object API access
 * ---------------------------------------------------------------------------*/


import { apiFetch, getUrl, parseResponse, type ApiResult } from '$lib/api';
import { identity, toUserObject, type UserObject, type UserObjectSummary } from '$lib/objects';
import { type Operation } from '$lib/models';

export type UserObjectDestination = 'working' | 'archive';
export type ImmediateOperation = {allowed: boolean; performed?: boolean; errors?: string[]};
export type UserObjectOperation = Operation | ImmediateOperation;

export async function getUserObjects(typeId: string): Promise<ApiResult<UserObjectSummary[]>> {
    const response = await apiFetch(getUrl(`/user-types/${typeId}/objects`));
    return await parseResponse(response, identity, 'getUserObjects');
}

export async function getUserObject(id: string): Promise<ApiResult<UserObject>> {
    const response = await apiFetch(getUrl(`/user-objects/${id}`));
    return await parseResponse(response, toUserObject, 'getUserObject');
}

export async function updateUserObject(item: UserObject): Promise<ApiResult<UserObject>> {
    const response = await apiFetch(getUrl(`/user-objects/${item.id}`), {
        method: 'PUT', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({display_name: item.display_name, purpose: item.purpose, tags: item.tags})
    });
    return await parseResponse(response, toUserObject, 'updateUserObject');
}

export async function syncUserObject(id: string): Promise<ApiResult<UserObjectOperation>> {
    const response = await apiFetch(getUrl(`/user-objects/${id}/synchronize?simulate=false`),
        {method: 'POST'});
    return await parseResponse(response, identity, 'syncUserObject');
}

export async function moveUserObject(id: string,
                                     destination: UserObjectDestination): Promise<ApiResult<UserObjectOperation>> {
    const response = await apiFetch(getUrl(
        `/user-objects/${id}/move?destination=${destination}&simulate=false`), {method: 'POST'});
    return await parseResponse(response, identity, 'moveUserObject');
}

export function isLongOperation(operation: UserObjectOperation): operation is Operation {
    return 'state' in operation && 'id' in operation;
}
