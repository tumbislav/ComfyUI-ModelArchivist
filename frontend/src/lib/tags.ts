/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/workflows.ts
 * purpose: Tag handling
 * ---------------------------------------------------------------------------*/

import {
    type Tag,
    PrimaryObjectType,
    identity } from "$lib/objects";

import {
    type ApiResult,
    getUrl,
    parseResponse } from "$lib/api";

export type TagSearchCriteria = {
    types: string[],
    collections: string[],
    required_tags: string[],
    forbiddenTags: string[],
    name: string
}

export async function getTag(tag: string): Promise<Tag> {
    const url = getUrl(`/tags/${tag}`);
    const res = await fetch(url);
    return await parseResponse(response, identity, 'getTag');
}

export async function getTags(targets: PrimaryObjectType[], offset?: number, limit?: number): Promise<string[]> {
    const url = getUrl('/tags');

    if (targets.length > 0) { url.searchParams.set('target', targets.join()); }
    if (offset) { url.searchParams.set('offset', offset); }
    if (limit) { url.searchParams.set('limit', limit); }

    const response = await fetch(url);
    return await parseResponse(response, identity, 'getTags');
}
