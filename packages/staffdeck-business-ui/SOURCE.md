# Source Map

FormalHostContractHelpers.ts preserves the four original SD01fb898e libraries
for agent scope, capability catalog events, handoff and clipboard, together
with normalizeCapabilityScope. Adapter3fa7b145 supplies the extraction and
clipboard focus-before-range correction. Native library paths, prior Formal
helper paths, Knowledge/Distill Host exports and the PD helper leaf re-export
this common source; the shared package never imports a PD-private helper.
Storage/event keys and source trim/web/null semantics remain unchanged.

Release0.1.13 mechanically extracts formal frontend helper components from
frontend-enterprise/src/components, chatHelpers, icons and graph helpers into
Formal*. SD keeps thin wrappers with its original frontend primitives; PD
injects ports of those primitives, without any enterprise backend dependency.
The complete source-directory snapshot is checked, rather than the original
thirteen-file slice. Mounted pages resolve transport, notify and scope through
their instance Host context. No SOP/Knowledge core/version/permission changes.
Runtime and browser contracts remain subject to independent gates.

Release0.1.12 forwards Content/Title refs through the active Knowledge and
Skills Host bridges to their injected formal dialog primitives. Original
business dialog content, controlled callbacks and host primitive semantics
remain unchanged.

Release0.1.11 adds optional selected-row editorQuery and an editor_context cache
namespace. Portable hosts can bind a selected draftID or published version to
the normal editor read without overwriting another lifecycle's dirty cache.
Hosts that omit the hook keep their original route/cache behavior.

Release0.1.10 adds optional mounted Host saveVersionPolicy: when the public
service allocates a new draft version, review shows that capability rather
than promising a client-selected version. Native hosts without the hook and
existing-draft ETag saves retain their original version review behavior.

`KnowledgePage.tsx`, `SkillsPage.tsx`, and `DistillPage.tsx` are copied from the corresponding
formal pages in `frontend-enterprise/src/pages` on the portable StaffDeck
baseline. Their list, filter, CRUD, import, job, version/lifecycle, graph,
discovery, search/citation, publish, rollback, and detail interactions remain
in the shared source. The deliberate extraction boundary is the host bridge:
transport, auth/scope, navigation, notifications, icons, UI primitives, and
small formatting helpers are injected by each host.

The Distill editor additionally keeps the source-view and flow-view editing
surfaces in the shared package. Hosts provide the API and streaming hooks;
portable hosts may return an explicit unavailable error for AI generation while
still supporting local definition read, save, and reload.

`SopVersionDetailDialog.tsx` remains a separately exported renderer extracted
from the Skills page's `VersionDetailDialog` function. The source interaction
is preserved: the selected version is optional, the dialog closes through the
host callback, the version/domain/status/call-rate/update fields remain
visible, and serialized SOP content remains inspectable in the detail view.

The extraction delta is limited to the host boundary: StaffDeck's API client,
Radix primitives, icon aliases, auth/scope context, notifications, and local
formatting helpers are supplied by the adapter. No replacement workbench or
second business workflow is implemented in the package.

PilotDeck consumes the checked-in release snapshot under
`ui/src/composition/modules/staffdeck/vendor/` for the Knowledge, Skills, and
Distill pages, their host bridges, the graph renderer, and the version-detail
dialog.
