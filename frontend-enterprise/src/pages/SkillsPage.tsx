import { SkillsPageHostProvider } from '@staffdeck/business-ui/SkillsPageHost';
import SharedSkillsPage from '@staffdeck/business-ui/SkillsPage';
import { skillsPageHost } from '../business-ui/skills-host';
import type { EnterpriseAuthUser } from '../auth';
import { useNavigate } from 'react-router-dom';

export default function SkillsPage({ currentUser, onLogout }: { currentUser?: EnterpriseAuthUser; onLogout?: () => void } = {}) {
  const navigate = useNavigate();
  return <SkillsPageHostProvider value={{ ...skillsPageHost, navigate }}><SharedSkillsPage currentUser={currentUser} onLogout={onLogout} /></SkillsPageHostProvider>;
}
