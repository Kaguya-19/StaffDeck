import type { SkillsPageHost } from '@staffdeck/business-ui/SkillsPageHost';
import { BusinessDataTable as DataTable } from '@staffdeck/business-ui/SkillsPageHost';
import { api, TENANT_ID } from '../api/client';
import AppHeader from '@/components/AppHeader';
import { notify } from '@/components/ui/app-toast';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { DetailField } from '@/components/DetailField';
import { Paginator } from '@/components/Paginator';
import { ResourceImportDialog } from '@/components/ResourceImportDialog';
import { StatusBadge } from '@/pages/scheduled-tasks/StatusBadge';
import { Button as UIButton } from '@/components/ui/button';
import {
  Dialog, DialogContent, DialogTitle, DropdownMenu, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui';
import { cn } from '@/lib/utils';
import { MENU_CONTENT_CLASS, MENU_ITEM_CLASS, MENU_ITEM_DANGER_CLASS, MOBILE_CARD_CLASS, SELECT_TRIGGER_CLASS } from '@/lib/enterprise-ui';
import { isEnterpriseAdmin, type EnterpriseAuthUser } from '../auth';
import { canManageEmployeeAgent, openGalleryAgentId, openGalleryImportSourceOptions, resourceCreatorName, visibleEmployeeAgents } from '../employee';
import { useClientPagination } from '../hooks/useClientPagination';
import { isTeamScope, readEmployeeScope } from '../lib/agent-scope-storage';
import IconAdd from '../assets/icons/add.svg?react';
import IconChevronDown from '../assets/icons/chevron-down.svg?react';
import IconClear from '../assets/icons/field-clear.svg?react';
import IconClipboard from '../assets/icons/cap-clipboard.svg?react';
import IconEdit from '../assets/icons/edit.svg?react';
import IconHistory from '../assets/icons/profile-history.svg?react';
import IconMore from '../assets/icons/more.svg?react';
import IconRefresh from '../assets/icons/refresh.svg?react';
import IconSearch from '../assets/icons/search.svg?react';
import IconSkill from '../assets/icons/plaza-skill.svg?react';
import IconTrash from '../assets/icons/trash.svg?react';

export const skillsPageHost: SkillsPageHost = {
  api,
  navigate: (path: string) => { window.history.pushState({}, '', path); window.dispatchEvent(new PopStateEvent('popstate')); },
  tenantId: TENANT_ID,
  notify,
  components: {
    AppHeader,
    ConfirmDialog, DataTable, DetailField, Dialog, DialogContent, DialogTitle,
    DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
    Paginator, ResourceImportDialog, Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
    StatusBadge, UIButton,
  },
  icons: { IconAdd, IconChevronDown, IconClear, IconClipboard, IconEdit, IconHistory, IconMore, IconRefresh, IconSearch, IconSkill, IconTrash },
  isEnterpriseAdmin: (user: EnterpriseAuthUser | undefined) => isEnterpriseAdmin(user),
  canManageEmployeeAgent,
  openGalleryAgentId,
  openGalleryImportSourceOptions,
  resourceCreatorName,
  visibleEmployeeAgents,
  readEmployeeScope,
  isTeamScope,
  useClientPagination,
};
