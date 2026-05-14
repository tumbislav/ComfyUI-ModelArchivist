/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/collections.ts
 * purpose: Collection handling
 * ---------------------------------------------------------------------------*/

import {
    CollectionSummary,
    Collection,
    get_url
} from "$lib/helpers";

export type CollectionSearchCriteria = {
    types: string[],
    collections: string[],
    required_tags: string[],
    forbiddenTags: string[],
    name: string
}

export async function getCollections(): Promise<CollectionSummary[]> {
    const url = get_url('/collections');
    const res = await fetch(url);
    if (!res.ok) {
        throw new Error(`GET /collections failed: ${res.status} ${res.statusText}`);
    }
    return await res.json();
}

export async functionSearchCollections(criteria: CollectionSearchCriteria): Promise<CollectionSummary[]> {
    const url = new URL(`/collections/search`, base_url);
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(criteria)
    });
    if (!res.ok) {
        throw new Error(`POST /collections/search failed: ${res.status} ${res.statusText}`);
    }
    return await res.json();
}

export async getCollection(collectionId: string): Promise<Collection> {
    const url = new URL(`/collections/${collectionId}`, base_url);
    const res = await fetch(url)
    if (!res.ok) {
        throw new Error(`GET /collection failed: ${res.status} ${res.statusText}`);
    }
    return await res.json(); /*TODO convert ISO string to date*/
}

export async function saveCollection(updatedCollection: CollectionRecord) {
    const url = new URL(`/collections/${updatedCollection.id}`, base_url);
    const res = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updatedCollection)
    });

    if (!res.ok) {
      throw new Error(`Could not save collection ${updatedCollection.name}`);
    }

    const saved = await res.json();
    return saved;
}
