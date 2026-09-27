// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { KnowledgePageHostProvider, CapabilityScopeControl, CapabilityScopeLoading, Progress, StatCard, Paginator } from '@staffdeck/business-ui/KnowledgePageHost';
import { knowledgePageHost } from './knowledge-host';
import { I18nProvider } from '@/i18n';

afterEach(cleanup);
const mount = (content: React.ReactNode) => render(<I18nProvider><KnowledgePageHostProvider value={knowledgePageHost}>{content}</KnowledgePageHostProvider></I18nProvider>);

describe('actual Knowledge Host presentation contract', () => {
  it('passes StatCard value/label and Progress value to the original primitives', () => {
    mount(<><StatCard value={17} label="知识库总数" tone="green" /><Progress value={42} aria-label="入库进度" /></>);
    expect(screen.getByText('17')).toBeTruthy();
    expect(screen.getByText('知识库总数')).toBeTruthy();
    const progress = screen.getByRole('progressbar', { name: '入库进度' });
    expect(progress.getAttribute('aria-valuenow')).toBe('42');
    expect(progress.querySelector('[data-slot="progress-indicator"]')?.getAttribute('style')).toContain('translateX(-58%)');
  });

  it('preserves loading semantics and scope switch value/disabled behavior', () => {
    const change = vi.fn();
    mount(<><CapabilityScopeLoading /><CapabilityScopeControl value="sop_specific" resourceType="knowledge_base" onChange={change} /></>);
    expect(screen.getByRole('status', { name: '正在加载员工能力' })).toBeTruthy();
    const scope = screen.getByRole('switch', { name: '切换能力范围' });
    expect(scope.getAttribute('aria-checked')).toBe('true');
    fireEvent.click(scope);
    expect(change).toHaveBeenCalledWith('general');
  });

  it('keeps paginator padding, aria current, ellipsis and bounded next navigation', () => {
    const change = vi.fn();
    mount(<Paginator aria-label="知识库分页" page={5} pageCount={12} onChange={change} />);
    const nav = screen.getByRole('navigation', { name: '知识库分页' });
    expect(within(nav).getByRole('button', { name: '05' }).getAttribute('aria-current')).toBe('page');
    expect(within(nav).getAllByText('···')).toHaveLength(2);
    fireEvent.click(within(nav).getByRole('button', { name: '下一页' }));
    expect(change).toHaveBeenCalledWith(6);
  });
});
