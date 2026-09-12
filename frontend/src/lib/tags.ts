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

import { apiFetch,
    type ApiResult,
    getUrl,
    parseResponse
} from '$lib/api';
import { locale } from '$lib/locale.svelte';

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
    const response = await apiFetch(url);
    return await parseResponse(response, identity, 'getTag');
}

export async function getTags(targets: PrimaryObjectType[], offset?: number, limit?: number): Promise<ApiResult<string[]>> {
    const url = getUrl('/tags');
    
    if (targets.length > 0) { url.searchParams.append('targets', targets.join(',')); }
    if (offset) { url.searchParams.append('offset', offset.toString()); }
    if (limit) { url.searchParams.append('limit', limit.toString()); }

    const response = await apiFetch(url);
    return await parseResponse(response, identity, 'getTags');
}

export type TagsContext = {
    all_tags: string[];
    loading: boolean;
    error: string | null;
    refresh: () => Promise<void>;
}

export const [getTagsContext, setTagsContext] = createContext<TagsContext>();

let tagPattern: RegExp | null = null;
let rulesRequest: Promise<void> | null = null;

export async function loadTagRules(): Promise<void> {
    if (!rulesRequest) {
        rulesRequest = (async () => {
            const response = await apiFetch(getUrl('/tags/rules'));
            const result = await parseResponse<{pattern: string}>(response, identity, 'tagRules');

            if (!result.ok) {
                throw new Error(result.message ?? locale.t('errors.load_tag_rules'));
            }

            tagPattern = new RegExp(result.data.pattern, 'u');
        })().catch(error => {
            rulesRequest = null;
            throw error;
        });
    }

    await rulesRequest;
}

export function normalizeTag(value: string): string | null {
    const trimmed = value.replace(/ +$/, '');

    if (!tagPattern?.test(trimmed)) {
        return null;
    }

    return trimmed.normalize('NFKC');
}

export type TagUsage = {
    tag: string;
    models: number;
    workflows: number;
    user_objects: number;
    collections: number;
};

export type TagRemapResult = {
    applied: string[];
    skipped: {source: string; code: string; message: string}[];
    errors: {code: string; message: string}[];
};

export async function getTagUsage(): Promise<ApiResult<TagUsage[]>> {
    return await parseResponse(await apiFetch(getUrl('/tags/usage')), identity, 'tagUsage');
}

export async function remapTags(mappings: Record<string, string>): Promise<ApiResult<import('$lib/models').Operation>> {
    const response = await apiFetch(getUrl('/tags/remap'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({mappings})
    });

    return await parseResponse(response, identity, 'remapTags');
}
