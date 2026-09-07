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
        let message = response.statusText;
        try {
            const contentType = response.headers.get('content-type');
            if (contentType?.includes('application/json')) {
                const body = await response.json();
                if (typeof body?.detail === 'string') message = body.detail;
                else if (Array.isArray(body?.detail)) {
                    message = body.detail.map((item: any) => item.msg ?? JSON.stringify(item)).join('; ');
                }
            } else {
                const body = await response.text();
                if (body) message = body;
            }
        } catch {
            // Preserve the HTTP reason phrase if the error body cannot be decoded.
        }
        return {
            ok: false,
            status: response.status,
            message,
            in_function: caller
        }
    }
}
