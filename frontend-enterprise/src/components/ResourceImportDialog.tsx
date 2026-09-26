import { Checkbox, Dialog, DialogContent, DialogTitle, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui';
import { Button } from '@/components/ui/button';
import { BusinessResourceImportDialog, type ResourceImportDialogProps, type ResourceImportPrimitives } from '@staffdeck/business-ui/SkillsPageHost';

export type { ImportChoiceItem, ImportSourceOption, ResourceImportDialogProps } from '@staffdeck/business-ui/SkillsPageHost';

const primitives: ResourceImportPrimitives = {
  Checkbox, Dialog, DialogContent, DialogTitle, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Button,
};

export function ResourceImportDialog(props: ResourceImportDialogProps) {
  return <BusinessResourceImportDialog {...props} primitives={primitives} />;
}
