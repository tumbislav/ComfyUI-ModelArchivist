/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/workflows.ts
 * purpose: Workflow handling
 * ---------------------------------------------------------------------------*/

import {
    WorkflowSummary,
    Workflow,
    get_url
} from "$lib/helpers";

export type WorkflowSearchCriteria = {
    types: string[],
    collections: string[],
    required_tags: string[],
    forbiddenTags: string[],
    name: string
}

export async function getWorkflows(): Promise<WorkflowSummary[]> {
    const url = get_url('/workflows');
    const res = await fetch(url);
    if (!res.ok) {
        throw new Error(`GET /workflows failed: ${res.status} ${res.statusText}`);
    }
    return await res.json();
}

export async functionSearchWorkflows(criteria: WorkflowSearchCriteria): Promise<WorkflowSummary[]> {
    const url = new URL(`/workflows/search`, base_url);
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(criteria)
    });
    if (!res.ok) {
        throw new Error(`POST /workflows/search failed: ${res.status} ${res.statusText}`);
    }
    return await res.json();
}

export async getWorkflow(workflowId: string): Promise<Workflow> {
    const url = new URL(`/workflows/${workflowId}`, base_url);
    const res = await fetch(url)
    if (!res.ok) {
        throw new Error(`GET /workflow failed: ${res.status} ${res.statusText}`);
    }
    return await res.json(); /*TODO convert ISO string to date*/
}

export async function saveWorkflow(updatedWorkflow: WorkflowRecord) {
    const url = new URL(`/workflows/${updatedWorkflow.id}`, base_url);
    const res = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updatedWorkflow)
    });

    if (!res.ok) {
      throw new Error(`Could not save workflow ${updatedWorkflow.name}`);
    }

    const saved = await res.json();
    return saved;
}
