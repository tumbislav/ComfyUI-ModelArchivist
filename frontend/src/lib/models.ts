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

import {
    type ApiResult,
    getUrl,
    parseResponse } from "$lib/api";

export type ModelSearchCriteria = {
    types: string[];
    collections: string[];
    required_tags: string[];
    forbidden_tags: string[];
    name_like: string;
}

export async function getModels(): Promise<ApiResult<ModelSummary[]>> {
    const url = getUrl('/models');
    const response = await fetch(url);
    return await parseResponse(response, identity, 'getModels');
}

export async function searchModels(criteria: ModelSearchCriteria): Promise<ApiResult<ModelSummary[]>> {
    const url = getUrl(`/models/search`);
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(criteria)
    });
    return await parseResponse(response, identity, 'searchModels');
}

export async function getModel(model_id: string): Promise<ApiResult<Model>> {
    const url = getUrl(`/models/${model_id}`);
    const response = await fetch(url)
    return await parseResponse(response, toModel, 'getModel');
}

export async function updateModel(updated_model: Model): Promise<ApiResult<Model>> {
    const url = getUrl(`/models/${updated_model.id}`);
    const response = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updated_model)
    });
    return await parseResponse(response, toModel, 'updateModel');
}

export async function syncModel(model_id: string): Promise<ApiResult<Model>> {
    const url = getUrl(`/models/${model_id}/deployment`);
    const response = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({deployment: 'synced'})
    });
    return await parseResponse(response, toModel, 'syncModel');
}
