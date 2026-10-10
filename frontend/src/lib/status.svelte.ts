/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/status.svelte.ts
 * purpose: Central repository status and long-running operation monitor
 * ---------------------------------------------------------------------------*/


import { apiFetch, getUrl, parseResponse, type ApiResult } from '$lib/api';
import { locale } from '$lib/locale.svelte';
import { type Operation } from '$lib/models';

export type RepositoryCounts = {
    models: number;
    workflows: number;
    user_objects: number;
    collections: number;
};

export type RepositoryStatus = {
    counts: RepositoryCounts;
    operation: Operation | null;
};

const ACTIVE_INTERVAL = 400;

export type ScanIssue = { code: string; message: string; params: Record<string, unknown>; scope?: string };

class StatusMonitor {
    counts = $state<RepositoryCounts>({models: 0, workflows: 0, user_objects: 0,
                                       collections: 0});
    operation = $state<Operation | null>(null);
    error = $state<string | null>(null);
    scanRevision = $state(0);
    scanErrors = $state<Record<string, ScanIssue[]>>({models: [], workflows: [], user_objects: []});
    get hasScanErrors(): boolean {
        return Object.values(this.scanErrors).some(issues => issues.length > 0);
    }
    private completedScans = new Set<string>();
    private timer: ReturnType<typeof setTimeout> | null = null;
    private users = 0;
    private refreshing = false;
    private trackedId: string | null = null;

    start(): () => void {
        this.users += 1;
        if (this.users === 1) void this.refresh();
        return () => {
            this.users = Math.max(0, this.users - 1);
            if (this.users === 0 && this.timer !== null) {
                clearTimeout(this.timer);
                this.timer = null;
            }
        };
    }

    track(operation: Operation): void {
        this.trackedId = operation.id;
        this.operation = operation;
        this.schedule(0);
    }

    async waitForOperation(operation: Operation): Promise<ApiResult<Operation>> {
        this.track(operation);
        while (this.operation?.id === operation.id &&
               (this.operation.state === 'pending' || this.operation.state === 'running')) {
            await new Promise(resolve => setTimeout(resolve, ACTIVE_INTERVAL));
        }
        if (this.operation?.id === operation.id) {
            return {ok: true, data: this.operation};
        }
        return {ok: false, message: this.error ?? locale.t('errors.retrieve_operation')};
    }

    private async refresh(): Promise<void> {
        if (this.refreshing) return;
        this.refreshing = true;
        const trackedId = this.trackedId;
        try {
            const response = await apiFetch(getUrl('/repository-status'));
            const status = await parseResponse<RepositoryStatus>(response, value => value,
                                                                  'repositoryStatus');
            if (status.ok) {
                this.counts = status.data.counts;
                if (this.trackedId !== trackedId) return;
                let operation = status.data.operation;
                if (trackedId !== null) {
                    const tracked = await apiFetch(getUrl(`/operations/${trackedId}`));
                    const result = await parseResponse<Operation>(tracked, value => value,
                                                                   'trackedOperation');
                    if (this.trackedId !== trackedId) return;
                    if (!result.ok) {
                        this.error = result.message ?? locale.t('errors.retrieve_operation');
                        if (result.status === 404) {
                            this.operation = null;
                            this.trackedId = null;
                        }
                        return;
                    }
                    operation = result.data;
                }
                this.operation = operation;
                this.error = null;
                if (operation !== null &&
                    (operation.state === 'succeeded' || operation.state === 'failed')) {
                    if (operation.type === 'scan' && !this.completedScans.has(operation.id)) {
                        this.completedScans.add(operation.id);
                        const scopes = operation.progress.scope === 'all' || !operation.progress.scope
                            ? ['models', 'workflows', 'user_objects'] : [String(operation.progress.scope)];
                        const issues = (operation.progress.scan_issues ?? operation.result?.errors ?? []) as ScanIssue[];
                        const errors = issues.length > 0 ? issues : operation.state === 'failed'
                            ? [{code: 'scan_failed', message: operation.error?.message ?? 'Scan failed.', params: {}}]
                            : [];
                        for (const scope of scopes) {
                            this.scanErrors[scope] = errors.filter(issue => !issue.scope || issue.scope === 'all' || issue.scope === scope);
                        }
                        this.scanRevision += 1;
                    }
                    this.trackedId = null;
                }
            } else {
                this.error = status.message ?? locale.t('errors.retrieve_repository_status');
            }
        } catch (error) {
            this.error = error instanceof Error
                ? error.message
                : locale.t('errors.retrieve_repository_status');
        } finally {
            this.refreshing = false;
            const active = this.operation !== null &&
                (this.operation.state === 'pending' || this.operation.state === 'running');
            if (active || this.trackedId !== null) this.schedule(ACTIVE_INTERVAL);
        }
    }

    private schedule(delay: number): void {
        if (this.users === 0) return;
        if (this.timer !== null) clearTimeout(this.timer);
        this.timer = setTimeout(() => {
            this.timer = null;
            void this.refresh();
        }, delay);
    }
}

export const statusMonitor = new StatusMonitor();
