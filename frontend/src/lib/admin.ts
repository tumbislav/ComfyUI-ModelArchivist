/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/admin.ts
 * purpose: Interface to admin functionalities
 * ---------------------------------------------------------------------------*/

import { identity } from "$lib/objects";
import {
    getUrl,
    parseResponse,
    type ApiResult
} from "$lib/api";
import { type Operation } from '$lib/models';

export type ActiveTab = 'models' | 'workflows' | 'user' | 'collections' | null;

export type ServerStatus = {
    started: boolean,
    ready: boolean,
    read_only: boolean,
    setup_required?: boolean,
    mode?: 'standalone' | 'comfyui',
    first_run?: boolean,
    scanning?: boolean
}

function toServerStatus(json: any): ServerStatus {
    return {
        started: json.started,
        ready: json.ready,
        read_only: json.read_only,
        ...('setup_required' in json ? {setup_required: json.setup_required} : {}),
        ...('mode' in json ? {mode: json.mode} : {}),
        ...('first_run' in json ? {first_run: json.first_run} : {}),
        ...('scanning' in json ? {scanning: json.scanning} : {})
    }
}

export async function getServerStatus(): Promise<ApiResult<ServerStatus>> {
    const url = getUrl('/server-status');
    const response = await fetch(url);
    return await parseResponse(response, toServerStatus, 'getServerStatus')
}

export type ScanStatus = {
    started: boolean,
    finished: boolean,
    start_time?: Date,
    end_time?: Date,
    duration?: number,
    models_scanned: number,
    workflows_scanned: number,
    hashes_calculated: number
}

function toScanStatus(json: any): ScanStatus {
    return {
        started: json.started,
        finished: json.finished,
        ...('start_time' in json ? {start_time: new Date(json.start_time)} : {}),
        ...('end_time' in json ? {end_time: new Date(json.end_time)} : {}),
        ...('duration' in json ? {duration: json.duration} : {}),
        models_scanned: json.models_scanned,
        workflows_scanned: json.workflows_scanned,
        hashes_calculated: json.hashes_calculated
    }
}

export async function startScan(): Promise<ApiResult<Operation>> {
    const url = getUrl('/scan');
    const response = await fetch(url,{
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    });
    return await parseResponse(response, identity, 'startScan');
}

export async function getScanStatus(scan_timestamp: string): Promise<ApiResult<ScanStatus>> {
    const url = getUrl(`/scan/${scan_timestamp}`);
    const response = await fetch(url);
    return await parseResponse(response, toScanStatus, 'getScanStatus');
}
