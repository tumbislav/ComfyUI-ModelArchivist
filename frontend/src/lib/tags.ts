/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/workflows.ts
 * purpose: Tag handling
 * ---------------------------------------------------------------------------*/

import {
    type Tag,
    PrimaryObjectType,
    identity
} from '$lib/objects';

import {
    type ApiResult,
    getUrl,
    parseResponse
} from '$lib/api';

import { createContext } from 'svelte';

export type TagSearchCriteria = {
    types: string[],
    collections: string[],
    required_tags: string[],
    forbiddenTags: string[],
    name: string
}

export async function getTag(tag: string): Promise<ApiResult<Tag>> {
    const url = getUrl(`/tags/${tag}`);
    const response = await fetch(url);
    return await parseResponse(response, identity, 'getTag');
}

export async function getTags(targets: PrimaryObjectType[], offset?: number, limit?: number): Promise<ApiResult<string[]>> {
    const url = getUrl('/tags');
    
    if (targets.length > 0) { url.searchParams.append('targets', targets.join(',')); }
    if (offset) { url.searchParams.append('offset', offset.toString()); }
    if (limit) { url.searchParams.append('limit', limit.toString()); }

    const response = await fetch(url);
    return await parseResponse(response, identity, 'getTags');
}

export type TagsContext = {
    all_tags: string[];
    loading: boolean;
    error: string | null;
    refresh: () => Promise<void>;
}

export const [getTagsContext, setTagsContext] = createContext<TagsContext>();