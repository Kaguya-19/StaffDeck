declare module '@staffdeck/business-ui/FormalDetailField' {
type DetailFieldProps = {
  label: string;
  children: ReactNode;
  className?: string;
};

 import type { ComponentType, ReactNode } from 'react';
 type ModelConfigRead = Record<string, any> & { id: string };
 
 export const DetailField: ComponentType<DetailFieldProps>;
}
declare module '@staffdeck/business-ui/FormalStatCard' {
type StatCardTone = 'default' | 'green' | 'red';
type StatCardProps = {
  value: ReactNode;
  label: ReactNode;
  /** Colour accent. `default` = neutral grey card, `green`/`red` = tinted. */
  tone?: StatCardTone;
  /** Extra classes for the big value (e.g. a custom colour). */
  valueClassName?: string;
  /** Extra classes for the outer card (e.g. override the flex basis). */
  className?: string;
};

 import type { ComponentType, ReactNode } from 'react';
 type ModelConfigRead = Record<string, any> & { id: string };
 
 export const StatCard: ComponentType<StatCardProps>;
}
declare module '@staffdeck/business-ui/FormalPaginator' {
type PaginatorProps = {
  /** Current 1-based page. */
  page: number;
  /** Total number of pages. */
  pageCount: number;
  onChange: (page: number) => void;
  /** How many page numbers to show on each side of the current page. */
  siblingCount?: number;
  /** Zero-pad page numbers (01, 02, …) to match the SD1 design. Defaults to true. */
  padZero?: boolean;
  className?: string;
  'aria-label'?: string;
};

 import type { ComponentType, ReactNode } from 'react';
 type ModelConfigRead = Record<string, any> & { id: string };
 
 export const Paginator: ComponentType<PaginatorProps>;
}
declare module '@staffdeck/business-ui/FormalConfirmDialog' {
type ConfirmDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Header title. Supports rich content (e.g. the target name in a `<strong>`). */
  title: ReactNode;
  /** Optional supporting copy shown below the title. */
  description?: ReactNode;
  confirmText?: string;
  cancelText?: string;
  onConfirm: () => void;
  /** When true, buttons are disabled and closing via overlay/esc is blocked. */
  loading?: boolean;
  /** Destructive (red) confirm button. Defaults to true — matches the delete flow. */
  destructive?: boolean;
  /** Override the leading header icon. Pass `null` to hide it. */
  icon?: ReactNode;
};

 import type { ComponentType, ReactNode } from 'react';
 type ModelConfigRead = Record<string, any> & { id: string };
 
 export const ConfirmDialog: ComponentType<ConfirmDialogProps>;
}
declare module '@staffdeck/business-ui/FormalModelConfigDropdown' {
type ModelConfigDropdownProps = {
  models: ModelConfigRead[];
  value: string;
  onChange: (modelId: string) => void;
  disabled?: boolean;
  buttonClassName?: string;
  menuClassName?: string;
  align?: 'start' | 'center' | 'end';
  placeholder?: string;
};

 import type { ComponentType, ReactNode } from 'react';
 type ModelConfigRead = Record<string, any> & { id: string };
 
 export const ModelConfigDropdown: ComponentType<ModelConfigDropdownProps>;
}
declare module '@staffdeck/business-ui/FormalCapabilityScopeControl' {
 import type { ComponentType } from 'react';
 type Scope = 'general' | 'sop_specific';
 export type CapabilityScopeResourceType = 'tool' | 'skill' | 'sop' | 'knowledge_base';
 export function normalizeCapabilityScope(value: unknown): Scope;
 export function capabilityScopeLabel(value: unknown): string;
 export const CapabilityScopeBadge: ComponentType<{value: unknown; className?:string}>;
 export const CapabilityScopeControl: ComponentType<{value:Scope;onChange:(value:Scope)=>void;disabled?:boolean;className?:string;compact?:boolean;resourceType:CapabilityScopeResourceType}>;
}
declare module '@staffdeck/business-ui/FormalCapabilityScopeLoading' { import type { ComponentType } from 'react'; const Component: ComponentType<{}>; export default Component; }
declare module '@staffdeck/business-ui/FormalHostPrimitives' { import type { ComponentType } from 'react'; export const FormalHostPrimitiveProvider: ComponentType<any>; }
declare module '@staffdeck/business-ui/FormalMarkdown' { import type { ReactNode } from 'react'; export function renderMarkdownBlocks(value: string): ReactNode[]; }
declare module '@staffdeck/business-ui/FormalKnowledgeGraphVisualization' { import type { ComponentType } from 'react'; export const KnowledgeGraphVisualization: ComponentType<any>; }
