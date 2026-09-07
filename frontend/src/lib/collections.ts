/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/collections.ts
 * purpose: Collection handling
 * ---------------------------------------------------------------------------*/

import {
    type CollectionSummary,
    type CollectionOverview,
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
    user_objects?: string[];
    children: string[];
};

export async function getCollections(): Promise<ApiResult<CollectionOverview[]>> {
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

export function collectionInput(collection: Collection): CollectionInput {
    return {
        name: collection.name,
        purpose: collection.purpose,
        tags: [...collection.tags],
        models: collection.models.map((model) => model.id),
        workflows: collection.workflows.map((workflow) => workflow.id),
        user_objects: collection.user_objects.map((item) => item.id),
        children: collection.children.map((child) => child.id)
    };
}

export type MemberField = 'models' | 'workflows' | 'user_objects' | 'children';
export type CollectionMember = {id: string; name: string; has_archive: boolean; has_working: boolean};
export type MemberSegment = {id: string; name: string; field: MemberField;
    members: CollectionMember[]; candidates: CollectionMember[]};
export type CollectionOperationResult = {allowed: boolean; performed?: boolean;
    errors?: {code: string; message: string}[]; warnings?: {code: string; message: string}[];
    members?: CollectionOperationResult[]};

export async function getCollectionMembers(id: string): Promise<ApiResult<MemberSegment[]>> {
    const response = await fetch(getUrl(`/collections/${id}/members`));
    return await parseResponse(response, identity, 'getCollectionMembers');
}

export async function operateCollection(id: string, destination: 'working' | 'archive' | null):
    Promise<ApiResult<import('$lib/models').Operation | CollectionOperationResult>> {
    const action = destination === null ? 'synchronize?simulate=false'
        : `move?simulate=false&destination=${destination}`;
    const response = await fetch(getUrl(`/collections/${id}/${action}`), {method: 'POST'});
    return await parseResponse(response, identity, 'operateCollection');
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

export async function updateCollectionModels(collectionId: string, modelIds: string[],
                                             add: boolean): Promise<ApiResult<CollectionSummary>> {
    const response = await fetch(getUrl(`/collections/${collectionId}/models`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({model_ids: modelIds, add})
    });
    return await parseResponse(response, identity, 'updateCollectionModels');
}

export async function updateCollectionWorkflows(collectionId: string, workflowIds: string[],
                                                add: boolean): Promise<ApiResult<CollectionSummary>> {
    const response = await fetch(getUrl(`/collections/${collectionId}/workflows`), {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({workflow_ids: workflowIds, add})
    });
    return await parseResponse(response, identity, 'updateCollectionWorkflows');
}

export async function updateCollectionUserObjects(collectionId: string, userObjectIds: string[],
                                                  add: boolean): Promise<ApiResult<CollectionSummary>> {
    const response = await fetch(getUrl(`/collections/${collectionId}/user-objects`), {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user_object_ids: userObjectIds, add})
    });
    return await parseResponse(response, identity, 'updateCollectionUserObjects');
}
