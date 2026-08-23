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
    deployment: string;
    touched: Date;
    tags: string[];
    component_sets: ComponentSet[];
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
        deployment: json.deployment,
        touched: new Date(json.touched),
        tags: json.tags,
        component_sets: json.component_sets.map(toComponentSet),
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
    deployment: string;
}

export type Workflow = {
    id: string;
    file_name: string;
    internal_name: string;
    purpose: string;
    relative_path: str;
    deployment: string;
    touched: Date;
    component_sets: ComponentSet[];
    tags: string[];
    collections: CollectionSummary[];
}

export function toWorkflow(json: any): Workflow {
    return {
        id: json.id,
        internal_name: json.name,
        purpose: json.purpose,
        relative_path: json.relative_path,
        deployment: json.deployment,
        touched: new Date(json.touched),
        tags: json.tags,
        component_sets: json.component_sets.map(toComponentSet),
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

