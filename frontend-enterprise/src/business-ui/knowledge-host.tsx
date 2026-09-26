import type { Host } from '@staffdeck/business-ui/KnowledgePageHost';
import { DataTable } from '@/components/DataTable';
import { api, TENANT_ID } from '../api/client';
import { notify } from '@/components/ui/app-toast';
import AppHeader from '@/components/AppHeader';
import CapabilityScopeLoading from '@/components/CapabilityScopeLoading';
import { CapabilityScopeBadge, CapabilityScopeControl, normalizeCapabilityScope } from '@/components/CapabilityScopeControl';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { ModelConfigDropdown } from '@/components/ModelConfigDropdown';
import { Paginator } from '@/components/Paginator';
import { ResourceImportDialog } from '@/components/ResourceImportDialog';
import { StatCard } from '@/components/StatCard';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger, Dialog, DialogContent, DialogTitle, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger, Input, Progress, Select as UISelect, SelectContent, SelectItem, SelectTrigger, SelectValue, Textarea } from '@/components/ui';
import { Button as UIButton } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { clearSharedAgentScope, emitAgentScopeChange, isTeamScope, persistSharedAgentScope, readEmployeeScope } from '@/lib/agent-scope-storage';
import { loadEmployeeDirectory } from '../api/employee-directory';
import { isEnterpriseAdmin } from '../auth';
import { canManageEmployeeAgent, openGalleryAgentId, openGalleryImportSourceOptions, resourceCreatorName, visibleEmployeeAgents } from '../employee';
import { useClientPagination } from '../hooks/useClientPagination';
import { renderMarkdownBlocks } from '../pages/chat/chatHelpers';
import { getDateLocale } from '@/i18n';
import IconAdd from '../assets/icons/add.svg?react';
import IconChevronDown from '../assets/icons/chevron-down.svg?react';
import IconClear from '../assets/icons/field-clear.svg?react';
import IconFolder from '../assets/icons/cap-folder.svg?react';
import IconRefresh from '../assets/icons/refresh.svg?react';
import IconSearch from '../assets/icons/search.svg?react';
import { KnowledgeGraphVisualization } from '../components/knowledge/KnowledgeGraphVisualization';

export const knowledgePageHost: Host = {
  api,
  navigate: (path: string) => { window.history.pushState({}, '', path); window.dispatchEvent(new PopStateEvent('popstate')); },
  tenantId: TENANT_ID,
  notify,
  isEnterpriseAdmin: (user: any) => isEnterpriseAdmin(user as any),
  loadEmployeeDirectory: () => loadEmployeeDirectory() as any,
  agentScope: { read: readEmployeeScope, persist: persistSharedAgentScope, clear: clearSharedAgentScope, emit: emitAgentScopeChange },
  visibleEmployeeAgents, canManageEmployeeAgent, openGalleryAgentId, openGalleryImportSourceOptions, resourceCreatorName,
  renderMarkdownBlocks: (value: string) => renderMarkdownBlocks(value), getDateLocale: () => getDateLocale(),
  components: { AppHeader, CapabilityScopeLoading, CapabilityScopeBadge, CapabilityScopeControl, ConfirmDialog, DataTable, Dialog, DialogContent, DialogTitle, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger, Input, ModelConfigDropdown, Paginator, Progress, ResourceImportDialog, StatCard, Textarea, UISelect, Accordion, AccordionContent, AccordionItem, AccordionTrigger, UIButton, KnowledgeGraphVisualization },
  icons: { IconAdd, IconChevronDown, IconClear, IconFolder, IconRefresh, IconSearch },
};
