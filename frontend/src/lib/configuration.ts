/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/configuration.ts
 * purpose: Read-only application configuration API
 * ---------------------------------------------------------------------------*/

import { type ApiResult, getUrl, parseResponse } from '$lib/api';
import { identity } from '$lib/objects';


export type ConfigOption = {
    value: string;
    label: string;
};

export async function getFileFormats(): Promise<ApiResult<string[]>> {
    const response = await fetch(getUrl('/config/file_formats'));
    return await parseResponse(response, identity, 'getFileFormats');
}


export async function getModelTypes(): Promise<ApiResult<ConfigOption[]>> {
    const response = await fetch(getUrl('/config/model_types'));
    return await parseResponse(response, identity, 'getModelTypes');
}
