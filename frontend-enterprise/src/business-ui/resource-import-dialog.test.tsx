// @vitest-environment jsdom

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ResourceImportDialog } from '@/components/ResourceImportDialog';

describe('shared resource import dialog in the native host', () => {
  it('preserves selection and disables both commands while loading', () => {
    const onClose = vi.fn();
    const onSubmit = vi.fn();
    const onSelectedChange = vi.fn();
    const onSourceChange = vi.fn();
    const props = {
      open: true, loading: true, icon: <span>图标</span>, title: '从广场复制知识库',
      sourcePlaceholder: '选择来源',
      sources: [{ value: 'overall', label: '整体智能体' }, { value: 'employee', label: '员工' }],
      sourceId: 'overall', itemsLabel: '选择知识库',
      items: [{ id: 'kb-1', label: '人事知识库' }], selectedIds: [],
      emptyText: '没有知识库', note: '仅复制可见资源',
      onSourceChange, onSelectedChange, onClose, onSubmit,
    };
    const view = render(<ResourceImportDialog {...props} />);

    expect(screen.getByRole('button', { name: '取消' })).toHaveProperty('disabled', true);
    expect(screen.getByRole('button', { name: '复制' })).toHaveProperty('disabled', true);
    fireEvent.click(screen.getByRole('checkbox'));
    expect(onSelectedChange).toHaveBeenCalledWith(['kb-1']);
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'employee' } });
    expect(onSourceChange).toHaveBeenCalledWith('employee');
    view.rerender(<ResourceImportDialog {...props} loading={false} />);
    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    fireEvent.click(screen.getByRole('button', { name: '复制' }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});
