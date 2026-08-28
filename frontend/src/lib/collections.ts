/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/collections.ts
 * purpose: Collection handling
 * ---------------------------------------------------------------------------*/

import {
    type CollectionSummary,
    type Collection,
    identity } from "$lib/objects";

import {
    type ApiResult,
    getUrl,
    parseResponse } from "$lib/api";

export type CollectionSearchCriteria = {
    types: string[];
    collections: string[];
    required_tags: string[];
    forbiddenTags: string[];
    name: string;
}

export type CollectionInput = {
    name: string;
    purpose: string;
    tags: string[];
    models: string[];
    workflows: string[];
    children: string[];
};

export async function getCollections(): Promise<ApiResult<CollectionSummary[]>> {
    const url = getUrl('/collections');
    const response = await fetch(url);
    return await parseResponse(response, identity, 'getCollections');
}

export async function searchCollections(criteria: CollectionSearchCriteria): Promise<ApiResult<CollectionSummary[]>> {
    const url = getUrl('/collections/search');
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(criteria)
    });
    return await parseResponse(response, identity, 'searchCollections');
}

export async function getCollection(collectionId: string): Promise<ApiResult<Collection>> {
    const url = getUrl(`/collections/${collectionId}`);
    const response = await fetch(url)
    return await parseResponse(response, identity, 'getCollection');
}

export async function updateCollection(collectionId: string,
                                       updatedCollection: CollectionInput): Promise<ApiResult<CollectionSummary>> {
    const url = getUrl(`/collections/${collectionId}`);
    const response = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updatedCollection)
    });
    return await parseResponse(response, identity, 'updateCollection')
}

export async function createCollection(collection: CollectionInput): Promise<ApiResult<CollectionSummary>> {
    const url = getUrl('/collections');
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(collection)
    });
    return await parseResponse(response, identity, 'createCollection');
}

function collectionInput(collection: Collection): CollectionInput {
    return {
        name: collection.name,
        purpose: collection.purpose,
        tags: [...collection.tags],
        models: collection.models.map((model) => model.id),
        workflows: collection.workflows.map((workflow) => workflow.id),
        children: collection.children.map((child) => child.id)
    };
}

export async function addModelToCollection(collectionId: string,
                                           modelId: string): Promise<ApiResult<CollectionSummary>> {
    const current = await getCollection(collectionId);
    if (!current.ok) return current;
    const input = collectionInput(current.data);
    input.models.push(modelId);
    return await updateCollection(collectionId, input);
}

export async function removeModelFromCollection(collectionId: string,
                                                modelId: string): Promise<ApiResult<CollectionSummary>> {
    const current = await getCollection(collectionId);
    if (!current.ok) return current;
    const input = collectionInput(current.data);
    input.models = input.models.filter((id) => id !== modelId);
    return await updateCollection(collectionId, input);
}
