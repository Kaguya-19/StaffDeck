// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  KnowledgePageHostProvider,
  useKnowledgePageHost,
} from '@staffdeck/business-ui/KnowledgePageHost';
import {
  SkillsPageHostProvider,
  useSkillsPageHost,
} from '@staffdeck/business-ui/SkillsPageHost';

import { knowledgePageHost } from './knowledge-host';
import { skillsPageHost } from './skills-host';

afterEach(cleanup);

describe('shared gallery host dispatch', () => {
  it('uses the active Knowledge and Skills host to resolve the real overall agent', () => {
    const agents = [
      { id: 'employee-1', is_overall: false },
      { id: 'overall-actual', is_overall: true },
    ];
    const knowledgeResolver = vi.fn(knowledgePageHost.openGalleryAgentId);
    const skillsResolver = vi.fn(skillsPageHost.openGalleryAgentId);

    function KnowledgeProbe() { const host = useKnowledgePageHost(); host.openGalleryAgentId(agents); host.openGalleryAgentId([{id:'employee-1',is_overall:false}]); return null; }
    function SkillsProbe() { const host = useSkillsPageHost(); host.openGalleryAgentId(agents); host.openGalleryAgentId([{id:'employee-1',is_overall:false}]); return null; }
    render(
      <>
        <KnowledgePageHostProvider value={{ ...knowledgePageHost, openGalleryAgentId: knowledgeResolver }}>
          <KnowledgeProbe />
        </KnowledgePageHostProvider>
        <SkillsPageHostProvider value={{ ...skillsPageHost, openGalleryAgentId: skillsResolver }}>
          <SkillsProbe />
        </SkillsPageHostProvider>
      </>,
    );

    expect(knowledgeResolver.mock.results[0].value).toBe('overall-actual');
    expect(skillsResolver.mock.results[0].value).toBe('overall-actual');
    expect(knowledgeResolver).toHaveBeenCalledWith(agents);
    expect(skillsResolver).toHaveBeenCalledWith(agents);
    expect(knowledgeResolver.mock.results[1].value).toBe('');
    expect(skillsResolver.mock.results[1].value).toBe('');
  });
});
