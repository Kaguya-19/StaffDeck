import { KnowledgePageHostProvider } from '@staffdeck/business-ui/KnowledgePageHost';
import SharedKnowledgePage, { KnowledgeAddPage as SharedKnowledgeAddPage } from '@staffdeck/business-ui/KnowledgePage';
import { knowledgePageHost } from '../business-ui/knowledge-host';
import type { EnterpriseAuthUser } from '../auth';
import { useNavigate } from 'react-router-dom';

type Props = { currentUser?: EnterpriseAuthUser; onLogout?: () => void };
export default function KnowledgeManagePage({ currentUser, onLogout }: Props = {}) {
  const navigate = useNavigate();
  return <KnowledgePageHostProvider value={{ ...knowledgePageHost, navigate }}><SharedKnowledgePage currentUser={currentUser} onLogout={onLogout} /></KnowledgePageHostProvider>;
}

export function KnowledgeAddPage({ currentUser }: Props = {}) {
  const navigate = useNavigate();
  return <KnowledgePageHostProvider value={{ ...knowledgePageHost, navigate }}><SharedKnowledgeAddPage currentUser={currentUser} /></KnowledgePageHostProvider>;
}
