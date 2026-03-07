/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/api.ts
 * purpose: REST interface to back end
 * ---------------------------------------------------------------------------*/

/* Object types that map to back-end types -----------------------------------*/

export type PrimaryObjectType = 'model' | 'workflow' | 'collection';

export type ModelRecord = {
    hash: string,
    name: string,
    type: string,
    active: boolean,
    archived: boolean
};

export interface GetTagsOptions {
    targets?: Iterable<PrimaryObjectType>;
    offset?: number;
    limit?: number;
    }

const base_url = "http://127.0.0.1:5173";

export async function getModels(): Promise<ModelRecord[]> {
    const url = new URL('/models', base_url);
    const res = await fetch(url);
    if (!res.ok) {
        throw new Error(`GET /models failed: ${res.status} ${res.statusText}`);
    }
    return await res.json();
}

export async function getModelsRescan(): Promise<ModelRecord[]> {
    const url = new URL('/models?rescan=true', base_url);
    const res = await fetch(url);
    if (!res.ok) {
        throw new Error(`GET /models failed: ${res.status} ${res.statusText}`);
    }
    return await res.json();
}

export async function getTags(target: str, offset?: number, limit?: number): Promise<string[]> {
    const url = new URL('tags', base_url);

    if (target) {
        url.searchParams.set("target", target);
    }
    if (offset) {
        url.searchParams.set("offset", offset);
    }
    if (limit) {
        url.searchParams.set("limit", limit);
    }

    const res = await fetch(url.toString(),
        {
            method: "GET",
            headers: { Accept: "application/json" }
        }
    );

    if (!res.ok) {
        throw new Error(`GET /tags failed: ${res.status} ${res.statusText}`);
    }
    return await res.json();
}
