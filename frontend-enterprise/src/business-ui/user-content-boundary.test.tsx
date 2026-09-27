// @vitest-environment jsdom
import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import SharedKnowledgePage from '@staffdeck/business-ui/KnowledgePage';
import { KnowledgePageHostProvider } from '@staffdeck/business-ui/KnowledgePageHost';
import SharedSkillsPage from '@staffdeck/business-ui/SkillsPage';
import SopVersionDetailDialog from '@staffdeck/business-ui/SopVersionDetailDialog';
import { SkillsPageHostProvider } from '@staffdeck/business-ui/SkillsPageHost';
import { knowledgePageHost } from './knowledge-host';
import { skillsPageHost } from './skills-host';
import SharedDistillPage from '@staffdeck/business-ui/DistillPage';
import { DistillPageHostProvider } from '@staffdeck/business-ui/DistillPageHost';
import { distillPageHost } from './distill-host';
import { I18nProvider, useI18n, type AppLocale } from '@/i18n';

let changeLocale: (locale: AppLocale) => void;
function LocaleControl() { changeLocale = useI18n().setLocale; return null; }

const agents = [
  { id: 'employee-1', name: '当前员工', is_overall: false, active: true },
  { id: 'overall-actual', name: '开放广场', is_overall: true, active: true },
];
const currentUser = { id: 'admin', tenant_id: 'tenant_demo', username: 'admin', role: 'admin' as const };
const notify = () => ({ success: vi.fn(), warning: vi.fn(), error: vi.fn() });
const boundary = (element: Element) => element.closest('[data-i18n-ignore][translate="no"]');
afterEach(() => { cleanup(); window.localStorage.clear(); vi.unstubAllGlobals(); });

describe('resource text boundaries in the actual shared pages', () => {
  it('protects Knowledge desktop/mobile names and descriptions, leaving labels and empty descriptions translatable', async () => {
    const get = vi.fn(async (path: string) => {
      if (path.startsWith('/api/enterprise/model-configs?')) return [];
      if (path.startsWith('/api/enterprise/knowledge/documents?')) return [];
      if (path.startsWith('/api/enterprise/knowledge-bases?')) return [
        { id: 'base-1', name: '新增', description: '暂无内容', status: 'active', version: '1.0.0' },
        { id: 'base-2', name: '用户资料', description: '', status: 'active', version: '1.0.0' },
      ];
      if (path.includes('/okf/concepts?')) return [];
      throw new Error(`Unexpected Knowledge request: ${path}`);
    });
    const host = {
      ...knowledgePageHost, api: { ...knowledgePageHost.api, get },
      loadEmployeeDirectory: async () => agents,
      agentScope: { ...knowledgePageHost.agentScope, read: () => 'employee-1' },
      resourceCreatorName: () => '删除', notify: notify(),
    };
    render(<I18nProvider><LocaleControl /><MemoryRouter><KnowledgePageHostProvider value={host}>
      <SharedKnowledgePage currentUser={currentUser} />
    </KnowledgePageHostProvider></MemoryRouter></I18nProvider>);
    const names = await screen.findAllByText('新增', { selector: 'strong' });
    expect(names.length).toBeGreaterThanOrEqual(2);
    names.forEach((name) => expect(boundary(name)).not.toBeNull());
    screen.getAllByText('暂无内容').forEach((description) => expect(boundary(description)).not.toBeNull());
    expect(boundary(screen.getByText('未填写描述'))).toBeNull();
    expect(boundary(screen.getByRole('button', { name: /新增/ }))).toBeNull();
    expect(boundary(screen.getByRole('columnheader', { name: '名称' }))).toBeNull();
    expect(boundary(document.querySelector('[title="删除"]')!)).not.toBeNull();
    act(() => changeLocale('en-US'));
    await screen.findByRole('columnheader', { name: 'Name' });
    expect(screen.getByRole('button', { name: /Add/ })).toBeTruthy();
    expect(screen.getByText('No Description Entered')).toBeTruthy();
    names.forEach((name) => expect(name.textContent).toBe('新增'));
    screen.getAllByText('暂无内容').forEach((description) => expect(boundary(description)).not.toBeNull());
    expect(document.querySelector('[title="删除"]')).not.toBeNull();
    act(() => changeLocale('zh-CN'));
    expect(await screen.findByRole('columnheader', { name: '名称' })).toBeTruthy();
    names.forEach((name) => expect(name.textContent).toBe('新增'));
    expect(host.notify.error).not.toHaveBeenCalled();
  });

  it('retains Knowledge resource boundaries through the real import dialog portal', async () => {
    const user = userEvent.setup();
    const get = vi.fn(async (path: string) => {
      if (path.startsWith('/api/enterprise/model-configs?') || path.startsWith('/api/enterprise/knowledge/documents?') || path.includes('/okf/concepts?')) return [];
      if (path.startsWith('/api/enterprise/knowledge-bases?')) return [{ id: 'base-1', name: '暂无内容', status: 'active' }];
      throw new Error(`Unexpected Knowledge request: ${path}`);
    });
    const host = {
      ...knowledgePageHost, api: { ...knowledgePageHost.api, get },
      loadEmployeeDirectory: async () => agents,
      agentScope: { ...knowledgePageHost.agentScope, read: () => 'employee-1' }, notify: notify(),
    };
    const { container } = render(<I18nProvider><LocaleControl /><MemoryRouter><KnowledgePageHostProvider value={host}>
      <SharedKnowledgePage currentUser={currentUser} />
    </KnowledgePageHostProvider></MemoryRouter></I18nProvider>);
    await user.click(await screen.findByRole('button', { name: /新增/ }));
    await user.click(await screen.findByText('从广场复制'));
    const dialog = await screen.findByRole('dialog');
    const resource = await within(dialog).findByText('暂无内容');
    expect(container.contains(dialog)).toBe(false);
    expect(boundary(resource)).not.toBeNull();
    expect(boundary(within(dialog).getByText('选择知识库'))).toBeNull();
    act(() => changeLocale('en-US'));
    expect(await within(dialog).findByText('Copy knowledge base from Marketplace')).toBeTruthy();
    expect(resource.textContent).toBe('暂无内容');
    act(() => changeLocale('zh-CN'));
    expect(await within(dialog).findByText('从广场复制知识库')).toBeTruthy();
    expect(resource.textContent).toBe('暂无内容');
    expect(host.notify.error).not.toHaveBeenCalled();
  });

  it('protects SOP names, title attributes, IDs, domains and creators while keeping table labels translatable', async () => {
    const get = vi.fn(async (path: string) => {
      if (path.startsWith('/api/enterprise/skills?')) return [{
        id: 'draft-1', skill_id: '取消', name: '新增', description: '', business_domain: '名称',
        version: '1.0.0', status: 'draft', updated_at: '2026-09-27',
      }];
      if (path.startsWith('/api/enterprise/agents?')) return agents;
      throw new Error(`Unexpected Skills request: ${path}`);
    });
    const host = {
      ...skillsPageHost, api: { ...skillsPageHost.api, get }, readEmployeeScope: () => 'employee-1',
      resourceCreatorName: () => '删除', notify: notify(),
    };
    render(<I18nProvider><LocaleControl /><MemoryRouter><SkillsPageHostProvider value={host}>
      <SharedSkillsPage currentUser={currentUser} />
    </SkillsPageHostProvider></MemoryRouter></I18nProvider>);
    await waitFor(() => expect(document.querySelector('[title="新增"]')).not.toBeNull());
    for (const title of ['新增', '取消', '删除']) {
      document.querySelectorAll(`[title="${title}"]`).forEach((node) => expect(boundary(node)).not.toBeNull());
    }
    screen.getAllByText('名称', { selector: 'span' }).forEach((domain) => expect(boundary(domain)).not.toBeNull());
    expect(boundary(screen.getByRole('columnheader', { name: 'SOP 名称' }))).toBeNull();
    expect(boundary(screen.getByRole('button', { name: /新增/ }))).toBeNull();
    expect(host.notify.error).not.toHaveBeenCalled();
  });
  it('protects real SOP graph preview text while allowing built-in loaded guidance to translate', async () => {
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
    const content = {
      skill_id: 'boundary-sop', name: '新增', description: '暂无内容', version: '1.0.0',
      business_domain: '名称', trigger_intents: ['取消'], user_utterance_examples: [], goal: [],
      required_info: ['删除'], response_rules: [], start_node_id: 'n1',
      nodes: [{ node_id: 'n1', name: '发布', type: 'collect_info', instruction: '暂无说明', expected_user_info: [], allowed_actions: [] }], edges: [],
    };
    const get = vi.fn(async (path: string) => {
      if (path.startsWith('/api/enterprise/skills/boundary-sop?')) return {
        id: 'draft-boundary', skill_id: 'boundary-sop', name: content.name, content,
        version: content.version, status: 'draft', updated_at: '2026-09-27',
      };
      if (/^\/api\/(enterprise\/(tools|general-skills|knowledge-bases|skills|model-configs)|auth\/users)\?/.test(path)) return [];
      throw new Error(`Unexpected Distill request: ${path}`);
    });
    const host = { ...distillPageHost, api: { ...distillPageHost.api, get }, notify: notify() };
    render(<I18nProvider><LocaleControl /><MemoryRouter><DistillPageHostProvider value={host}>
      <SharedDistillPage searchParamsOverride={new URLSearchParams('skill_id=boundary-sop&agent_id=employee-1')} currentUser={currentUser} />
    </DistillPageHostProvider></MemoryRouter></I18nProvider>);
    await waitFor(() => expect(screen.getAllByText('新增', { selector: 'strong' }).length).toBeGreaterThan(0));
    for (const text of ['新增', '发布']) {
      screen.getAllByText(text, { selector: 'strong' }).forEach((node) => expect(boundary(node)).not.toBeNull());
    }
    expect(boundary(screen.getByText('暂无内容', { selector: 'p' }))).not.toBeNull();
    expect(boundary(screen.getByText('暂无说明', { selector: 'p' }))).not.toBeNull();
    const guidance = screen.getByText(/已加载「新增」/);
    expect(boundary(guidance)).toBeNull();
    expect(host.notify.error).not.toHaveBeenCalled();
  });

  it('keeps version detail labels localizable and user definition values untouched', async () => {
    const detail = {
      id: 'version-1', skill_id: '取消', name: '新增', version: '名称', business_domain: '暂无内容',
      status: 'draft', call_count: 0, positive_rate: 0, negative_rate: 0,
      updated_at: '2026-09-27', content: { name: '新增', description: '暂无内容', nodes: [] },
    };
    render(<I18nProvider><LocaleControl /><SkillsPageHostProvider value={skillsPageHost}>
      <SopVersionDetailDialog detail={detail} onClose={vi.fn()} />
    </SkillsPageHostProvider></I18nProvider>);
    const dialog = screen.getByRole('dialog');
    expect(boundary(within(dialog).getByText('新增'))).not.toBeNull();
    expect(boundary(within(dialog).getAllByText('名称')[0])).not.toBeNull();
    expect(boundary(within(dialog).getByText('暂无内容'))).not.toBeNull();
    expect(boundary(within(dialog).getByText(/# 新增/))).not.toBeNull();
    act(() => changeLocale('en-US'));
    await waitFor(() => expect(within(dialog).getByText('新增').textContent).toBe('新增'));
    expect(within(dialog).getByText('暂无内容').textContent).toBe('暂无内容');
    act(() => changeLocale('zh-CN'));
    expect(within(dialog).getByText('新增').textContent).toBe('新增');
  });

});
