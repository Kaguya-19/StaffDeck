import { useState } from 'react';
import { Moon, Sun } from 'lucide-react';
import { useI18n } from '@/i18n';

const STORAGE_KEY = 'staffdeck_theme';
export function initializeTheme() {
  let dark = false;
  try { dark = window.localStorage.getItem(STORAGE_KEY) === 'dark'; } catch {}
  document.documentElement.classList.toggle('dark', dark);
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
}
export default function ThemeSwitcher() {
  const { t } = useI18n();
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'));
  return <button type="button" aria-label={t(dark ? '切换到浅色主题' : '切换到深色主题')}
    title={t(dark ? '切换到浅色主题' : '切换到深色主题')}
    className="grid size-8 shrink-0 place-items-center rounded-[10px] border border-border bg-background text-foreground"
    onClick={() => {
      const next = !document.documentElement.classList.contains('dark');
      try { window.localStorage.setItem(STORAGE_KEY, next ? 'dark' : 'light'); } catch {}
      document.documentElement.classList.toggle('dark', next);
      document.documentElement.style.colorScheme = next ? 'dark' : 'light';
      setDark(next);
    }}>{dark ? <Sun size={16} /> : <Moon size={16} />}</button>;
}
