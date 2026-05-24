/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/workflows.ts
 * purpose: Workflow handling
 * ---------------------------------------------------------------------------*/

import {
    type WorkflowSummary,
    type Workflow,
    identity } from "$lib/objects";

import {
    type ApiResult,
    getUrl,
    parseResponse } from "$lib/api";

export type WorkflowSearchCriteria = {
    types: string[];
    collections: string[];
    required_tags: string[];
    forbiddenTags: string[];
    name: string;
}

export async function getWorkflows(): Promise<WorkflowSummary[]> {
    const url = getUrl('/workflows');
    const response = await fetch(url);
    return await parseResponse(response, identity, 'getWorkflows')
}

export async function searchWorkflows(criteria: WorkflowSearchCriteria): Promise<WorkflowSummary[]> {
    const url = getUrl(`/workflows/search`);
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(criteria)
    });
    return await parseResponse(response, identity, searchWorkflows);
}

export async function getWorkflow(workflowId: string): Promise<Workflow> {
    const url = getUrl(`/workflows/${workflowId}`);
    const response = await fetch(url)
    return await parseResponse(response, toWorkflow, 'getWorkflow')
}

export async function updateWorkflow(updatedWorkflow: Workflow): Promise<Workflow> {
    const url = getUrl(`/workflows/${updatedWorkflow.id}`);
    const response = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updatedWorkflow)
    });
    return await parseResponse(response, toWorkflow, 'updateWorkflow')
}
