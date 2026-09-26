import type { ReactNode } from 'react';
import { BusinessDataTable, type DataTablePrimitives } from '@staffdeck/business-ui/SkillsPageHost';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui';

export type DataTableColumn<T> = {
  key: string;
  title: ReactNode;
  render?: (row: T, index: number) => ReactNode;
  dataIndex?: keyof T;
  width?: number | string;
  align?: 'left' | 'center' | 'right';
  className?: string;
  headClassName?: string;
  sticky?: 'left' | 'right';
};

export type DataTableProps<T> = {
  columns: DataTableColumn<T>[];
  data: T[];
  rowKey: (row: T, index: number) => string | number;
  loading?: boolean;
  emptyText?: ReactNode;
  loadingText?: ReactNode;
  onRowClick?: (row: T, index: number) => void;
  size?: 'default' | 'compact';
  striped?: boolean;
  bordered?: boolean;
  className?: string;
  'aria-label'?: string;
};

const primitives: DataTablePrimitives = { Table, TableBody, TableCell, TableHead, TableHeader, TableRow };

export function DataTable<T>(props: DataTableProps<T>) {
  return <BusinessDataTable {...props} primitives={primitives} />;
}
