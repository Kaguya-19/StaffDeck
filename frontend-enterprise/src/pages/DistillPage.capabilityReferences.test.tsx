// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { I18nProvider, useI18n, type AppLocale } from '@/i18n';

import { DistillPageHostProvider } from '@staffdeck/business-ui/DistillPageHost';
import { distillPageHost } from '../business-ui/distill-host';

import { ActionCombobox, EditableCapabilityReferencesLine } from './DistillPage';

afterEach(cleanup);

describe('SOP capability references', () => {
  it('hides unavailable resources unless the node already references them', async () => {
    const user = userEvent.setup();

    render(
      <I18nProvider>
        <EditableCapabilityReferencesLine
          label="SOP 技能"
          values={[]}
          requiredValues={[]}
          options={[
            {
              value: 'skill_active',
              label: '可用技能',
              unavailableReason: undefined,
            },
            {
              value: 'skill_archived',
              label: '已停用技能',
              unavailableReason: '技能未启用',
            },
          ]}
          emptyText="未指定技能"
          onChange={vi.fn()}
          onRequiredChange={vi.fn()}
        />
      </I18nProvider>,
    );

    await user.click(screen.getByRole('button', { name: /选择/ }));

    expect(screen.getByText('可用技能')).toBeTruthy();
    expect(screen.queryByText('已停用技能')).toBeNull();
  });

  it('removes an unavailable optional reference with one state update', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const onRequiredChange = vi.fn();

    render(
      <I18nProvider>
        <EditableCapabilityReferencesLine
          label="SOP 工具"
          values={['tool_missing']}
          requiredValues={[]}
          options={[]}
          emptyText="未指定工具"
          onChange={onChange}
          onRequiredChange={onRequiredChange}
        />
      </I18nProvider>,
    );

    await user.click(screen.getByRole('button', { name: /已选择 1 个/ }));
    await user.click(screen.getByRole('checkbox', { name: '取消选择 tool_missing' }));

    expect(onChange).toHaveBeenCalledOnce();
    expect(onChange).toHaveBeenCalledWith([]);
    expect(onRequiredChange).not.toHaveBeenCalled();
  });
  it('keeps selected capability name and native title verbatim while translating its required label', async () => {
    let setLocale: (locale: AppLocale) => void;
    function LocaleControl() { setLocale = useI18n().setLocale; return null; }
    render(<I18nProvider><LocaleControl /><DistillPageHostProvider value={distillPageHost}><EditableCapabilityReferencesLine
      label="SOP 工具" values={['tool']} requiredValues={['tool']}
      options={[{ value: 'tool', label: '新增' }]} emptyText="未指定工具"
      onChange={vi.fn()} onRequiredChange={vi.fn()} /></DistillPageHostProvider></I18nProvider>);
    const name = screen.getByText('新增', { selector: 'span.truncate' });
    const title = name.parentElement!;
    expect(title.getAttribute('title')).toBe('新增');
    expect(title.hasAttribute('data-i18n-ignore-title')).toBe(true);
    expect(name.getAttribute('translate')).toBe('no');
    expect(name.hasAttribute('data-i18n-ignore')).toBe(true);
    const required = screen.getByText('强制');
    expect(required.closest('[data-i18n-ignore]')).toBeNull();
    act(() => setLocale('en-US'));
    expect(await screen.findByText('Required')).toBeTruthy();
    expect(name.textContent).toBe('新增');
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /1 selected/ }));
    expect(await screen.findByRole('checkbox', { name: 'Deselect 新增' })).toBeTruthy();
    expect(screen.getByText('新增', { selector: 'strong' }).hasAttribute('data-i18n-ignore')).toBe(true);
    expect(title.getAttribute('title')).toBe('新增');
    act(() => setLocale('zh-CN'));
    expect(await screen.findByText('强制')).toBeTruthy();
    expect(title.getAttribute('title')).toBe('新增');
  });

  it('keeps the actual action picker text-editable with autofocus, filtering, Enter selection and original Escape interception', async () => {
    const select = vi.fn();
    render(<I18nProvider><DistillPageHostProvider value={distillPageHost}><ActionCombobox
      value="alpha" options={[{ value: 'alpha', label: 'Alpha' }, { value: 'beta', label: 'Beta' }]}
      onSelect={select} /></DistillPageHostProvider></I18nProvider>);
    const input = await screen.findByRole('textbox');
    expect(input.getAttribute('type')).toBe('text');
    await waitFor(() => expect(document.activeElement).toBe(input));
    fireEvent.change(input, { target: { value: 'beta' } });
    expect(screen.queryByRole('button', { name: 'Alpha' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Beta' })).toBeTruthy();
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(select).toHaveBeenCalledExactlyOnceWith('beta');
    select.mockClear();
    const escape = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
    fireEvent(input, escape);
    expect(escape.defaultPrevented).toBe(true);
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(document.activeElement).toBe(input);
    expect(select).toHaveBeenCalledExactlyOnceWith('alpha');
  });

});
