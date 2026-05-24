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

export async function getModels(): Promise<ModelSummary[]> {
    const url = getUrl('/models');
    const response = await fetch(url);
    return await parseResponse(response, identity, 'getModels');
}

export async function searchModels(criteria: ModelSearchCriteria): Promise<ModelSummary[]> {
    const url = gerUrl(`/models/search`);
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(criteria)
    });
    return await parseResponse(response, identity, 'searchModels');
}

export async function getModel(modelId: string): Promise<Model> {
    const url = new URL(`/models/${modelId}`, base_url);
    const response = await fetch(url)
    return await parseResponse(response, toModel, 'getModel');
}

export async function updateModel(updatedModel: ModelRecord): Promis<Model> {
    const url = new URL(`/models/${updatedModel.id}`, base_url);
    const response = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updatedModel)
    });
    return await parseResponse(response, toModel, 'updateModel');
}

