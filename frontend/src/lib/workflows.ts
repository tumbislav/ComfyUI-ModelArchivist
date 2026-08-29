/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/workflows.ts
 * purpose: Workflow handling
 * ---------------------------------------------------------------------------*/

import { identity, toWorkflow, type Workflow, type WorkflowSummary } from '$lib/objects';
import { getUrl, parseResponse, type ApiResult } from '$lib/api';

export type WorkflowSearchCriteria = {
    required_tags: string[];
    forbidden_tags: string[];
    name_prefix: string;
};

export type WorkflowDestination = 'working' | 'archive';

export async function getWorkflows(): Promise<ApiResult<WorkflowSummary[]>> {
    const response = await fetch(getUrl('/workflows'));
    return await parseResponse(response, identity, 'getWorkflows');
}

export async function searchWorkflows(criteria: WorkflowSearchCriteria):
    Promise<ApiResult<WorkflowSummary[]>> {
    const response = await fetch(getUrl('/workflows/search'), {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(criteria)
    });
    return await parseResponse(response, identity, 'searchWorkflows');
}

export async function getWorkflow(id: string): Promise<ApiResult<Workflow>> {
    const response = await fetch(getUrl(`/workflows/${id}`));
    return await parseResponse(response, toWorkflow, 'getWorkflow');
}

export async function updateWorkflow(workflow: Workflow): Promise<ApiResult<Workflow>> {
    const response = await fetch(getUrl(`/workflows/${workflow.id}`), {
        method: 'PUT', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(workflow)
    });
    return await parseResponse(response, toWorkflow, 'updateWorkflow');
}

async function workflowOperation(path: string): Promise<ApiResult<Record<string, any>>> {
    const response = await fetch(getUrl(path), {method: 'POST'});
    return await parseResponse(response, identity, 'workflowOperation');
}

export async function syncWorkflow(id: string) {
    return workflowOperation(`/workflows/${id}/synchronize?simulate=false`);
}

export async function moveWorkflow(id: string, destination: WorkflowDestination) {
    return workflowOperation(`/workflows/${id}/move?destination=${destination}&simulate=false`);
}

export async function updateWorkflowTags(ids: string[], add: string[], remove: string[]) {
    const response = await fetch(getUrl('/workflows/bulk/tags'), {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ids, add, remove})
    });
    return await parseResponse<Workflow[]>(response,
        value => value.workflows.map(toWorkflow), 'updateWorkflowTags');
}

export async function syncWorkflows(ids: string[]) {
    const response = await fetch(getUrl('/workflows/bulk/synchronize?simulate=false'), {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ids})
    });
    return await parseResponse<Record<string, any>>(response, identity, 'syncWorkflows');
}

export async function moveWorkflows(ids: string[], destination: WorkflowDestination) {
    const response = await fetch(getUrl(
        `/workflows/bulk/move?destination=${destination}&simulate=false`), {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ids})
    });
    return await parseResponse<Record<string, any>>(response, identity, 'moveWorkflows');
}
