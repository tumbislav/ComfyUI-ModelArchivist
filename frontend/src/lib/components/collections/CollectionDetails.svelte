<!-- -------------------------------------------------------------------------
 ! system: ModelArchivist
 ! file: CollectionDetails.svelte
 ! purpose: Collection metadata and direct membership editor
 ! -------------------------------------------------------------------------- -->

<script lang="ts">
import TagEditor from '$components/controls/TagEditor.svelte';
import closeIcon from '$icons/actions/close8.png';
import saveIcon from '$icons/actions/save16.png';
import trashIcon from '$icons/actions/trash16.png';
import moveUpIcon from '$icons/actions/move-up16.png';
import moveDownIcon from '$icons/actions/move-down16.png';
import syncIcon from '$icons/actions/move-up-down16.png';
import type { Collection } from '$lib/objects';
import type { CollectionMember, MemberSegment } from '$lib/collections';

let {item=$bindable(), segments, changed, busy, error, warning, onClose, onSave, onRemove, onAdd, onOperate}: {
    item: Collection; segments: MemberSegment[]; changed: boolean; busy: boolean;
    error: string | null; warning: string | null; onClose: () => Promise<void>;
    onSave: () => Promise<void>;
    onRemove: (segment: MemberSegment, member: CollectionMember) => Promise<void>;
    onAdd: (segment: MemberSegment) => Promise<void>;
    onOperate: (destination: 'working' | 'archive' | null) => Promise<void>;
} = $props();
let segmentId = $state('');
const memberGroups = [
    {name: 'Models', field: 'models'},
    {name: 'Workflows', field: 'workflows'},
    {name: 'User types', field: 'user_objects'},
    {name: 'Collections', field: 'children'}
] as const;
function chooseType(event: Event) {
    const select = event.currentTarget as HTMLSelectElement;
    const chosen = segments.find(segment => segment.id === select.value);
    segmentId = ''; select.value = '';
    if (chosen && !busy) void onAdd(chosen);
}
</script>

<div class="space-below spaced-horizontally"><div></div>
    <button class="round" disabled={busy} aria-label="Close collection details" onclick={onClose}>
        <img class="action-icon" alt="" src={closeIcon} /></button></div>
{#if error}<p class="error-message">{error}</p>{/if}
{#if item.error_count > 0}<p class="error-details">{item.error_count} {item.error_count === 1 ? 'member has' : 'members have'} errors.</p>{/if}
{#if warning}<p class="warning-details">{warning}</p>{/if}
    <div class="space-below dialog-section">
        <label class="dialog-label">Name<input class="text-input full-width" disabled={busy} bind:value={item.name} /></label>
        <p class="annotation-right">{item.id}</p>
        <label class="dialog-label">Purpose<textarea class="text-input full-width" disabled={busy} bind:value={item.purpose}></textarea></label>
        <TagEditor tags={[...item.tags]} title="Tags" editable={true} disabled={busy}
            onChanged={(tags: string[]) => item.tags = [...tags]} />
        <div class="spaced-horizontally"><div></div>
            <button class="button-with-text" disabled={busy || !changed || !item.name.trim()} onclick={onSave}>
                <img class="action-icon" alt="" src={saveIcon} /><span class="button-label">Save</span></button></div>
    </div>
    <div class="space-below dialog-section">
        <h2 class="tight-vertical">Membership</h2>
        <div class="collection-member-scroll">
            <table class="main-table collection-member-table">
                <thead><tr class="table-head table-section"><th>Name</th><th title="Archive">A</th>
                    <th title="Working set">W</th><th aria-label="Remove member"></th></tr></thead>
                <tbody>
                    {#each segments.filter(segment => segment.members.length > 0) as segment (segment.id)}
                        <tr class="table-section"><th colspan="4">{segment.name}</th></tr>
                        {#each segment.members as member (member.id)}
                            <tr><td class="ellipsized-cell" title={member.name}>{member.name}</td>
                                <td>{member.has_archive ? 'A' : ''}</td><td>{member.has_working ? 'W' : ''}</td>
                                <td><button class="inline-button" disabled={busy} aria-label={`Remove ${member.name} from collection`}
                                    onclick={() => onRemove(segment, member)}><img class="action-icon" alt="" src={trashIcon} /></button></td></tr>
                        {/each}
                    {/each}
                </tbody>
            </table>
        </div>
        <div class="collection-add-row space-below">
            <label class="dialog-label" for="collection-member-segment">Add members</label>
            <select id="collection-member-segment" class="text-input" disabled={busy}
                bind:value={segmentId} onchange={chooseType}>
                <option value="">Choose a type…</option>
                {#each memberGroups as group}
                    <optgroup label={group.name}>
                        {#each segments.filter(segment => segment.field === group.field) as segment (segment.id)}
                            <option value={segment.id}>{segment.name}</option>
                        {/each}
                    </optgroup>
                {/each}
            </select>
        </div>
        <div class="spaced-horizontally">
            <button class="button-with-text" disabled={busy || changed || item.read_only || !item.has_archive}
                onclick={() => onOperate('working')}><img class="action-icon" alt="" src={moveUpIcon} />
                <span class="button-label">To working set</span></button>
            <button class="button-with-text" disabled={busy || changed || item.read_only || item.deployment === 'synced'}
                onclick={() => onOperate(null)}><img class="action-icon" alt="" src={syncIcon} />
                <span class="button-label">Sync</span></button>
            <button class="button-with-text" disabled={busy || changed || item.read_only || !item.has_working}
                onclick={() => onOperate('archive')}><img class="action-icon" alt="" src={moveDownIcon} />
                <span class="button-label">To archive</span></button>
        </div>
        {#if changed}<p class="annotation">Save metadata changes before running location actions.</p>{/if}
    </div>
