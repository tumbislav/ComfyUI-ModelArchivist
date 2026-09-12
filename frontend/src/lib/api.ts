/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/api.ts
 * purpose: Helper types and functions for API
 * ---------------------------------------------------------------------------*/


/* Calling APIs
 * ---------------------------------------------------------------------------*/

import { writable } from 'svelte/store';
import { locale } from '$lib/locale.svelte';

const API_PREFIX = '/model-archivist/api';
export const API_TIMEOUT_MS = 3000;
export const serverUnresponsive = writable(false);
let requestSequence = 0;
let lastFailedRequest = 0;

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {},
                               timeoutMs: number | null = API_TIMEOUT_MS): Promise<Response> {
    const sequence = ++requestSequence;
    const controller = new AbortController();
    const cancel = () => controller.abort(init.signal?.reason);
    init.signal?.addEventListener('abort', cancel, { once: true });
    if (init.signal?.aborted) cancel();

    const timer = timeoutMs === null ? null : setTimeout(
        () => controller.abort(new DOMException('Request timed out', 'TimeoutError')),
        timeoutMs);

    try {
        const response = await globalThis.fetch(input, { ...init, signal: controller.signal });
        // Include the response body in the timeout, not just the arrival of headers.
        const body = await response.arrayBuffer();

        if ([408, 502, 503, 504].includes(response.status)) {
            lastFailedRequest = Math.max(lastFailedRequest, sequence);
            serverUnresponsive.set(true);
        } else if (sequence > lastFailedRequest) {
            serverUnresponsive.set(false);
        }

        return new Response([204, 205, 304].includes(response.status) ? null : body, {
            status: response.status,
            statusText: response.statusText,
            headers: response.headers
        });
    } catch {
        const cancelled = init.signal?.aborted;
        if (!cancelled) {
            lastFailedRequest = Math.max(lastFailedRequest, sequence);
            serverUnresponsive.set(true);
        }

        return new Response(JSON.stringify({ detail: cancelled
            ? locale.t('errors.request_cancelled') : locale.t('errors.server_unresponsive') }), {
            status: cancelled ? 499 : 503,
            headers: { 'Content-Type': 'application/json' }
        });
    } finally {
        if (timer !== null) clearTimeout(timer);
        init.signal?.removeEventListener('abort', cancel);
    }
}

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
                else if (typeof body?.detail?.message === 'string') message = body.detail.message;
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
