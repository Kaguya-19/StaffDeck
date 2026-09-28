// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import FormalSopApprovalInbox from './formal-sop-approval-inbox';
import { I18nProvider, useI18n, type AppLocale } from '@/i18n';

afterEach(cleanup);
const approval = { waitId: 'wait-a', revision: 7, skillId: 'skill-old', version: '1.2.3', nodeId: 'handoff-node', assigneeUserId: 'user-1' };

it('renders only the authenticated pinned approval and sends its exact wait/revision without making an ID or local wait', () => {
  const reply = vi.fn();
  const { rerender } = render(<FormalSopApprovalInbox status={{ sessionId: 'session-a', revision: 7, approval }} onReply={reply} />);
  expect(screen.getByText('skill-old').hasAttribute('data-i18n-ignore')).toBe(true);
  const button = screen.getByRole('button', { name: '回复并恢复' });
  expect(button).toHaveProperty('disabled', true);
  fireEvent.change(screen.getByRole('textbox', { name: '人工回复' }), { target: { value: '  已审核  ' } });
  fireEvent.click(button);
  expect(reply).toHaveBeenCalledExactlyOnceWith(approval, '已审核');
  rerender(<FormalSopApprovalInbox status={{ sessionId: 'session-a', revision: 8, approval: { ...approval, waitId: 'wait-b', revision: 8 } }} onReply={reply} />);
  expect(screen.getByRole('textbox', { name: '人工回复' })).toHaveProperty('value', '');
  rerender(<FormalSopApprovalInbox status={{ sessionId: 'session-a', revision: 9, approvalError: { code: 'PIN_UNAVAILABLE', message: '原固定版本不可用' } }} onReply={reply} />);
  expect(screen.getByRole('alert').textContent).toBe('原固定版本不可用');
  expect(screen.queryByRole('button', { name: '回复并恢复' })).toBeNull();
});

it('does not offer an approval action for absent or invalid pinned state', () => {
  const reply = vi.fn();
  const { rerender } = render(<FormalSopApprovalInbox status={null} onReply={reply} />);
  expect(screen.getByText('当前会话没有待处理的人工审批')).toBeTruthy();
  rerender(<FormalSopApprovalInbox status={{ sessionId: 'session-a', revision: 1, approval: { ...approval, revision: -1 } }} onReply={reply} />);
  fireEvent.change(screen.getByRole('textbox', { name: '人工回复' }), { target: { value: 'reply' } });
  expect(screen.getByRole('button', { name: '回复并恢复' })).toHaveProperty('disabled', true);
  expect(reply).not.toHaveBeenCalled();
});

it('translates approval controls while keeping pinned skill, version and node values intact', () => {
  let changeLocale: (locale: AppLocale) => void;
  function Control() { changeLocale = useI18n().setLocale; return null; }
  const reply = vi.fn();
  render(<I18nProvider><Control /><FormalSopApprovalInbox
    status={{ sessionId: 'session-a', revision: 7, approval }} onReply={reply} /></I18nProvider>);
  act(() => changeLocale('en-US'));
  expect(screen.getByRole('region', { name: 'SOP Human Approval' })).toBeTruthy();
  expect(screen.getByRole('textbox', { name: 'Human Reply' })).toBeTruthy();
  for (const value of ['skill-old', '1.2.3', 'handoff-node']) {
    expect(screen.getByText(value).textContent).toBe(value);
  }
  act(() => changeLocale('zh-CN'));
  expect(screen.getByRole('textbox', { name: '人工回复' })).toBeTruthy();
});
