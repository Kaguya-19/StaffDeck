// @vitest-environment jsdom

import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import SharedKnowledgePage from '@staffdeck/business-ui/KnowledgePage';
import { KnowledgePageHostProvider } from '@staffdeck/business-ui/KnowledgePageHost';
import SharedSkillsPage from '@staffdeck/business-ui/SkillsPage';
import { SkillsPageHostProvider } from '@staffdeck/business-ui/SkillsPageHost';

import { knowledgePageHost } from './knowledge-host';
import { skillsPageHost } from './skills-host';
import { I18nProvider } from '@/i18n';

const agents = [
  { id: 'employee-1', name: '当前员工', is_overall: false, active: true },
  { id: 'overall-actual', name: '开放广场', is_overall: true, active: true },
];
const currentUser = { id: 'admin', tenant_id: 'tenant_demo', username: 'admin', role: 'admin' as const };

afterEach(cleanup);

describe('shared plaza copy entry', () => {
  it('selects a Knowledge source and submits the actual overall agent and base', async () => {
    const user = userEvent.setup();
    const get = vi.fn(async (path: string) => {
      if (path.startsWith('/api/enterprise/model-configs?')) return [];
      if (path.startsWith('/api/enterprise/knowledge/documents?')) return [];
      if (path.startsWith('/api/enterprise/knowledge-bases?')) return [{ id: 'base-1', name: 'Policy', status: 'active' }];
      if (path.startsWith('/api/enterprise/knowledge-bases/base-1/okf/concepts?')) return [];
      throw new Error(`Unexpected Knowledge request: ${path}`);
    });
    const post = vi.fn(async (path: string) => {
      if (path === '/api/enterprise/agents/employee-1/resources/import') return { imported: [{ id: 'base-1' }], missing: [] };
      throw new Error(`Unexpected Knowledge POST: ${path}`);
    });
    const host = {
      ...knowledgePageHost,
      api: { ...knowledgePageHost.api, get, post },
      loadEmployeeDirectory: async () => agents,
      agentScope: { ...knowledgePageHost.agentScope, read: () => 'employee-1' },
      notify: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
    };

    render(
      <I18nProvider>
        <MemoryRouter>
          <KnowledgePageHostProvider value={host}>
            <SharedKnowledgePage currentUser={currentUser} />
          </KnowledgePageHostProvider>
        </MemoryRouter>
      </I18nProvider>,
    );

    await user.click(await screen.findByRole('button', { name: /新增/ }));
    await user.click(await screen.findByText('从广场复制'));

    expect(await screen.findByRole('dialog')).toBeTruthy();
    expect(screen.getByText('从广场复制知识库')).toBeTruthy();
    await waitFor(() => expect(get).toHaveBeenCalledWith(
      '/api/enterprise/knowledge-bases?tenant_id=tenant_demo&agent_id=overall-actual',
      undefined,
    ));
    await user.click(await within(screen.getByRole('dialog')).findByText('Policy'));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '复制' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/api/enterprise/agents/employee-1/resources/import',
      { tenant_id: 'tenant_demo', source_agent_id: 'overall-actual', resource_type: 'knowledge_base', resource_ids: ['base-1'] },
      undefined,
    ));
    expect(host.notify.error).not.toHaveBeenCalled();
  });

  it('selects a SOP source and submits the actual overall agent and skill', async () => {
    const user = userEvent.setup();
    const get = vi.fn(async (path: string) => {
      if (path.startsWith('/api/enterprise/skills?')) return [];
      if (path.startsWith('/api/enterprise/agents?')) return agents;
      if (path.startsWith('/api/enterprise/agents/overall-actual/skills?')) return [{ id: 'skill-1', skill_id: 'skill-1', name: 'Review', version: '1.0.0', status: 'published', updated_at: '2026-09-27' }];
      throw new Error(`Unexpected Skills request: ${path}`);
    });
    const post = vi.fn(async (path: string) => {
      if (path === '/api/enterprise/agents/employee-1/resources/import') return { imported: [{ id: 'skill-1' }], missing: [] };
      throw new Error(`Unexpected Skills POST: ${path}`);
    });
    const host = {
      ...skillsPageHost,
      api: { ...skillsPageHost.api, get, post },
      readEmployeeScope: () => 'employee-1',
      notify: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
    };

    render(
      <I18nProvider>
        <MemoryRouter>
          <SkillsPageHostProvider value={host}>
            <SharedSkillsPage currentUser={currentUser} />
          </SkillsPageHostProvider>
        </MemoryRouter>
      </I18nProvider>,
    );

    await user.click(await screen.findByRole('button', { name: /新增/ }));
    await user.click(await screen.findByText('从广场复制'));

    expect(await screen.findByRole('dialog')).toBeTruthy();
    expect(screen.getByText('从广场复制 SOP')).toBeTruthy();
    await waitFor(() => expect(get).toHaveBeenCalledWith(
      '/api/enterprise/agents/overall-actual/skills?tenant_id=tenant_demo',
    ));
    await user.click(await within(screen.getByRole('dialog')).findByText('Review'));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '复制' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/api/enterprise/agents/employee-1/resources/import',
      { tenant_id: 'tenant_demo', source_agent_id: 'overall-actual', resource_type: 'skill', resource_ids: ['skill-1'] },
    ));
    expect(host.notify.error).not.toHaveBeenCalled();
  });
});
