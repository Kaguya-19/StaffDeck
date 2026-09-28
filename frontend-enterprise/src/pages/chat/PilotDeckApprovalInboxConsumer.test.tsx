// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { api } from '@/api/client';
import { usePilotDeckApprovalInbox } from './PilotDeckApprovalInboxConsumer';

vi.mock('@/api/client', () => ({ api: { getWithSignal: vi.fn(), postWithSignal: vi.fn() } }));
const approval = { waitId: 'wait', revision: 4, skillId: 'skill', version: '1', nodeId: 'human', assigneeUserId: 'approver' };
const status = { sessionId: 'pd-session', revision: 4, approval };
beforeEach(() => vi.clearAllMocks());

it('uses normal SD authenticated API routes and replays the original snake_case command', async () => {
  vi.mocked(api.getWithSignal).mockResolvedValueOnce({ status } as never).mockResolvedValueOnce({ status: null } as never);
  vi.mocked(api.postWithSignal).mockRejectedValueOnce(new Error('bridge unavailable'))
    .mockImplementationOnce(async (_path, body) => ({ accepted: true, duplicate: true, sessionId: 'pd-session', requestId: (body as { request_id: string }).request_id, revision: 5, message: 'continue' }) as never);
  const prepared = vi.fn();
  const { result } = renderHook(() => usePilotDeckApprovalInbox({ mapping: { sessionKey: 'pd-session', projectKey: '/project' }, onPrepared: prepared }));
  await waitFor(() => expect(result.current.status?.approval).toEqual(approval));
  expect(api.getWithSignal).toHaveBeenCalledWith('/api/v1/pilotdeck/approvals/pd-session', expect.any(AbortSignal));
  await act(async () => { await result.current.onReply(approval, ' approved '); });
  expect(result.current.error).toBe('bridge unavailable');
  await act(async () => { await result.current.onReply(approval, 'approved'); });
  const first = vi.mocked(api.postWithSignal).mock.calls[0][1] as { request_id: string };
  const second = vi.mocked(api.postWithSignal).mock.calls[1][1] as { request_id: string };
  expect(second.request_id).toBe(first.request_id);
  expect(first).toMatchObject({ session_key: 'pd-session', wait_id: 'wait', expected_revision: 4, message: 'approved' });
  expect(prepared).toHaveBeenCalledWith('continue');
  await waitFor(() => expect(result.current.status).toBeNull());
});

it('makes no request or reply without an admitted PD session mapping', async () => {
  const { result } = renderHook(() => usePilotDeckApprovalInbox({ mapping: null }));
  await waitFor(() => expect(result.current.error).toBe('SOP_APPROVAL_SESSION_MAPPING_UNAVAILABLE'));
  await act(async () => { await result.current.onReply(approval, 'approved'); });
  expect(api.getWithSignal).not.toHaveBeenCalled();
  expect(api.postWithSignal).not.toHaveBeenCalled();
});
