declare module '@staffdeck/business-ui/KnowledgeGraphCanvas' {
  import type { KnowledgeConceptRead } from '../types';
  import type { ComponentType } from 'react';
  const KnowledgeGraphCanvas: ComponentType<{
    concepts: KnowledgeConceptRead[];
    onSelectConcept: (concept: KnowledgeConceptRead) => void;
    height?: number;
    labels?: Record<string, unknown>;
  }>;
  export default KnowledgeGraphCanvas;
}

declare module '@staffdeck/business-ui/SopVersionDetailDialog' {
  import type { ComponentType } from 'react';
  type StaffDeckSopVersion = {
    id: string;
    skill_id?: string;
    name: string;
    version: string;
    business_domain?: string;
    status?: string;
    call_count?: number;
    positive_rate?: number;
    negative_rate?: number;
    updated_at: string;
    content?: unknown;
  };
  const SopVersionDetailDialog: ComponentType<{ detail: StaffDeckSopVersion | null; onClose: () => void; labels?: Record<string, string> }>;
  export type { StaffDeckSopVersion };
  export default SopVersionDetailDialog;
}

declare module '@staffdeck/business-ui/SkillsPageHost' {
  import type { ComponentType, ReactNode } from 'react';
  export type EnterpriseAuthUser = { id?: string; username?: string; tenant_id?: string; is_admin?: boolean };
  export type SkillsPageHost = Record<string, any>;
  export const SkillsPageHostProvider: ComponentType<{ value: SkillsPageHost; children: ReactNode }>;
  export const openGalleryAgentId: (agents: Array<{ id: string; is_overall?: boolean }>) => string;
}

declare module '@staffdeck/business-ui/SkillsPage' {
  import type { ComponentType } from 'react';
  const SkillsPage: ComponentType<{ currentUser?: import('../auth').EnterpriseAuthUser; onLogout?: () => void }>;
  export default SkillsPage;
}

declare module '@staffdeck/business-ui/KnowledgePageHost' {
  import type { ComponentType, ReactNode } from 'react';
  export type Host = Record<string, any>;
  export const KnowledgePageHostProvider: ComponentType<{ value: Host; children: ReactNode }>;
  export const openGalleryAgentId: (agents: Array<{ id: string; is_overall?: boolean }>) => string;
}

declare module '@staffdeck/business-ui/KnowledgePage' {
  import type { ComponentType } from 'react';
  const KnowledgePage: ComponentType<{ currentUser?: import('../auth').EnterpriseAuthUser; onLogout?: () => void }>;
  export const KnowledgeAddPage: ComponentType<{ currentUser?: import('../auth').EnterpriseAuthUser }>;
  export default KnowledgePage;
}

declare module '@staffdeck/business-ui/DistillPageHost' {
  import type { ComponentType, ReactNode } from 'react';
  export type DistillPageHost = Record<string, any>;
  export const DistillPageHostProvider: ComponentType<{ value: DistillPageHost; children: ReactNode }>;
}

declare module '@staffdeck/business-ui/DistillPage' {
  import type { ComponentType } from 'react';
  export type DistillPageProps = { active?: boolean; searchParamsOverride?: URLSearchParams; currentUser?: import('../auth').EnterpriseAuthUser; onLogout?: () => void };
  const DistillPage: ComponentType<DistillPageProps>;
  export function handoffAssigneeUserOptions(users: Array<Record<string, any>>): Array<{ value: string; label: string }>;
  export function applyNodeTypeChange(...args: any[]): any;
  export function filterActionOptionsForNodeType(...args: any[]): any;
  export function EditableCapabilityReferencesLine(...args: any[]): any;
  export default DistillPage;
}
