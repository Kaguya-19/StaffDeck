import { DistillPageHostProvider } from '@staffdeck/business-ui/DistillPageHost';
import SharedDistillPage from '@staffdeck/business-ui/DistillPage';
import { distillPageHost } from '../business-ui/distill-host';
import type { EnterpriseAuthUser } from '../auth';
import { useNavigate } from 'react-router-dom';

export default function DistillPage({ active = true, searchParamsOverride, currentUser, onLogout }: {
  active?: boolean;
  searchParamsOverride?: URLSearchParams;
  currentUser?: EnterpriseAuthUser;
  onLogout?: () => void;
} = {}) {
  const routerNavigate = useNavigate();
  return <DistillPageHostProvider value={{ ...distillPageHost, navigate: (path: string, options?: { replace?: boolean }) => routerNavigate(path, options) }}><SharedDistillPage active={active} searchParamsOverride={searchParamsOverride} currentUser={currentUser} onLogout={onLogout} /></DistillPageHostProvider>;
}

export * from '@staffdeck/business-ui/DistillPage';
