// @vitest-environment jsdom
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import SkillsPage from '@staffdeck/business-ui/SkillsPage';
import { SkillsPageHostProvider } from '@staffdeck/business-ui/SkillsPageHost';
import { skillsPageHost } from './skills-host';
import { I18nProvider } from '@/i18n';
afterEach(cleanup);

describe('selected Skills row publish', () => {
  it.each([['draft/selected ?1', '&draft_id=draft%2Fselected%20%3F1'], [undefined, '']])('publishes only the selected row draft (%s)', async (draftId, suffix) => {
    const user = userEvent.setup();
    const row = { id: 'row-selected', skill_id: 'shared-sop', name: 'Selected draft', draft_id: draftId,
      version: '1.0.1', status: 'draft', updated_at: '2026-09-27' };
    const get = vi.fn(async (path: string) => {
      if (path.startsWith('/api/enterprise/skills?')) return [row];
      if (path.startsWith('/api/enterprise/agents?')) return [{ id: 'employee-1', name: 'Employee', is_overall: false, active: true }];
      throw new Error(`Unexpected read: ${path}`);
    });
    const post = vi.fn(async () => ({}));
    const host = { ...skillsPageHost, api: { ...skillsPageHost.api, get: get as typeof skillsPageHost.api.get, post: post as typeof skillsPageHost.api.post }, readEmployeeScope: () => 'employee-1',
      notify: { success: vi.fn(), warning: vi.fn(), error: vi.fn() } };
    render(<I18nProvider><MemoryRouter><SkillsPageHostProvider value={host}>
      <SkillsPage currentUser={{ id: 'admin', username: 'admin', role: 'admin' } as any} />
    </SkillsPageHostProvider></MemoryRouter></I18nProvider>);
    const names = await screen.findAllByText('Selected draft');
    const tableRow = names.find(name => name.closest('tr'))!.closest('tr')!;
    await user.click(within(tableRow).getByRole('button', { name: 'SOP 操作' }));
    await user.click(await screen.findByRole('menuitem', { name: '启用本地版本' }));
    await waitFor(() => expect(post).toHaveBeenCalledExactlyOnceWith(`/api/enterprise/skills/shared-sop/publish?tenant_id=tenant_demo&agent_id=employee-1${suffix}`));
    expect(host.notify.error).not.toHaveBeenCalled();
  });
});
