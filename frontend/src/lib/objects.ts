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

export function identity<T>(x: T): T { return x; }

/* Components  and component sets
 * ---------------------------------------------------------------------------*/

export type Component = {
    id: string;
    file_name: string;
    component_type: string;
    touched: Date;
}

export function toComponent(json: any): Component {
    return {
        id: json.id,
        file_name: json.file_name,
        component_type: json.component_type,
        touched: new Date(json.touched)
    }
}

export type ComponentSet = {
    id: string;
    where: string;
    primary_dir: string;
    examples_dir?: string;
    components: Component[];
}

export function toComponentSet(json: any): ComponentSet {
    return {
        id: json.id,
        where: json.where,
        primary_dir: json.primary_dir,
        examples_dir: json.examples_dir,
        components: json.components.map(toComponent)
    }
}

/* Models
 * ---------------------------------------------------------------------------*/

export type ModelSummary = {
    id: string;
    file_name: string;
    internal_name: string;
    type: string;
    file_format: string;
    deployment: string;
};

export type Model = {
    id: string;
    file_name: string;
    internal_name: string;
    type: string;
    raw_type: string;
    file_format: string;
    relative_path: string;
    working_path: string | null;
    archive_path: string | null;
    deployment: string;
    touched: Date;
    tags: string[];
    working_set?: ComponentSet;
    archive_set?: ComponentSet;
    collections: CollectionSummary[];
}

export function toModel(json: any): Model {
    return {
        id: json.id,
        file_name: json.file_name,
        internal_name: json.internal_name,
        type: json.type,
        raw_type: json.raw_type,
        file_format: json.file_format,
        relative_path: json.relative_path,
        working_path: json.working_path,
        archive_path: json.archive_path,
        deployment: json.deployment,
        touched: new Date(json.touched),
        tags: json.tags,
        working_set: json.working_set ? toComponentSet(json.working_set) : undefined,
        archive_set: json.archive_set ? toComponentSet(json.archive_set) : undefined,
        collections: json.collections
    }
}

export function toModelSummary(model: any): ModelSummary {
    return {
        id: model.id,
        file_name: model.file_name,
        internal_name: model.internal_name,
        type: model.type,
        file_format: model.file_format,
        deployment: model.deployment
    }
}

/* Workflows
 * ---------------------------------------------------------------------------*/

export type WorkflowSummary = {
    id: string;
    internal_name: string;
    file_name: string;
    purpose: string;
    deployment: string;
    errors: string[];
    read_only: boolean;
}

export type Workflow = {
    id: string;
    file_name: string;
    internal_name: string;
    purpose: string;
    relative_path: string;
    working_path: string | null;
    archive_path: string | null;
    deployment: string;
    touched: Date;
    working_set?: ComponentSet;
    archive_set?: ComponentSet;
    tags: string[];
    collections: CollectionSummary[];
    errors: string[];
    read_only: boolean;
}

export function toWorkflow(json: any): Workflow {
    return {
        id: json.id,
        file_name: json.file_name,
        internal_name: json.internal_name,
        purpose: json.purpose,
        relative_path: json.relative_path,
        working_path: json.working_path,
        archive_path: json.archive_path,
        deployment: json.deployment,
        touched: new Date(json.touched),
        tags: json.tags,
        working_set: json.working_set ? toComponentSet(json.working_set) : undefined,
        archive_set: json.archive_set ? toComponentSet(json.archive_set) : undefined,
        collections: json.collections,
        errors: json.errors ?? [],
        read_only: json.read_only ?? false
    }
}

export function toWorkflowSummary(workflow: any): WorkflowSummary {
    return {
        id: workflow.id,
        file_name: workflow.file_name,
        internal_name: workflow.internal_name,
        purpose: workflow.purpose,
        deployment: workflow.deployment,
        errors: workflow.errors ?? [],
        read_only: workflow.read_only ?? false
    };
}

/* User-defined objects
 * ---------------------------------------------------------------------------*/

export type UserDefinedType = {
    id: string;
    name: string;
    short_name: string;
    object_class: 'file' | 'folder';
    extensions: string[];
    icon: string;
    purpose: string;
    size_limit: number;
    small: boolean;
    object_count: number;
    working_dir?: string;
    archive_dir?: string;
}

export type UserObjectSummary = {
    id: string;
    type_id: string;
    relative_path: string;
    display_name: string;
    purpose: string;
    deployment: string;
    size: number;
    modified_at_ns: number;
    errors: string[];
    read_only: boolean;
}

/* Collections
 * ---------------------------------------------------------------------------*/

export type CollectionSummary = {
    id: string;
    name: string;
    parents?: CollectionSummary[];
}

export type Collection = {
    id: string;
    name: string
    purpose: string;
    deployment: string;
    tags: string[];
    models: ModelSummary[];
    workflows: WorkflowSummary[];
    user_objects: UserObjectSummary[];
    parents: CollectionSummary[];
    children: CollectionSummary[];
}

/* Tags
 * ---------------------------------------------------------------------------*/

export type Tag = {
    tag: string;
    models: ModelSummary[];
    workflows: WorkflowSummary[];
    user_objects: UserObjectSummary[];
    collections: CollectionSummary[];
}

