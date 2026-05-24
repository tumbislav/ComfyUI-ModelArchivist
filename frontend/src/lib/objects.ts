/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/objects.ts
 * purpose: Common object types and helper functions
 * ---------------------------------------------------------------------------*/

/* General
 * ---------------------------------------------------------------------------*/

export enum PrimaryObjectType {
    MODEL = 'md',
    WORKFLOW = 'wf',
    COLLECTION = 'cl'
}

export function clone<T>(value: T): T {
    return structuredClone(value);
}

export function identity<T>(x: T): T { return x; }

/* Components / files
 * ---------------------------------------------------------------------------*/

export type Component = {
    id: string;
    where: string;
    file_name: string;
    file_dir: string;
    component_type: string;
    last_scanned: Date;
}

export function toComponent(json: any): Component {
    return {
        id: json.id,
        where: json.where,
        file_name: json.file_name,
        file_dir: json.file_dir,
        component_type: json.component_type,
        last_scanned: new Date(json.last_scanned)
    }
}

/* Models
 * ---------------------------------------------------------------------------*/

export type ModelSummary = {
    id: string;
    name: string;
    type: string;
    working: number;
    archived: number;
};

export type Model = {
    id: string;
    name: string;
    type: string;
    raw_type: string;
    relative_path: string;
    working_dir: string;
    archive_dir: string;
    working: number;
    archived: number;
    last_scanned: Date;
    components: Component[];
    tags: string[];
    collections: CollectionSummary[];
}

export function toModel(json: any): Model {
    return {
        id: json.id,
        name: json.name,
        type: json.type,
        raw_type: jason.raw_type,
        relative_path: json.relative_path,
        working_dir: json.working_dir,
        archive_dir: json.archive_dir,
        working: json.working,
        archived: json.archived,
        last_scanned: new Date(json.last_scanned),
        components: json.components.map(toComponent),
        tags: json.tags,
        collections: json.collections
    }
}

/* Workflows
 * ---------------------------------------------------------------------------*/

export type WorkflowSummary = {
    id: string;
    name: string;
    working: number;
    archived: number;
}

export type Workflow = {
    id: string;
    name: string;
    purpose: string;
    relative_path: str;
    archived: number;
    working: number;
    last_scanned: Date;
    components: Component[];
    tags: string[];
    collections: CollectionSummary[];
}

export function toWorkflow(json: any): Workflow {
    return {
        id: json.id,
        name: json.name,
        purpose: json.purpose,
        relative_path: json.relative_path,
        archived: json.archived,
        working: json.working,
        last_scanned: new Date(json.last_scanned),
        components: json.components.map(toComponent),
        tags: json.tags,
        collections: json.collections
    }
}

/* Collections
 * ---------------------------------------------------------------------------*/

export type CollectionSummary = {
    id: string;
    name: string;
}

export type Collection = {
    id: string;
    name: string
    purpose: string;
    working: boolean;
    archived: boolean;
    tags: string[];
    models: ModelSummary[];
    workflows: WorkflowSummary[];
    contained_in: CollectionSummary[];
    contains: CollectionSummary[];
}

/* Tags
 * ---------------------------------------------------------------------------*/

export type Tag = {
    tag: string;
    models: ModelSummary[];
    workflows: WorkflowSummary[];
    collections: CollectionSummary[];
}

