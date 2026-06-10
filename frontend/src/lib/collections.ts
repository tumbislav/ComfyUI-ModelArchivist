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

export async function getCollections(): Promise<CollectionSummary[]> {
    const url = getUrl('/collections');
    const response = await fetch(url);
    return await parseResponse(response, identity, 'getCollections');
}

export async function searchCollections(criteria: CollectionSearchCriteria): Promise<CollectionSummary[]> {
    const url = getUrl('/collections/search');
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(criteria)
    });
    return await parseResponse(response, identity, 'searchCollections');
}

export async function getCollection(collectionId: string): Promise<Collection> {
    const url = getUrl(`/collections/${collectionId}`);
    const response = await fetch(url)
    return await parseResponse(response, identity, 'getCollection');
}

export async function updateCollection(updatedCollection: Collection): Promise<Collection> {
    const url = getUrl(`/collections/${updatedCollection.id}`);
    const response = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updatedCollection)
    });
    return await parseResponse(response, identity, 'updateCollection')
}
