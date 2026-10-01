// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { I18nProvider, useI18n } from './index';

afterEach(() => { cleanup(); localStorage.clear(); });

it('translates system ingestion metadata and stats without translating document names', async () => {
  localStorage.setItem('staffdeck_locale', 'en-US');
  function Fixture() {
    const { setLocale } = useI18n();
    return <><button onClick={() => setLocale('zh-CN')}>ZH</button>
      <span>规范化 Source</span><span>写入 Source Document</span><span>规划 Wiki 页面</span>
      <span>写入 OKF Wiki</span><span>刷新 PageIndex</span>
      <span>完成入库：3 个 Wiki 页面，2 个内部索引，7 个引用来源</span>
      <span data-i18n-ignore translate="no">规划 Wiki 页面</span>
    </>;
  }
  render(<I18nProvider><Fixture /></I18nProvider>);
  expect(await screen.findByText('Normalize Source')).toBeTruthy();
  expect(screen.getByText('Write Source Document')).toBeTruthy();
  expect(screen.getByText('Plan Wiki pages')).toBeTruthy();
  expect(screen.getByText('Write OKF Wiki')).toBeTruthy();
  expect(screen.getByText('Refresh PageIndex')).toBeTruthy();
  expect(screen.getByText('Ingestion complete: 3 Wiki pages, 2 internal indexes, 7 citation sources')).toBeTruthy();
  expect(screen.getByText('规划 Wiki 页面')).toBeTruthy();
  screen.getByText('ZH').click();
  await waitFor(() => expect(screen.getByText('刷新 PageIndex')).toBeTruthy());
});
