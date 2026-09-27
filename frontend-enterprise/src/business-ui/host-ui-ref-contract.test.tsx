// @vitest-environment jsdom
import { createRef } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DistillPageHostProvider, UIButton as DistillButton } from '@staffdeck/business-ui/DistillPageHost';
import { KnowledgePageHostProvider, Input as KnowledgeInput, Textarea as KnowledgeTextarea } from '@staffdeck/business-ui/KnowledgePageHost';
import { distillPageHost } from './distill-host';
import { knowledgePageHost } from './knowledge-host';
import { I18nProvider } from '@/i18n';

afterEach(cleanup);

describe('actual formal Host primitive refs', () => {
  it('forwards the fullscreen button ref and native keyboard/focus props through the Distill Host', () => {
    const ref = createRef<HTMLButtonElement>();
    const click = vi.fn();
    render(<I18nProvider><DistillPageHostProvider value={distillPageHost}>
      <DistillButton ref={ref} aria-label="全屏查看流程图" title="全屏查看流程图" onClick={click}>
        全屏
      </DistillButton>
    </DistillPageHostProvider></I18nProvider>);
    const button = screen.getByRole('button', { name: '全屏查看流程图' });
    expect(ref.current).toBe(button);
    expect(button.getAttribute('title')).toBe('全屏查看流程图');
    ref.current?.focus();
    expect(document.activeElement).toBe(button);
    fireEvent.click(button);
    expect(click).toHaveBeenCalledOnce();
  });

  it('forwards input ref, placeholder, value and change through the Knowledge Host', () => {
    const ref = createRef<HTMLInputElement>();
    const change = vi.fn();
    render(<I18nProvider><KnowledgePageHostProvider value={knowledgePageHost}>
      <KnowledgeInput ref={ref} aria-label="知识库名称" placeholder="输入名称" value="初始名称" onChange={change} />
    </KnowledgePageHostProvider></I18nProvider>);
    const input = screen.getByRole('textbox', { name: '知识库名称' });
    expect(ref.current).toBe(input);
    expect(input.getAttribute('placeholder')).toBe('输入名称');
    expect(input).toHaveProperty('value', '初始名称');
    fireEvent.change(input, { target: { value: '更新名称' } });
    expect(change).toHaveBeenCalledOnce();
    const textareaRef = createRef<HTMLTextAreaElement>();
    const { unmount } = render(<I18nProvider><KnowledgePageHostProvider value={knowledgePageHost}>
      <KnowledgeTextarea ref={textareaRef} aria-label="知识正文" value="正文" onChange={change} />
    </KnowledgePageHostProvider></I18nProvider>);
    const textarea = screen.getByRole('textbox', { name: '知识正文' });
    expect(textareaRef.current).toBe(textarea);
    unmount();
  });
});
