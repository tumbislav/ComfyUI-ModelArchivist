/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/session.ts
 * purpose: Tab-scoped launcher credentials for same-origin Archivist requests
 * ---------------------------------------------------------------------------*/

const storageKey = 'archivist.access';
type Access = { session?: string; user?: string };
let access: Access | undefined;

function initialize(): Access {
    if (access) return access;
    if (typeof window === 'undefined') return {};

    const fragment = new URLSearchParams(window.location.hash.slice(1));
    if (fragment.has('archivist-session') || fragment.has('comfy-user')) {
        access = fragment.has('archivist-session')
            ? { session: fragment.get('archivist-session') ?? '' }
            : { user: fragment.get('comfy-user') ?? '' };
        // Remove credentials before any requests, navigation, or application rendering.
        window.history.replaceState(window.history.state, '',
            window.location.pathname + window.location.search);
        try {
            window.sessionStorage.setItem(storageKey, JSON.stringify(access));
        } catch {
            // In-memory access still works when storage is unavailable.
        }
    } else {
        try {
            const saved = JSON.parse(window.sessionStorage.getItem(storageKey) ?? '{}');
            access = {
                session: typeof saved?.session === 'string' ? saved.session : undefined,
                user: typeof saved?.user === 'string' ? saved.user : undefined
            };
        } catch {
            access = {};
        }
    }
    return access;
}

export function sessionHeaders(input: RequestInfo | URL, init: RequestInit): Headers {
    const headers = new Headers(init.headers ?? (input instanceof Request ? input.headers : undefined));
    const current = initialize();
    if (typeof window === 'undefined') return headers;

    const url = new URL(input instanceof Request ? input.url : String(input), window.location.href);
    if (url.origin !== window.location.origin || !url.pathname.startsWith('/model-archivist/api/')) {
        throw new Error('Archivist credentials may only be sent to its same-origin API.');
    }
    headers.set('X-Archivist-Request', '1');
    headers.delete('X-Archivist-Internal');
    headers.delete('X-Archivist-Session');
    headers.delete('Comfy-User');
    if (current.session) headers.set('X-Archivist-Session', current.session);
    if (current.user) headers.set('Comfy-User', current.user);
    return headers;
}

// This module is loaded before components issue their initial requests.
initialize();
