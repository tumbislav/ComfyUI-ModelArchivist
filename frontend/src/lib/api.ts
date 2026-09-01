/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/api.ts
 * purpose: Helper types and functions for API
 * ---------------------------------------------------------------------------*/


/* Calling APIs
 * ---------------------------------------------------------------------------*/

const API_PREFIX = '/model-archivist/api';

export function getUrl(resource: string): URL {
    const origin = typeof window === 'undefined' ? 'http://127.0.0.1' : window.location.origin;
    return new URL(`${API_PREFIX}${resource.startsWith('/') ? resource : `/${resource}`}`, origin);
}

/* Response handling
 * ---------------------------------------------------------------------------*/

export type ApiResult<T> =
    | { ok: true;
        data: T; }
    | { ok: false;
        status?: number;
        message?: string;
        in_function?: string};

export async function parseResponse<T>(response: Response, packager: (x: any) => any, caller: string): Promise<ApiResult<T>> {
    if (response.ok) {
        const content_type = response.headers.get('content-type');
        if (content_type?.includes('application/json')) {
            return {
                ok: true,
                data: packager(await response.json())
            }
        }
        else {
            return {
                ok: true,
                data: packager(await response.text())
            }
        }
    }
    else {
        return {
            ok: false,
            status: response.status,
            message: response.statusText,
            in_function: caller
        }
    }
}
