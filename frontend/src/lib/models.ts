/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/models.ts
 * purpose: Model handling
 * ---------------------------------------------------------------------------*/

import {
    ModelSummary,
    Model,
    get_url
} from "$lib/helpers";

export type ModelSearchCriteria = {
    types: string[],
    collections: string[],
    required_tags: string[],
    forbiddenTags: string[],
    name: string
}

export async function getModels(): Promise<ModelSummary[]> {
    const url = get_url('/models');
    const res = await fetch(url);
    if (!res.ok) {
        throw new Error(`GET /models failed: ${res.status} ${res.statusText}`);
    }
    return await res.json();
}

export async functionSearchModels(criteria: ModelSearchCriteria): Promise<ModelSummary[]> {
    const url = new URL(`/models/search`, base_url);
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(criteria)
    });
    if (!res.ok) {
        throw new Error(`POST /models/search failed: ${res.status} ${res.statusText}`);
    }
    return await res.json();
}

export async getModel(modelId: string): Promise<Model> {
    const url = new URL(`/models/${modelId}`, base_url);
    const res = await fetch(url)
    if (!res.ok) {
        throw new Error(`GET /model failed: ${res.status} ${res.statusText}`);
    }
    return await res.json(); /*TODO convert ISO string to date*/
}

export async function saveModel(updatedModel: ModelRecord) {
    const url = new URL(`/models/${updatedModel.id}`, base_url);
    const res = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updatedModel)
    });

    if (!res.ok) {
      throw new Error(`Could not save model ${updatedModel.name}`);
    }

    const saved = await res.json();
    return saved;
}

