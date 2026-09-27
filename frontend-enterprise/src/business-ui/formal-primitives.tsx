import type { ReactNode } from 'react';
import { FormalHostPrimitiveProvider } from '@staffdeck/business-ui/FormalHostPrimitives';
import { AlertDialog, AlertDialogContent, AlertDialogDescription, AlertDialogTitle, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, Pagination, PaginationContent, PaginationItem, Switch, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui';
import { Button } from '@/components/ui/button';
import { InfoCircleOutlined, CheckOutlined } from '../icons';
import IconChevronDown from '../assets/icons/chevron-down.svg?react';
import IconWarningFill from '../assets/icons/warning-fill.svg?react';
const primitives = { AlertDialog, AlertDialogContent, AlertDialogDescription, AlertDialogTitle, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, Pagination, PaginationContent, PaginationItem, Switch, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger, Button, InfoCircleOutlined, CheckOutlined, IconChevronDown, IconWarningFill };
export function FormalPrimitives({ children }: { children: ReactNode }) {
  return <FormalHostPrimitiveProvider value={primitives}>{children}</FormalHostPrimitiveProvider>;
}
