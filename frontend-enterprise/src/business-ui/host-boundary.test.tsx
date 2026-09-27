// @vitest-environment jsdom
import { cleanup, fireEvent, render, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import DistillPage from '../../../packages/staffdeck-business-ui/src/DistillPage';
import { ApiError, DistillPageHostProvider, type DistillPageHost } from '../../../packages/staffdeck-business-ui/src/DistillPageHost';
import { ApiError as NativeApiError } from '../api/client';

afterEach(() => { cleanup(); window.localStorage.clear(); vi.unstubAllGlobals(); });

describe('mounted Distill boundary', () => {
  it('keeps the original error constructor, body and instanceof contract', () => {
    expect(ApiError).toBe(NativeApiError);
    const body = JSON.stringify({ detail: { code: 'DRAFT_CONFLICT', message: 'draft changed' } });
    const error = new ApiError(412, body, 'Precondition Failed');
    expect(error).toBeInstanceOf(NativeApiError);
    expect(error).toMatchObject({ name: 'ApiError', status: 412, body, code: 'DRAFT_CONFLICT', message: 'draft changed' });
  });

  it('sends a child editor warning to its own Host after another Host renders', async () => {
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
    const host = (tenantId: string): DistillPageHost => ({
      api: {
        get: vi.fn(async (path: string) => path.startsWith('/api/enterprise/skills/example?') ? {
          id: 'draft-' + tenantId, skill_id: 'example', name: 'Example', version: '1.0.0',
          content: { skill_id: 'example', name: 'Example', version: '1.0.0', nodes: [{ node_id: 'one', name: 'Only node', type: 'reply' }], edges: [] },
        } : []),
        post: vi.fn(), postWithSignal: vi.fn(), put: vi.fn(), delete: vi.fn(),
      },
      tenantId, navigate: vi.fn(), streamGet: vi.fn(), streamPost: vi.fn(),
      notify: { success: vi.fn(), warning: vi.fn(), error: vi.fn(), info: vi.fn() },
      readEmployeeScope: () => 'agent-one', isTeamScope: () => false,
    });
    const a = host('tenant-a');
    const b = host('tenant-b');
    const view = render(<MemoryRouter><section data-testid="host-a"><DistillPageHostProvider value={a}>
      <DistillPage searchParamsOverride={new URLSearchParams('skill_id=example')} />
    </DistillPageHostProvider></section><section data-testid="host-b"><DistillPageHostProvider value={b}>
      <DistillPage searchParamsOverride={new URLSearchParams('skill_id=example')} />
    </DistillPageHostProvider></section></MemoryRouter>);
    const first = within(view.getByTestId('host-a'));
    await waitFor(() => expect(first.queryAllByText('Only node').length).toBeGreaterThan(0));
    fireEvent.click(first.getByRole('button', { name: '显示源码' }));
    fireEvent.click(first.getByRole('button', { name: '删除节点' }));
    expect(a.notify.warning).toHaveBeenCalledWith('至少需要保留一个节点');
    expect(b.notify.warning).not.toHaveBeenCalled();
  });
});
