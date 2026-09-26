// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  KnowledgePageHostProvider,
  openGalleryAgentId as knowledgeGalleryAgentId,
} from '@staffdeck/business-ui/KnowledgePageHost';
import {
  SkillsPageHostProvider,
  openGalleryAgentId as skillsGalleryAgentId,
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

    render(
      <>
        <KnowledgePageHostProvider value={{ ...knowledgePageHost, openGalleryAgentId: knowledgeResolver }}>
          <span />
        </KnowledgePageHostProvider>
        <SkillsPageHostProvider value={{ ...skillsPageHost, openGalleryAgentId: skillsResolver }}>
          <span />
        </SkillsPageHostProvider>
      </>,
    );

    expect(knowledgeGalleryAgentId(agents)).toBe('overall-actual');
    expect(skillsGalleryAgentId(agents)).toBe('overall-actual');
    expect(knowledgeResolver).toHaveBeenCalledWith(agents);
    expect(skillsResolver).toHaveBeenCalledWith(agents);
    expect(knowledgeGalleryAgentId([{ id: 'employee-1', is_overall: false }])).toBe('');
    expect(skillsGalleryAgentId([{ id: 'employee-1', is_overall: false }])).toBe('');
  });
});
