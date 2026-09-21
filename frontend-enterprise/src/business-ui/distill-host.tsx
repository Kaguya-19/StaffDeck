import type { DistillPageHost } from '@staffdeck/business-ui/DistillPageHost';
import { api, streamGet, streamPost, TENANT_ID } from '../api/client';
import { notify } from '@/components/ui/app-toast';
import AppHeader from '@/components/AppHeader';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { CapabilityScopeBadge, CapabilityScopeControl, normalizeCapabilityScope } from '@/components/CapabilityScopeControl';
import { ModelConfigDropdown } from '@/components/ModelConfigDropdown';
import { isTeamScope, readEmployeeScope } from '@/lib/agent-scope-storage';
import { subscribeEnterpriseCapabilityCatalogRefresh } from '@/lib/capability-catalog-events';
import { SELECT_TRIGGER_CLASS } from '@/lib/enterprise-ui';
import { formatHandoffAssigneeValue, parseHandoffAssigneeValue } from '@/lib/handoff-assignee';
import { copyTextToClipboard } from '@/lib/clipboard';
import {
  Checkbox, Dialog, DialogContent, DialogFooter, DialogTitle, Input, Popover,
  PopoverContent, PopoverTrigger, Select as UISelect, SelectContent, SelectItem,
  SelectTrigger, SelectValue, Textarea, Tooltip, TooltipContent,
  TooltipProvider, TooltipTrigger,
} from '@/components/ui';
import { Button as UIButton } from '@/components/ui/button';
import {
  ApiOutlined, ArrowLeftOutlined, BranchesOutlined, CheckCircleOutlined,
  CheckOutlined, CodeOutlined, CloseOutlined, CloseCircleOutlined,
  DeleteOutlined, DownOutlined, FileTextOutlined, InfoCircleOutlined,
  LoadingOutlined, PlusOutlined, RightOutlined, SaveOutlined, SendOutlined,
  StopOutlined, UploadOutlined, WarningOutlined,
} from '../icons';

export const distillPageHost: DistillPageHost = {
  api: {
    get: api.get,
    post: api.post,
    postWithSignal: api.postWithSignal,
    put: api.put,
    delete: api.delete,
  },
  streamGet,
  streamPost,
  navigate: (path: string, options?: { replace?: boolean }) => { window.history[options?.replace ? 'replaceState' : 'pushState']({}, '', path); window.dispatchEvent(new PopStateEvent('popstate')); },
  tenantId: TENANT_ID,
  notify,
  readEmployeeScope,
  isTeamScope,
  components: {
    AppHeader, ConfirmDialog, CapabilityScopeBadge, CapabilityScopeControl,
    ModelConfigDropdown, Checkbox, Dialog, DialogContent, DialogFooter,
    DialogTitle, Input, Popover, PopoverContent, PopoverTrigger, UISelect,
    SelectContent, SelectItem, SelectTrigger, SelectValue, Textarea, Tooltip,
    TooltipContent, TooltipProvider, TooltipTrigger, UIButton,
  },
  icons: {
    ApiOutlined, ArrowLeftOutlined, BranchesOutlined, CheckCircleOutlined,
    CheckOutlined, CodeOutlined, CloseOutlined, CloseCircleOutlined,
    DeleteOutlined, DownOutlined, FileTextOutlined, InfoCircleOutlined,
    LoadingOutlined, PlusOutlined, RightOutlined, SaveOutlined, SendOutlined,
    StopOutlined, UploadOutlined, WarningOutlined,
  },
};

export { normalizeCapabilityScope, subscribeEnterpriseCapabilityCatalogRefresh, SELECT_TRIGGER_CLASS, formatHandoffAssigneeValue, parseHandoffAssigneeValue, copyTextToClipboard };
