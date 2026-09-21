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
