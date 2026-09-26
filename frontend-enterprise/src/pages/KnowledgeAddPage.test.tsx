// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { KnowledgeAddPage } from '@staffdeck/business-ui/KnowledgePage';
import { KnowledgePageHostProvider, type Host } from '@staffdeck/business-ui/KnowledgePageHost';

afterEach(cleanup);

function renderWithDiscoveries(discoveries: () => unknown[]) {
  const get = vi.fn(async (path: string) => {
    if (path.startsWith('/api/enterprise/knowledge-bases?')) return [];
    if (path.startsWith('/api/enterprise/knowledge/jobs?')) {
      return [{ id: 'job-1', status: 'succeeded', knowledge_base_id: 'base-1', document_id: 'doc-1', filename: 'source.md' }];
    }
    if (path.startsWith('/api/enterprise/knowledge/discoveries?')) return discoveries();
    throw new Error(`Unexpected request: ${path}`);
  });
  const host: Host = {
    api: {
      get: get as Host['api']['get'],
      post: vi.fn() as Host['api']['post'],
      put: vi.fn() as Host['api']['put'],
      delete: vi.fn() as Host['api']['delete'],
      blob: vi.fn() as Host['api']['blob'],
    },
    navigate: vi.fn(),
    tenantId: 'tenant_demo',
    notify: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
    isEnterpriseAdmin: () => true,
    loadEmployeeDirectory: async () => [],
    agentScope: { read: () => '', persist: vi.fn(), clear: vi.fn(), emit: vi.fn() },
    visibleEmployeeAgents: (agents: unknown[]) => agents,
    canManageEmployeeAgent: () => true,
    openGalleryAgentId: (agents: Array<{ id: string; is_overall?: boolean }>) => agents.find((agent) => agent.is_overall)?.id || '',
    openGalleryImportSourceOptions: () => [],
    resourceCreatorName: () => '',
    renderMarkdownBlocks: (value: string) => value,
    getDateLocale: () => 'zh-CN',
  };
  const view = render(
    <KnowledgePageHostProvider value={host}>
      <KnowledgeAddPage currentUser={{ id: 'admin', tenant_id: 'tenant_demo', username: 'admin', role: 'admin' }} />
    </KnowledgePageHostProvider>,
  );
  const discoveryCalls = () => get.mock.calls.filter(([path]) => path.startsWith('/api/enterprise/knowledge/discoveries?')).length;
  return { ...view, discoveryCalls };
}

describe('shared Knowledge discovery loading', () => {
  it('rechecks asynchronous discoveries without accepting another document in the same base', async () => {
    let attempts = 0;
    const { discoveryCalls } = renderWithDiscoveries(() => {
      attempts += 1;
      if (attempts === 1) return [];
      return [
        { id: 'other', status: 'pending', suggestion_type: 'skill', knowledge_base_id: 'base-1', document_id: 'doc-2', title: 'Other document' },
        { id: 'matching', status: 'pending', suggestion_type: 'skill', knowledge_base_id: 'base-1', document_id: 'doc-1', title: 'Matching document' },
      ];
    });

    expect(await screen.findByText('Matching document', {}, { timeout: 2500 })).toBeTruthy();
    expect(screen.queryByText('Other document')).toBeNull();
    expect(discoveryCalls()).toBe(2);
  });

  it('stops pending retries after the page unmounts', async () => {
    const { discoveryCalls, unmount } = renderWithDiscoveries(() => []);
    await waitFor(() => expect(discoveryCalls()).toBe(1));
    unmount();
    await new Promise((resolve) => setTimeout(resolve, 800));
    expect(discoveryCalls()).toBe(1);
  });
});
