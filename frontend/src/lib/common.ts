/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/common.ts
 * purpose: Common types, helper funcions
 * ---------------------------------------------------------------------------*/


/* Object types
 * ---------------------------------------------------------------------------*/

export type PrimaryObjectType = 'model' | 'workflow' | 'collection';

export type Component = {
    is_archive: boolean,
    file_name: string,
    file_dir: string,
    component_type: string,
    last_scanned: Date
}

export type ModelSummary = {
    id: string,
    name: string,
    type: string,
    active: boolean,
    archived: boolean
};

export type Model = {
    id: string,
    name: string,
    type: string,
    raw_type: string,
    relative_path: string,
    active_type_dir: string,
    archive_type_dir: string,
    is_active: boolean,
    is_archived: boolean,
    last_scanned: Date,
    components: Component[],
    tags: string[],
    collections: CollectionSummary[]
}

export type WorkflowSummary = {
    id: string,
    name: string,
    active: boolean,
    archived: boolean
}

export type Workflow = {
    id: string,
    name: string,
    purpose: string,
    relative_path: str,
    is_archived: bool,
    is_active: bool,
    last_scanned: Date,
    components: Component[],
    tags: string[],
    collections: CollectionSummary[]
}

export type CollectionSummary = {
    id: int,
    name: string
}

export type Collection = {
    id: int,
    name: string
    purpose: string,
    is_active: boolean,
    tags: string[],
    models: ModelSummary[],
    workflows: WorkflowSummary[],
    parent_collections: CollectionSummary[],
    child_collections: CollectionSummary[]
}

export type Tag = {
    tag: string,
    models: ModelSummary[],
    workflows: WorkflowSummary[],
    collections: CollectionSummary[]
}

/* Helper functions
 * ---------------------------------------------------------------------------*/

export function clone<T>(value: T): T {
    return structuredClone(value);
}

/* Web interface related
 * ---------------------------------------------------------------------------*/

const base_url = "http://127.0.0.1:5173";

export function get_url(ext: string): {
    return new URL(ext, base_url);
}