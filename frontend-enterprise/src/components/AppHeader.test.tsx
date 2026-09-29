// @vitest-environment jsdom

import { createElement } from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';

import { I18nProvider } from '@/i18n';
import { ENTERPRISE_AUTH_STORAGE_KEY } from '@/auth';

import AppHeader from './AppHeader';

describe('AppHeader', () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
  });

  it('allows simple page titles to opt into centered controls', () => {
    const { container } = render(
      createElement(
        I18nProvider,
        null,
        createElement(AppHeader, {
          title: '模型',
          right: createElement('span', null, 'controls'),
          className: 'items-center',
        }),
      ),
    );
    const header = container.querySelector('header');

    expect(header?.classList.contains('items-center')).toBe(true);
    expect(header?.classList.contains('items-start')).toBe(false);
  });

  it('places the current user full-access key in the global account menu', async () => {
    window.localStorage.setItem(ENTERPRISE_AUTH_STORAGE_KEY, JSON.stringify({
      token: 'session-token',
      user: {
        id: 'user_member',
        tenant_id: 'tenant_demo',
        username: 'member',
        display_name: '普通成员',
        role: 'member',
      },
    }));
    const user = userEvent.setup();
    render(
      createElement(
        I18nProvider,
        null,
        createElement(AppHeader, { title: '账号管理' }),
      ),
    );

    await user.click(screen.getByRole('button', { name: '账户菜单' }));

    expect(await screen.findByText('API 全量密钥')).toBeTruthy();
    expect(screen.getByText('普通成员')).toBeTruthy();
  });
});


it('switches the normal header theme and restores the saved choice', async () => {
  const { initializeTheme } = await import('./ThemeSwitcher');
  window.localStorage.removeItem('staffdeck_theme');
  initializeTheme();
  render(createElement(I18nProvider, null, createElement(AppHeader, { title: 'Knowledge' })));
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: '切换到深色主题' }));
  expect(document.documentElement.classList.contains('dark')).toBe(true);
  expect(window.localStorage.getItem('staffdeck_theme')).toBe('dark');
  document.documentElement.classList.remove('dark');
  initializeTheme();
  expect(document.documentElement.classList.contains('dark')).toBe(true);
  await user.click(screen.getByRole('button', { name: '切换到浅色主题' }));
  expect(document.documentElement.classList.contains('dark')).toBe(false);
});
