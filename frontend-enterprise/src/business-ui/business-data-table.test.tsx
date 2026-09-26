// @vitest-environment jsdom

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { BusinessDataTable } from '@staffdeck/business-ui/SkillsPageHost';

describe('shared business DataTable', () => {
  it('preserves the consumed column, index, selection, and wide-table contracts', () => {
    const rowKey = vi.fn((row: { id: string }, index: number) => `${row.id}-${index}`);
    const renderCell = vi.fn((row: { id: string; name: string }, index: number) => `${row.name}-${index}`);
    const onRowClick = vi.fn();
    render(<BusinessDataTable
      aria-label="SOP 版本"
      className="min-w-[820px]"
      columns={[
        { key: 'name', title: '名称', dataIndex: 'name', width: 320 },
        { key: 'actions', title: '操作', width: 80, sticky: 'right', render: renderCell },
      ]}
      data={[{ id: 'one', name: '第一版' }, { id: 'two', name: '第二版' }]}
      rowKey={rowKey}
      onRowClick={onRowClick}
    />);

    const table = screen.getByRole('table', { name: 'SOP 版本' });
    expect(table.closest('[data-slot="table-container"]')?.className).toContain('overflow-x-auto');
    expect(table.style.minWidth).toBe('400px');
    expect(table.parentElement?.parentElement?.className).toContain('min-w-[820px]');
    expect(screen.getByRole('columnheader', { name: '操作' }).className).toContain('sticky');
    expect(screen.getByText('第二版').textContent).toBe('第二版');
    expect(renderCell).toHaveBeenCalledWith({ id: 'two', name: '第二版' }, 1);
    expect(rowKey).toHaveBeenCalledWith({ id: 'two', name: '第二版' }, 1);
    fireEvent.click(screen.getByText('第二版'));
    expect(onRowClick).toHaveBeenCalledWith({ id: 'two', name: '第二版' }, 1);
  });
});
