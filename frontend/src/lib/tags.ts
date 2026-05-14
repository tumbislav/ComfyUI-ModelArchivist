/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/workflows.ts
 * purpose: Tag handling
 * ---------------------------------------------------------------------------*/

import {
    Tag,
    get_url
} from "$lib/helpers";

export type TagSearchCriteria = {
    types: string[],
    collections: string[],
    required_tags: string[],
    forbiddenTags: string[],
    name: string
}

export interface GetTagsOptions {
    targets?: Iterable<PrimaryObjectType>;
    offset?: number;
    limit?: number;
}

export async getTag(tag: string): Promise<Tag> {
    const url = new URL(`/tags/${tag}`, base_url);
    const res = await fetch(url)
    if (!res.ok) {
        throw new Error(`GET /tag failed: ${res.status} ${res.statusText}`);
    }
    return await res.json();
}

export async function getTags(target: str, offset?: number, limit?: number): Promise<string[]> {
    const url = get_url('/tags');

    if (target) {  url.searchParams.set("target", target); }
    if (offset) { url.searchParams.set("offset", offset); }
    if (limit) { url.searchParams.set("limit", limit); }

    const res = await fetch(url.toString(), {
            method: "GET",
            headers: { Accept: "application/json" }
        }
    );

    if (!res.ok) {
        throw new Error(`GET /tags failed: ${res.status} ${res.statusText}`);
    }
    return await res.json();
}
