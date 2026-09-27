// @vitest-environment jsdom
import { cleanup, render, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import KnowledgePage from '../../../packages/staffdeck-business-ui/src/KnowledgePage';
import { KnowledgePageHostProvider, type Host } from '../../../packages/staffdeck-business-ui/src/KnowledgePageHost';
import SkillsPage from '../../../packages/staffdeck-business-ui/src/SkillsPage';
import { SkillsPageHostProvider, type SkillsPageHost } from '../../../packages/staffdeck-business-ui/src/SkillsPageHost';
import { knowledgePageHost } from './knowledge-host';
import { skillsPageHost } from './skills-host';
import { I18nProvider } from '@/i18n';

afterEach(() => { cleanup(); window.localStorage.clear(); });
const agents = [{ id: 'employee', name: 'Employee', is_overall: false, active: true }];
const user = { id: 'actor', is_admin: true };

it('renders each actual Knowledge Markdown preview through its mounted Host after its sibling unmounts', async () => {
  const makeHost = (id: string): Host => ({
    ...knowledgePageHost, tenantId: id, loadEmployeeDirectory: async () => agents,
    agentScope: { ...knowledgePageHost.agentScope, read: () => 'employee' },
    api: { ...knowledgePageHost.api, get: vi.fn(async (path: string) => {
      if (path.startsWith('/api/enterprise/knowledge/documents?')) return [{
        id: 'doc', knowledge_base_id: 'base', title: 'Document', filename: 'source.md',
        metadata: { document_card: { summary: 'summary-' + id } },
      }];
      if (path.startsWith('/api/enterprise/knowledge-bases?')) return [{ id: 'base', name: 'Base', status: 'active' }];
      return [];
    }) as Host['api']['get'] },
    renderMarkdownBlocks: vi.fn((value: string) => <span data-testid={'markdown-' + id}>{value}</span>),
    notify: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
  });
  const a = makeHost('tenant-a');
  const b = makeHost('tenant-b');
  const page = (host: Host) => <section key={host.tenantId} data-testid={host.tenantId}>
    <KnowledgePageHostProvider value={host}><KnowledgePage currentUser={user} /></KnowledgePageHostProvider>
  </section>;
  const view = render(<I18nProvider><MemoryRouter>{page(a)}{page(b)}</MemoryRouter></I18nProvider>);
  const first = within(view.getByTestId('tenant-a'));
  await waitFor(() => expect(first.getAllByTestId('markdown-tenant-a').some(node => node.textContent === 'summary-tenant-a')).toBe(true));
  await waitFor(() => expect(within(view.getByTestId('tenant-b')).getAllByTestId('markdown-tenant-b').some(node => node.textContent === 'summary-tenant-b')).toBe(true));
  expect(first.queryAllByTestId('markdown-tenant-b')).toEqual([]);
  view.rerender(<I18nProvider><MemoryRouter>{page(a)}</MemoryRouter></I18nProvider>);
  expect(first.getAllByTestId('markdown-tenant-a').some(node => node.textContent === 'summary-tenant-a')).toBe(true);
  expect(b.renderMarkdownBlocks).not.toHaveBeenCalledWith('summary-tenant-a');
  expect(a.notify.error).not.toHaveBeenCalled();
  expect(b.notify.error).not.toHaveBeenCalled();
});

it('keeps actual Skills pagination calls with the Host that owns their rows', async () => {
  const makeHost = (id: string): SkillsPageHost => ({
    ...skillsPageHost, tenantId: id, readEmployeeScope: () => 'employee',
    api: { ...skillsPageHost.api, get: vi.fn(async (path: string) => path.startsWith('/api/enterprise/skills?') ? [{
      id: 'row-' + id, skill_id: 'sop-' + id, name: 'Name-' + id, version: '1', status: 'draft', updated_at: '2026-09-27',
    }] : agents) as SkillsPageHost['api']['get'] },
    useClientPagination: vi.fn(skillsPageHost.useClientPagination) as SkillsPageHost['useClientPagination'],
    notify: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
  });
  const a = makeHost('tenant-a');
  const b = makeHost('tenant-b');
  const view = render(<I18nProvider><MemoryRouter><SkillsPageHostProvider value={a}><SkillsPage currentUser={user} /></SkillsPageHostProvider>
    <SkillsPageHostProvider value={b}><SkillsPage currentUser={user} /></SkillsPageHostProvider></MemoryRouter></I18nProvider>);
  await waitFor(() => expect(view.getAllByText('Name-tenant-a').length).toBeGreaterThan(0));
  await waitFor(() => expect(view.getAllByText('Name-tenant-b').length).toBeGreaterThan(0));
  const rowsSeen = (host: SkillsPageHost) => vi.mocked(host.useClientPagination).mock.calls.flatMap(call => call[0]).map((row: any) => row.skill_id);
  expect(rowsSeen(a)).toContain('sop-tenant-a');
  expect(rowsSeen(a)).not.toContain('sop-tenant-b');
  expect(rowsSeen(b)).toContain('sop-tenant-b');
  expect(rowsSeen(b)).not.toContain('sop-tenant-a');
});
