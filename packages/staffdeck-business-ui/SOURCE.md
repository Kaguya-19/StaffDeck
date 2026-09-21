# Source Map

`KnowledgePage.tsx` and `SkillsPage.tsx` are copied from the corresponding
formal pages in `frontend-enterprise/src/pages` on the portable StaffDeck
baseline. Their list, filter, CRUD, import, job, version/lifecycle, graph,
discovery, search/citation, publish, rollback, and detail interactions remain
in the shared source. The deliberate extraction boundary is the host bridge:
transport, auth/scope, navigation, notifications, icons, UI primitives, and
small formatting helpers are injected by each host.

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
`ui/src/composition/modules/staffdeck/vendor/` for the Knowledge and Skills
pages, their host bridges, the graph renderer, and the version-detail dialog.
