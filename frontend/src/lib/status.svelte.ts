/* ---------------------------------------------------------------------------
 * system: ModelArchivist
 * file: frontend/src/lib/status.svelte.ts
 * purpose: Central repository status and long-running operation monitor
 * ---------------------------------------------------------------------------*/

import { getUrl, parseResponse, type ApiResult } from '$lib/api';
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
const IDLE_INTERVAL = 4000;

class StatusMonitor {
    counts = $state<RepositoryCounts>({models: 0, workflows: 0, user_objects: 0,
                                       collections: 0});
    operation = $state<Operation | null>(null);
    error = $state<string | null>(null);
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
        return {ok: false, message: this.error ?? 'Cannot retrieve operation'};
    }

    private async refresh(): Promise<void> {
        if (this.refreshing) return;
        this.refreshing = true;
        try {
            const response = await fetch(getUrl('/repository-status'));
            const status = await parseResponse<RepositoryStatus>(response, value => value,
                                                                  'repositoryStatus');
            if (status.ok) {
                this.counts = status.data.counts;
                let operation = status.data.operation;
                if (operation === null && this.trackedId !== null) {
                    const tracked = await fetch(getUrl(`/operations/${this.trackedId}`));
                    const result = await parseResponse<Operation>(tracked, value => value,
                                                                   'trackedOperation');
                    if (result.ok) operation = result.data;
                }
                this.operation = operation;
                this.error = null;
                if (operation !== null &&
                    (operation.state === 'succeeded' || operation.state === 'failed')) {
                    this.trackedId = null;
                }
            } else {
                this.error = status.message ?? 'Cannot retrieve repository status';
            }
        } catch (error) {
            this.error = error instanceof Error
                ? error.message
                : 'Cannot retrieve repository status';
        } finally {
            this.refreshing = false;
            const active = this.operation !== null &&
                (this.operation.state === 'pending' || this.operation.state === 'running');
            this.schedule(active ? ACTIVE_INTERVAL : IDLE_INTERVAL);
        }
    }

    private schedule(delay: number): void {
        if (this.users === 0) return;
        if (this.timer !== null) clearTimeout(this.timer);
        this.timer = setTimeout(() => void this.refresh(), delay);
    }
}

export const statusMonitor = new StatusMonitor();
