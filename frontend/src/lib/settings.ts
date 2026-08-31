/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: settings.ts
 * purpose: Settings API types and operations
 * ---------------------------------------------------------------------------*/

import { getUrl, parseResponse, type ApiResult } from '$lib/api';

export type RepositoryLocation = {
    id?: string;
    working_dir: string;
    archive_dir: string | null;
    source?: 'standalone' | 'comfyui';
    active?: boolean;
};

export type ModelTypeSetting = {
    name: string;
    display_name: string;
    extensions: string[];
    locations: RepositoryLocation[];
};

export type RepositorySettings = {
    mode: 'standalone' | 'comfyui';
    setup_complete: boolean;
    options: {
        update_json_metadata: boolean;
        ignore_unknown_types: boolean;
        always_recalc_hashes: boolean;
    };
    model_types: ModelTypeSetting[];
    workflow_locations: RepositoryLocation[];
};

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<ApiResult<T>> {
    const response = await fetch(getUrl(path), {
        method,
        headers: body === undefined ? undefined : {'Content-Type': 'application/json'},
        body: body === undefined ? undefined : JSON.stringify(body)
    });
    return await parseResponse<T>(response, value => value, path);
}

export const getRepositorySettings = () => request<RepositorySettings>('/config/repository');

export const saveModelSettings = (model_types: ModelTypeSetting[]) =>
    request<RepositorySettings>('/config/models', 'PUT', {model_types});

export const saveWorkflowSettings = (workflow_locations: RepositoryLocation[]) =>
    request<RepositorySettings>('/config/workflows', 'PUT', {workflow_locations});
