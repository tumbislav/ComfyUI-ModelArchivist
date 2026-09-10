/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/models.ts
 * purpose: Model handling
 * ---------------------------------------------------------------------------*/


import {
    type ModelSummary,
    type Model,
    toModel,
    identity } from "$lib/objects";

import { apiFetch,
    type ApiResult,
    getUrl,
    parseResponse } from "$lib/api";

export type ModelSearchCriteria = {
    types: string[];
    file_formats: string[];
    required_tags: string[];
    forbidden_tags: string[];
    name_prefix: string;
}

export type ModelDestination = 'working' | 'archive';

export type Operation = {
    id: string;
    type: string;
    state: 'pending' | 'running' | 'succeeded' | 'failed';
    progress: Record<string, unknown>;
    result: Record<string, unknown> | null;
    error: { type: string; message: string } | null;
};

export async function getModels(): Promise<ApiResult<ModelSummary[]>> {
    const url = getUrl('/models');
    const response = await apiFetch(url);
    return await parseResponse(response, identity, 'getModels');
}

export async function searchModels(filter: ModelSearchCriteria): Promise<ApiResult<ModelSummary[]>> {
    const url = getUrl(`/models/search`);
    const response = await apiFetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(filter)
    });
    return await parseResponse(response, identity, 'searchModels');
}

export async function getModel(model_id: string): Promise<ApiResult<Model>> {
    const url = getUrl(`/models/${model_id}`);
    const response = await apiFetch(url)
    return await parseResponse(response, toModel, 'getModel');
}

export async function updateModel(updated_model: Model): Promise<ApiResult<Model>> {
    const url = getUrl(`/models/${updated_model.id}`);
    const response = await apiFetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updated_model)
    });
    return await parseResponse(response, toModel, 'updateModel');
}

export async function syncModel(model_id: string): Promise<ApiResult<Operation>> {
    const url = getUrl(`/models/${model_id}/synchronize?simulate=false`);
    const response = await apiFetch(url, {
      method: 'POST'
    });
    return await parseResponse(response, identity, 'syncModel');
}

export async function getBaseModels(): Promise<ApiResult<string[]>> {
    const response = await apiFetch(getUrl('/models/base-models'));
    return await parseResponse(response, identity, 'getBaseModels');
}

export async function moveModel(model_id: string,
                                destination: ModelDestination): Promise<ApiResult<Operation>> {
    const url = getUrl(`/models/${model_id}/move?destination=${destination}&simulate=false`);
    const response = await apiFetch(url, {
      method: 'POST'
    });
    return await parseResponse(response, identity, 'moveModel');
}

export async function updateModelTags(ids: string[], add: string[],
                                      remove: string[]): Promise<ApiResult<Model[]>> {
    const response = await apiFetch(getUrl('/models/bulk/tags'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ids, add, remove})
    });
    return await parseResponse(response,
        value => value.models.map(toModel), 'updateModelTags');
}

export async function updateModelBaseModels(ids: string[],
                                            base_model: string): Promise<ApiResult<Model[]>> {
    const response = await apiFetch(getUrl('/models/bulk/base-model'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ids, base_model})
    });
    return await parseResponse(response,
        value => value.models.map(toModel), 'updateModelBaseModels');
}

export async function syncModels(ids: string[]): Promise<ApiResult<Operation>> {
    const response = await apiFetch(getUrl('/models/bulk/synchronize?simulate=false'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ids})
    });
    return await parseResponse(response, identity, 'syncModels');
}

export async function moveModels(ids: string[],
                                 destination: ModelDestination): Promise<ApiResult<Operation>> {
    const response = await apiFetch(getUrl(
        `/models/bulk/move?destination=${destination}&simulate=false`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ids})
    });
    return await parseResponse(response, identity, 'moveModels');
}

export async function getModelRelativePaths(typeId: string): Promise<ApiResult<string[]>> {
    const response = await apiFetch(getUrl(
        `/models/relative-paths?type_id=${encodeURIComponent(typeId)}`));
    return await parseResponse(response, identity, 'getModelRelativePaths');
}

export async function relocateModels(ids: string[], destination: string, simulate: boolean) {
    const response = await apiFetch(getUrl(`/models/relocate?simulate=${simulate}`), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ids, destination})
    });
    return await parseResponse<Record<string, any>>(response, identity, 'relocateModels');
}
