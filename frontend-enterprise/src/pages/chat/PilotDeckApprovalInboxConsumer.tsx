import { useCallback, useEffect, useRef, useState, type ComponentType } from 'react';
import { api } from '@/api/client';
import type { FormalSopApproval, FormalSopApprovalInboxProps, FormalSopApprovalStatus } from '@/business-ui/formal-sop-approval-inbox';

export type AdmittedPilotDeckApprovalSession = Readonly<{ sessionKey: string; projectKey?: string }>;
type ApprovalReceipt = Readonly<{ accepted: true; duplicate: boolean; sessionId: string; requestId: string; revision: number; message: string }>;
type ApprovalConsumerOptions = {
  mapping: AdmittedPilotDeckApprovalSession | null;
  refreshKey?: string;
  onPrepared?: (message: string) => void;
  onError?: (message: string) => void;
};

/** The normal SD API client authenticates the approver; only root admission supplies the PD session mapping. */
export function usePilotDeckApprovalInbox({ mapping, refreshKey, onPrepared, onError }: ApprovalConsumerOptions): FormalSopApprovalInboxProps & { refresh: () => Promise<void> } {
  const [status, setStatus] = useState<FormalSopApprovalStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const requestAbort = useRef<AbortController | null>(null);
  const replyAbort = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const inFlight = useRef(false);
  const mappingKey = mapping ? `${mapping.projectKey ?? ''}\0${mapping.sessionKey}` : '';
  const pending = useRef<{ key: string; requestId: string } | null>(null);
  const previousMapping = useRef(mappingKey);
  const inputs = useRef({ mapping, onPrepared, onError });
  inputs.current = { mapping, onPrepared, onError };

  const refresh = useCallback(async () => {
    const current = ++generation.current;
    requestAbort.current?.abort();
    const admitted = inputs.current.mapping;
    if (!admitted?.sessionKey) {
      setStatus(null);
      setLoading(false);
      setError('SOP_APPROVAL_SESSION_MAPPING_UNAVAILABLE');
      return;
    }
    const controller = new AbortController();
    requestAbort.current = controller;
    setLoading(true);
    try {
      const envelope = await api.getWithSignal<{ status: FormalSopApprovalStatus | null }>(
        `/api/v1/pilotdeck/approvals/${encodeURIComponent(admitted.sessionKey)}`, controller.signal);
      if (current !== generation.current || controller.signal.aborted) return;
      if (!envelope || !Object.prototype.hasOwnProperty.call(envelope, 'status') ||
          (envelope.status && envelope.status.sessionId !== admitted.sessionKey)) throw new Error('Approval status does not match the admitted session.');
      setStatus(envelope.status);
      setError('');
    } catch (cause) {
      if (current !== generation.current || controller.signal.aborted) return;
      setStatus(null);
      const message = cause instanceof Error ? cause.message : String(cause);
      setError(message);
      inputs.current.onError?.(message);
    } finally {
      if (current === generation.current && !controller.signal.aborted) setLoading(false);
    }
  }, [mappingKey]);

  useEffect(() => {
    if (previousMapping.current !== mappingKey) pending.current = null;
    previousMapping.current = mappingKey;
    inFlight.current = false;
    setSubmitting(false);
    setStatus(null);
    setError('');
    void refresh();
    return () => { generation.current++; requestAbort.current?.abort(); replyAbort.current?.abort(); };
  }, [refresh, refreshKey]);

  const onReply = useCallback(async (approval: FormalSopApproval, message: string): Promise<void> => {
    const admitted = inputs.current.mapping;
    const pinned = status?.approval;
    if (!admitted?.sessionKey) { setError('SOP_APPROVAL_SESSION_MAPPING_UNAVAILABLE'); return; }
    if (!pinned || status?.approvalError || inFlight.current ||
        pinned.waitId !== approval.waitId || pinned.revision !== approval.revision ||
        pinned.skillId !== approval.skillId || pinned.version !== approval.version ||
        pinned.nodeId !== approval.nodeId || pinned.assigneeUserId !== approval.assigneeUserId) {
      setError('SOP_APPROVAL_WAIT_STALE');
      return;
    }
    const normalized = message.trim();
    if (!normalized) return;
    const key = `${mappingKey}\0${pinned.waitId}\0${pinned.revision}\0${normalized}`;
    const requestId = pending.current?.key === key ? pending.current.requestId : crypto.randomUUID();
    pending.current = { key, requestId };
    const controller = new AbortController();
    replyAbort.current = controller;
    inFlight.current = true;
    setSubmitting(true);
    setError('');
    try {
      const receipt = await api.postWithSignal<ApprovalReceipt>('/api/v1/pilotdeck/approvals/reply', {
        session_key: admitted.sessionKey, request_id: requestId, wait_id: pinned.waitId,
        expected_revision: pinned.revision, message: normalized,
      }, controller.signal);
      if (controller.signal.aborted) return;
      if (receipt.accepted !== true || receipt.sessionId !== admitted.sessionKey || receipt.requestId !== requestId) {
        throw new Error('Approval receipt does not match the original command.');
      }
      pending.current = null;
      inputs.current.onPrepared?.(receipt.message);
      await refresh();
    } catch (cause) {
      if (controller.signal.aborted) return;
      const failure = cause instanceof Error ? cause.message : String(cause);
      setError(failure);
      inputs.current.onError?.(failure);
    } finally {
      inFlight.current = false;
      if (!controller.signal.aborted) setSubmitting(false);
    }
  }, [mappingKey, status, refresh]);

  return { status, loading, submitting, error, onReply, refresh };
}

/** Root may mount either native chat page verbatim once it has an authenticated admission mapping. */
export function PilotDeckApprovalInboxConsumer({ Page, mapping, refreshKey, onPrepared, onError }: ApprovalConsumerOptions & {
  Page: ComponentType<{ pilotDeckApprovalInbox?: FormalSopApprovalInboxProps }>;
}) {
  const { refresh: _refresh, ...pilotDeckApprovalInbox } = usePilotDeckApprovalInbox({ mapping, refreshKey, onPrepared, onError });
  return <><Page pilotDeckApprovalInbox={pilotDeckApprovalInbox} />
    {!pilotDeckApprovalInbox.status && pilotDeckApprovalInbox.error ? <div role="alert">{pilotDeckApprovalInbox.error}</div> : null}</>;
}
